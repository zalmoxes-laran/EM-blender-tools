"""MICRO-BLEND-OFFICINA-2 (31 Oct 2026) · EM Tools' half, bpy-free: detail on
request (the area of a selection, the cache, the document a cache file
cites), the lease's decision, the selection's ids, the master's folder and
the manual level agreeing with s3Dgraphy's."""

import os
import pathlib
import sys
import types

import pytest

_REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "sync_manager"))

import blend_detail as BD  # noqa: E402
import blend_lease as BL  # noqa: E402
import blend_officina as BO  # noqa: E402
import selection_ids as SI  # noqa: E402

blend_room = pytest.importorskip("s3dgraphy.resources.blend_room",
                                 reason="s3dgraphy < 1.6.0.dev79 (no blend_room)")


def test_the_area_of_a_selection():
    boxes = [[(0, 0, 0), (1, 2, 3)], [(-1, 5, 1), (0, 6, 2)]]
    assert BD.area_from_boxes(boxes) == [-1, 0, 0, 1, 6, 3]
    assert BD.area_from_boxes(boxes, pad=0.5) == [-1.5, -0.5, -0.5, 1.5, 6.5, 3.5]
    assert BD.area_from_boxes([]) is None


def test_the_cache_and_the_document_it_cites():
    p = "/p/T/EM/em_cache/local/detail/abc123/Data_a.gltf"
    assert BD.is_cache_path(p) and not BD.is_cache_path("/p/T/RB/cesium/TempluMare.3tz")
    assert BD.cache_key_of_path(p) == "abc123"
    doc = types.SimpleNamespace(node_type="document", node_id="D.12",
                                data={"detail_recipes": [{"key": "abc123"}]})
    other = types.SimpleNamespace(node_type="document", node_id="D.13", data={})
    graph = types.SimpleNamespace(nodes=[other, doc], edges=[])
    assert BD.document_for_cache_path(graph, p) is doc
    assert BD.document_for_cache_path(graph, "/p/T/x.obj") is None


def test_the_resource_and_document_of_a_tileset(tmp_path):
    (tmp_path / "RB" / "cesium" / "TM").mkdir(parents=True)
    em = str(tmp_path / "EM")
    res = types.SimpleNamespace(node_type="resource", node_id="r1", url="../RB/cesium/TM", data={})
    doc = types.SimpleNamespace(node_type="document", node_id="D.01", url="", data={})
    edge = types.SimpleNamespace(edge_source="D.01", edge_target="r1", edge_type="has_linked_resource")
    nodes = {"r1": res, "D.01": doc}
    graph = types.SimpleNamespace(nodes=[res, doc], edges=[edge], find_node_by_id=nodes.get)
    got = BD.resource_for_path(graph, str(tmp_path / "RB" / "cesium" / "TM" / "tileset.json"), em)
    assert got is res and BD.document_of(graph, got) is doc


def test_the_state_survives_a_bad_value():
    assert BD.read_state("not json")["cut"] == []
    assert BD.read_state('{"kind": "tileset", "cut": ["a"]}')["cut"] == ["a"]
    lines = BD.estimate_lines({"pieces": 2, "triangles": 1000, "texture_px": 2_000_000, "ram_mb": 12.0,
                               "file_bytes": 1048576, "unknown": 1})
    assert "1,000 triangles" in lines[0] and "12 MB in Blender" in lines[1] and "not measured" in lines[2]


def test_the_lease_decision():
    now = 1000.0
    mine = blend_room.lease_record("SB/GT.blend", person="ed", host="mac", now=now)
    other = blend_room.lease_record("SB/GT.blend", person="el", host="pc", now=now)
    kw = dict(key="SB/GT.blend", person="ed", host="mac", supported=True, joined=True, now=now + 10)
    assert BL.decide(leases=[], **kw)["send"] == "take"
    got = BL.decide(leases=[mine], **kw)
    assert got["mode"] == "mine" and got["send"] == "renew" and got["say"].startswith("aperto da ed su mac")
    ro = BL.decide(leases=[other], **kw)
    assert ro["mode"] == "readonly" and ro["send"] is None and "nuova versione" in ro["say"]
    assert BL.decide(leases=[other], **dict(kw, now=now + 16 * 60))["send"] == "take"
    assert BL.decide(leases=[], **dict(kw, supported=False))["say"] == BL.NO_ROOM_LEASES
    assert BL.decide(leases=[], **dict(kw, joined=False))["mode"] == "local"


def test_selection_ids_of_any_object():
    a = {"em_rm_node_id": "rm1", "em_asset_id": "as1"}
    assert SI.ids_of_props(a) == ["rm1", "as1"]
    assert SI.first_known(a, lambda i: i == "as1") == "as1"
    objs = [{"name": "Architrave", "em_rm_node_id": "rm1"}, {"name": "Walls", "em_version_id": "v1"},
            {"name": "Camera"}]
    assert SI.names_for_ids(objs, ["v1", "rm1"]) == ["Architrave", "Walls"]
    assert SI.ID_PROPS == blend_room.ID_PROPS


def test_master_place_and_manual_level_agree_with_s3dgraphy(tmp_path):
    (tmp_path / "SB").mkdir()
    em = str(tmp_path / "EM")
    for cont in ("SB", "sb", "Reconstruction II AC"):
        assert BO.master_place(project_root=str(tmp_path), em_folder=em, container=cont, branch="SB") == \
            blend_room.master_place(project_root=str(tmp_path), em_folder=em, container=cont, branch="SB")
    assert BO.master_place(project_root=str(tmp_path), em_folder=em, container="SB")["folder"] == \
        os.path.join(str(tmp_path), "SB", "master")
    taken = ["manual-2026-10-31", "lod1", "manual-2026-10-31-2"]
    assert BO.manual_level(taken, "2026-10-31") == blend_room.manual_level(taken, "2026-10-31") \
        == "manual-2026-10-31-3"
    assert BO.versions_place(os.path.join(em, "_master", "X")) == os.path.join(em, "_master", "X", "versions")


def test_a_cache_file_is_never_a_document():
    sys.path.insert(0, str(_REPO))
    import importlib.util
    spec = importlib.util.spec_from_file_location("property_documentation", _REPO / "property_documentation.py")
    PD = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(PD)
    doc = types.SimpleNamespace(node_id="d", name="D.1", url="EM/em_cache/local/detail/k/crop.gltf")
    prop = types.SimpleNamespace(node_id="p")
    with pytest.raises(ValueError, match="cite the document"):
        PD.document_through_extractor(types.SimpleNamespace(nodes=[], edges=[]), prop, doc)


def test_emstudio_says_read_only_when_it_opens_a_held_blend():
    told_readonly = BL.told_readonly
    held = {"key": "SB/GT.blend", "person": "orcid:EL", "display": "Elisa", "host": "pc-lab",
            "since": 1000.0, "renewed": 1000.0, "person_here": "orcid:ED"}
    import json
    assert told_readonly(json.dumps(held))["display"] == "Elisa"
    assert told_readonly(held)["person_here"] == "orcid:ED"
    assert told_readonly("") is None and told_readonly("not json") is None and told_readonly("{}") is None
