"""MICRO EM Tools «l'alternativa del contenitore» (E.D., 17 Oct 2026) — the logic.

Outside Blender: the tilesets of the graph (how s3Dgraphy recognises one), the
name proposed, a tileset read without loading a tile (folder, .3tz, .zip, the
external tileset.json), the coverage check on the leaf tiles' boxes, the
storage (copied into the project's tree, the locator relative to the em.json),
the graph (the container is the hat, the uses on the version, «Remove the
alternative» keeps the resource) and the document the models say.

The true case: Survey2015 (10 meshes) and the 2015 survey's tileset. With a
fixture built from the true boxes of the 11 meshes (``fixtures/
templu_survey2015_boxes.json``) and, when the copy of Templu Mare is on this
disk (``TEMPLU_MARE_DIR``, default ``/tmp/spazio3/templu-mare``), with the real
tileset: TEMPLUM «more», nothing missing.
"""

import importlib.util
import json
import os
import pathlib
import sys
import zipfile

import pytest

_REPO = pathlib.Path(__file__).resolve().parent.parent
_CHECKOUT = _REPO.parent / "s3Dgraphy" / "src"
if _CHECKOUT.is_dir():
    sys.path.insert(0, str(_CHECKOUT))
sys.path.insert(0, str(_REPO))

pytest.importorskip("s3dgraphy.resources.alternatives")


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, _REPO / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


CA = _load("container_alternative", "rm_manager/container_alternative.py")
GN = _load("group_nodes_ca", "rm_manager/group_nodes.py")

BOXES = json.loads((_REPO / "tests" / "fixtures" / "templu_survey2015_boxes.json").read_text("utf-8"))
MEMBERS = {k: v for k, v in BOXES["members"].items()}
TEMPLUM = BOXES["graph_only"]["SM_OB_TEMPLUM_LOD1"]
TEMPLU = pathlib.Path(os.environ.get("TEMPLU_MARE_DIR", "/tmp/spazio3/templu-mare"))


# ── a tileset built from boxes ───────────────────────────────────────────────

def _tile(lo, hi, uri):
    c = [(lo[i] + hi[i]) / 2 for i in range(3)]
    h = [(hi[i] - lo[i]) / 2 for i in range(3)]
    box = c + [h[0], 0, 0, 0, h[1], 0, 0, 0, h[2]]
    return {"boundingVolume": {"box": box}, "geometricError": 0.0,
            "content": {"uri": uri, "boundingVolume": {"box": box}}}


def _skin(boxes, offset, n=4):
    """Leaf tiles over each box's plan (a survey is a skin): n×n tiles, the
    box's height, written in the tileset's local frame (minus ``offset``)."""
    tiles = []
    for k, (lo, hi) in enumerate(boxes):
        for i in range(n):
            for j in range(n):
                a = [lo[0] + (hi[0] - lo[0]) * i / n - offset[0],
                     lo[1] + (hi[1] - lo[1]) * j / n - offset[1], lo[2] - offset[2]]
                b = [lo[0] + (hi[0] - lo[0]) * (i + 1) / n - offset[0],
                     lo[1] + (hi[1] - lo[1]) * (j + 1) / n - offset[1], hi[2] - offset[2]]
                tiles.append(_tile(a, b, f"t{k}_{i}{j}.b3dm"))
    return tiles


def _write_tileset(folder, boxes, *, name=None, external_half=True):
    """A tileset like Metashape's: a root cube of 98 m (too large on purpose),
    a root.transform that places it, half of the leaves behind an external
    ``Data/c0/tileset.json``."""
    folder = pathlib.Path(folder)
    (folder / "Data" / "c0").mkdir(parents=True, exist_ok=True)
    offset = [-29.4, -53.8, 489.25]
    leaves = _skin(boxes, offset)
    half = len(leaves) // 2 if external_half else 0
    cube = [49.152, 49.152, 49.152, 49.152, 0, 0, 0, 49.152, 0, 0, 0, 49.152]
    children = leaves[half:]
    if half:
        (folder / "Data" / "c0" / "tileset.json").write_text(json.dumps(
            {"asset": {"version": "1.0"}, "geometricError": 10,
             "root": {"boundingVolume": {"box": cube}, "geometricError": 1,
                      "children": [dict(t, content={"uri": "../../" + t["content"]["uri"],
                                                    "boundingVolume": t["content"]["boundingVolume"]})
                                   for t in leaves[:half]]}}))
        children.append({"boundingVolume": {"box": cube}, "geometricError": 1,
                         "content": {"uri": "Data/c0/tileset.json"}})
    asset = {"version": "1.0"}
    if name:
        asset["extras"] = {"name": name}
    (folder / "tileset.json").write_text(json.dumps(
        {"asset": asset, "geometricError": 10000,
         "root": {"boundingVolume": {"box": cube}, "geometricError": 10, "refine": "REPLACE",
                  "transform": [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0] + offset + [1],
                  "children": children}}))
    return folder


