"""MICRO le alternative e la trasformazione, Parte 5 — EM Tools writes the new form.

s3Dgraphy's node datamodel 1.6.31 (E.D. 16-17 Oct 2026): ``data.transform`` in
numbers, degrees with ``rotation_order``, ``up_axis`` Z, the ``pivot`` (the
centre of the mesh's box in its own frame) and the quaternion. And the tileset
of a whole container is its ALTERNATIVE: the container is its hat. Outside
Blender: the pure halves (``version_recipe.placement``,
``transform_export.box_centre``, ``group_nodes.tileset_models`` and
``declare_container_alternative``).
"""

import importlib.util
import math
import pathlib
import sys

import pytest

_REPO = pathlib.Path(__file__).resolve().parent.parent
_CHECKOUT = _REPO.parent / "s3Dgraphy" / "src"
if _CHECKOUT.is_dir():
    sys.path.insert(0, str(_CHECKOUT))
sys.path.insert(0, str(_REPO))

T = pytest.importorskip("s3dgraphy.geometry.transform")
import version_recipe as VR  # noqa: E402
import transform_export as TE  # noqa: E402


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, _REPO / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


GN = _load("group_nodes_alt", "rm_manager/group_nodes.py")


def test_placement_writes_the_new_form():
    t = VR.placement((1.0, 2.0, 3.0), (0.0, 0.0, math.pi / 6), (1.0, 1.0, 1.0))
    assert t["angle_unit"] == "deg" and t["rotation_order"] == "XYZ" and t["up_axis"] == "Z"
    assert t["rotation"] == [0.0, 0.0, 30.0]
    assert all(isinstance(v, float) for k in ("position", "rotation", "scale") for v in t[k])
    # without a box, the pivot Blender turns about: the origin
    assert t["pivot"] == [0.0, 0.0, 0.0]
    assert t["quaternion"] == pytest.approx([0.9659258263, 0, 0, 0.2588190451])
    # read by s3Dgraphy as the new form, nothing to convert
    back, old = T.read_transform(t)
    assert not old and back == t


def test_placement_about_the_box_keeps_blenders_matrix():
    loc, rot, scl = (10.0, -4.0, 494.0), (0.2, -0.1, 0.9), (1.5, 1.5, 2.0)
    origin = VR.placement(loc, rot, scl)
    centre = [-16.18, -2.49, 493.69]
    about = VR.placement(loc, rot, scl, pivot=centre)
    assert about["pivot"] == centre
    for v in ([0, 0, 0], centre, [5, 3, 490]):
        assert T.apply(about, v) == pytest.approx(T.apply(origin, v), abs=1e-6)
    # the identity about the box: still the identity, the position zero
    ident = VR.placement((0, 0, 0), (0, 0, 0), (1, 1, 1), pivot=centre)
    assert ident["position"] == [0.0, 0.0, 0.0]


def test_a_blender_euler_order_goes_out_as_itself():
    # until 17 Oct a ZXY Euler went out as if it were XYZ
    t = VR.placement((0, 0, 0), (math.pi / 2, 0, math.pi / 2), (1, 1, 1), rotation_order="ZXY")
    assert t["rotation_order"] == "ZXY"
    assert t["quaternion"] == pytest.approx(T.quaternion_of([90, 0, 90], "ZXY"))
    assert t["quaternion"] != pytest.approx(T.quaternion_of([90, 0, 90], "XYZ"))


def test_box_centre():
    corners = [(x, y, z) for x in (-1, 3) for y in (0, 2) for z in (490, 500)]
    assert TE.box_centre(corners) == [1.0, 1.0, 495.0]
    assert TE.box_centre(None) is None


def _survey():
    from s3dgraphy import api
    from s3dgraphy.graph import Graph
    from s3dgraphy.nodes.epoch_node import EpochNode
    from s3dgraphy.nodes.representation_node import RepresentationModelNode
    g = Graph("alt")
    g.add_node(EpochNode("ep", name="XX sec", start_time=1900, end_time=2000))
    GN.ensure_group(g, "D.01_rmgroup", "Survey 2015")
    for i in range(2):
        api.add_resource(g, resource_id=f"m{i}", name=f"EST_{i}", kind="3d_model", tier="master",
                         files=[{"path": f"m{i}.glb", "checksum": "sha256:" + str(i) * 64}])
        g.add_node(RepresentationModelNode(f"rm{i}", name=f"EST_{i}"))
        g.add_edge(f"rm{i}~m{i}", f"rm{i}", f"m{i}", "has_linked_resource")
        g.add_edge(f"ep~rm{i}", "ep", f"rm{i}", "has_representation_model")
        GN.add_member(g, "D.01_rmgroup", f"rm{i}")
    api.add_resource(g, resource_id="tiles", name="Survey tileset", kind="3d_model", tier="master",
                     files=[{"path": "survey.zip", "checksum": "sha256:" + "f" * 64}])
    api.add_version(g, "tiles", level="lod0", use=["web"], version_id="tiles.lod0",
                    files=[{"path": "survey/tileset.json", "checksum": "sha256:" + "e" * 64}])
    g.find_node_by_id("tiles.lod0").data["packaging"] = "directory"
    g.add_node(RepresentationModelNode("XX_tileset_model", name="XX_tileset"))
    g.add_edge("t~tiles", "XX_tileset_model", "tiles", "has_linked_resource")
    g.add_edge("ep~t", "ep", "XX_tileset_model", "has_representation_model")
    return g


def test_tileset_models_are_found_by_what_they_declare():
    pytest.importorskip("s3dgraphy.resources.alternatives")
    g = _survey()
    assert GN.tileset_models(g) == [("XX_tileset_model", "XX_tileset")]


def test_use_as_container_alternative():
    alt = pytest.importorskip("s3dgraphy.resources.alternatives")
    g = _survey()
    res = GN.declare_container_alternative(g, "XX_tileset_model", "D.01_rmgroup", scene_rm_ids=())
    assert res["dropped_rm"] == ["XX_tileset_model"]
    assert alt.hats_of(g, "tiles") == ["D.01_rmgroup"]
    sets = alt.alternative_sets(g)
    s = alt.find_set(sets, "D.01_rmgroup")
    assert [x["reason"] for x in s["alternatives"]] == ["packaging", "packaging"]
    assert s["covers"] == ["rm0", "rm1"] and sets["warnings"] == []
    # chosen for the web: the tileset, the members go off
    ch = alt.choose_alternative(s, ["web"])
    assert ch["level"] == "container" and ch["entry"]["id"] == "tiles.lod0"


def test_an_rm_the_scene_points_at_stays():
    alt = pytest.importorskip("s3dgraphy.resources.alternatives")
    g = _survey()
    res = GN.declare_container_alternative(g, "XX_tileset_model", "D.01_rmgroup",
                                           scene_rm_ids={"XX_tileset_model"})
    assert res["dropped_rm"] == [] and g.find_node_by_id("XX_tileset_model") is not None
    assert alt.hats_of(g, "tiles") == ["D.01_rmgroup"]


def test_a_container_without_group_is_refused():
    pytest.importorskip("s3dgraphy.resources.alternatives")
    g = _survey()
    with pytest.raises(ValueError, match="project"):
        GN.declare_container_alternative(g, "XX_tileset_model", "nope_rmgroup")
