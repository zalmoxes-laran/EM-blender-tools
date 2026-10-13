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
from typing import Any, Dict, Iterable, List, Optional

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
    (a field that went is an emptying, `remove`), a new edge, an edge gone, a
    node gone (a tombstone: «Withdraw», the old proxy form closed)."""
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

    def triple(e):
        return (e.get("source"), e.get("edge_type"), e.get("target"))

    # an edge that kept its id but changed its ends is a removal and an
    # addition (the room matches a removal by id OR by its ends)
    changed = {eid for eid, e in new_edges.items()
               if eid in old_edges and triple(old_edges[eid]) != triple(e)}
    for eid, e in old_edges.items():
        if eid not in new_edges or eid in changed:
            ops.append({"op": "remove_edge", "id": eid, "source": e.get("source"),
                        "target": e.get("target"), "edge_type": e.get("edge_type")})
    for eid, e in new_edges.items():
        if eid not in old_edges or eid in changed:
            ops.append({"op": "add_edge", "id": eid, "source": e.get("source"),
                        "target": e.get("target"), "edge_type": e.get("edge_type")})
    # a node gone is a tombstone, after its edges
    for nid in old_nodes:
        if nid not in new_nodes:
            ops.append({"op": "remove_node", "id": nid})
    return ops


#: what a node brought into the room carries with it, outward: what it cites
#: and the files of what it cites (an RM → its datablock → the `blend://`)
_FOLLOW = ("has_linked_resource", "has_file")


def _bring(ids, section: Dict[str, Any], known: set, skip_edges: set
           ) -> Dict[str, Any]:
    """Nodes of `section` the room does not have, as `add_node`, with what
    they cite (`_FOLLOW`) and every edge of theirs whose other end the room
    has or receives now (their epoch, their document). `known` and
    `skip_edges` grow with what is brought."""
    nodes = {n.get("id"): n for n in section.get("nodes") or [] if n.get("id")}
    todo = [i for i in ids if i in nodes and i not in known]
    brought: List[str] = []
    while todo:
        nid = todo.pop(0)
        if nid in known:
            continue
        known.add(nid)
        brought.append(nid)
        for e in section.get("edges") or []:
            if (e.get("source") == nid and e.get("edge_type") in _FOLLOW
                    and e.get("target") in nodes and e.get("target") not in known):
                todo.append(e["target"])
    ops = [{"op": "add_node", "id": nid, "node": nodes[nid]} for nid in brought]
    fresh = set(brought)
    for e in section.get("edges") or []:
        eid = e.get("id")
        ends = (e.get("source"), e.get("target"))
        if not eid or eid in skip_edges or not (fresh & set(ends)):
            continue
        if all(x in known for x in ends):
            skip_edges.add(eid)
            ops.append({"op": "add_edge", "id": eid, "source": ends[0],
                        "target": ends[1], "edge_type": e.get("edge_type")})
    return {"ops": ops, "brought": brought}


def close_over(ops: List[Dict[str, Any]], section: Dict[str, Any],
               holds: Optional[Dict[str, Any]], bring: Iterable[str] = ()
               ) -> Dict[str, Any]:
    """MICRO RM e aggancio (13 Oct 2026) · an edge never leaves toward a node
    the room does not have. `ops` is a delta (`section_delta_ops`), `section`
    the graph as it is now, `holds` what the room has
    (`room_session.room_holds`; None = unknown → the delta as it is).

    * an end the room lacks and this graph has goes first, whole, with what it
      cites and its own edges (`_bring`: an RM arrives with its epoch and its
      datablock); an end nobody has drops the edge (``dropped``);
    * the room as it is, repaired: an edge it HOLDS toward a node it lacks
      gets the node, or goes (``removed``);
    * `bring` (the RMs of the list) arrive the same way.

    Measured: «Replace» at 16:11 sent ``ME_EST_bk_LOD2_model
    ─has_linked_resource→ 2f69bffb`` and the RM, made here before the gesture,
    was in neither side of the delta. → ``{ops, brought, dropped, removed}``."""
    if holds is None:
        return {"ops": list(ops), "brought": [], "dropped": [], "removed": []}
    known = set(holds.get("nodes") or ())
    for op in ops:
        if op.get("op") == "add_node":
            known.add(op.get("id"))
    skip = set(holds.get("edges") or ()) | {op.get("id") for op in ops
                                             if op.get("op") == "add_edge"}
    section_ids = {n.get("id") for n in section.get("nodes") or []}
    gone_here = {op.get("id") for op in ops if op.get("op") == "remove_edge"}
    dangling = {eid: t for eid, t in (holds.get("edges") or {}).items()
                if eid not in gone_here and (t[0] not in known or t[2] not in known)}
    wanted = list(bring) + [end for op in ops if op.get("op") == "add_edge"
                            for end in (op.get("source"), op.get("target"))]
    wanted += [x for t in dangling.values() for x in (t[0], t[2])]
    extra = _bring([w for w in wanted if w not in known and w in section_ids],
                   section, known, skip)
    kept, dropped = [], []
    for op in ops:
        if op.get("op") == "add_edge" and not (op.get("source") in known
                                               and op.get("target") in known):
            dropped.append(op)
            continue
        kept.append(op)
    removed = [{"op": "remove_edge", "id": eid, "source": t[0], "edge_type": t[1],
                "target": t[2]} for eid, t in dangling.items()
               if t[0] not in known or t[2] not in known]
    nodes_first = [o for o in extra["ops"] if o["op"] == "add_node"]
    edges_after = [o for o in extra["ops"] if o["op"] != "add_node"]
    return {"ops": nodes_first + kept + edges_after + removed,
            "brought": extra["brought"], "dropped": dropped,
            "removed": [r["id"] for r in removed]}


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


def emit_delta(graph, before: Dict[str, Any], bring: Iterable[str] = ()
               ) -> Dict[str, Any]:  # pragma: no cover — bpy
    """What changed since `before`, closed over what the room holds
    (`close_over`: never an edge toward a node it lacks; the room's edges
    toward nothing repaired; `bring` sent with their epoch and datablock),
    sent as operations. → `close_over`'s report."""
    from . import operators as ops
    from .room_session import SESSION
    after = _section(graph)
    closed = close_over(section_delta_ops(before, after), after, SESSION.holds, bring)
    if closed["brought"]:
        print(f"[sync] sent with the edges that need them: {', '.join(closed['brought'][:8])}")
    for op in closed["dropped"]:
        print(f"[sync] not sent: {op.get('edge_type')} {op.get('source')} → "
              f"{op.get('target')} (an end is in no graph)")
    if closed["removed"]:
        print(f"[sync] the room's edges toward a node it lacks, removed: "
              f"{', '.join(closed['removed'][:6])}")
    for op in closed["ops"]:
        ops.emit_op(op)
    return closed


