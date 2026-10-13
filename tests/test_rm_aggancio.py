"""MICRO RM e aggancio (13 Oct 2026), measured without bpy on the room as it
was: `tavolo-2026-10-12`, snapshot of 18:26 (`fixtures/
tavolo_2026-10-13_1826.room.json`), and this Blender's graph beside it.

A · the room holds ``ME_EST_bk_LOD2_model ─has_linked_resource→ 2f69bffb``
and ``2f69bffb ─was_revision_of→ ME_EST_bk_LOD2_model_res_blend``, and
neither the RM nor its datablock: «Replace» (16:11) sent what changed, and
the RM, made here before the gesture, was in neither side of the delta. The
rule: an edge never leaves toward a node the room does not have; an RM of
the list arrives with its node, its epoch and its datablock; the sync
repairs the room as it is.

B · 2f69bffb's bytes (8ddcb515) are «US 2», a monkey of 1 970 vertices: a
proxy sent as a revision of the RM's datablock. The rule: a revision is born
only from the object bound to its resource; the wrong one is withdrawn (with
Undo) and the RM goes back to its datablock.

C · «US 4» (an Icosphere) is «only here»: its unit is «US 4 · B online (più
recente) 19:56:23». «Make it the proxy of…» proposes that one first, and the
proxy goes in the canonical chain.
"""

import copy
import importlib.util
import json
import pathlib
import sys
import tempfile
import types

import pytest

_REPO = pathlib.Path(__file__).resolve().parent.parent
_S3D = _REPO.parent / "s3Dgraphy" / "src"
if _S3D.is_dir():
    sys.path.insert(0, str(_S3D))

pytest.importorskip("s3dgraphy.geometry.proxy")

from s3dgraphy.api import load_container_file  # noqa: E402
from s3dgraphy.nodes.representation_node import RepresentationModelNode  # noqa: E402


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, _REPO / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _pkg(name, rel):
    p = types.ModuleType(name)
    p.__path__ = [str(_REPO / rel)]
    sys.modules[name] = p


sys.path.insert(0, str(_REPO))
_pkg("_tra", "")
_pkg("_tra.sync_bridge", "sync_bridge")
_load("_tra.sync_bridge.wire", "sync_bridge/wire.py")
_load("_tra.sync_bridge.ws_client", "sync_bridge/ws_client.py")
_pkg("_tra.sync_manager", "sync_manager")
_load("_tra.sync_manager.room", "sync_manager/room.py")
RS = _load("_tra.sync_manager.room_session", "sync_manager/room_session.py")
SS = _load("_tra.sync_manager.scene_sync", "sync_manager/scene_sync.py")
PH = _load("_tra.sync_manager.proxy_hook", "sync_manager/proxy_hook.py")
PC = _load("_tra_proxy_chain", "proxy_chain.py")
GOV = _load("resource_governance", "resource_governance.py")

ROOM = "tavolo-2026-10-12"
FIXTURE = _REPO / "tests" / "fixtures" / "tavolo_2026-10-13_1826.room.json"
RM = "ME_EST_bk_LOD2_model"
BLEND = "ME_EST_bk_LOD2_model_res_blend"
LOD2 = "2f69bffb-1757-58ed-bfe7-d7990d79196e"
LOD2_FILE = "d2860464-f65e-547a-9f8f-4f5004d811f2"
EPOCH = "49f50053-5472-4a2f-8759-beb366f14ded"
V1 = "0ab59a82-f7d8-5299-9148-9b4ada0c9e8d"
SHAPE2 = "a6c53253-9f1d-5e7d-b47d-1eb483e1a510"
LOCATOR = ("blend://../Library/CloudStorage/OneDrive-CNR/Extended%20Matrix/EM_CaseStudies/"
           "01_EM_Tempio%20Grande%20v2/RB/TempluMare_2021.blend#Object/ME_EST_bk_LOD2")


def _doc():
    return json.loads(FIXTURE.read_text())


