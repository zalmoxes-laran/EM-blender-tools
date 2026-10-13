"""MICRO una verità (13 Oct 2026), measured without bpy.

Room `tavolo-2026-10-12`, editor2, 17:09: the room cited v1 of US 2
(0ab59a82, the shape's citation moved there by «Use» at 14:10:57 UTC), the
panel said «v2 · 16:03 · in use», and the scene held «US 2» bound to
2f69bffb — a revision of «Blend datablock for ME_EST_bk_LOD2» that «Replace»
had made of it at 14:11:09 UTC, the card having fallen back on row 0 after
«Use» — and «US 2.001» bound to 989e63da (v2), brought by the sync.

The rule: **in use = what the room cites**. The panel says it, the scene
carries only it, and what is here and not sent is said in the room's state.
Here, on the graph as it was measured (chain 0ab59a82 ← beaacb9e ← 989e63da):

* a citation the room deleted and this Blender still holds is dropped at the
  entry (`room_session.tombstones` / `drop_tombstoned`) — without it, in use
  is v2, and the sync owes v2 to the scene;
* the panel says v1 in use, `materialise` does not owe 989e63da;
* the state says «● 1 change here, not sent», never «● Aligned»;
* «Replace» is not offered with US 2.001 active (bound to a version not in
  use); «US 2» bound to the datablock goes back to the version in use;
* a glb is never a revision of a .blend datablock, which is called by its
  object («ME_EST_bk_LOD2 — model in this .blend»);
* after «Use» the selected row stays the same resource, or none;
* the three addresses of the node are one row, «● in use», no Use;
* the head of Files counts its rows; a cached copy has no «Open where it
  is»; «No bucket» is grey; one «Open in EMStudio»; no Heriverse hexagon in
  the Data Tree; no window opens another from inside it.
"""

import importlib.util
import pathlib
import re
import sys
import types

import pytest

_REPO = pathlib.Path(__file__).resolve().parent.parent
_S3D = _REPO.parent / "s3Dgraphy" / "src"
if _S3D.is_dir():
    sys.path.insert(0, str(_S3D))

pytest.importorskip("s3dgraphy.geometry.proxy")

from s3dgraphy.api import geometry_summary  # noqa: E402
from s3dgraphy.graph import Graph  # noqa: E402
from s3dgraphy.nodes.representation_node import RepresentationModelNode  # noqa: E402
from s3dgraphy.nodes.stratigraphic_node import StratigraphicUnit  # noqa: E402


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
_pkg("_tuv", "")
_pkg("_tuv.sync_bridge", "sync_bridge")
_load("_tuv.sync_bridge.wire", "sync_bridge/wire.py")
_load("_tuv.sync_bridge.ws_client", "sync_bridge/ws_client.py")
_pkg("_tuv.sync_manager", "sync_manager")
_load("_tuv.sync_manager.room", "sync_manager/room.py")
RS = _load("_tuv.sync_manager.room_session", "sync_manager/room_session.py")
WHERE = _load("_tuv.sync_manager.where", "sync_manager/where.py")
FL = _load("_tuv.sync_manager.files_list", "sync_manager/files_list.py")
MAT = _load("_tuv.sync_manager.materialise", "sync_manager/materialise.py")
NC = _load("_tuv.sync_manager.node_choice", "sync_manager/node_choice.py")
OE = _load("_tuv.sync_manager.open_in_emstudio", "sync_manager/open_in_emstudio.py")
PC = _load("_tuv_proxy_chain", "proxy_chain.py")
GOV = _load("resource_governance", "resource_governance.py")

ROOM = "tavolo-2026-10-12"
NODE = "https://em.localhost:8443/em"
V1_BYTES, V2_BYTES, LOD2_BYTES = ("sha256:" + "6c" * 32, "sha256:" + "a0" * 32,
                                  "sha256:" + "8d" * 32)


def _resident(g, rid, digest, at):
    g.find_node_by_id(rid).data.update(
        {"url": GOV.store_url(NODE, ROOM, digest), "checksum": digest,
         "residency": "resident", "media_type": "model/gltf-binary", "created_at": at})


def _revise(g, rid, digest, at):
    rr = GOV._rr()
    spec = {"path": "x.glb", "url": GOV.store_url(NODE, ROOM, digest), "checksum": digest,
            "size_bytes": 10, "media_type": "model/gltf-binary"}
    new = rr.revise_files(g, rid, [spec], force=True)["new_resource_id"]
    _resident(g, new, digest, at)
    rr.move_citations(g, rid, new, [c["edge_id"] for c in GOV.citing(g, rid)])
    return new