def to_the_room(graph, change) -> Any:  # pragma: no cover — bpy
    """Run `change(graph)` and send what it changed to the room, as operations
    (P1: a dropped connection keeps them). → what `change` returned."""
    before = _section(graph)
    out = change(graph)
    emit_delta(graph, before)
    return out


def _revise(context, graph, model) -> Dict[str, Any]:  # pragma: no cover — bpy
    """A changed model: its bytes up, a revision of its resource, the
    citations moved to it."""
    import bpy  # type: ignore

    obj = bpy.data.objects.get(model["object"])
    rid = str(obj.get("em_resource_id") or "") if obj is not None else ""
    if obj is None or not rid or graph.find_node_by_id(rid) is None:
        return {"ok": False, "error": f"{model['object']}: no resource to revise"}
    return revise_object(context, graph, obj, rid, kind=model.get("kind") or "",
                         target=model.get("target") or "")


def revise_object(context, graph, obj, rid: str, *, kind: str = "",
                  target: str = "") -> Dict[str, Any]:  # pragma: no cover — bpy
    """The object's mesh as a revision of the resource `rid` (of its CURRENT
    revision: `resource_governance.revise_and_cite`), its citations moved;
    nothing written when the current revision already has these bytes. Also
    «Replace with the scene's object» of the Storage panel."""
    from . import commands
    from . import room as room_cfg
    from .. import resource_governance as governance

    # a proxy's glb is its chain's resource: the object may still be bound to
    # the `<US>.model` of before or to an old revision — the chain is the one
    # revised, once (measured 13 Oct 2026: revising the object's resource and
    # then the chain's made two revisions of the same bytes)
    if kind == "proxy" and target:
        try:
            from ..proxy_chain import glb_proxy
            _shape, chain = glb_proxy(graph, target)
        except Exception:  # noqa: BLE001
            chain = None
        if chain is not None:
            rid = chain.node_id
    # MICRO RM e aggancio · a revision is born only from the object bound to
    # its resource: a proxy never revises an RM's model (16:11, «US 2» as a
    # revision of the LOD2 datablock)
    refusal = governance.revision_refusal(
        graph, rid, {k: obj.get(k) for k in ("em_resource_id", "em_rm_node_id")},
        unit_id=target if kind == "proxy" else "")
    if refusal:
        return {"ok": False, "error": f"{obj.name}: {refusal}"}
    data = commands._export_gltf(obj, context)
    info = room_cfg.put_asset(data, room_cfg.GLTF_MEDIA_TYPE)
    spec = {"path": f"{obj.name}.glb",
            "url": commands._store_url(graph, info["ref"]) or info["url"],
            "checksum": info["ref"], "size_bytes": len(data),
            "media_type": room_cfg.GLTF_MEDIA_TYPE}
    out = governance.revise_and_cite(graph, rid, spec)
    obj["em_resource_id"] = out["resource_id"]
    obj["em_asset_sha256"] = info["ref"]
    record_fingerprint(obj)
    if not out["created"]:
        # the same bytes as the version in use, or as an older one: then the
        # pointer moved to it — never a second version of the same bytes
        return {"ok": True, "info": {"object": obj.name, "resource_id": out["resource_id"],
                                     "revision_of": None, "size": 0,
                                     "same": not out.get("reused"),
                                     "reused": out.get("reused"), "stored": False}}
    return {"ok": True, "info": {"object": obj.name, "resource_id": out["resource_id"],
                                 "revision_of": out["revision_of"], "size": len(data),
                                 "stored": bool(info.get("created"))}}