def _blender_graph():
    """The graph this Blender held: the room's document (live) and, beside
    it, what only this Blender had — the RM of the list, its datablock, its
    epoch — with the two edges the room already holds toward them."""
    doc = RS.live_view(_doc())
    path = tempfile.mktemp(suffix=".em.json")
    pathlib.Path(path).write_text(json.dumps(doc))
    g = next(iter(load_container_file(path)[0].graphs.values()))
    from s3dgraphy import api
    g.add_node(RepresentationModelNode(RM, name="Model for ME_EST_bk_LOD2", type="RM",
                                       description=""))
    api.add_resource(g, resource_id=BLEND, name="Blend datablock for ME_EST_bk_LOD2",
                     kind="3d_model", tier="master", packaging="datablock",
                     files=[{"url": LOCATOR}])
    for eid, s, t, kind in (
            (f"{RM}_has_linked_resource_{LOD2}", RM, LOD2, "has_linked_resource"),
            (f"{LOD2}~revision~>{BLEND}", LOD2, BLEND, "was_revision_of"),
            (f"{EPOCH}_has_representation_model_{RM}", EPOCH, RM, "has_representation_model")):
        if g.find_edge_by_id(eid) is None:
            g.add_edge(eid, s, t, kind)
    return g


def _emjson(g):
    """The graph as an em.json section, as `scene_sync._section` gives it."""
    nodes = []
    for n in g.nodes:
        data = getattr(n, "data", None)
        nodes.append({"id": n.node_id, "node_type": getattr(n, "node_type", ""),
                      "name": getattr(n, "name", ""),
                      "data": dict(data) if isinstance(data, dict) else {}})
    edges = [{"id": e.edge_id, "source": e.edge_source, "target": e.edge_target,
              "edge_type": e.edge_type} for e in g.edges]
    return {"nodes": nodes, "edges": edges}


def _applied(holds, ops):
    """What the room holds after these operations."""
    h = copy.deepcopy(holds)
    for op in ops:
        RS.note_op(h, op)
    return h


def _dangling(holds):
    return {eid for eid, (s, _t, d) in holds["edges"].items()
            if s not in holds["nodes"] or d not in holds["nodes"]}


# ── A · the RM arrives with its node ────────────────────────────────────────

def test_the_room_holds_edges_toward_nodes_it_lacks():
    """The measure: two edges, toward the RM and its datablock."""
    holds = RS.room_holds(_doc(), ROOM)
    assert RM not in holds["nodes"] and BLEND not in holds["nodes"]
    assert LOD2 in holds["nodes"]
    assert _dangling(holds) == {f"{RM}_has_linked_resource_{LOD2}",
                                f"{LOD2}~revision~>{BLEND}"}


def test_the_delta_of_a_gesture_never_carries_the_node_made_before_it():
    """The defect, measured: the RM existed here before «Replace»; the delta
    adds the edge and not the node. Closed over what the room holds, the RM
    and its datablock go first, and nothing points at a node the room lacks."""
    g = _blender_graph()
    holds = RS.room_holds(_doc(), ROOM)
    # the room before 16:11: without 2f69bffb and what it brought
    before_room = _applied(holds, [{"op": "remove_node", "id": LOD2},
                                   {"op": "remove_node", "id": LOD2_FILE}])
    after = _emjson(g)
    before = {"nodes": [n for n in after["nodes"] if n["id"] not in (LOD2, LOD2_FILE)],
              "edges": [e for e in after["edges"]
                        if LOD2 not in (e["source"], e["target"])
                        and LOD2_FILE not in (e["source"], e["target"])]}
    raw = SS.section_delta_ops(before, after)
    assert any(o["op"] == "add_edge" and o["source"] == RM for o in raw)
    assert not any(o["op"] == "add_node" and o["id"] == RM for o in raw)
    assert _dangling(_applied(before_room, raw))                 # the defect

    closed = SS.close_over(raw, after, before_room)
    assert RM in closed["brought"] and BLEND in closed["brought"]
    ids = [o.get("id") for o in closed["ops"]]
    assert ids.index(RM) < ids.index(f"{RM}_has_linked_resource_{LOD2}")
    assert not _dangling(_applied(before_room, closed["ops"]))


def test_an_rm_of_the_list_arrives_with_its_node_its_epoch_its_datablock():
    g = _blender_graph()
    GOV.retire_revision(g, LOD2)                       # (B) the RM back on its datablock
    holds = RS.room_holds(_doc(), ROOM)
    closed = SS.close_over([], _emjson(g), holds, bring=[RM])
    adds = {o["id"] for o in closed["ops"] if o["op"] == "add_node"}
    assert {RM, BLEND} <= adds
    edges = {(o["source"], o["edge_type"], o["target"]) for o in closed["ops"]
             if o["op"] == "add_edge"}
    assert (EPOCH, "has_representation_model", RM) in edges
    assert (RM, "has_linked_resource", BLEND) in edges
    # an RM the room has is not sent again
    after = _applied(holds, closed["ops"])
    again = SS.close_over([], _emjson(g), after, bring=[RM])
    assert again["ops"] == [] or all(o["op"] == "remove_edge" for o in again["ops"])