def _zip(folder, target):
    with zipfile.ZipFile(target, "w") as z:
        for p in pathlib.Path(folder).rglob("*"):
            if p.is_file():
                z.write(p, p.relative_to(folder).as_posix())
    return target


@pytest.fixture
def survey_tileset(tmp_path):
    boxes = list(MEMBERS.values()) + [TEMPLUM]
    return _write_tileset(tmp_path / "Survey2015_tiles", boxes)


# ── the name ─────────────────────────────────────────────────────────────────

def test_the_name_from_the_asset_else_from_the_file():
    assert CA.proposed_name("/x/Rilievo.3tz", {"version": "1.0", "extras": {"name": "Rilievo 2015"}}) \
        == "Rilievo 2015"
    assert CA.proposed_name("/x/TempluMare.zip", {"version": "1.0"}) == "TempluMare"
    assert CA.proposed_name("/x/TempluMare/", {"version": "1.0"}) == "TempluMare"
    assert CA.proposed_name("/x/TempluMare/tileset.json", {}) == "TempluMare"


# ── reading a tileset ────────────────────────────────────────────────────────

def test_the_leaves_not_the_root(survey_tileset, tmp_path):
    ins = CA.inspect_tileset(str(survey_tileset))
    assert ins["kind"] == "directory" and ins["name"] == "Survey2015_tiles"
    assert ins["external"] == 1 and ins["unread"] == [] and ins["level"] == "leaves"
    assert len(ins["leaves"]) == 11 * 16
    lo, hi = ins["envelope"]
    # the leaves lie on the meshes, placed by root.transform — the root cube does not
    assert lo == pytest.approx([-37.817, -47.08, 490.083], abs=0.01)
    assert hi == pytest.approx([11.93, 16.44, 498.33], abs=0.01)
    # the same content in a .zip and a .3tz: the same leaves
    for ext in (".zip", ".3tz"):
        arc = _zip(survey_tileset, tmp_path / f"Survey2015{ext}")
        other = CA.inspect_tileset(str(arc))
        assert other["kind"] == ext[1:] and other["name"] == "Survey2015"
        assert other["envelope"][0] == pytest.approx(lo) and len(other["leaves"]) == len(ins["leaves"])


def test_an_unreadable_external_tileset_stands_with_its_box(survey_tileset):
    os.remove(survey_tileset / "Data" / "c0" / "tileset.json")
    ins = CA.inspect_tileset(str(survey_tileset))
    assert ins["level"] == "coarse" and ins["unread"] == ["Data/c0/tileset.json"]


def test_not_a_tileset_is_refused(tmp_path):
    (tmp_path / "empty").mkdir()
    with pytest.raises(ValueError, match="tileset.json"):
        CA.inspect_tileset(str(tmp_path / "empty"))
    z = tmp_path / "plain.zip"
    with zipfile.ZipFile(z, "w") as f:
        f.writestr("readme.txt", "no")
    with pytest.raises(ValueError, match="tileset.json"):
        CA.inspect_tileset(str(z))


# ── coverage: the true case ─────────────────────────────────────────────────