def _measured():
    """The room as it was at 17:09, and this Blender's graph with the
    citation of 16:03 still alive (the edge the room deleted at 14:10:40)."""
    g = Graph(ROOM)
    g.add_node(StratigraphicUnit("US2", name="US 2"))
    chain = PC.ensure_unit_proxy(g, "US2", "US 2")
    v1 = chain["resource_id"]
    _resident(g, v1, V1_BYTES, "2026-10-13T08:51:34Z")              # 10:51
    bea = _revise(g, v1, V1_BYTES, "2026-10-13T08:51:34Z")          # the double
    v2 = _revise(g, bea, V2_BYTES, "2026-10-13T14:03:34Z")          # 16:03
    stale = next(c["edge_id"] for c in GOV.citing(g, v2))           # 6f24…
    GOV.use_version(g, v1)                                          # «Use v1», 16:10
    # …and the stale citation, as this Blender held it
    g.add_edge(stale, chain["shape_id"], v2, "has_linked_resource")
    # the RM of the .blend and its datablock; 2f69 the revision «Replace» made
    g.add_node(RepresentationModelNode("ME_EST_bk_LOD2_model", name="Model for ME_EST_bk_LOD2",
                                       type="RM", description=""))
    from s3dgraphy import api
    api.add_resource(g, resource_id="ME_EST_bk_LOD2_model_res_blend",
                     name="Blend datablock for ME_EST_bk_LOD2", kind="3d_model", tier="master",
                     packaging="datablock",
                     files=[{"url": "blend://RB/TempluMare_2021.blend#Object/ME_EST_bk_LOD2"}])
    g.add_edge("rm_blend", "ME_EST_bk_LOD2_model", "ME_EST_bk_LOD2_model_res_blend",
               "has_linked_resource")
    lod2 = _revise(g, "ME_EST_bk_LOD2_model_res_blend", LOD2_BYTES, "2026-10-13T14:11:09Z")
    doc = {"graphs": {ROOM: {"graph_id": ROOM, "nodes": [{"id": n.node_id} for n in g.nodes],
                             "edges": [{"id": stale, "source": chain["shape_id"], "target": v2,
                                        "edge_type": "has_linked_resource",
                                        "attributes": {"removed": {"ts": "2026-10-13T14:10:40Z",
                                                                   "by": "editor2"}}}]}}}
    return g, {"v1": v1, "bea": bea, "v2": v2, "shape": chain["shape_id"], "lod2": lod2,
               "stale": stale, "doc": doc}


def _owed(g):
    return {r.get("resource_id") for r in MAT.superseded_out(g, geometry_summary(g))["resident"]}


# ── 1 · in use = what the room cites ────────────────────────────────────────

def test_without_the_rooms_deletions_this_blender_said_v2():
    """The defect, measured: two citations of one chain, and `in_use` takes
    the newer — the panel's «v2 · 16:03 · in use», and the sync owed v2."""
    g, m = _measured()
    assert GOV.in_use(g, m["v1"]) == m["v2"]
    assert m["v2"] in _owed(g)


def test_the_rooms_deletions_win_and_v1_is_in_use():
    g, m = _measured()
    dead = RS.tombstones(m["doc"])[ROOM]
    assert m["stale"] in dead["edges"]
    gone = RS.drop_tombstoned(g, dead)
    assert gone == [m["stale"]]
    assert GOV.in_use(g, m["v1"]) == m["v1"]
    # the panel: v1 · in use, of two (the double of the morning is the same bytes)
    groups = GOV.distinct_versions(GOV.versions(g, m["v2"]))
    assert [(x["n"], x["in_use"]) for x in groups] == [(1, True), (2, False)]
    assert GOV.version_count(g, m["v2"]) == (1, 2)
    # materialise owes v1, never 989e63da
    owed = _owed(g)
    assert m["v1"] in owed and m["v2"] not in owed and m["bea"] not in owed
    # a second entry drops nothing more
    assert RS.drop_tombstoned(g, dead) == []


def test_an_edge_deleted_then_back_is_not_a_deletion():
    doc = {"graphs": {ROOM: {"graph_id": ROOM, "nodes": [], "edges": [
        {"id": "a", "source": "s", "target": "t", "edge_type": "has_linked_resource",
         "attributes": {"removed": {"ts": "2026-10-13T14:10:57Z"}}},
        {"id": "b", "source": "s", "target": "t", "edge_type": "has_linked_resource"}]}}}
    dead = RS.tombstones(doc)[ROOM]
    assert dead["edges"] == {"a"} and dead["triples"] == set()


def test_what_is_here_and_not_sent_is_said_in_the_state():
    s = {"place": "room", "room_title": "Tavolo", "members": 2, "sent": 4, "answered": 4,
         "tally": {"here": 4, "changed": 0, "missing": 0}, "here_only": 1}
    assert WHERE.zones(s)["state"]["text"] == "● 1 change here, not sent"
    assert WHERE.zones({**s, "here_only": 0})["state"]["text"] == "● Aligned"