def test_the_sync_repairs_the_room_as_it_is():
    """No gesture: the room's two edges toward nothing get their nodes."""
    g = _blender_graph()
    holds = RS.room_holds(_doc(), ROOM)
    closed = SS.close_over([], _emjson(g), holds)
    assert set(closed["brought"]) >= {RM, BLEND}
    assert not _dangling(_applied(holds, closed["ops"]))


def test_an_edge_toward_a_node_nobody_has_is_not_sent_and_the_rooms_goes():
    holds = {"nodes": {"a"}, "edges": {"old": ("a", "has_linked_resource", "ghost")}}
    section = {"nodes": [{"id": "a"}], "edges": []}
    ops = [{"op": "add_edge", "id": "e", "source": "a", "target": "nowhere",
            "edge_type": "has_linked_resource"}]
    closed = SS.close_over(ops, section, holds)
    assert [o["id"] for o in closed["dropped"]] == ["e"]
    assert closed["removed"] == ["old"]
    assert not _dangling(_applied(holds, closed["ops"]))


def test_unknown_room_sends_the_delta_as_it_is():
    ops = [{"op": "add_edge", "id": "e", "source": "a", "target": "b", "edge_type": "x"}]
    assert SS.close_over(ops, {"nodes": [], "edges": []}, None)["ops"] == ops


def test_what_the_room_holds_follows_the_operations():
    holds = {"nodes": {"a"}, "edges": {}}
    RS.note_op(holds, {"op": "add_node", "id": "b", "node": {"id": "b"}})
    RS.note_op(holds, {"op": "add_edge", "id": "ab", "source": "a", "target": "b",
                       "edge_type": "x"})
    assert holds == {"nodes": {"a", "b"}, "edges": {"ab": ("a", "x", "b")}}
    RS.note_op(holds, {"op": "remove_node", "id": "b"})
    assert holds == {"nodes": {"a"}, "edges": {}}
    # a session counts what it sends
    s = RS.RoomSession()
    s.holds = {"nodes": set(), "edges": {}}
    s.send_op({"op": "add_node", "id": "c", "node": {"id": "c"}})
    assert "c" in s.holds["nodes"]


# ── B · a proxy's bytes are never a revision of an RM's model ───────────────

def test_the_glb_on_the_datablock_is_found_and_withdrawn_with_undo():
    g = _blender_graph()
    assert GOV.glb_on_datablock(g) == [LOD2]
    before = _emjson(g)
    plan = GOV.retire_revision(g, LOD2)
    assert plan["back_to"] == BLEND and plan["files"] == [LOD2_FILE]
    assert g.find_node_by_id(LOD2) is None
    # the RM back on its version: its datablock
    assert [c["source"] for c in GOV.citing(g, BLEND)] == [RM]
    assert GOV.in_use(g, BLEND) == BLEND
    assert GOV.glb_on_datablock(g) == []
    # the room gets the withdrawal, the RM and its datablock, nothing dangling
    holds = RS.room_holds(_doc(), ROOM)
    closed = SS.close_over(SS.section_delta_ops(before, _emjson(g)), _emjson(g), holds,
                           bring=[RM])
    after = _applied(holds, closed["ops"])
    assert LOD2 not in after["nodes"] and RM in after["nodes"] and BLEND in after["nodes"]
    assert not _dangling(after)
    # Undo puts 2f69bffb and its citation back
    record = GOV.withdrawal_record(before, plan, by="EMtools (sync)", at="2026-10-13T17:00:00Z")
    assert record["id"] == LOD2 and record["cited_by"] == [RM]
    undo = GOV.undo_ops(record, at="2026-10-13T17:01:00Z")
    assert {"op": "add_node", "id": LOD2} == {k: undo[0][k] for k in ("op", "id")}
    assert any(o["op"] == "add_edge" and o["source"] == RM and o["target"] == LOD2
               for o in undo)