def test_survey2015_templum_more_nothing_missing(survey_tileset):
    ins = CA.inspect_tileset(str(survey_tileset))
    far = [[200, 200, 490], [210, 210, 495]]
    cov = CA.coverage(ins, MEMBERS, {"SM_OB_TEMPLUM_LOD1": TEMPLUM, "Faraway": far})
    assert cov["m_container"] == 10 and cov["n_tileset"] == 11
    assert cov["extra"] == ["SM_OB_TEMPLUM_LOD1"] and cov["missing"] == []
    assert not cov["same"] and CA.note_of(cov) == "confirmed with 1 more"
    lines = CA.coverage_lines(cov)
    assert lines[0] == "The tileset holds 11 model(s), the container 10"
    assert lines[1] == "More in the tileset (1): SM_OB_TEMPLUM_LOD1"


def test_a_model_of_the_graph_with_a_members_box_is_that_member(survey_tileset):
    """GreatTemple_2026_v2.blend: the ME_ meshes carry no id of their RM, and
    SM_OB_*_LOD1 of the graph have their boxes: the same models, not «more»."""
    ins = CA.inspect_tileset(str(survey_tileset))
    same = {"SM_OB_EST_L_LOD1": [[x + 0.001 for x in MEMBERS["ME_EST_L"][0]], MEMBERS["ME_EST_L"][1]]}
    cov = CA.coverage(ins, MEMBERS, dict(same, SM_OB_TEMPLUM_LOD1=TEMPLUM))
    assert cov["twins"] == {"SM_OB_EST_L_LOD1": "ME_EST_L"}
    assert cov["extra"] == ["SM_OB_TEMPLUM_LOD1"] and cov["n_tileset"] == 11
    assert any("the same, not counted twice" in x for x in CA.coverage_lines(cov))
    # TEMPLUM overlaps the podium and the walls, but is none of them
    assert CA.twins(MEMBERS, {"T": TEMPLUM}) == {}
    assert CA.box_iou(MEMBERS["ME_PODIO"], MEMBERS["ME_PODIO"]) == pytest.approx(1.0)


def test_the_missing_ones_and_the_other_containers(tmp_path):
    """A tileset of the podium alone against three models: the two walls of
    the front (12 m and more away from it) are missing."""
    three = {k: MEMBERS[k] for k in ("ME_PODIO", "ME_EST_fr", "ME_INT_fr")}
    t = _write_tileset(tmp_path / "podio", [MEMBERS["ME_PODIO"]])
    column = [[-15, -6, 492], [-14, -5, 505]]
    cov = CA.coverage(CA.inspect_tileset(str(t)), three, {}, elsewhere={"Column": column})
    assert cov["covered"] == ["ME_PODIO"] and cov["missing"] == ["ME_EST_fr", "ME_INT_fr"]
    assert cov["n_tileset"] == 1 and cov["extra"] == []
    # a model of another container in the same place is counted, not listed
    assert cov["elsewhere_inside"] == ["Column"]
    assert "1 model(s) of other containers stand in the same place (not counted)" \
        in CA.coverage_lines(cov)
    # a model with no box is said, not guessed
    cov = CA.coverage(CA.inspect_tileset(str(t)), dict(three, Ghost=None), {})
    assert cov["unmeasured"] == ["Ghost"]


@pytest.mark.skipif(not (TEMPLU / "RB" / "cesium" / "TempluMare" / "tileset.json").exists(),
                    reason="the copy of Templu Mare is not on this disk")
def test_survey2015_with_the_real_tileset():
    """The 2015 survey's tileset (Metashape, 7,301 tiles, b3dm without names):
    5,476 leaves; the 10 meshes of Survey2015 in, TEMPLUM more. The .zip as
    received is in Metashape's frame (no placement): it holds none of them."""
    ins = CA.inspect_tileset(str(TEMPLU / "RB" / "cesium" / "TempluMare"))
    assert ins["tiles"] == 7301 and len(ins["leaves"]) == 5476 and ins["external"] == 6
    templum = CA.glb_box(str(TEMPLU / "RB" / "versions" / "SM_OB_TEMPLUM_LOD1@lod4-web.glb"))
    assert templum[0] == pytest.approx(TEMPLUM[0], abs=0.01)
    cov = CA.coverage(ins, MEMBERS, {"SM_OB_TEMPLUM_LOD1": templum})
    assert cov["extra"] == ["SM_OB_TEMPLUM_LOD1"] and cov["missing"] == []
    assert min(cov["shares"][m] for m in MEMBERS) >= 0.75
    zipped = CA.inspect_tileset(str(TEMPLU / "RB" / "cesium" / "TempluMare.zip"))
    assert CA.coverage(zipped, MEMBERS, {})["n_tileset"] == 0


