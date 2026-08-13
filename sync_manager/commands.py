"""CMD1 · the COMMAND channel — EMStudio conducts, Blender is the 3D arm.

The sync channel until now carried an ECHO: a selection made over there showed
up over here. This is a different kind of message and needs saying plainly:
EMStudio asks Blender to **do** something — *model the proxy for this unit*,
*import this asset and bind it to that node* — Blender executes, and what comes
back is a **graph delta** that is merged into the em.json.

Three properties the design turns on:

* **The result is DATA, not a live state.** A command produces nodes and edges
  in em.json terms; they are the answer, and they survive the session because
  the em.json does. Nothing meaningful lives only in the socket.
* **Idempotent by `cmd_id`.** The id is a uuid5 over (verb, target, params), so
  re-sending the same command is the same command: the second time returns the
  first result instead of building a second proxy. A dropped reply must not cost
  you a duplicate.
* **Consent, and it is not the sync toggle.** Executing somebody's command
  changes YOUR scene. That is a stronger act than mirroring a selection, so it
  has its own switch and that switch is OFF by default — see
  `Scene.em_accept_commands` in `operators.py`.

The vocabulary is deliberately small: two verbs, both with a clear target and a
delta anybody can read. Generating a proxy from a point cloud, boolean surgery,
the FBK tools — all of that is a bigger conversation about what a command IS,
and inventing the vocabulary before the two ends agree on the mechanism is how
protocols rot.

bpy is imported lazily inside the verb bodies so the module can be imported (and
its pure parts exercised) outside Blender.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional, Tuple

#: Namespace for deterministic command ids. Shared with EMStudio's `commands.ts`
#: — the two ends must mint the SAME id for the same command, or idempotence
#: only works within one process and is therefore not idempotence.
CMD_NAMESPACE = uuid.UUID("6f1f2f4a-3f2a-5c7e-9d1b-4a6c8e2f0b31")

#: The verbs this host will execute. A verb that is not here is refused BY NAME,
#: which is the difference between "I do not do that" and a silent no-op.
VERBS = ("create_proxy_for_unit", "import_geometry")


def make_cmd_id(verb: str, target: str, params: Optional[Dict[str, Any]] = None) -> str:
    """The deterministic id of a command. Same command → same id, on both ends.

    The params are canonicalised (sorted keys, compact separators) so that two
    dictionaries that say the same thing hash the same — otherwise idempotence
    would depend on key order, which nobody controls.
    """
    import json

    payload = json.dumps(params or {}, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False)
    return str(uuid.uuid5(CMD_NAMESPACE, f"{verb}|{target}|{payload}"))


# ── the delta ────────────────────────────────────────────────────────────────

def _node_payload(node: Any) -> Dict[str, Any]:
    from s3dgraphy.exporter.emjson_exporter import _node_payload as _p
    return _p(node)


def _edge_payload(edge: Any) -> Dict[str, Any]:
    from s3dgraphy.exporter.emjson_exporter import _edge_payload as _p
    return _p(edge)


def build_delta(graph: Any, node_ids: List[str], edge_ids: List[str]) -> Dict[str, Any]:
    """The created nodes and edges, in em.json shape.

    Serialised with the em.json exporter's own functions rather than by hand:
    the delta must be readable by exactly the same reader as a file, or the two
    would drift and the drift would only show up in somebody's project.

    Ids that no longer resolve are skipped silently — they were reported as
    created by the writer, and a delta is a report, not a second source of truth.
    """
    nodes = []
    for nid in dict.fromkeys(node_ids):           # de-dup, keep order
        node = graph.find_node_by_id(nid)
        if node is not None:
            nodes.append(_node_payload(node))
    by_id = {getattr(e, "edge_id", None): e for e in graph.edges}
    edges = []
    for eid in dict.fromkeys(edge_ids):
        edge = by_id.get(eid)
        if edge is not None:
            edges.append(_edge_payload(edge))
    return {"nodes": nodes, "edges": edges}


# ── verb: create_proxy_for_unit ──────────────────────────────────────────────

def _bbox_hull(obj) -> List[float]:
    """The object's world-space bounding box as a flat convex-hull point list.

    A box is a legitimate proxy — it is what the EM proxy workflow produces by
    hand — and its eight corners are the honest description of the volume this
    command asserts. The numbers are WORLD space: a hull in local coordinates
    would describe a shape nobody could place.
    """
    flat: List[float] = []
    for corner in obj.bound_box:
        world = obj.matrix_world @ __import__("mathutils").Vector(corner)
        flat.extend([round(world.x, 6), round(world.y, 6), round(world.z, 6)])
    return flat


def _proxy_object_for(node_name: str, context, graph):
    """The proxy object already bound to this node, or None."""
    import bpy  # type: ignore
    from ..operators.addon_prefix_helpers import node_name_to_proxy_name

    name = node_name_to_proxy_name(node_name, context=context, graph=graph)
    return bpy.data.objects.get(name) or bpy.data.objects.get(node_name)


def create_proxy_for_unit(target: str, params: Dict[str, Any], context,
                          graph) -> Dict[str, Any]:
    """Model the proxy of a stratigraphic unit, and report it as a delta.

    The mesh is a box placed at the 3D cursor (or at `params.location`), sized by
    `params.size` — a STARTING POINT somebody then shapes, which is how the proxy
    workflow already works. What makes it a proxy in EM terms is not the mesh but
    the chain this builds beside it: a `geometry` PropertyNode carrying a
    SemanticShape payload (`s3dgraphy.api.create_geometry_proxy`), which is the
    same chain the annotator and the 2D→3D path produce.

    Idempotent twice over: an existing proxy object for the unit is REUSED
    rather than duplicated, and `create_geometry_proxy` mints deterministic ids
    from (unit, payload).
    """
    import bpy  # type: ignore
    from s3dgraphy.api import create_geometry_proxy
    from ..operators.addon_prefix_helpers import node_name_to_proxy_name

    unit = graph.find_node_by_id(target)
    if unit is None:
        # a unit that is not in the graph is not a modelling problem, it is a
        # wrong target — say which, and do nothing
        return {"ok": False, "error": f"unit '{target}' is not in this graph"}

    node_name = getattr(unit, "name", None) or target
    proxy = _proxy_object_for(node_name, context, graph)
    reused = proxy is not None
    if proxy is None:
        size = float(params.get("size") or 1.0)
        loc = params.get("location")
        if isinstance(loc, (list, tuple)) and len(loc) == 3:
            location = tuple(float(v) for v in loc)
        else:
            location = tuple(context.scene.cursor.location)
        bpy.ops.mesh.primitive_cube_add(size=size, location=location)
        proxy = context.active_object
        proxy.name = node_name_to_proxy_name(node_name, context=context, graph=graph)
        proxy.data.name = proxy.name
        col = bpy.data.collections.get("Proxy")
        if col is None:
            col = bpy.data.collections.new("Proxy")
            context.scene.collection.children.link(col)
        for c in list(proxy.users_collection):
            c.objects.unlink(proxy)
        col.objects.link(proxy)

    shape = {"convexshapes": [_bbox_hull(proxy)]}
    result = create_geometry_proxy(graph, target, shape,
                                   name=params.get("name") or None)
    delta = build_delta(graph,
                        [result.shape_id, result.property_id] + result.extractor_ids,
                        result.edge_ids)
    return {
        "ok": True,
        "delta": delta,
        "info": {"proxy_object": proxy.name, "reused_object": reused,
                 "property_id": result.property_id, "shape_id": result.shape_id,
                 "warnings": result.warnings},
    }


# ── verb: import_geometry ────────────────────────────────────────────────────

def import_geometry(target: str, params: Dict[str, Any], context,
                    graph) -> Dict[str, Any]:
    """Import an asset's mesh and bind it to the graph as a RepresentationModel.

    `target` is the ResourceNode (a shelf entry). The file comes from the node's
    own `url`, so the command carries a REFERENCE and not a path: a path in a
    message is a path on somebody else's disk.

    The graph side reuses `shelf.hat_as_representation_model` — the same
    reference-by-stable-id hinge the Shelf tool uses, so an asset imported by
    command and one hatted by hand are the same thing in the graph.
    """
    from s3dgraphy.api import hat_as_representation_model
    from ..shelf_tool.operators import _import_mesh

    resource = graph.find_node_by_id(target)
    if resource is None:
        return {"ok": False, "error": f"resource '{target}' is not in this graph"}
    url = (getattr(resource, "url", None)
           or (getattr(resource, "data", {}) or {}).get("url") or "")
    path = str(params.get("path") or url)
    if not path:
        return {"ok": False,
                "error": f"resource '{target}' carries no url to import"}

    objects = _import_mesh(path)
    if not objects:
        # the graph is NOT written when the mesh did not arrive: an RM whose
        # model is not there is a claim about something nobody can look at
        return {"ok": False,
                "error": f"could not import '{path}' (missing file or no importer "
                         f"for that extension)"}

    epochs = params.get("epochs") or None
    info = hat_as_representation_model(
        graph, target, rm_id=params.get("rm_id") or None,
        name=params.get("name") or None,
        epochs=list(epochs) if isinstance(epochs, (list, tuple)) else None,
    )
    rm_id = info.get("rm_id")
    edge_ids = [e.edge_id for e in graph.edges
                if e.edge_source == rm_id or e.edge_target == rm_id]
    delta = build_delta(graph, [rm_id], edge_ids)
    for obj in objects:
        obj["em_resource_id"] = target
        obj["em_rm_node_id"] = rm_id
    return {"ok": True, "delta": delta,
            "info": {"imported_objects": [o.name for o in objects],
                     "rm_id": rm_id, "created": info.get("created"),
                     "skipped": info.get("skipped")}}


# ── dispatch ─────────────────────────────────────────────────────────────────

_HANDLERS = {
    "create_proxy_for_unit": create_proxy_for_unit,
    "import_geometry": import_geometry,
}

#: cmd_id → result, for the run of this Blender session. Idempotence is a
#: promise about the WORLD (no second proxy), and this is what keeps the promise
#: cheap: a repeat returns the first answer without touching the scene.
_done: Dict[str, Dict[str, Any]] = {}


def clear_history() -> None:
    """Forget the executed commands (a new session, or a test)."""
    _done.clear()


def execute(msg: Dict[str, Any], context, graph) -> Dict[str, Any]:
    """Run one command message and return the `command_result` payload.

    Never raises: a command that fails comes back as `{ok: False, error}`, so a
    bad verb or a broken file is a message the other end can show rather than a
    traceback in a console nobody is watching.
    """
    cmd_id = str(msg.get("cmd_id") or "")
    verb = str(msg.get("verb") or "")
    target = str(msg.get("target") or "")
    params = msg.get("params") or {}
    if not isinstance(params, dict):
        params = {}

    if cmd_id and cmd_id in _done:
        out = dict(_done[cmd_id])
        out["repeated"] = True          # said, not hidden: the caller may care
        return out

    handler = _HANDLERS.get(verb)
    if handler is None:
        return {"ok": False, "cmd_id": cmd_id,
                "error": f"unknown verb '{verb}' (this host does: "
                         f"{', '.join(VERBS)})"}
    if graph is None:
        return {"ok": False, "cmd_id": cmd_id,
                "error": "no active graph in Blender — open a project first"}
    try:
        result = handler(target, params, context, graph)
    except Exception as exc:  # noqa: BLE001 — a command must not kill the host
        import traceback
        traceback.print_exc()
        result = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    result["cmd_id"] = cmd_id
    if result.get("ok") and cmd_id:
        _done[cmd_id] = dict(result)
    return result