def test_a_revision_is_born_only_from_the_object_bound_to_its_resource():
    g = _blender_graph()
    us2 = {"em_resource_id": V1, "em_rm_node_id": SHAPE2}
    # «US 2» (a proxy, carrier: its shape) on the RM's datablock: refused
    assert "model in this .blend" in GOV.revision_refusal(g, BLEND, us2)
    assert GOV.revision_refusal(g, LOD2, us2)
    # on its own chain: yes
    assert GOV.revision_refusal(g, V1, us2) == ""
    assert GOV.revision_refusal(g, V1, {}, unit_id="US2") == ""
    # «US 2.001» as measured at 17:50, bound to the RM's revision: refused
    us2_001 = {"em_resource_id": LOD2, "em_rm_node_id": LOD2}
    assert GOV.revision_refusal(g, LOD2, us2_001)
    # an RM's model that is not a datablock: a proxy never revises it
    from s3dgraphy import api
    api.add_resource(g, resource_id="X.model", name="X.glb", kind="3d_model")
    g.find_node_by_id("X.model").data["checksum"] = "sha256:" + "11" * 32
    g.add_edge("rm_x", RM, "X.model", "has_linked_resource")
    said = GOV.revision_refusal(g, "X.model", us2)
    assert said.startswith("this object is not") and "US 2" in said
    assert GOV.revision_refusal(g, "X.model", {"em_rm_node_id": RM}) == ""


def test_the_rebinding_never_moves_an_object_onto_another_carriers_resource():
    g = _blender_graph()
    us2_001 = {"em_resource_id": LOD2, "em_rm_node_id": LOD2}
    assert GOV.rebind_target(g, us2_001) == ""
    # «US 2» goes back to ITS chain, the version the room cites (since
    # 15:39:53 UTC the room cites v2 again, 989e63da)
    assert GOV.rebind_target(g, {"em_resource_id": LOD2, "em_rm_node_id": SHAPE2}) \
        == GOV.in_use(g, V1)
    assert GOV.in_use(g, V1) in GOV.chain_of(g, V1)
    GOV.retire_revision(g, LOD2)
    # the object stays, marked: withdrawn, removed by a gesture only
    assert GOV.object_status(g, LOD2, removed=[LOD2]) == GOV.STATUS_WITHDRAWN


# ── C · «Make it the proxy of…» ─────────────────────────────────────────────

def _units():
    sec = _doc()["graphs"][ROOM]
    return [(n["id"], n["name"]) for n in sec["nodes"] if n.get("node_type") == "US"
            and not (n.get("data") or {}).get("removed")]


def test_us_4_finds_its_unit_first_and_not_us_40():
    ranked = PH.rank_units("US 4", _units())
    assert ranked[0] == ("US4", "US 4 · B online (più recente) 19:56:23")
    assert not PH.alike("US 4", ("US40", "US 40"))
    assert PH.alike("US 4", ranked[0])
    assert PH.rank_units("US_4.001", _units())[0][0] == "US4"
    assert PH.rank_units("us4", _units())[0][0] == "US4"
    # everything is still offered, the similar ones first
    assert len(ranked) == len(_units())


def test_files_says_the_objects_not_in_the_graph():
    assert PH.not_in_graph_line([]) is None
    assert PH.not_in_graph_line(["US 4"]) == "1 object here is not in the graph: US 4"
    assert PH.not_in_graph_line(["A", "B"]) == "2 objects here are not in the graph: A, B"


def test_the_proxy_of_us_4_goes_in_the_canonical_chain():
    """What the next Sync does with it (`promote_model`): unit → geometry
    property → shape → resource, every node in the room with its edges."""
    g = _blender_graph()
    holds = RS.room_holds(_doc(), ROOM)
    before = _emjson(g)
    chain = PC.ensure_unit_proxy(g, "US4", "US 4 · B online (più recente) 19:56:23")
    shape, res = PC.glb_proxy(g, "US4")
    assert shape is not None and res is not None and res.node_id == chain["resource_id"]
    links = {(e.edge_source, e.edge_type, e.edge_target) for e in g.edges}
    assert ("US4", "has_property", chain["property_id"]) in links
    assert (chain["property_id"], "has_semantic_shape", chain["shape_id"]) in links
    assert (chain["shape_id"], "has_linked_resource", chain["resource_id"]) in links
    closed = SS.close_over(SS.section_delta_ops(before, _emjson(g)), _emjson(g), holds)
    after = _applied(holds, closed["ops"])
    assert {chain["property_id"], chain["shape_id"], chain["resource_id"]} <= after["nodes"]
    assert closed["dropped"] == []


def test_an_edge_toward_another_section_of_the_room_is_not_toward_nothing():
    doc = {"graphs": {
        ROOM: {"graph_id": ROOM, "nodes": [{"id": "u"}],
               "edges": [{"id": "x", "source": "u", "target": "shelf_node",
                          "edge_type": "has_property"}]},
        "shelf": {"graph_id": "shelf", "nodes": [{"id": "shelf_node"}], "edges": []}}}
    holds = RS.room_holds(doc, ROOM)
    assert not _dangling(holds)
    assert SS.close_over([], {"nodes": [{"id": "u"}], "edges": []}, holds)["removed"] == []