def test_replace_is_only_for_the_object_of_the_version_in_use():
    g, m = _measured()
    RS.drop_tombstoned(g, RS.tombstones(m["doc"])[ROOM])
    us2_001 = {"em_resource_id": m["v2"], "em_rm_node_id": m["shape"],
               "em_asset_sha256": V2_BYTES}
    assert not GOV.bound_to(g, m["v1"], us2_001)
    assert GOV.bound_to(g, m["v1"], {"em_resource_id": m["v1"], "em_rm_node_id": m["shape"],
                                     "em_asset_sha256": V1_BYTES})
    # the double of the morning has the bytes in use: it is the same geometry
    assert GOV.bound_to(g, m["v1"], {"em_resource_id": m["bea"], "em_asset_sha256": V1_BYTES})
    # «US 2» bound to the LOD2 datablock: not US 2's object, and it goes back
    us2 = {"em_resource_id": m["lod2"], "em_rm_node_id": m["shape"]}
    assert not GOV.bound_to(g, m["v1"], us2)
    assert GOV.rebind_target(g, us2) == m["v1"]
    assert GOV.rebind_target(g, us2_001) == ""          # its own chain: not mis-bound


def test_a_glb_is_never_a_revision_of_a_datablock():
    g, m = _measured()
    spec = {"path": "US 2.glb", "url": "u", "checksum": "sha256:" + "77" * 32}
    with pytest.raises(ValueError, match="model in this .blend"):
        GOV.revise_and_cite(g, "ME_EST_bk_LOD2_model_res_blend", spec)
    with pytest.raises(ValueError):
        GOV.write_bytes(g, m["lod2"], spec)
    # its name: the object and what it is, never «Blend datablock for …»
    assert GOV.display_name(g, m["lod2"]) == "ME_EST_bk_LOD2 — model in this .blend"
    # ✕ where the room has its bytes (2f69 went to the store), not on a
    # datablock that only lives in the .blend
    assert GOV.withdrawable(g, m["lod2"])
    from s3dgraphy import api
    api.add_resource(g, resource_id="X_model_res_blend", name="Blend datablock for X",
                     kind="3d_model", tier="master", packaging="datablock",
                     files=[{"url": "blend://a.blend#Object/X"}])
    assert not GOV.withdrawable(g, "X_model_res_blend")
    assert GOV.withdrawable(g, m["v1"])


def test_after_use_the_card_stays_on_its_resource_or_on_none():
    rows = [{"id": "lod2", "head": "lod2"}, {"id": "v1", "head": "v2"}]
    assert FL.kept_index(rows, "v2", "v2") == 1          # «Use» changed the row's id
    assert FL.kept_index(rows, "gone", "gone") == -1     # never row 0 instead
    assert FL.kept_index(rows, "", "") == 0
    assert FL.kept_index([], "", "") == -1


# ── the node: one row, whatever the addresses ───────────────────────────────

def test_the_three_addresses_of_one_node_are_one_row():
    found = {"local": [{"url": "http://localhost:8000", "reachable": True, "version": "1.6.0.dev17"},
                       {"url": NODE, "reachable": True, "version": "1.6.0.dev17"}],
             "lan": [], "saved": [{"url": "http://macbook-pro-di-emanuel.local:8000",
                                   "reachable": True, "version": "1.6.0.dev17"}]}
    said = {"http://localhost:8000": NODE, NODE: NODE,
            "http://macbook-pro-di-emanuel.local:8000": NODE}
    idents = {u: NC.identity_of(u, fetch=lambda url, t: {"public_base": said[url[:-len("/v1/node")]]})
              for u in said}
    rows = NC.one_row_per_node(found, idents, in_use=NODE,
                               saved=["http://macbook-pro-di-emanuel.local:8000"])
    assert len(rows) == 1
    row = rows[0]
    assert row["url"] == NODE and row["in_use"] and row["saved"]
    assert set(row["addresses"]) == set(said)
    tip = NC.advice(rows, personal_on=False)
    assert tip == {"sentence": "", "turn_on": False}    # no «there is a node…», no «Turn on…»
    # in use through another of its addresses: the same row
    assert NC.one_row_per_node(found, idents, in_use="http://localhost:8000")[0]["in_use"]


def test_a_node_that_says_no_identity_is_its_address():
    NC.IDENTITY.clear()
    assert NC.identity_of("http://x:8000", fetch=lambda url, t: {}) == ""
    rows = NC.one_row_per_node({"saved": [{"url": "http://x:8000", "reachable": False}]},
                               {"http://x:8000": ""})
    assert [r["url"] for r in rows] == ["http://x:8000"] and not rows[0]["in_use"]
    tip = NC.advice(rows, personal_on=False)
    assert tip["turn_on"] and tip["sentence"].startswith("No node found")


