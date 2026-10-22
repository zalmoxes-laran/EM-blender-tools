"""Removing versions (E.D., 22 Oct 2026): the chain, the versions made from
it, the files and their stamps, the master never (bpy-free)."""

import os
import pathlib
import sys

import pytest

_REPO = pathlib.Path(__file__).resolve().parent.parent
_CHECKOUT = _REPO.parent / "s3Dgraphy" / "src"
if _CHECKOUT.is_dir():
    sys.path.insert(0, str(_CHECKOUT))
pytest.importorskip("s3dgraphy.resources.versions")

from s3dgraphy.graph import Graph  # noqa: E402
from s3dgraphy.resources.files import add_resource  # noqa: E402
from s3dgraphy.resources.versions import add_version, versions_of  # noqa: E402

import version_removal as vr  # noqa: E402


def _write(path, n):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(bytes([n]) * 16)
    return [{"url": path, "checksum": "sha256:" + f"{n:064x}"}]


@pytest.fixture
def asset(tmp_path):
    cache = tmp_path / "em_cache"
    outside = tmp_path / "RB"
    g = Graph(graph_id="g")
    m = add_resource(g, name="Walls", kind="model", tier="master",
                     files=_write(str(outside / "Walls.blend"), 1)).node_id
    lod0 = add_version(g, m, level="lod0", use=["analysis"],
                       files=_write(str(outside / "Walls_LOD0.obj"), 2))["version_id"]
    lod1 = add_version(g, lod0, level="lod1", use=["web"],
                       files=_write(str(cache / "local" / "versions" / "Walls@lod1-web.glb"), 3)
                       )["version_id"]
    web = add_version(g, m, level="lod0-web", use=["web"],
                      files=_write(str(cache / "local" / "versions" / "Walls@lod0-web.glb"), 4)
                      )["version_id"]
    stamp = str(cache / "local" / "versions" / "Walls@lod0-web.glb.stamp.json")
    with open(stamp, "w") as fh:
        fh.write("{}")
    return {"g": g, "m": m, "lod0": lod0, "lod1": lod1, "web": web, "cache": str(cache),
            "stamp": stamp}


def test_the_master_is_refused(asset):
    plan = vr.removal_plan(asset["g"], [asset["m"]], cache_root=asset["cache"])
    assert plan["resources"] == []
    assert plan["refused"] and "master" in plan["refused"][0]["why"]


def test_a_derived_version_goes_with_its_step_file_and_stamp(asset):
    g = asset["g"]
    plan = vr.removal_plan(g, [asset["web"]], cache_root=asset["cache"])
    assert plan["resources"] == [asset["web"]]
    assert len(plan["processes"]) == 1
    assert [os.path.basename(p) for p in plan["files_cache"]] == ["Walls@lod0-web.glb"]
    assert plan["stamps_cache"] == [asset["stamp"]]
    assert plan["files_outside"] == []
    vr.remove_from_graph(g, plan)
    done = vr.delete_files(vr.paths_to_delete(plan))
    assert len(done["deleted"]) == 2 and not os.path.exists(asset["stamp"])
    left = [e["id"] for e in versions_of(g, asset["m"])]
    assert asset["web"] not in left and asset["lod0"] in left and asset["lod1"] in left
    assert g.find_node_by_id(plan["processes"][0]) is None


def test_removing_lod0_takes_the_lod1_made_from_it(asset):
    g = asset["g"]
    plan = vr.removal_plan(g, [asset["lod0"]], cache_root=asset["cache"])
    assert set(plan["resources"]) == {asset["lod0"], asset["lod1"]}
    whys = {v["id"]: v["why"] for v in plan["versions"]}
    assert whys[asset["lod0"]] == "asked" and whys[asset["lod1"]].startswith("made from")
    # the author's OBJ is outside the cache: kept unless asked
    assert [os.path.basename(p) for p in plan["files_outside"]] == ["Walls_LOD0.obj"]
    assert all(os.path.basename(p) != "Walls_LOD0.obj" for p in vr.paths_to_delete(plan))
    assert any(os.path.basename(p) == "Walls_LOD0.obj"
               for p in vr.paths_to_delete(plan, outside=True))
    vr.remove_from_graph(g, plan)
    left = [e["id"] for e in versions_of(g, asset["m"])]
    assert left == [asset["m"], asset["web"]]


def test_a_file_another_resource_names_stays(asset):
    g = asset["g"]
    shared = g.find_node_by_id(asset["web"]).data["url"]
    add_resource(g, name="someone else", kind="model",
                 files=[{"url": shared, "checksum": "sha256:" + f"{4:064x}"}])
    plan = vr.removal_plan(g, [asset["web"]], cache_root=asset["cache"])
    assert plan["files_cache"] == [] and plan["kept_shared"] == [os.path.normpath(shared)]


def test_merge_and_summary(asset):
    g = asset["g"]
    p = vr.merge([vr.removal_plan(g, [asset["web"]], cache_root=asset["cache"]),
                  vr.removal_plan(g, [asset["web"], asset["lod1"]], cache_root=asset["cache"])])
    assert sorted(p["resources"]) == sorted([asset["web"], asset["lod1"]])
    lines = vr.summary_lines(p)
    assert any("Files deleted from disk: 2" in line for line in lines)