def test_glb_box_reads_the_accessors(tmp_path):
    import struct
    doc = {"asset": {"version": "2.0"}, "scene": 0, "scenes": [{"nodes": [0]}],
           "nodes": [{"mesh": 0, "translation": [10, 494, 2]}],
           "meshes": [{"primitives": [{"attributes": {"POSITION": 0}}]}],
           "accessors": [{"min": [-1, -1, -1], "max": [1, 1, 1], "count": 3,
                          "componentType": 5126, "type": "VEC3"}]}
    js = json.dumps(doc).encode()
    js += b" " * (-len(js) % 4)
    p = tmp_path / "m.glb"
    p.write_bytes(b"glTF" + struct.pack("<II", 2, 20 + len(js)) + struct.pack("<II", len(js), 0x4E4F534A) + js)
    lo, hi = CA.glb_box(str(p))
    # glTF Y up → Blender Z up: (x, -z, y)
    assert lo == pytest.approx([9, -3, 493]) and hi == pytest.approx([11, -1, 495])


# ── the tilesets of the graph ───────────────────────────────────────────────

def _survey_graph():
    from s3dgraphy import api
    from s3dgraphy.graph import Graph
    from s3dgraphy.nodes.document_node import DocumentNode
    from s3dgraphy.nodes.representation_node import RepresentationModelNode
    g = Graph("alt")
    g.add_node(DocumentNode("d01", name="D.01"))
    g.add_node(DocumentNode("d09", name="D.09"))
    GN.ensure_group(g, "rmgroup_Survey2015", "Survey2015")
    for i in range(3):
        api.add_resource(g, resource_id=f"m{i}", name=f"EST_{i}", kind="3d_model", tier="master",
                         files=[{"path": f"m{i}.glb", "checksum": "sha256:" + str(i) * 64}])
        g.add_node(RepresentationModelNode(f"rm{i}", name=f"EST_{i}"))
        g.add_edge(f"rm{i}~m{i}", f"rm{i}", f"m{i}", "has_linked_resource")
        g.add_edge(f"d01~rm{i}", "d01", f"rm{i}", "has_representation_model")
        GN.add_member(g, "rmgroup_Survey2015", f"rm{i}")
    # Templu Mare's shape: the zip as received (master), the folder its lod0
    api.add_resource(g, resource_id="tiles", name="Survey tileset", kind="3d_model", tier="master",
                     packaging="archive", files=[{"path": "survey.zip", "checksum": "sha256:" + "f" * 64,
                                                  "size_bytes": 1000}])
    api.add_version(g, "tiles", level="lod0", use=["web", "realtime"], version_id="tiles.lod0",
                    packaging="directory", size_bytes=1200,
                    files=[{"path": "survey/tileset.json", "checksum": "sha256:" + "e" * 64}])
    g.add_node(RepresentationModelNode("XX_tileset_model", name="XX_tileset"))
    g.add_edge("t~tiles", "XX_tileset_model", "tiles", "has_linked_resource")
    # a plain zip with nothing that declares a tileset: not one
    api.add_resource(g, resource_id="z", name="photos", kind="3d_model",
                     files=[{"path": "photos.zip", "checksum": "sha256:" + "a" * 64}])
    return g


def test_the_tilesets_of_the_graph_as_s3dgraphy_recognises_them():
    g = _survey_graph()
    got = CA.tileset_assets(g)
    assert [a["asset_id"] for a in got] == ["tiles"]
    a = got[0]
    assert a["name"] == "Survey tileset" and a["uses"] == ["web", "realtime"]
    assert a["size_bytes"] == 1200 and a["hat_names"] == ["XX_tileset"]
    assert CA.human_size(198361152) == "198.4 MB"


