"""MICRO-RM-WEB (13 Oct 2026), measured without bpy on the room as it was
(`tavolo-2026-10-12`, snapshot of 18:26) and the RM E.D. pressed «Upload» on
at 19:30: «ME_EST_bk_LOD0 — model in this .blend».

A · «Upload» sent the whole TempluMare_2021.blend (539 181 434 bytes,
``application/x-blender``) and wrote nothing in the graph. The rule: a model
in the .blend is never uploaded as its .blend — «Upload» refuses, without
sending a byte, and says «Send a web version».

B · «Send a web version» makes the glb by the way of «Prepare for a use…»
(use ``web``), sends it, and the graph gets a DISTRIBUTION version of the
asset — resident, with its digest, ``model/gltf-binary`` — made from the
datablock by its ``lod_generation`` step, never ``was_revision_of`` it; it
goes to the room closed over what the room holds (the RM, its epoch, its
datablock with it), and `geometry_summary` finds it resident under the RM.

C · «Upload» of any other file RECORDS what it sent: checksum, residency,
the url on the room's one base (the disk path kept as an address), as an
``update_field`` the room hears.
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

pytest.importorskip("s3dgraphy.geometry.store_backed")

from s3dgraphy import api  # noqa: E402
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
_pkg("_rw", "")
_pkg("_rw.sync_bridge", "sync_bridge")
_load("_rw.sync_bridge.wire", "sync_bridge/wire.py")
_load("_rw.sync_bridge.ws_client", "sync_bridge/ws_client.py")
_pkg("_rw.sync_manager", "sync_manager")
_load("_rw.sync_manager.room", "sync_manager/room.py")
RS = _load("_rw.sync_manager.room_session", "sync_manager/room_session.py")
SS = _load("_rw.sync_manager.scene_sync", "sync_manager/scene_sync.py")
GOV = _load("resource_governance", "resource_governance.py")
WV = _load("_rw.sync_manager.web_version", "sync_manager/web_version.py")

ROOM = "tavolo-2026-10-12"
FIXTURE = _REPO / "tests" / "fixtures" / "tavolo_2026-10-13_1826.room.json"
BASE = "https://em.localhost:8443/em"
RM = "ME_EST_bk_LOD0_model"
BLEND = "ME_EST_bk_LOD0_model_res_blend"
EPOCH = "49f50053-5472-4a2f-8759-beb366f14ded"
LOCATOR = ("blend://../Library/CloudStorage/OneDrive-CNR/Extended%20Matrix/EM_CaseStudies/"
           "01_EM_Tempio%20Grande%20v2/RB/TempluMare_2021.blend#Object/ME_EST_bk_LOD0")
WHOLE_BLEND = "sha256:7fb52213" + "0" * 56          # what was sent at 19:30
GLB = "sha256:" + "ab" * 32


def _doc():
    return json.loads(FIXTURE.read_text())


def _graph():
    """The room's graph and, beside it, what only this Blender has: the RM
    of ME_EST_bk_LOD0, its datablock, its epoch."""
    path = tempfile.mktemp(suffix=".em.json")
    pathlib.Path(path).write_text(json.dumps(RS.live_view(_doc())))
    g = next(iter(load_container_file(path)[0].graphs.values()))
    g.add_node(RepresentationModelNode(RM, name="Model for ME_EST_bk_LOD0", type="RM",
                                       description=""))
    api.add_resource(g, resource_id=BLEND, name="Blend datablock for ME_EST_bk_LOD0",
                     kind="3d_model", tier="master", packaging="datablock",
                     files=[{"url": LOCATOR}])
    g.add_edge(f"{RM}_has_linked_resource_{BLEND}", RM, BLEND, "has_linked_resource")
    g.add_edge(f"{EPOCH}_has_representation_model_{RM}", EPOCH, RM,
               "has_representation_model")
    return g


def _emjson(g):
    nodes = []
    for n in g.nodes:
        data = getattr(n, "data", None)
        nodes.append({"id": n.node_id, "node_type": getattr(n, "node_type", ""),
                      "name": getattr(n, "name", ""),
                      "data": copy.deepcopy(dict(data)) if isinstance(data, dict) else {}})
    edges = [{"id": e.edge_id, "source": e.edge_source, "target": e.edge_target,
              "edge_type": e.edge_type} for e in g.edges]
    return {"nodes": nodes, "edges": edges}


def _applied(holds, ops):
    h = copy.deepcopy(holds)
    for op in ops:
        RS.note_op(h, op)
    return h


def _dangling(holds):
    return {eid for eid, (s, _t, d) in holds["edges"].items()
            if s not in holds["nodes"] or d not in holds["nodes"]}


def _store(digest):
    return GOV.store_url(BASE, ROOM, digest)


def _prepare(g, calls):
    """«Prepare for a use…» (web) without bpy: the version as
    `add_version_from_mesh` writes it, a glb in the cache."""
    def prepare(name):
        calls.append(name)
        files = [{"path": f"{name}·lod0-web.glb", "url": f"/tmp/em_cache/{name}·lod0-web.glb",
                  "checksum": GLB, "size_bytes": 2_400_000, "media_type": WV.GLB_MEDIA}]
        out = api.add_version(g, BLEND, use=["web"], files=files, residency="resident",
                              primitives={"vertices": 50_000, "faces": 98_000,
                                          "triangles": 98_000},
                              technique="glTF export · Draco", tool="EM Tools")
        return {**out, "files": files}
    return prepare


# ── A · «Upload» never sends a whole .blend ─────────────────────────────────

def test_a_model_in_the_blend_is_a_datablock_row():
    g = _graph()
    assert WV.is_datablock(g, BLEND)
    assert WV.object_of(g, BLEND) == "ME_EST_bk_LOD0"
    assert GOV.display_name(g, BLEND) == "ME_EST_bk_LOD0 — model in this .blend"
    assert WV.rm_of(g, BLEND) == RM


def test_upload_on_a_datablock_refuses_without_sending():
    g = _graph()
    before = _emjson(g)
    sent = []
    row = {"id": BLEND, "state": "on_disk", "sha256": WHOLE_BLEND,
           "path": "/Users/x/EM_CaseStudies/RB/TempluMare_2021.blend"}
    out = WV.upload_row(g, row, upload=lambda r: sent.append(r) or {}, store_url=_store)
    assert out["ok"] is False and sent == []
    assert "Send a web version" in out["error"] and "Archive this .blend" in out["error"]
    assert "ME_EST_bk_LOD0" in out["error"]
    assert _emjson(g) == before                       # the graph untouched


# ── B · «Send a web version» ────────────────────────────────────────────────

def test_send_a_web_version_makes_a_distribution_version_of_the_datablock():
    g = _graph()
    calls, sent = [], []
    out = WV.send_web_version(g, BLEND, prepare=_prepare(g, calls), store_url=_store,
                              upload=lambda f: sent.append(f) or {"sha256": f["checksum"][7:]})
    assert out["ok"], out
    assert calls == ["ME_EST_bk_LOD0"] and [f["checksum"] for f in sent] == [GLB]
    vid = out["version_id"]
    v = g.find_node_by_id(vid).data
    assert v["tier"] == "distribution" and v["residency"] == "resident"
    assert v["checksum"] == GLB and v["media_type"] == "model/gltf-binary"
    assert v["use"] == ["web"]
    assert v["url"] == _store(GLB)
    # the cache copy stays an address of the same bytes
    assert [a["locator"] for a in v["addresses"]] == [_store(GLB),
                                                      "/tmp/em_cache/ME_EST_bk_LOD0·lod0-web.glb"]
    # a version of the asset, from the master — not a revision of it
    assert api.asset_of(g, vid) == BLEND
    assert [e["id"] for e in api.versions_of(g, BLEND) if not e["master"]] == [vid]
    assert not any(e.edge_type == "was_revision_of" and e.edge_source == vid for e in g.edges)
    assert GOV.chain_of(g, BLEND) == [BLEND]
    # the RM still cites its datablock, and reaches the version through it
    assert [c["source"] for c in GOV.citing(g, BLEND)] == [RM]
    from s3dgraphy.resources.versions import inherited_links
    assert [f["id"] for f in inherited_links(g, vid)["facets"]] == [RM]
    assert out["rm_id"] == RM
    # the version is never taken for the datablock, whatever its name
    # (`add_version` names it «Blend datablock for ME_EST_bk_LOD0 lod0»)
    assert not WV.is_datablock(g, vid)
    assert "model in this .blend" not in GOV.display_name(g, vid)
    assert WV.upload_refusal(g, vid) == ""


def test_geometry_summary_gives_the_web_version_resident_under_the_rm():
    g = _graph()
    before = api.geometry_summary(g)
    assert all(r["resource_id"] != BLEND for r in before["resident"])
    assert BLEND in {r["resource_id"] for r in before["elsewhere"]}
    out = WV.send_web_version(g, BLEND, prepare=_prepare(g, []), store_url=_store,
                              upload=lambda f: {"sha256": f["checksum"]})
    rec = [r for r in api.geometry_summary(g)["resident"] if r["resource_id"] == out["version_id"]]
    assert len(rec) == 1
    assert rec[0]["node_id"] == RM and rec[0]["checksum"] == GLB
    assert rec[0]["kind"] == "RM" and rec[0]["url"] == _store(GLB)
    assert EPOCH in {b["id"] for b in rec[0]["bind"]}


def test_the_web_version_goes_to_the_room_closed_with_its_rm():
    g = _graph()
    holds = RS.room_holds(_doc(), ROOM)
    assert RM not in holds["nodes"] and BLEND not in holds["nodes"]
    before = _emjson(g)
    out = WV.send_web_version(g, BLEND, prepare=_prepare(g, []), store_url=_store,
                              upload=lambda f: {"sha256": f["checksum"]})
    after = _emjson(g)
    closed = SS.close_over(SS.section_delta_ops(before, after), after, holds,
                           bring=[out["rm_id"]])
    room = _applied(holds, closed["ops"])
    assert {RM, BLEND, out["version_id"]} <= room["nodes"]
    assert not _dangling(room)
    assert closed["dropped"] == []
    triples = set(room["edges"].values())
    assert (EPOCH, "has_representation_model", RM) in triples
    assert (RM, "has_linked_resource", BLEND) in triples
    assert not any(t == (out["version_id"], "was_revision_of", BLEND) for t in triples)
    # the version reaches the master in the room: its lod_generation step
    step = [o for o in closed["ops"] if o["op"] == "add_node"
            and o["id"] not in (RM, BLEND, out["version_id"])]
    assert step, "the lod_generation step goes with the version"
    ends = {(o["source"], o["target"]) for o in closed["ops"] if o["op"] == "add_edge"}
    assert any(BLEND in pair for pair in ends) and any(out["version_id"] in pair for pair in ends)
    # the version arrives resident, with its digest and its store url
    v = next(o["node"] for o in closed["ops"]
             if o["op"] == "add_node" and o["id"] == out["version_id"])
    assert v["data"]["checksum"] == GLB and v["data"]["residency"] == "resident"
    assert v["data"]["url"] == _store(GLB)


def test_send_a_web_version_of_a_file_that_is_not_in_the_blend_refuses():
    g = _graph()
    api.add_resource(g, resource_id="D.32", name="D.32.jpg", kind="image",
                     files=[{"url": "/DosCo/D.32.jpg", "checksum": "sha256:" + "cd" * 32}])
    called = []
    out = WV.send_web_version(g, "D.32", prepare=lambda n: called.append(n) or {},
                              upload=lambda f: {}, store_url=_store)
    assert out["ok"] is False and called == []


def test_a_version_of_another_model_is_refused():
    g = _graph()
    api.add_resource(g, resource_id="OTHER", name="other", kind="3d_model", tier="master",
                     files=[{"url": "/x/other.glb", "checksum": "sha256:" + "ee" * 32}])

    def prepare(name):
        out = api.add_version(g, "OTHER", use=["web"], residency="resident",
                              files=[{"path": "o.glb", "url": "/tmp/o.glb", "checksum": GLB,
                                      "media_type": WV.GLB_MEDIA}])
        return {**out, "files": []}
    out = WV.send_web_version(g, BLEND, prepare=prepare, upload=lambda f: {},
                              store_url=_store)
    assert out["ok"] is False and "another model" in out["error"]


# ── C · «Upload» records what it sent ───────────────────────────────────────

def test_upload_of_a_file_records_checksum_residency_and_url_and_tells_the_room():
    g = _graph()
    api.add_resource(g, resource_id="D.32", name="D.32.jpg", kind="image",
                     files=[{"url": "/DosCo/D.32.jpg"}])
    holds = RS.room_holds(_doc(), ROOM)
    holds["nodes"].add("D.32")                       # the room has the resource
    before = _emjson(g)
    digest = "cd" * 32
    row = {"id": "D.32", "state": "on_disk", "path": "/DosCo/D.32.jpg", "sha256": None}
    out = WV.upload_row(g, row, upload=lambda r: {"sha256": digest, "already": False},
                        store_url=_store)
    assert out["ok"] and out["recorded"] and out["digest"] == "sha256:" + digest
    d = g.find_node_by_id("D.32").data
    assert d["checksum"] == "sha256:" + digest and d["residency"] == "resident"
    assert d["url"] == _store("sha256:" + digest)
    assert [a["locator"] for a in d["addresses"]] == [d["url"], "/DosCo/D.32.jpg"]
    after = _emjson(g)
    closed = SS.close_over(SS.section_delta_ops(before, after), after, holds, bring=["D.32"])
    fields = {(o["node_id"], o["field"]) for o in closed["ops"] if o["op"] == "update_field"}
    assert {("D.32", "data.checksum"), ("D.32", "data.residency"),
            ("D.32", "data.url")} <= fields
    assert not any(o["op"] == "add_node" for o in closed["ops"])


def test_upload_of_a_file_the_room_lacks_brings_it_whole():
    g = _graph()
    api.add_resource(g, resource_id="D.33", name="D.33.jpg", kind="image",
                     files=[{"url": "/DosCo/D.33.jpg"}])
    holds = RS.room_holds(_doc(), ROOM)
    before = _emjson(g)
    WV.upload_row(g, {"id": "D.33", "path": "/DosCo/D.33.jpg"},
                  upload=lambda r: {"sha256": "ef" * 32}, store_url=_store)
    after = _emjson(g)
    closed = SS.close_over(SS.section_delta_ops(before, after), after, holds, bring=["D.33"])
    added = [o for o in closed["ops"] if o["op"] == "add_node" and o["id"] == "D.33"]
    assert added and added[0]["node"]["data"]["residency"] == "resident"


def test_a_resource_is_not_resident_without_its_digest():
    g = _graph()
    api.add_resource(g, resource_id="X", name="x", kind="image", files=[{"url": "/x.jpg"}])
    with pytest.raises(ValueError):
        WV.point_at_store(g, "X", _store("sha256:" + "11" * 32), "")
