"""MICRO tileset, shift e epoche (E.D., 25 Oct 2026) — the logic, outside Blender.

E.D.'s case: the RM container «tls» with 0 meshes, its alternative the tileset
of the whole Basilica Iulia; the epoch is said by the Document wrapping the
group (D.1 has_first_epoch → Epoch 1, D.1 has_representation_model → the
group). The alternative lies in Epoch 1 and Automatic picks it.

The tileset's coordinates are shifted (E − 291407, N − 4640813 declared as
EPSG:6708): ``data.frame`` on its asset, «Use the graph's shift», and the box
of the alternative relocated by the frame (PROJ needed for that one: skipped
without ``pyproj``).
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


TF = _load("tileset_frame", "rm_manager/tileset_frame.py")
CA = _load("container_alternative_tf", "rm_manager/container_alternative.py")

#: the Basilica Iulia's root (tileset_Basilica_TLS_UAV_ED.3tz, measured 25 Oct)
BASILICA_T = [-0.18243234, 0.98321841, 0.0, 0.0, -1.97e-06, -3.6e-07, 1.0, 0.0,
              0.98321841, 0.18243234, 2e-06, 0.0,
              6271099.97842686, 1163587.23952703, 12.30475555, 1.0]
BASILICA_BOX = [-4.6006813, -2.48278046, 6.83278513, 94.20596313, 0.0, 0.0,
                0.0, 49.0687027, 0.0, 0.0, 0.0, 12.45930481]
SHIFT6708 = [291407.0, 4640813.0, 0.0]


def _ed_graph(with_member_epoch=False, doc_epoch=True):
    """E.D.'s em.json of 25 Oct, its shape: the group rmgroup_tls, no member,
    the tileset as its alternative (a master and its lod0), D.1 wrapping it."""
    from s3dgraphy import api
    from s3dgraphy.graph import Graph
    from s3dgraphy.nodes.document_node import DocumentNode
    from s3dgraphy.nodes.epoch_node import EpochNode
    from s3dgraphy.nodes.group_node import RepresentationModelNodeGroup
    g = Graph("ed")
    g.add_node(EpochNode("ep1", "Epoch 1", 2026, 2026))
    g.add_node(EpochNode("ep2", "Epoch 2", 100, 200))
    g.add_node(RepresentationModelNodeGroup(node_id="rmgroup_tls", name="tls"))
    g.add_node(DocumentNode("d1", name="D.1"))
    if doc_epoch:
        g.add_edge("d1~ep1", "d1", "ep1", "has_first_epoch")
    g.add_edge("d1~grp", "d1", "rmgroup_tls", "has_representation_model")
    api.add_resource(g, resource_id="ts", name="tileset_Basilica_TLS_UAV_ED", kind="3d_model",
                     tier="master", packaging="archive",
                     files=[{"path": "tilesets/tileset_Basilica_TLS_UAV_ED.3tz",
                             "checksum": "sha256:" + "3" * 64, "size_bytes": 1285510644}])
    api.add_version(g, "ts", level="lod0", use=["web", "realtime"], version_id="ts.lod0",
                    packaging="archive", size_bytes=1285510644,
                    files=[{"path": "tilesets/tileset_Basilica_TLS_UAV_ED.3tz",
                            "checksum": "sha256:" + "3" * 64}])
    g.add_edge("grp~ts", "rmgroup_tls", "ts", "has_linked_resource")
    if with_member_epoch:
        from s3dgraphy.nodes.representation_node import RepresentationModelNode
        g.add_node(RepresentationModelNode("rm1", name="mesh"))
        g.add_edge("rm1~grp", "rm1", "rmgroup_tls", "is_in_representation_model_group")
        g.add_edge("ep2~rm1", "ep2", "rm1", "has_representation_model")
    return g


@pytest.fixture
def no_rule(monkeypatch):
    """An s3Dgraphy without the container's own epochs (the bundled dev64)."""
    import s3dgraphy.resources.alternatives as alt
    monkeypatch.delattr(alt, "container_own_epochs", raising=False)
    assert not TF.has_container_rule()