def test_a_tileset_of_the_graph_becomes_the_alternative():
    alt = pytest.importorskip("s3dgraphy.resources.alternatives")
    g = _survey_graph()
    res = CA.write_alternative(g, "rmgroup_Survey2015", "tiles", uses=["web"],
                               name="Rilievo 2015", scene_rm_ids=())
    assert res["dropped_rm"] == ["XX_tileset_model"] and res["uses_on"] == ["tiles.lod0"]
    assert alt.hats_of(g, "tiles") == ["rmgroup_Survey2015"]
    assert g.find_node_by_id("tiles.lod0").data["use"] == ["web"]
    got = CA.alternative_of(g, "rmgroup_Survey2015")
    assert got["name"] == "Rilievo 2015" and got["uses"] == ["web"]
    s = alt.find_set(alt.alternative_sets(g), "rmgroup_Survey2015")
    assert alt.choose_alternative(s, ["web"])["entry"]["id"] == "tiles.lod0"
    # «Remove the alternative»: the hat goes, the resource and its file stay
    assert CA.remove_alternative(g, "rmgroup_Survey2015") == ["tiles"]
    assert CA.alternative_of(g, "rmgroup_Survey2015") is None
    assert g.find_node_by_id("tiles") is not None and g.find_node_by_id("tiles.lod0") is not None


def test_an_rm_a_scene_object_stands_for_stays():
    g = _survey_graph()
    res = CA.write_alternative(g, "rmgroup_Survey2015", "tiles", scene_rm_ids={"XX_tileset_model"})
    assert res["dropped_rm"] == [] and g.find_node_by_id("XX_tileset_model") is not None


def test_without_its_group_the_container_is_refused():
    g = _survey_graph()
    with pytest.raises(ValueError, match="project"):
        CA.write_alternative(g, "rmgroup_Nope", "tiles")


# ── the storage, and a tileset from the disk ────────────────────────────────

def _project(tmp_path):
    root = tmp_path / "templu"
    (root / "EM").mkdir(parents=True)
    return root


def test_from_outside_it_is_copied_into_the_tree(survey_tileset, tmp_path):
    root = _project(tmp_path)
    arc = _zip(survey_tileset, tmp_path / "Survey2015.3tz")
    plan = CA.storage_plan(str(arc), str(root), str(root / "EM"))
    assert plan["copy"] and plan["locator"] == "../RM/tilesets/Survey2015.3tz" and not plan["unpack"]
    done = CA.apply_storage(plan)
    assert done["copied"] and (root / "RM" / "tilesets" / "Survey2015.3tz").is_file()
    # the same bytes again: nothing copied twice
    assert not CA.apply_storage(plan)["copied"]
    # other bytes under the same name: never written over
    other = tmp_path / "elsewhere" / "Survey2015.3tz"
    other.parent.mkdir()
    other.write_bytes(b"other bytes")
    p2 = CA.apply_storage(CA.storage_plan(str(other), str(root), str(root / "EM")))
    assert p2["locator"] == "../RM/tilesets/Survey2015-2.3tz"


def test_inside_the_project_it_stays_and_a_zip_is_unpacked(survey_tileset, tmp_path):
    root = _project(tmp_path)
    (root / "RB" / "cesium").mkdir(parents=True)
    arc = _zip(survey_tileset, root / "RB" / "cesium" / "Survey.zip")
    plan = CA.storage_plan(str(arc), str(root), str(root / "EM"))
    assert not plan["copy"] and plan["locator"] == "../RB/cesium/Survey.zip"
    assert plan["unpack_locator"] == "../RB/cesium/Survey/tileset.json"
    done = CA.apply_storage(plan)
    assert done["unpacked"] and (root / "RB" / "cesium" / "Survey" / "tileset.json").is_file()