def repair_versions(graph) -> Dict[str, Any]:  # pragma: no cover — bpy
    """A room migrated before the old form was closed, or written by an older
    EMtools: the `<US>.model` left alive are closed, a checksum without its
    `sha256:` and a store url on another host take the one form
    (`normalise_formats`), and the objects bound to another version with the
    bytes of the version IN USE are bound to it.

    No citation is moved here any more: since 13 Oct 2026 the version in use
    IS the cited one, and a shape that cites an older version is a choice
    («Use»), not a lag to repair."""
    import bpy  # type: ignore
    from .. import resource_governance as governance
    from . import room as room_cfg
    from .materialise import PROP_DIGEST, PROP_RESOURCE

    closed = governance.close_legacy_models(graph)
    where = room_cfg.room()
    room_id = str(where.get("room_id") or "")
    base = governance.room_base(graph, room_id, declared=room_cfg.public_base(),
                                connected=str(where.get("base_url") or "")) \
        if room_cfg.is_configured() else ""
    formats = governance.normalise_formats(graph, room_id, base)
    rebound = 0
    for obj in bpy.data.objects:
        rid = str(obj.get(PROP_RESOURCE) or "")
        if not rid or graph.find_node_by_id(rid) is None:
            continue
        # MICRO una verità · bound to another chain than its carrier cites
        # (US 2 → «Blend datablock for ME_EST_bk_LOD2»): back to the version
        # in use; its bytes are that version's when the mesh is the one its
        # bytes were recorded from (nothing changed here since)
        right = governance.rebind_target(graph, {
            PROP_RESOURCE: rid, "em_rm_node_id": str(obj.get("em_rm_node_id") or "")})
        if right:
            obj[PROP_RESOURCE] = right
            recorded = str(obj.get(PROP_FINGERPRINT) or "")
            if recorded and mesh_fingerprint(obj) == recorded:
                obj[PROP_DIGEST] = governance.full_digest(governance.digest_of(graph, right))
            print(f"[sync] {obj.name} was bound to {rid[:8]} (not its carrier's): "
                  f"bound to {right[:8]}, the version in use")
            rebound += 1
            continue
        used = governance.in_use(graph, rid)
        if used != rid and governance.object_status(
                graph, rid, str(obj.get(PROP_DIGEST) or "")) == governance.STATUS_CURRENT:
            obj[PROP_RESOURCE] = used
            rebound += 1
        digest = str(obj.get(PROP_DIGEST) or "")
        if digest and not digest.startswith("sha256:"):
            obj[PROP_DIGEST] = governance.full_digest(digest)
    return {"closed": closed["closed"], "warnings": closed["warnings"],
            "formats": formats, "rebound": rebound}