# ── Part 1 · the container's own epochs ─────────────────────────────────────

def test_a_container_without_meshes_lies_in_its_documents_epoch():
    if not TF.has_container_rule():
        pytest.skip("this s3Dgraphy has no container_own_epochs")
    got = TF.container_epochs(_ed_graph(), "rmgroup_tls")
    assert got == {"ids": ["ep1"], "names": ["Epoch 1"], "source": "own"}


def test_the_same_answer_without_the_rule_in_s3dgraphy(no_rule):
    got = TF.container_epochs(_ed_graph(), "rmgroup_tls")
    assert got == {"ids": ["ep1"], "names": ["Epoch 1"], "source": "own (local)"}


def test_the_local_reading_agrees_with_s3dgraphy():
    if not TF.has_container_rule():
        pytest.skip("this s3Dgraphy has no container_own_epochs")
    from s3dgraphy.resources.alternatives import container_own_epochs
    g = _ed_graph()
    g.add_edge("d1~ep2", "d1", "ep2", "survive_in_epoch")
    assert TF.own_epochs_local(g, "rmgroup_tls") == container_own_epochs(g, "rmgroup_tls") \
        == ["ep1", "ep2"]


def test_the_members_epochs_win_over_the_containers_own():
    got = TF.container_epochs(_ed_graph(with_member_epoch=True), "rmgroup_tls")
    assert got["names"] == ["Epoch 2"] and got["source"] == "members"


def test_when_the_graph_says_nothing_the_epochs_of_this_set_close_the_chain():
    g = _ed_graph(doc_epoch=False)
    assert TF.container_epochs(g, "rmgroup_tls", ["Epoch 1"]) == \
        {"ids": [], "names": ["Epoch 1"], "source": "scene"}
    assert TF.container_epochs(g, "rmgroup_tls")["source"] == "none"
    # no graph at all (a scene not opened from an em.json)
    assert TF.container_epochs(None, "", ["Epoch 1"])["names"] == ["Epoch 1"]


def test_s3dgraphy_sets_carry_the_containers_own_epochs():
    if not TF.has_container_rule():
        pytest.skip("this s3Dgraphy has no container_own_epochs")
    from s3dgraphy.resources.alternatives import alternative_sets, find_set
    s = find_set(alternative_sets(_ed_graph()), "rmgroup_tls")
    assert s["epochs"] == ["ep1"] and not s["members"] and s["alternatives"]


# ── Automatic ───────────────────────────────────────────────────────────────

def test_automatic_with_no_member_picks_the_tileset():
    from s3dgraphy.resources.alternatives import alternative_sets, find_set
    s = find_set(alternative_sets(_ed_graph()), "rmgroup_tls")
    assert TF.effective_mode("AUTO", True, 0, s) == "TILESET"
    assert TF.effective_mode("AUTO", True, 0) == "TILESET"


def test_automatic_without_the_rule_counts_the_members(monkeypatch):
    import s3dgraphy.resources.alternatives as alt
    s = alt.find_set(alt.alternative_sets(_ed_graph()), "rmgroup_tls")
    monkeypatch.delattr(alt, "container_own_epochs", raising=False)
    assert not TF.has_container_rule()
    assert TF.effective_mode("AUTO", True, 0, s) == "TILESET"
    assert TF.effective_mode("AUTO", True, 3, s) == "MODELS"


def test_automatic_with_members_stays_the_models_in_blender():
    from s3dgraphy.resources.alternatives import alternative_sets, find_set
    g = _ed_graph(with_member_epoch=True)
    s = find_set(alternative_sets(g), "rmgroup_tls")
    assert TF.effective_mode("AUTO", True, 1, s) == "MODELS"


def test_the_persons_choice_and_no_alternative():
    assert TF.effective_mode("MODELS", True, 0) == "MODELS"
    assert TF.effective_mode("TILESET", True, 5) == "TILESET"
    assert TF.effective_mode("AUTO", False, 0) == "MODELS"


