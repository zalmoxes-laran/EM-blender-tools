"""H4 · Heriverse as a destination, two roads (E.D., 5 Oct 2026).

On the node, the Deck says what the rule of s3dgraphy picks for each published
model; on disk, it writes a folder with the em.json and the bytes of those
versions at paths relative to it — the package Heriverse opens offline.
Measured here on a real graph and real files, headless (`publication_heriverse`
has no bpy); the rule itself is s3Dgraphy's, tested there in Python and JS.
"""

import hashlib
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

api = pytest.importorskip("s3dgraphy.api")
if not hasattr(api, "version_for"):
    pytest.skip("s3dgraphy without version_for", allow_module_level=True)

from s3dgraphy.graph import Graph                                       # noqa: E402
from s3dgraphy.nodes.representation_node import RepresentationModelNode  # noqa: E402

_spec = importlib.util.spec_from_file_location("_emtools_publication_heriverse",
                                               _REPO / "publication_heriverse.py")
PH = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = PH
_spec.loader.exec_module(PH)


def _sha(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _study(tmp_path):
    """Three models: one with a web version AND one made for Heriverse (on
    disk, in the cache), one with only a glTF master, one with only a .blend
    master. The files are real, their sha256 the registered one."""
    cache = tmp_path / "em_cache" / "local" / "versions"
    cache.mkdir(parents=True)
    blend_dir = tmp_path / "studio"
    blend_dir.mkdir()
    files = {"podio_web.glb": b"glTF web version",
             "podio@heriverse.glb": b"glTF made for Heriverse, as is",
             "muro.glb": b"glTF master of the wall"}
    for name, data in files.items():
        (cache / name if name.startswith("podio") else blend_dir / name).write_bytes(data)
    g = Graph("templu")
    api.add_resource(g, name="podio", kind="3d_model", tier="master",
                     files=[{"path": "podio.blend", "url": "blend://podio.blend#Object/podio",
                             "checksum": "sha256:" + "0" * 64}],
                     resource_id="podio")
    web = api.add_version(g, "podio", use="web", files=[{
        "path": "podio_web.glb", "url": str(cache / "podio_web.glb"),
        "checksum": _sha(files["podio_web.glb"])}])
    heri = api.add_version(g, "podio", use=list(PH.PACKAGE_USES), level="heriverse", files=[{
        "path": "podio@heriverse.glb", "url": "/somewhere/else/podio@heriverse.glb",
        "checksum": _sha(files["podio@heriverse.glb"])}])
    api.add_resource(g, name="muro", kind="3d_model", files=[{
        "path": "muro.glb", "url": "muro.glb", "checksum": _sha(files["muro.glb"])}],
        resource_id="muro")
    api.add_resource(g, name="arco", kind="3d_model", tier="master", files=[{
        "path": "arco.blend", "url": "arco.blend", "checksum": "sha256:" + "9" * 64}],
        resource_id="arco")
    for rm, res in (("rm_podio", "podio"), ("rm_muro", "muro"), ("rm_arco", "arco")):
        g.add_node(RepresentationModelNode(node_id=rm, name=rm.replace("rm_", "").upper()))
        g.add_edge(f"{rm}_r", rm, res, "has_linked_resource")
    return g, web, heri, cache, blend_dir


def test_the_rule_on_the_node_road(tmp_path):
    g, web, heri, *_ = _study(tmp_path)
    plan = PH.plan_for(g, [("rm_podio", "PODIO"), "rm_muro", "rm_arco", "rm_ghost"])
    assert plan["uses"] == ["heriverse", "aton", "web", "realtime"]
    ready = {r["rm_id"]: r for r in plan["ready"]}
    assert ready["rm_podio"]["version_id"] == heri["version_id"]
    assert ready["rm_podio"]["use"] == "heriverse"
    assert {r["rm_id"]: r["reason"] for r in plan["missing"]} == {"rm_muro": "master",
                                                                  "rm_arco": "master"}
    assert plan["absent"] == ["rm_ghost"]
    assert "heriverse, aton, web or realtime" in PH.summary(plan)
    assert PH.row_line(ready["rm_podio"]).startswith("PODIO → heriverse version")
    muro = next(r for r in plan["missing"] if r["rm_id"] == "rm_muro")
    assert "the master is loaded" in PH.row_line(muro)


def test_the_bytes_on_this_disk_are_found_by_their_sha256(tmp_path):
    g, web, heri, cache, blend_dir = _study(tmp_path)
    plan = PH.plan_for(g, ["rm_podio", "rm_muro"])
    podio = plan["ready"][0]
    # the url says another folder: the cache has a file with its name and its bytes
    got = PH.local_bytes(podio, roots=[str(blend_dir)], caches=[str(tmp_path / "em_cache")])
    assert got["path"] == str(cache / "podio@heriverse.glb")
    muro = plan["missing"][0]
    assert PH.local_bytes(muro, roots=[str(blend_dir)])["path"] == str(blend_dir / "muro.glb")
    # a file with the right name and other bytes is not the version
    (blend_dir / "muro.glb").write_bytes(b"something else")
    said = PH.local_bytes(muro, roots=[str(blend_dir)])
    assert said["path"] == "" and "other bytes" in said["said"]


def test_the_package_on_disk(tmp_path):
    g, web, heri, cache, blend_dir = _study(tmp_path)
    plan = PH.plan_for(g, ["rm_podio", "rm_muro", "rm_arco"])
    finder = lambda row: PH.local_bytes(row, roots=[str(blend_dir)],  # noqa: E731
                                        caches=[str(tmp_path / "em_cache")])
    disk = PH.disk_plan(plan, finder=finder)
    rels = {r["rm_id"]: r["rel"] for r in disk["rows"]}
    assert rels["rm_podio"] == "versions/PODIO@lod0-heriverse.glb"
    assert rels["rm_muro"] == "versions/MURO@master.glb"
    arco = next(r for r in disk["rows"] if r["rm_id"] == "rm_arco")
    assert arco["rel"] == "" and ".blend" in arco["local_said"]

    doc = PH.heriverse_document({"templu": g}, active="templu")
    dest = tmp_path / "out" / "templu_heriverse"
    report = PH.write_package(str(dest), doc, disk["rows"], make_zip=True)
    assert [w["rel"] for w in report["written"]] == ["versions/PODIO@lod0-heriverse.glb",
                                                    "versions/MURO@master.glb"]
    assert report["failed"] == []
    em = json.loads((dest / "em.json").read_text())
    assert (dest / "project.json").read_text() == (dest / "em.json").read_text()
    nodes = {n["id"]: n for n in em["graphs"]["templu"]["nodes"]}
    # the chosen resources point INTO the package, sha256 unchanged …
    assert nodes[heri["version_id"]]["data"]["url"] == "versions/PODIO@lod0-heriverse.glb"
    assert nodes["muro"]["data"]["url"] == "versions/MURO@master.glb"
    for rid in (heri["version_id"], "muro"):
        rel = nodes[rid]["data"]["url"]
        assert _sha((dest / rel).read_bytes()) == nodes[rid]["data"]["checksum"]
    # … the others keep the address they had
    assert nodes[web["version_id"]]["data"]["url"] == str(cache / "podio_web.glb")
    # read back, the package gives the same choice (what Heriverse will do)
    from s3dgraphy.container import parse_container
    back, _ = parse_container(em)
    again = api.version_for(back.graphs["templu"], "rm_podio", list(PH.USES))
    assert again["entry"]["url"] == "versions/PODIO@lod0-heriverse.glb"
    with zipfile.ZipFile(report["zip"]) as zf:
        assert {"em.json", "project.json", "versions/PODIO@lod0-heriverse.glb"} <= set(zf.namelist())


def test_bytes_that_are_not_the_version_stay_out(tmp_path):
    g, web, heri, cache, blend_dir = _study(tmp_path)
    plan = PH.plan_for(g, ["rm_podio"])
    rows = PH.disk_plan(plan, finder=lambda row: {"path": "", "said": "not on this disk"})["rows"]
    # not here, and the node gives other bytes: left out, and said
    report = PH.write_package(str(tmp_path / "p"), PH.heriverse_document({"t": g}), rows,
                              fetch=lambda ref: (b"not the version", "model/gltf-binary"))
    assert report["written"] == []
    assert "not the registered version" in report["failed"][0]["why"]
    assert not (tmp_path / "p" / "versions" / "PODIO@lod0-heriverse.glb").exists()
    # the node gives the right ones: in, from the node
    good = (cache / "podio@heriverse.glb").read_bytes()
    report = PH.write_package(str(tmp_path / "q"), PH.heriverse_document({"t": g}), rows,
                              fetch=lambda ref: (good, "model/gltf-binary"))
    assert [(w["rel"], w["from"]) for w in report["written"]] == [
        ("versions/PODIO@lod0-heriverse.glb", "the node")]


def test_a_removed_model_is_not_published(tmp_path):
    g, *_ = _study(tmp_path)
    node = g.find_node_by_id("rm_arco")
    from s3dgraphy import crdt
    if not hasattr(crdt, "REMOVED_KEY"):
        pytest.skip("s3dgraphy without tombstones")
    node.data = dict(getattr(node, "data", {}) or {})
    node.data[crdt.REMOVED_KEY] = {"ts": "2026-10-05T10:00:00Z", "by": "test"}
    if not PH.is_removed(node):
        pytest.skip("this tombstone shape is not the library's")
    plan = PH.plan_for(g, ["rm_podio", "rm_arco"])
    assert plan["removed"] == 1
    em = PH.heriverse_document({"templu": g})
    assert "rm_arco" not in {n["id"] for n in em["graphs"]["templu"]["nodes"]}
