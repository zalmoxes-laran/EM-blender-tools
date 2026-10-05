"""P2 · «Sync the scene…»: what the scene has that the room does not, offered
for sending — the half of the check that used to be missing.

The check (`scene_check`) downloads what is missing and flags what is older
here; until now no gesture sent a model that had CHANGED HERE into a room that
already exists (`promote_model` was reached only from «Bring into a room…»).
This module finds those models and sends the ones the person ticks:

* **changed here** — a model linked to the graph whose mesh is no longer the
  one its bytes were made from or fetched from. Measured, never guessed: when a
  model's bytes are born (`promote_model`) or arrive (`materialise`) its mesh
  fingerprint is written on the object (`em_mesh_fp`: the vertices, the faces
  and the placement), and the sync compares it with the mesh as it is now. An
  object published before this existed has no fingerprint: the first sync
  writes it and counts it («baseline recorded»), and from then on it is known.
* **new** — a model linked to the graph (an RM of the list, a proxy) whose
  bytes the room has never had.

What goes up goes as the decision of 30 September says a changed file goes:
**a new revision of the resource** (`resource_revisions.revise_files`,
``new ──was_revision_of──▶ old``), the citations moved to it, the old one left
as it was and citable — never an overwrite. A new model is published as
«Bring into a room…» publishes it (`promote_model`, resident). Both reach the
room as operations (`emit_op`), so a dropped connection keeps them (P1).

Never sent: an object «◆ only here», and a model linked from a library (a
reality-based version, R1: invariant, it cannot have changed here).

The decisions are pure (`classify_models`, `section_delta_ops`,
`estimated_size`) and measured by `tests/test_scene_sync.py`.
"""

# NOT `from __future__ import annotations`: see scene_check — the operator
# properties are read in this module's globals.
import hashlib
from typing import Any, Dict, List, Optional

PROP_FINGERPRINT = "em_mesh_fp"

STATE_CHANGED = "changed"
STATE_NEW = "new"


# ── pure ────────────────────────────────────────────────────────────────────

def classify_models(models: List[Dict[str, Any]]) -> Dict[str, Any]:
    """`models`: `{object, target, kind, digest, published, fingerprint,
    recorded, linked_library, only_here}` → `{changed, new, baseline, skipped}`.

    `fingerprint` is the mesh as it is, `recorded` the one written when its
    bytes were made or fetched; `published` says the room's resource holds the
    object's digest."""
    changed, new, baseline, skipped = [], [], [], []
    for m in models:
        if m.get("only_here") or m.get("linked_library"):
            skipped.append(m)
            continue
        if not m.get("digest") and not m.get("published"):
            new.append({**m, "state": STATE_NEW})
            continue
        if not m.get("recorded"):
            baseline.append(m)
            continue
        if m.get("fingerprint") and m["fingerprint"] != m["recorded"]:
            changed.append({**m, "state": STATE_CHANGED})
    return {"changed": changed, "new": new, "baseline": baseline,
            "skipped": skipped}


def estimated_size(vertices: int, triangles: int) -> int:
    """≈ the glb of a mesh, in bytes: position + normal + uv per vertex
    (32 B), three 4-byte indices per triangle, and a header. An estimate for
    the list before sending; the size that went is reported after."""
    return 32 * int(vertices) + 12 * int(triangles) + 2048