def test_the_box_is_seen_in_the_containers_epochs():
    assert TF.box_visible(True, True, "Epoch 1", ["Epoch 1"])
    assert not TF.box_visible(True, True, "Epoch 2", ["Epoch 1"])
    assert not TF.box_visible(True, True, "Epoch 1", [])
    assert TF.box_visible(True, False, "Epoch 2", ["Epoch 1"])      # no sync by epoch
    assert not TF.box_visible(False, False, "", ["Epoch 1"])         # the eye


# ── Part 2 · the frame ──────────────────────────────────────────────────────

def test_the_frame_is_written_on_the_tilesets_asset():
    g = _ed_graph()
    assert TF.frame_node(g, "ts.lod0") == "ts"            # a version → its asset
    assert TF.frame_node(g, "ts") == "ts"
    f = TF.make_frame("6708", SHIFT6708, "SHIFT6708.txt", "file")
    assert f == {"crs": "EPSG:6708", "shift": SHIFT6708, "note": "SHIFT6708.txt",
                 "source": "file"}
    assert TF.write_frame(g, "ts", f) is None
    assert g.find_node_by_id("ts").data["frame"]["shift"] == SHIFT6708
    got, where = TF.frame_for(g, "ts.lod0")
    assert got["crs"] == "EPSG:6708" and where == "ts"
    assert TF.write_frame(g, "ts", None)["crs"] == "EPSG:6708"
    assert "frame" not in g.find_node_by_id("ts").data


def test_the_frame_without_s3dgraphy_geometry(monkeypatch):
    monkeypatch.setitem(sys.modules, "s3dgraphy.geometry.frame", None)   # ImportError
    g = _ed_graph()
    f = TF.make_frame(6708, ["291407", "4640813,0"], "", "manual")
    assert f == {"crs": "EPSG:6708", "shift": SHIFT6708, "source": "manual"}
    TF.write_frame(g, "ts", f)
    assert TF.frame_for(g, "ts")[0]["shift"] == SHIFT6708
    assert TF.read_frame({"frame": {"epsg": 6708, "shift": {"x": 1, "y": 2}}}) == \
        {"crs": "EPSG:6708", "shift": [1.0, 2.0, 0.0]}
    with pytest.raises(ValueError):
        TF.make_frame(6708, [0, 0, 0], source="guess")


def test_an_rm_without_resource_carries_its_own_frame():
    from s3dgraphy.graph import Graph
    from s3dgraphy.nodes.representation_node import RepresentationModelNode
    g = Graph("cesium")
    g.add_node(RepresentationModelNode("Tileset_model", name="Model for Tileset"))
    assert TF.frame_node(g, "Tileset_model") == "Tileset_model"
    TF.write_frame(g, "Tileset_model", TF.make_frame("EPSG:6708", SHIFT6708))
    assert TF.frame_for(g, "Tileset_model")[1] == "Tileset_model"


def test_the_copy_and_the_line():
    f = TF.make_frame("EPSG:6708", SHIFT6708, "SHIFT6708.txt", "file")
    assert TF.loads(TF.dumps(f)) == f and TF.loads("") is None and TF.dumps(None) == ""
    assert TF.frame_line(f) == "EPSG:6708 − (291407, 4640813, 0)"
    assert TF.frame_line(None).startswith("No frame")
    assert TF.parse_number(" 4640813,5 ") == 4640813.5 and TF.parse_number("") == 0.0
    with pytest.raises(ValueError):
        TF.parse_number("abc")


def test_use_the_graphs_shift():
    # the graph's geo_position as the georef manager reads it
    assert TF.study_frame({"epsg": None, "shift_x": 0, "shift_y": 0, "shift_z": 0}) is None
    assert TF.study_frame({"epsg": "NotSet", "shift_x": 0.0}) is None
    s = TF.study_frame({"epsg": "6708", "shift_x": 291407.0, "shift_y": 4640813.0, "shift_z": 0})
    assert s == {"crs": "EPSG:6708", "shift": SHIFT6708}
    f = TF.frame_from_study(s, "the graph's geo_position")
    assert f["source"] == "graph" and f["crs"] == "EPSG:6708" and f["shift"] == SHIFT6708
    assert TF.frame_from_study(None) is None


