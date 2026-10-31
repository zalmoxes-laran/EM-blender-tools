"""MICRO-BLEND-OFFICINA-3 (31 Oct 2026) · EM Tools' half, bpy-free:
«Consolidate for…» in the Publication Deck (s3Dgraphy's ``consolidate`` on the
Deck's published models, the gestures of a row), «Compose a .blend from the
graph» (the files fetched from the room by sha256, where the file goes), the
before/after rows of «Check against the graph», the detail box (the ground
plane, the box of a rectangle, the area «More detail here» uses) and the
document of a tileset through ``graph_compose.document_of_resource``."""

import hashlib
import importlib.util
import pathlib
import sys
import types

import pytest

_REPO = pathlib.Path(__file__).resolve().parent.parent
_CHECKOUT = _REPO.parent / "s3Dgraphy" / "src"
if _CHECKOUT.is_dir():
    sys.path.insert(0, str(_CHECKOUT))
sys.path.insert(0, str(_REPO / "sync_manager"))

import blend_compose as BC  # noqa: E402
import blend_detail as BD  # noqa: E402
import blend_officina as BO  # noqa: E402

_spec = importlib.util.spec_from_file_location("_emtools_publication_heriverse_3",
                                               _REPO / "publication_heriverse.py")
PH = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = PH
_spec.loader.exec_module(PH)