def retire_glb_on_datablocks(context, graph, before: Dict[str, Any]
                             ) -> List[str]:  # pragma: no cover — bpy
    """The glb revisions of an RM's datablock (`governance.glb_on_datablock`)
    leave the graph — and the room, with the delta — the RM's citation back on
    its datablock. Each is kept in `WITHDRAWN`, so Files ▸ «Withdrawn» offers
    «Undo». The objects that show those bytes are marked «withdrawn», never
    removed by themselves. → the ids."""
    import datetime as dt
    from .. import resource_governance as governance
    from .room_session import REMOVED_IN_ROOM, WITHDRAWN
    out: List[str] = []
    for rid in governance.glb_on_datablock(graph):
        name = governance.display_name(graph, rid)
        plan = governance.retire_revision(graph, rid)
        record = governance.withdrawal_record(
            before, plan, by="EMtools (sync)",
            at=dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
        record["name"] = f"{name} · a glb sent as its version by mistake"
        WITHDRAWN[record["id"]] = record
        REMOVED_IN_ROOM.update(plan["members"] + plan["files"])
        print(f"[sync] {rid[:8]} was a glb sent as a version of {name}: withdrawn, "
              f"the RM back on {plan['back_to']} (Undo: Files ▸ «Withdrawn»)")
        out.append(rid)
    return out


def seat_listed_rms(context, graph) -> List[str]:  # pragma: no cover — bpy
    """The RMs of the list whose node is in this graph and NOT in the room:
    their datablock resource and their epochs from the object, as the export
    writes them. → their ids, for `close_over` to bring into the room. An RM
    the room has is left as the room has it."""
    import bpy  # type: ignore
    from .room_session import SESSION
    out: List[str] = []
    if SESSION.holds is None:
        return out
    try:
        from ..rm_manager.containers import ensure_rm_and_internal_resource
        from ..rm_manager.epoch_edges import sync_epoch_edges
    except Exception as exc:  # noqa: BLE001 — the sync goes on without them
        print(f"[sync] the RMs of the list were not seated: {exc}")
        return out
    held = SESSION.holds.get("nodes") or set()
    for item in getattr(context.scene, "rm_list", []) or []:
        obj = bpy.data.objects.get(item.name)
        rm_id = str(getattr(item, "node_id", "") or "")
        if obj is None or not rm_id or graph.find_node_by_id(rm_id) is None \
                or rm_id in held:
            continue
        try:
            got, _res, _notes = ensure_rm_and_internal_resource(context.scene, graph, obj)
        except Exception as exc:  # noqa: BLE001 — one RM is one line
            print(f"[sync] {item.name}: its datablock not seated ({exc})")
            got = rm_id
        rm_id = got or rm_id
        epochs = [ep.epoch for ep in getattr(obj, "EM_ep_belong_ob", ())
                  if ep.epoch and ep.epoch != "no_epoch"]
        if epochs and getattr(item, "is_publishable", True):
            sync_epoch_edges(graph, rm_id, epochs)
        out.append(rm_id)
    return out


def migrate_proxy_models(context, graph) -> Dict[str, Any]:  # pragma: no cover — bpy
    """A room an older EMtools filled: its ``<US>.model`` become the canonical
    proxy chain (`proxy_chain.migrate_unit_models`), the changes go to the
    room as operations, and the objects bound to the old resource are bound
    to the new one. Once: a second sync finds nothing to migrate.

    Only for who may write — a viewer reads the old form (it is still read,
    `residence.is_proxy_resource`) and leaves it to an editor."""
    import bpy  # type: ignore
    from ..proxy_chain import legacy_unit_models, migrate_old_proxies, migrate_unit_models
    from . import operators as ops

    if not ops.current_session(context).can_write:
        return {"migrated": [], "closed": [], "warnings": [], "ops": 0}
    before = _section(graph)
    if legacy_unit_models(graph):
        migrate_old_proxies(graph)
        report = migrate_unit_models(graph)
    else:
        report = {"migrated": [], "closed": [], "warnings": []}
    # …and what an earlier sync left: the old form alive, a citation behind
    repaired = repair_versions(graph)
    report["closed"] = list(report.get("closed") or []) + repaired["closed"]
    report["warnings"] = list(report["warnings"]) + repaired["warnings"]
    report["formats"] = repaired["formats"]
    # MICRO RM e aggancio · a glb sent as a revision of an RM's datablock
    # goes (Undo in Files ▸ «Withdrawn»), the RM back on its datablock; the
    # RMs of the list are seated with their epoch
    report["retired"] = retire_glb_on_datablocks(context, graph, before)
    rms = seat_listed_rms(context, graph)
    from . import room_session
    for item in report["closed"]:
        room_session.REMOVED_IN_ROOM.update(item["removed"])
    closed = emit_delta(graph, before, rms)
    sent = len(closed["ops"])
    report["brought"] = closed["brought"]
    report["dangling_removed"] = closed["removed"]
    if not sent and not report["migrated"]:
        report["ops"] = 0
        return report
    moved = {m["old"]: m["new"] for m in report["migrated"]}
    for obj in bpy.data.objects:
        if str(obj.get("em_resource_id") or "") in moved:
            obj["em_resource_id"] = moved[str(obj["em_resource_id"])]
    report["ops"] = sent
    try:
        from ..functions import em_log
    except Exception:  # noqa: BLE001
        em_log = print
    em_log(f"[sync] proxies migrated to the canonical form (property → shape → "
           f"resource): {', '.join(m['unit_id'] for m in report['migrated']) or 'none'}"
           f" · old form closed: {', '.join(i for c in report['closed'] for i in c['removed']) or 'none'}"
           f" · checksums and store urls put in one form: {len(report['formats'])}"
           f" · glb revisions of a datablock withdrawn: {', '.join(r[:8] for r in report['retired']) or 'none'}"
           f" · sent with their edges: {', '.join(report['brought'][:8]) or 'none'}"
           f" · edges toward nothing removed: {len(report['dangling_removed'])}"
           f" · {sent} change(s) to the room"
           + (f" · {'; '.join(report['warnings'])}" if report["warnings"] else ""),
           "WARNING")
    return report


def send(context, graph, models: List[Dict[str, Any]]) -> Dict[str, Any]:  # pragma: no cover — bpy
    """Send the chosen models; the graph's changes go to the room as ops."""
    import bpy  # type: ignore
    from . import commands

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
    closed = emit_delta(graph, before)
    return {"sent": sent, "failed": failed, "size": size, "ops": len(closed["ops"])}