def test_where_you_are_is_the_one_place_marked():
    rows = WHERE.place_rows({"place": "room", "room_title": "Tavolo · prova multi-client"})
    assert [r["now"] for r in rows] == [False, False, True]
    assert rows[2]["label"] == "In the room Tavolo · prova multi-client"
    assert [r["now"] for r in WHERE.place_rows({"place": "here"})] == [True, False, False]


def test_a_finished_sign_in_is_not_waiting():
    s = {"place": "room", "connected": True, "signin_waiting": True, "members": 1}
    assert WHERE.zones(s)["message"]["text"] == ""
    assert WHERE.zones({"place": "here", "signin_waiting": True})["message"]["text"] == \
        "Waiting for the browser…"


# ── Files, Project storage ──────────────────────────────────────────────────

def test_the_head_counts_the_rows():
    rows = [{"state": "both"}, {"state": "both"}, {"state": "on_disk"}, {"state": "on_node"},
            {"state": "withdrawn"}]
    c = FL.row_counts(rows)
    assert FL.summary_line(c, in_room=True) == "4 files · 1 only on the node · 1 only here"


def test_a_cached_copy_is_not_where_a_person_keeps_it():
    assert FL.in_cache("/var/folders/xy/T/em/abc.glb")
    assert FL.in_cache("/Users/x/Library/Caches/em_cache/files/ab/abc.glb")
    assert not FL.in_cache("/Users/x/Projects/Templu/DosCo/US2.glb")


def test_no_bucket_is_grey_a_difference_is_red():
    assert FL.bucket_configured({}) is False
    said = FL.bucket_todo(False, {}, True, configured=False)
    assert said == "No bucket" and not FL.bucket_alert(said)
    assert not FL.bucket_alert(FL.bucket_todo(False, {}, True))
    assert FL.bucket_alert(FL.bucket_todo(True, {"a": {"state": "differ"}}))


# ── the sources ─────────────────────────────────────────────────────────────

def _src(rel):
    return (_REPO / rel).read_text(encoding="utf-8")


def test_one_open_in_emstudio_desktop_first():
    import glob
    ids = []
    for path in glob.glob(str(_REPO / "**" / "*.py"), recursive=True):
        if any(x in path for x in ("/_dead_code/", "/tests/", "/build/")):
            continue
        text = pathlib.Path(path).read_text(errors="replace")
        ids += re.findall(r'bl_idname\s*=\s*"(em\.(?:open_in_emstudio|room_open_elsewhere))"', text)
    assert ids == ["em.open_in_emstudio"]
    p = OE.plan(sidecar_clients=0, room={"base_url": NODE, "room_id": ROOM}, desktop=False,
                web=f"{NODE}/studio/?room={ROOM}")
    assert p["way"] == "web"


def test_no_heriverse_hexagon_in_the_data_tree():
    for rel in ("em_setup/graph_tree.py", "em_setup/ui.py"):
        code = re.sub(r"#.*", "", _src(rel))
        assert "em_publish" not in code and 'prop(row, "is_publishable"' not in code, rel
    # in a room the bar is the ▾ alone
    tree = _src("em_setup/graph_tree.py")
    bar = tree[tree.index("def draw_toolbar"):tree.index("class EM_MT_graph_more")]
    assert bar.index("if in_room()") < bar.index('"em_tools.add_file"')


def test_no_window_opens_another_from_inside_it():
    """The steps of «Where you work» are a property of one window: a step's
    draw never calls an operator that opens a window of its own."""
    src = _src("sync_manager/windows.py")
    steps = src[src.index("def _back"):src.index("class EM_OT_where_change")]
    for opener in ('"em.node_choose"', '"em.room_enter"', '"em.where_change"'):
        inside = re.findall(r"operator\(" + re.escape(opener), steps)
        # EM ▸ Mode (outside the window) may open it: once, behind `window`
        assert len(inside) <= (1 if opener != '"em.node_choose"' else 0), opener
    assert 'prop_enum(wm, "em_where_step", STEP_NODE' in steps
    assert "‹ Back" in steps
    assert "invoke_props_dialog" not in steps


def test_a_datablock_is_not_owed_to_the_scene():
    """2f69bffb (the LOD2 datablock's revision, resident by mistake) would
    have come back to the scene as one more object: a model that lives in
    the .blend is not downloaded into it."""
    g, m = _measured()
    RS.drop_tombstoned(g, RS.tombstones(m["doc"])[ROOM])
    assert m["lod2"] not in _owed(g)
