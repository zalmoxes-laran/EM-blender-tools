"""R1 · the residence follows the origin (`sync_manager/residence.py`)."""
import importlib.util
import pathlib
import sys
import types

_REPO = pathlib.Path(__file__).resolve().parent.parent
_S3D = _REPO.parent / "s3Dgraphy" / "src"
if _S3D.is_dir():
    sys.path.insert(0, str(_S3D))


def _load(name):
    pkg = types.ModuleType("_r1")
    pkg.__path__ = [str(_REPO / "sync_manager")]
    sys.modules["_r1"] = pkg
    spec = importlib.util.spec_from_file_location(f"_r1.{name}", _REPO / "sync_manager" / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


res = _load("residence")


def test_the_geometry_axis_decides_then_the_folders():
    assert res.origin_from("reality_based", [])[0] == res.ORIGIN_RB
    for axis in ("observable", "asserted", "symbolic", "em_based"):
        assert res.origin_from(axis, [])[0] == res.ORIGIN_SB
    assert res.origin_from(None, ["Templu/RB/tiles/LOD0.glb"]) == (res.ORIGIN_RB, "in RB/")
    assert res.origin_from(None, ["SB/column.glb"]) == (res.ORIGIN_SB, "in SB/")
    # the axis wins over the folder
    assert res.origin_from("asserted", ["RB/x.glb"])[0] == res.ORIGIN_SB
    assert res.origin_from(None, ["models/x.glb"])[0] == res.ORIGIN_UNKNOWN
    assert res.origin_from("reality_based", [], proxy=True)[0] == res.ORIGIN_PROXY


def test_reality_based_is_a_library_source_based_and_proxy_resident():
    assert res.residence(res.ORIGIN_RB, False) == res.RESIDENCE_LIBRARY
    assert res.residence(res.ORIGIN_SB, True) == res.RESIDENCE_RESIDENT
    assert res.residence(res.ORIGIN_PROXY, False) == res.RESIDENCE_RESIDENT
    # no declared origin: as before
    assert res.residence(res.ORIGIN_UNKNOWN, True) == res.RESIDENCE_LIBRARY
    assert res.residence(res.ORIGIN_UNKNOWN, False) == res.RESIDENCE_RESIDENT


def _graph():
    from s3dgraphy import api
    from s3dgraphy.graph import Graph
    g = Graph(graph_id="r1")
    for rid, path in (("RB-tile", "RB/tile.glb"), ("SB-col", "SB/col.glb"),
                      ("plain", "models/plain.glb"), ("survey", "x/survey.glb")):
        api.add_resource(g, name=rid, resource_id=rid,
                         data={"path": path, "url": path, "checksum": "sha256:" + rid,
                               "residency": "resident"})
    api.hat_as_document(g, "survey", geometry="reality_based")
    return g


def test_the_summary_moves_each_model_where_its_origin_says():
    g = _graph()
    summary = {"resident": [{"resource_id": r, "node_id": r, "checksum": "sha256:" + r}
                            for r in ("RB-tile", "SB-col", "plain", "survey")]
               + [{"resource_id": "SB-col", "node_id": "v", "checksum": "sha256:v",
                   "asset_id": "SB-col"}]}
    out = res.apply_to_summary(g, summary)
    rows = {(r["resource_id"], r["node_id"]): r for r in out["resident"]}
    assert rows[("RB-tile", "RB-tile")]["asset_id"] == "RB-tile"       # its own library
    assert rows[("survey", "survey")]["origin_how"] == "geometry reality_based"
    assert rows[("survey", "survey")]["residence"] == "library"
    assert "asset_id" not in rows[("SB-col", "v")]                      # resident
    assert rows[("plain", "plain")]["origin"] == ""                     # as before
    assert out["origins"] == {"reality_based": 2, "source_based": 2, "proxy": 0, "": 1}
    line = res.sentence(out["origins"])
    assert "2 reality-based (linked libraries)" in line and "1 with no declared origin" in line


def test_a_reality_based_model_resident_from_before_is_left_as_it_is():
    sc = _load("scene_check")
    g = _graph()
    out = res.apply_to_summary(g, {"resident": [
        {"resource_id": "RB-tile", "node_id": "RB-tile", "checksum": "sha256:RB-tile"}]})
    kept = sc.keep_resident_from_before(out, [{"name": "tile", "type": "MESH",
                                               "digest": "sha256:RB-tile"}])
    assert kept == 1 and "asset_id" not in out["resident"][0]