def _sha(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


# ── «Consolidate for…» ───────────────────────────────────────────────────────

def _study():
    api = pytest.importorskip("s3dgraphy.api")
    from s3dgraphy.graph import Graph
    from s3dgraphy.nodes.representation_node import RepresentationModelNode
    g = Graph("templu")
    for name in ("podio", "muro"):
        api.add_resource(g, name=name, kind="3d_model", tier="master", files=[{
            "path": f"{name}.glb", "url": f"{name}.glb", "checksum": _sha(name.encode())}],
            resource_id=name)
        g.add_node(RepresentationModelNode(node_id=f"rm_{name}", name=name.upper()))
        g.add_edge(f"rm_{name}_r", f"rm_{name}", name, "has_linked_resource")
    heri = api.add_version(g, "podio", use=list(PH.PACKAGE_USES), level="heriverse", files=[{
        "path": "podio@heriverse.glb", "url": "versions/podio@heriverse.glb",
        "checksum": _sha(b"podio heriverse")}])
    base = api.add_version(g, "muro", use=["mobile_ar"], level="mobile", files=[{
        "path": "muro@mobile.glb", "url": "versions/muro@mobile.glb",
        "checksum": _sha(b"muro mobile")}])
    return g, heri, base


def test_consolidate_for_heriverse_on_the_decks_models():
    pytest.importorskip("s3dgraphy.resources.consolidate")
    g, heri, base = _study()
    got = PH.consolidation(g, [("rm_podio", "PODIO"), ("rm_muro", "MURO"), "rm_ghost"],
                           states={heri["version_id"]: "on_disk"}, in_room=True)
    assert got["available"] and got["counts"]["rms"] == 2
    rows = {r["id"]: r for r in got["rows"]}
    podio, muro = rows["rm_podio"], rows["rm_muro"]
    assert podio["object"] == "PODIO" and podio["base"] is None and podio["status"] == "necessary"
    assert podio["best"]["id"] == heri["version_id"]
    acts = PH.row_actions(podio)
    prep = next(a for a in acts if a["kind"] == "prepare")
    assert prep["profile"] == "mobile_webxr" and prep["uses"] == ("mobile_ar",) and prep["object"] == "PODIO"
    up = next(a for a in acts if a["kind"] == "upload")
    assert up["resource_id"] == heri["version_id"]
    assert muro["base"]["id"] == base["version_id"]
    assert "base mobile" in PH.consolidation_row_line(muro) or "base" in PH.consolidation_row_line(muro)
    assert PH.consolidation_row_line(podio).startswith("✗ PODIO")
    assert any("mobile webXR" in line for line in PH.totals_lines(got))


def test_without_consolidate_the_deck_says_it_and_keeps_the_rule(monkeypatch):
    monkeypatch.setattr(PH, "consolidate_function", lambda: None)
    said = PH.consolidation(None, ["x"])
    assert said["available"] is False and "dev80" in said["note"]
    # the rule's plan (plan_for) is untouched: the Deck draws it under the line
    fake = types.SimpleNamespace(find_node_by_id=lambda i: None)
    got = PH.consolidation(fake, ["x"], fn=lambda *a, **k: {"rows": [], "counts": {}, "totals": {},
                                                            "say_it": ""})
    assert got["available"] and got["rows"] == []


def test_the_uses_of_prepare_and_the_merge_of_graphs():
    assert PH.prepare_uses("mobile_webxr") == ("mobile_ar",)
    assert PH.prepare_uses("webxr", "heriverse") == tuple(PH.PACKAGE_USES)
    assert PH.prepare_uses("webxr", "aton") == tuple(PH.PACKAGE_USES)
    one = {"available": True, "rows": [{"id": "a"}], "counts": {"rms": 1, "status": {"ok": 1}},
           "totals": {"platform": {"say_it": "webXR: …", "ok": True}}, "say_it": "A", "in_room": False}
    two = {"available": True, "rows": [{"id": "b"}], "counts": {"rms": 2, "status": {"ok": 1, "necessary": 1}},
           "totals": {"platform": {"say_it": "webXR: …", "ok": False}}, "say_it": "B", "in_room": False}
    m = PH.merge_consolidations([("g1", one), ("g2", two)])
    assert [r["graph_id"] for r in m["rows"]] == ["g1", "g2"]
    assert m["counts"]["rms"] == 3 and m["counts"]["status"] == {"ok": 2, "necessary": 1}
    assert PH.totals_lines(m) == ["✔ webXR: …", "✗ webXR: …"]
    assert PH.merge_consolidations([("g", {"available": False, "note": "n"})])["note"] == "n"


# ── «Compose a .blend from the graph» ────────────────────────────────────────

def test_the_files_of_the_room_are_fetched_by_sha256(tmp_path):
    good, bad = b"glb bytes", b"other"
    hx = hashlib.sha256(good).hexdigest()
    asked = []

    def get(ref):
        asked.append(ref)
        if ref == f"sha256:{hx}":
            return good, "model/gltf-binary"
        if ref.endswith("1" * 64):
            return bad, "x"
        raise RuntimeError("the room has no asset (404)")

    to = tmp_path / "em_cache" / "files" / hx[:2] / f"{hx}.glb"
    plan = [{"sha256": f"sha256:{hx}", "to": str(to)}, {"sha256": f"sha256:{hx}", "to": str(to)},
            {"sha256": "sha256:" + "1" * 64, "to": str(tmp_path / "x.glb")},
            {"sha256": "sha256:" + "2" * 64, "to": str(tmp_path / "y.glb")},
            {"sha256": "nope", "to": str(tmp_path / "z.glb")}]
    got = BC.fetch_files(plan, get)
    assert got["fetched"] == 1 and to.read_bytes() == good
    assert len(got["failed"]) == 3 and any("not the graph's" in f for f in got["failed"])
    assert asked.count(f"sha256:{hx}") == 1
    again = BC.fetch_files(plan[:1], get)
    assert again == {"fetched": 0, "kept": 1, "failed": []}


def test_where_a_composed_blend_goes(tmp_path):
    em = tmp_path / "EM" / "TempluMare_v6_optimized.em.json"
    em.parent.mkdir()
    out = BC.graph_out(str(em), "modelling")
    assert out == str(tmp_path / "EM" / "TempluMare_v6_optimized__modelling.blend")
    pathlib.Path(out).write_bytes(b"")
    assert BC.graph_out(str(em), "modelling").endswith("__modelling-2.blend")
    assert BC.sha_hex("sha256:" + "A" * 64) == "a" * 64 and BC.sha_hex("x") == ""
    assert set(BC.TAG_KEYS) == {"em_rm_node_id", "em_belong_id", "EM_ep_belong_ob", "em_asset_id",
                                "em_version_id", "em_resource_id", "em_level", "em_asset_sha256"}
    G = pytest.importorskip("s3dgraphy.resources.graph_compose")
    assert tuple(BC.TAG_KEYS) == tuple(G.TAG_KEYS)
    assert tuple(k for k, _l, _t in BC.WORK_PROFILES) == tuple(G.WORK_PROFILES)


# ── «Check against the graph»: before / after ────────────────────────────────

def test_the_before_after_rows():
    ba = [{"name": "Architrave", "state": "newer",
           "here": {"level": "lod1", "made_say": "EM Tools, 2026-10-05 10:00"},
           "latest": {"level": "manual-2026-10-31", "made_say": "Elisa, 2026-10-31 12:30"},
           "action": {"kind": "update", "resource_id": "v2"}, "say_it": "nel grafo c'è …"},
          {"name": "Podio", "state": "aligned", "here": {"level": "lod1", "made_say": "x"},
           "latest": {"level": "lod1"}, "action": {}, "say_it": "ultima"},
          {"name": "Ghost", "state": "unknown", "here": None, "latest": None, "action": {}}]
    rows = BO.ba_rows(ba)
    assert [r["name"] for r in rows] == ["Architrave", "Podio"]
    a, p = rows
    assert a["sign"] == "↓" and a["tick"] and a["action"] == "update_version" and a["resource_id"] == "v2"
    assert "lod1 (EM Tools, 2026-10-05 10:00) → in the graph manual-2026-10-31 (Elisa, 2026-10-31 12:30)" \
        in a["label"]
    assert p["sign"] == "✔" and not p["tick"] and p["actions"] == []
    assert BO.has_graph_tags({"em_rm_node_id": "x"}) and not BO.has_graph_tags({"USV": "y"})
    # another rung of the LOD chain (lod1 → lod4, made a minute apart in one
    # batch — Templu Mare) is offered, not ticked
    rung = BO.ba_rows([dict(ba[0], here={"level": "lod1"}, latest={"level": "lod4"})])[0]
    assert rung["action"] == "update_version" and not rung["tick"]
    assert BO.other_rung("LOD1", "lod4") and not BO.other_rung("lod1", "manual-2026-10-31")
    assert not BO.other_rung("lod1", "lod1")


def test_update_status_on_a_real_graph_sees_the_newer_version():
    G = pytest.importorskip("s3dgraphy.resources.graph_compose")
    g, heri, _base = _study()
    from s3dgraphy import api
    from s3dgraphy.resources.versions import versions_of
    entry = next(e for e in versions_of(g, "podio") if e["id"] == heri["version_id"])
    tags = G.graph_tags(g, "rm_podio", dict(entry, asset_id="podio"))
    assert tags["em_version_id"] == heri["version_id"] and tags["em_rm_node_id"] == "rm_podio"
    new = api.add_version(g, "podio", use=["realtime"], level="manual-2026-10-31", files=[{
        "path": "podio@manual.glb", "url": "versions/podio@manual.glb", "checksum": _sha(b"new")}])
    # two steps born in the same second are a tie: the one in the scene stays
    # (measured: «aligned»); the newer one is born later
    from s3dgraphy.resources.versions import EDGE_HAD_OUTPUT
    step = next(e.edge_source for e in g.edges
                if e.edge_type == EDGE_HAD_OUTPUT and e.edge_target == new["version_id"])
    g.find_node_by_id(step).data["created_at"] = "2099-01-01T10:00:00Z"
    rows = BO.ba_rows(G.before_after(g, [{"name": "PODIO", "props": tags}]))
    if not hasattr(G, "level_key"):        # ≤ dev80: «newer» was any version made again
        assert rows and rows[0]["state"] == "newer"
        return
    # MICRO-CONSOLIDA-2 · a version by hand for desktop realtime is ANOTHER
    # version of the one for Heriverse shown: said, not an update
    assert rows and rows[0]["name"] == "PODIO" and rows[0]["state"] == "aligned"
    assert "another version, not an update" in rows[0]["label"] and not rows[0]["tick"]
    # the file of the version shown modified after its stamp → offered, not ticked
    now = _sha(b"touched")
    ba = G.before_after(g, [{"name": "PODIO", "props": tags}], files_now={heri["version_id"]: now})
    mod = BO.ba_rows(ba)[0]
    assert mod["state"] == "modified" and mod["action"] == "register_new_version" and not mod["tick"]
    assert mod["checksum_now"].endswith(now.split(":")[-1])
    # registered as a new version: the one shown has a newer revision → ↓ Update, ticked
    got = G.register_new_version(g, heri["version_id"], checksum=now, at="2099-01-02T10:00:00Z")
    up = BO.ba_rows(G.before_after(g, [{"name": "PODIO", "props": tags}]))[0]
    assert up["state"] == "revised" and up["tick"] and up["resource_id"] == got["version_id"]


# ── the detail box ───────────────────────────────────────────────────────────

def test_the_ground_plane_and_the_box_of_a_rectangle():
    assert BD.ray_plane((0, 0, 10), (0, 0, -1), (0, 0, 2)) == [0, 0, 2]
    assert BD.ray_plane((0, 0, 10), (1, 0, 0), (0, 0, 2)) is None        # parallel
    assert BD.ray_plane((0, 0, 10), (0, 0, 1), (0, 0, 2)) is None        # behind
    hit = BD.ray_plane((0, 0, 10), (1, 1, -2), (0, 0, 490.0))
    assert hit is None
    hit = BD.ray_plane((0, 0, 500), (1, 1, -2), (0, 0, 490.0))
    assert hit == [5.0, 5.0, 490.0]
    b = BD.rect_box([(0, 0, 490), (4, 0, 490), (4, 2, 490), (0, 2, 490)], 490, 494)
    assert b == {"center": [2.0, 1.0, 492.0], "half": [2.0, 1.0, 2.0]}
    assert BD.rect_box([(1, 1, 0), (1, 1, 0)], 0, 0)["half"] == [0.05, 0.05, 0.05]
    assert BD.rect_box([None], 0, 1) is None


def test_the_area_of_a_box_and_which_area_is_used():
    rows = [[2, 0, 0, 10], [0, 1, 0, 20], [0, 0, 3, 490], [0, 0, 0, 1]]   # scale 2,1,3 at 10,20,490
    assert BD.box_area(rows) == [8, 19, 487, 12, 21, 493]
    assert BD.box_area(rows, 0.5) == [9, 19.5, 488.5, 11, 20.5, 491.5]
    assert BD.z_span([[0, 0, 490, 1, 1, 492], None, [0, 0, 489, 1, 1, 491]]) == (489, 492)
    assert BD.z_span([]) is None
    sel, last, selection = [0] * 6, [1] * 6, [2] * 6
    assert BD.pick_area(sel, last, selection) == (sel, "box")
    assert BD.pick_area(None, last, selection) == (last, "last_box")
    assert BD.pick_area(None, None, selection) == (selection, "selection")
    assert BD.pick_area(None, None, None) == (None, "")


def test_the_document_of_a_tileset_through_graph_compose(monkeypatch):
    doc = types.SimpleNamespace(node_type="document", node_id="D.01", data={})
    other = types.SimpleNamespace(node_type="document", node_id="D.99", data={})
    ts = types.SimpleNamespace(node_type="resource", node_id="tileset", data={})
    edge = types.SimpleNamespace(edge_source="D.99", edge_target="tileset", edge_type="whatever")
    graph = types.SimpleNamespace(nodes=[doc, other, ts], edges=[edge],
                                  find_node_by_id=lambda i: {"D.01": doc, "D.99": other,
                                                             "tileset": ts}.get(i))
    G = pytest.importorskip("s3dgraphy.resources.graph_compose")
    monkeypatch.setattr(G, "document_of_resource", lambda g, rid: "D.01" if rid == "tileset" else None)
    assert BD.document_for_resource(graph, ts) is doc
    monkeypatch.setattr(G, "document_of_resource", lambda g, rid: None)
    assert BD.document_for_resource(graph, ts) is other       # as before: any edge to a document
    assert BD.document_for_resource(graph, doc) is doc
    assert BD.document_for_resource(graph, None) is None