def test_a_tileset_from_the_disk_enters_the_graph(survey_tileset, tmp_path):
    pytest.importorskip("dtcstamp")
    alt = pytest.importorskip("s3dgraphy.resources.alternatives")
    root = _project(tmp_path)
    arc = _zip(survey_tileset, tmp_path / "Survey2015.zip")
    done = CA.apply_storage(CA.storage_plan(str(arc), str(root), str(root / "EM")))
    master = CA.measure(done["dest"], done["locator"])
    served = CA.measure(done["unpack"], done["unpack_locator"])
    assert master["packaging"] == "archive" and master["file"]["url"] == "../RM/tilesets/Survey2015.zip"
    assert master["file"]["checksum"].startswith("sha256:") and master["file"]["size_bytes"] > 0
    assert served["packaging"] == "directory"
    assert served["file"]["url"] == "../RM/tilesets/Survey2015/tileset.json"
    # the fixture's tree: its two tileset.json (no tile bytes written)
    assert served["data"]["content_digest"]["files"] == 2
    g = _survey_graph()
    made = CA.new_tileset_asset(g, "Survey2015", master, served, ["web", "realtime"])
    asset = made["asset_id"]
    assert g.find_node_by_id(asset).data["tier"] == "master"
    v = g.find_node_by_id(made["version_id"])
    assert v.data["use"] == ["web", "realtime"] and v.data["packaging"] == "directory"
    assert [a["asset_id"] for a in CA.tileset_assets(g)].count(asset) == 1
    # the same bytes chosen again are the same resource
    assert CA.find_by_checksum(g, master["file"]["checksum"]) == asset
    CA.write_alternative(g, "rmgroup_Survey2015", asset)
    assert alt.hats_of(g, asset) == ["rmgroup_Survey2015"]
    s = alt.find_set(alt.alternative_sets(g), "rmgroup_Survey2015")
    assert "packaging" in s["reasons"]
    assert alt.choose_alternative(s, ["web"])["entry"]["id"] == made["version_id"]


def test_a_3tz_carries_its_uses_on_a_version():
    """A tileset whose only form is its master (a .3tz received alone) gets a
    lod0 with the same bytes to carry the uses: s3Dgraphy reads them on the
    versions, never on the master."""
    from s3dgraphy import api
    g = _survey_graph()
    api.add_resource(g, resource_id="t3", name="Alone", kind="3d_model", tier="master",
                     files=[{"path": "alone.3tz", "checksum": "sha256:" + "b" * 64}])
    ids = CA.set_uses(g, "t3", ["web"])
    assert len(ids) == 1 and g.find_node_by_id(ids[0]).data["use"] == ["web"]
    assert g.find_node_by_id(ids[0]).data["url"] == "alone.3tz"


# ── the document ────────────────────────────────────────────────────────────

def test_the_document_the_models_say():
    g = _survey_graph()
    got = CA.propose_document(g, ["rm0", "rm1", "rm2"])
    assert got["proposal"] == "d01" and got["name"] == "D.01" and (got["count"], got["of"]) == (3, 3)
    # split between two documents: no proposal, the ranking says why
    g.add_edge("d09~rm2", "d09", "rm2", "has_representation_model")
    for e in list(g.edges):
        if e.edge_source == "d01" and e.edge_target == "rm2":
            g.remove_edge(e.edge_id)
    got = CA.propose_document(g, ["rm0", "rm1", "rm2"])
    assert got["proposal"] is None and [r[1] for r in got["ranking"]] == ["D.01", "D.09"]
    # models no document reaches: nothing to say
    assert CA.propose_document(g, ["XX_tileset_model"])["proposal"] is None


@pytest.mark.skipif(not (TEMPLU / "EM" / "TempluMare_v3.2.em.json").exists(),
                    reason="the copy of Templu Mare is not on this disk")
def test_templu_mare_d01_and_d09():
    from s3dgraphy import api
    g, _ = api.load_emjson_file(str(TEMPLU / "EM" / "TempluMare_v3.2.em.json"))
    rms = [n.node_id for n in g.nodes if n.node_type == "representation_model"]
    survey = [r for r in rms if r.startswith("SM_OB_") and "TEMPLUM" not in r]
    rec = [r for r in rms if not r.startswith("SM_OB_") and r != "XX_tileset_model"]
    assert len(survey) == 10 and len(rec) == 87
    assert CA.propose_document(g, survey)["name"] == "D.01"
    assert CA.propose_document(g, rec)["name"] == "D.09"
    assert [a["name"] for a in CA.tileset_assets(g)][0] == "TempluMare (Cesium 3D Tiles tileset)"