def human_size(n: Optional[int]) -> str:
    n = int(n or 0)
    for unit in ("B", "kB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024.0
    return f"{n} B"


def _flat(data: Any, prefix: str = "") -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    if isinstance(data, dict):
        for k, v in data.items():
            if k.startswith("_"):
                continue
            key = f"{prefix}{k}"
            if isinstance(v, dict) and k == "data":
                out.update(_flat(v, "data."))
            else:
                out[key] = v
    return out


def section_delta_ops(before: Dict[str, Any], after: Dict[str, Any]
                      ) -> List[Dict[str, Any]]:
    """The changes from one em.json section to another, as local changes
    `emit_op` takes: a new node whole, a changed node by its changed fields
    (a field that went is an emptying, `remove`), a new edge, an edge gone."""
    old_nodes = {n.get("id"): n for n in before.get("nodes") or [] if n.get("id")}
    new_nodes = {n.get("id"): n for n in after.get("nodes") or [] if n.get("id")}
    ops: List[Dict[str, Any]] = []
    for nid, node in new_nodes.items():
        if nid not in old_nodes:
            ops.append({"op": "add_node", "id": nid, "node": node})
            continue
        was, now = _flat(old_nodes[nid]), _flat(node)
        for field in sorted(set(was) | set(now)):
            # what an update_field may address (`crdt.is_addressable_field`):
            # the rest of a node is structure
            if not (field in ("name", "description")
                    or (field.startswith("data.") and len(field) > 5)):
                continue
            if field not in now:
                ops.append({"op": "update_field", "node_id": nid, "field": field,
                            "remove": True})
            elif was.get(field) != now[field]:
                ops.append({"op": "update_field", "node_id": nid, "field": field,
                            "value": now[field]})
    old_edges = {e.get("id"): e for e in before.get("edges") or [] if e.get("id")}
    new_edges = {e.get("id"): e for e in after.get("edges") or [] if e.get("id")}
    for eid, e in new_edges.items():
        if eid not in old_edges:
            ops.append({"op": "add_edge", "id": eid, "source": e.get("source"),
                        "target": e.get("target"), "edge_type": e.get("edge_type")})
    for eid, e in old_edges.items():
        if eid not in new_edges:
            ops.append({"op": "remove_edge", "id": eid, "source": e.get("source"),
                        "target": e.get("target"), "edge_type": e.get("edge_type")})
    return ops


# ── Blender ─────────────────────────────────────────────────────────────────

def mesh_fingerprint(obj) -> str:  # pragma: no cover — bpy
    """The mesh as the glb would carry it: vertices, faces, placement."""
    data = getattr(obj, "data", None)
    if getattr(obj, "type", "") != "MESH" or data is None:
        return ""
    import array
    h = hashlib.sha1()
    co = array.array("f", [0.0]) * (len(data.vertices) * 3)
    data.vertices.foreach_get("co", co)
    h.update(co.tobytes())
    loops = array.array("i", [0]) * len(data.loops)
    data.loops.foreach_get("vertex_index", loops)
    h.update(loops.tobytes())
    h.update(str(len(data.polygons)).encode())
    for row in obj.matrix_world:
        h.update(array.array("f", list(row)).tobytes())
    return h.hexdigest()


def record_fingerprint(obj) -> None:  # pragma: no cover — bpy
    """Write what the mesh is NOW, as the state its bytes describe."""
    try:
        fp = mesh_fingerprint(obj)
        if fp:
            obj[PROP_FINGERPRINT] = fp
    except Exception as exc:  # noqa: BLE001 — a fingerprint never fails a gesture
        print(f"[sync] no fingerprint for {getattr(obj, 'name', '?')}: {exc}")


def _counts(obj):  # pragma: no cover — bpy
    data = getattr(obj, "data", None)
    if getattr(obj, "type", "") != "MESH" or data is None:
        return 0, 0
    tris = sum(max(0, len(p.vertices) - 2) for p in data.polygons)
    return len(data.vertices), tris


def read_models(context, graph) -> List[Dict[str, Any]]:  # pragma: no cover — bpy
    """The graph-linked models of the scene, read for `classify_models`."""
    import bpy  # type: ignore
    from .bring import _already_published, scene_models
    from .scene_check import PROP_ONLY_HERE

    out = []
    models = list(scene_models(context, graph))
    # …and the models that came from the store (materialised, R1: a source-
    # based one is resident): bound to a resource of this graph, neither an RM
    # of the list nor a proxy
    from .materialise import PROP_CARRIER, PROP_RESOURCE
    listed = {m["object"] for m in models}
    for obj in bpy.data.objects:
        rid = str(obj.get(PROP_RESOURCE) or "")
        if obj.name in listed or not rid or graph.find_node_by_id(rid) is None:
            continue
        if obj.get("em_asset_id"):
            continue                    # an asset's library object: its versions
        models.append({"object": obj.name, "kind": "model",
                       "target": str(obj.get(PROP_CARRIER) or rid)})
    for model in models:
        obj = bpy.data.objects.get(model["object"])
        if obj is None:
            continue
        verts, tris = _counts(obj)
        out.append({**model,
                    "digest": str(obj.get("em_asset_sha256") or ""),
                    "resource_id": str(obj.get("em_resource_id") or ""),
                    "published": _already_published(obj, graph),
                    "fingerprint": mesh_fingerprint(obj),
                    "recorded": str(obj.get(PROP_FINGERPRINT) or ""),
                    "linked_library": bool(obj.library or getattr(obj.data, "library", None)),
                    "only_here": bool(obj.get(PROP_ONLY_HERE)),
                    "vertices": verts, "triangles": tris,
                    "size": estimated_size(verts, tris)})
    return out


def candidates(context, graph) -> Dict[str, Any]:  # pragma: no cover — bpy
    """The models to offer, with the baselines written for the unknown ones."""
    import bpy  # type: ignore
    groups = classify_models(read_models(context, graph))
    for m in groups["baseline"]:
        obj = bpy.data.objects.get(m["object"])
        if obj is not None:
            record_fingerprint(obj)
    return groups


def _section(graph) -> Dict[str, Any]:  # pragma: no cover — bpy
    from ..emjson_support import graph_to_emjson_dict
    return graph_to_emjson_dict(graph).get("graph") or {}


def _revise(context, graph, model) -> Dict[str, Any]:  # pragma: no cover — bpy
    """A changed model: its bytes up, a revision of its resource, the
    citations moved to it."""
    import bpy  # type: ignore
    from . import commands
    from . import room as room_cfg

    obj = bpy.data.objects.get(model["object"])
    rid = str(obj.get("em_resource_id") or "") if obj is not None else ""
    if obj is None or not rid or graph.find_node_by_id(rid) is None:
        return {"ok": False, "error": f"{model['object']}: no resource to revise"}
    data = commands._export_gltf(obj, context)
    info = room_cfg.put_asset(data, room_cfg.GLTF_MEDIA_TYPE)
    spec = {"path": f"{obj.name}.glb", "url": info["url"], "checksum": info["sha256"],
            "size_bytes": len(data), "media_type": room_cfg.GLTF_MEDIA_TYPE}
    new_id = _revision(graph, rid, spec)
    if not new_id:
        return {"ok": False, "error": f"{model['object']}: the bytes did not change"}
    # a proxy's glb is also its chain's resource (`_fill_proxy_chain`): the
    # same bytes, the same revision — or the next check would owe the scene
    # the old glb
    if model.get("kind") == "proxy":
        try:
            from ..proxy_chain import glb_proxy
            _shape, chain = glb_proxy(graph, model["target"])
        except Exception:  # noqa: BLE001
            chain = None
        if chain is not None and chain.node_id != rid:
            _revision(graph, chain.node_id, spec)
    obj["em_resource_id"] = new_id
    obj["em_asset_sha256"] = info["ref"]
    record_fingerprint(obj)
    return {"ok": True, "info": {"object": obj.name, "resource_id": new_id,
                                 "revision_of": rid, "size": len(data),
                                 "stored": bool(info.get("created"))}}


def _revision(graph, rid: str, spec: Dict[str, Any]) -> Optional[str]:  # pragma: no cover — bpy
    """`rid` revised with the bytes of `spec`, resident, its citations moved."""
    from .. import resource_revisions as revisions
    out = revisions.revise_files(graph, rid, [spec], force=True)
    new_id = out.get("new_resource_id")
    if not new_id:
        return None
    node = graph.find_node_by_id(new_id)
    if node is not None:
        node.data = dict(getattr(node, "data", None) or {})
        node.data.update({"url": spec["url"], "checksum": spec["checksum"],
                          "residency": "resident"})
    citing, _staying = revisions.split_pointers(out.get("pointing_at_old") or [])
    revisions.move_citations(graph, rid, new_id, [c["edge_id"] for c in citing])
    return new_id


def send(context, graph, models: List[Dict[str, Any]]) -> Dict[str, Any]:  # pragma: no cover — bpy
    """Send the chosen models; the graph's changes go to the room as ops."""
    import bpy  # type: ignore
    from . import commands
    from . import operators as ops

    before = _section(graph)
    sent, failed, size = [], [], 0
    for model in models:
        try:
            if model.get("state") == STATE_CHANGED:
                result = _revise(context, graph, model)
            else:
                result = commands.promote_model(
                    model["target"], {"object": model["object"],
                                      "residency": "resident"}, context, graph)
                obj = bpy.data.objects.get(model["object"])
                if result.get("ok") and obj is not None:
                    record_fingerprint(obj)
                    if model.get("kind") == "proxy":
                        from .bring import _fill_proxy_chain
                        _fill_proxy_chain(graph, model["target"], result["info"], [])
        except Exception as exc:  # noqa: BLE001 — one model is one row
            result = {"ok": False, "error": f"{model['object']}: {exc}"}
        if result.get("ok"):
            sent.append(result["info"])
            size += int(result["info"].get("size") or 0)
        else:
            failed.append(str(result.get("error")))
    delta = section_delta_ops(before, _section(graph))
    for op in delta:
        ops.emit_op(op)
    return {"sent": sent, "failed": failed, "size": size, "ops": len(delta)}