def test_where_the_box_lands():
    f = TF.make_frame("EPSG:6708", SHIFT6708)
    study = {"crs": "EPSG:6708", "shift": [291000.0, 4640000.0, 0.0]}
    t, said = TF.placement_target(f, None, study)
    assert t == study and "study" in said
    t, said = TF.placement_target(f, {"crs": None, "shift": [1.0, 2.0, 0.0]})
    assert t == {"crs": "EPSG:6708", "shift": [1.0, 2.0, 0.0]}
    t, said = TF.placement_target(f, None, None)            # E.D.'s graph: no shift
    assert t == {"crs": "EPSG:6708", "shift": SHIFT6708} and "shifted grid" in said
    assert TF.placement_target(TF.make_frame(None, [1, 2, 3])) == (None, "")
    assert TF.placement_target(None) == (None, "")


def _basilica_zip(tmp_path):
    root = {"asset": {"version": "1.0"}, "geometricError": 50,
            "root": {"boundingVolume": {"box": BASILICA_BOX}, "geometricError": 1,
                     "transform": BASILICA_T,
                     "children": [{"boundingVolume": {"box": BASILICA_BOX}, "geometricError": 0,
                                   "content": {"uri": "t.b3dm"}}]}}
    p = tmp_path / "basilica.3tz"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("tileset.json", json.dumps(root))
        z.writestr("t.b3dm", b"b3dm")
    return str(p)


def test_without_a_frame_the_box_stays_where_the_transform_puts_it(tmp_path):
    p = _basilica_zip(tmp_path)
    plain = CA.inspect_tileset(p)
    assert plain["relocation"] is None
    assert plain["envelope"][0][0] > 6.2e6                  # ECEF, the equator
    # a frame that cannot relocate (no CRS): said, and the box unchanged
    got = CA.inspect_tileset(p, frame={"crs": None, "shift": [1, 2, 3]})
    assert got["relocation"]["ok"] is False and got["envelope"] == plain["envelope"]


def test_the_frame_relocates_the_basilica_into_the_scene(tmp_path):
    pytest.importorskip("pyproj")
    pytest.importorskip("numpy")
    pytest.importorskip("s3dgraphy.geometry.frame")
    p = _basilica_zip(tmp_path)
    f = TF.make_frame("EPSG:6708", SHIFT6708)
    target, _said = TF.placement_target(f)
    got = CA.inspect_tileset(p, frame=f, target=target)
    rel = got["relocation"]
    assert rel["ok"] and rel["residual_max_m"] < 0.01
    lo, hi = got["envelope"]
    # the file's shifted grid: around the origin, ~190 × 100 m, metres high
    assert all(abs(v) < 200 for v in lo + hi)
    assert 150 < hi[0] - lo[0] < 230 and 80 < hi[1] - lo[1] < 130
    # towards ECEF the Basilica is in Rome
    ecef = CA.inspect_tileset(p, frame=f, target=None)["relocation"]
    assert ecef["true"]["lat"] == pytest.approx(41.8918, abs=1e-3)
    assert ecef["true"]["lon"] == pytest.approx(12.4860, abs=1e-3)
    assert "residual" in TF.placement_line(rel, "x")


def test_the_true_basilica_when_its_copy_is_on_this_disk():
    pytest.importorskip("pyproj")
    pytest.importorskip("s3dgraphy.geometry.frame")
    p = os.environ.get("ED_BASILICA_3TZ", "/tmp/ed-tss2/tilesets/tileset_Basilica_TLS_UAV_ED.3tz")
    if not os.path.isfile(p):
        pytest.skip("no copy of the Basilica's tileset on this disk")
    f = TF.make_frame("EPSG:6708", SHIFT6708)
    got = CA.inspect_tileset(p, frame=f, target=TF.placement_target(f)[0])
    assert got["relocation"]["ok"] and got["relocation"]["residual_max_m"] < 0.01
    lo, hi = got["envelope"]
    assert all(abs(v) < 300 for v in lo + hi), (lo, hi)
