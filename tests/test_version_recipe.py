"""The recipe of a version and its stamp (E.D., 6 Oct 2026: «i parametri
diventano la ricetta della versione», R4 «il dtcstamp in ogni versione»).

Outside Blender, on real files: the recipe each category starts from (the old
Heriverse export's, read in its code), a glTF with its .bin and textures
registered as ONE version of several files, stamped before it is born and
checked member by member, made again as a revision, and written into the
package on disk with the proxies, the DosCo and the panorama.
"""

import hashlib
import importlib.util
import json
import os
import pathlib
import sys

import pytest

_REPO = pathlib.Path(__file__).resolve().parent.parent
_CHECKOUT = _REPO.parent / "s3Dgraphy" / "src"
if _CHECKOUT.is_dir():
    sys.path.insert(0, str(_CHECKOUT))

import version_recipe as VR  # noqa: E402

api = pytest.importorskip("s3dgraphy.api")
versions = pytest.importorskip("s3dgraphy.resources.versions")
if not hasattr(versions, "planned_version"):
    pytest.skip("s3dgraphy without the revisions of a version", allow_module_level=True)

import birth_stamp as bs  # noqa: E402
import resource_digest as rd  # noqa: E402
import version_stamp as VS  # noqa: E402
from s3dgraphy.graph import Graph  # noqa: E402
from s3dgraphy.nodes.representation_node import RepresentationModelNode  # noqa: E402

_spec = importlib.util.spec_from_file_location("_emtools_publication_heriverse_r",
                                               _REPO / "publication_heriverse.py")
PH = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = PH
_spec.loader.exec_module(PH)

VIEWER = ["aton", "heriverse"]


# ── R2 · the recipe, by category ────────────────────────────────────────────

def test_the_old_exports_defaults_by_category():
    rm, doc, sf = (VR.defaults(c, VIEWER) for c in ("rm", "rmdoc", "rmsf"))
    # a glTF with its textures, the model as it is, no Draco (Q5), for every one
    for r in (rm, doc, sf):
        assert r["format"] == "gltf_separate" and r["draco"] is False and r["ratio"] == 1.0
        assert r["animations"] == "none"
    # RM and RMSF: the placement in the glTF, as `use_selection` wrote it
    assert rm["transform"] == sf["transform"] == "world"
    assert rm["max_texture_px"] == sf["max_texture_px"] == 0
    # RMDoc: «Preserve Transforms», «Compress Textures» 2048 px, quality 60
    assert doc["transform"] == "node"
    assert (doc["max_texture_px"], doc["jpeg_quality"]) == (2048, 60)
    # not for a viewer: what «Prepare for a use…» did before
    web = VR.defaults("rm", ["web"])
    assert (web["format"], web["transform"], web["draco"]) == ("glb", "local", True)


def test_a_recipe_is_checked_and_draco_never_goes_to_a_viewer():
    rec = VR.checked(dict(VR.defaults("rm", VIEWER), draco=True), VIEWER)
    assert rec["draco"] is False
    with pytest.raises(ValueError, match="transform"):
        VR.checked(dict(VR.defaults("rm", VIEWER), transform="sideways"), VIEWER)
    assert VR.category_of(doc_node_id="D.12") == "rmdoc"
    assert VR.category_of(in_anastylosis=True) == "rmsf"
    assert VR.category_of() == "rm"


def test_the_step_records_the_recipe_and_what_was_measured():
    rec = VR.checked(VR.defaults("rmdoc", VIEWER), VIEWER)
    params = VR.step_parameters(rec, applied={"textures_resized": 1, "reencoded": 2,
                                              "size_bytes": 1234, "files": 4})
    assert VR.recipe_of_step(params) == {k: rec[k] for k in VR.KEYS}
    assert params["textures_resized"] == 1 and params["files"] == 4
    assert VR.technique_of(rec, resized=1, reencoded=2) == "texture_reduction"
    assert VR.technique_of(VR.defaults("rm", VIEWER), resized=0, reencoded=0) \
        == "format_conversion"
    assert "RMDOC" in VR.said(rec) and "JPEG 60" in VR.said(rec)
    # the stamp takes the scalars only (a placement goes in the graph's step)
    assert VS.scalar_parameters({"a": 1, "placement": {"x": 1}}) == {"a": 1}


# ── R3 · a glTF with its textures, one version of several files ─────────────

GLTF = {"asset": {"version": "2.0"},
        "buffers": [{"uri": "PODIO.bin", "byteLength": 4}],
        "images": [{"uri": "textures/podio.jpg"}]}


def _write_set(folder: pathlib.Path, texture: bytes = b"jpeg bytes"):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "PODIO.gltf").write_text(json.dumps(GLTF), encoding="utf-8")
    (folder / "PODIO.bin").write_bytes(b"\x00\x01\x02\x03")
    (folder / "textures").mkdir(exist_ok=True)
    (folder / "textures" / "podio.jpg").write_bytes(texture)
    return folder / "PODIO.gltf"


def _files_of(entry: pathlib.Path):
    """`asset_versions.files_of_entry` without Blender: dtcstamp's members."""
    found = rd.dtcstamp().follow_references(str(entry))
    out = []
    for m in sorted(found["members"], key=lambda m: (m["path"] != entry.name, m["path"])):
        spec = {"path": m["path"], "url": str(entry.parent / m["path"]),
                "checksum": m["digest"], "size_bytes": m["size_bytes"],
                "role": "entry_point" if m["path"] == entry.name else "member"}
        out.append(spec)
    return out


def _podio():
    g = Graph("templu")
    api.add_resource(g, resource_id="podio", name="OB_PODIO", kind="3d_model",
                     tier="master", files=[{"path": "x.blend",
                                            "url": "blend://x.blend#Object/OB_PODIO"}])
    g.add_node(RepresentationModelNode("rm", name="PODIO"))
    g.add_edge("rm~podio", "rm", "podio", "has_linked_resource")
    return g


def _born(g, files, *, revise=False, writer=None):
    """What `add_version_from_mesh` does: the stamp first, then the version."""
    plan = versions.planned_version(g, "podio", files=files, revise=revise)
    master = {"resource_id": "podio", "label": "OB_PODIO",
              "locator": "blend://x.blend#Object/OB_PODIO",
              "blend_digest": "sha256:" + "b" * 64, "blend_saved": True,
              "fingerprint": "struct:f=12:v=8"}
    rec = VR.checked(VR.defaults("rm", VIEWER), VIEWER)
    params = VR.step_parameters(rec, applied={"files": len(files)})
    revision_of = None
    if plan["revises"]:
        revision_of = {"resource_id": plan["revises"],
                       "digest": g.find_node_by_id(plan["revises"]).data["checksum"]}
    stamped = VS.stamp_version(VS.entry_of(files), version_id=plan["version_id"],
                               inputs=VS.inputs_for(g, "podio", master=master),
                               technique="format_conversion", parameters=params,
                               label="PODIO for aton, heriverse",
                               expected_digest=rd.members_digest(files),
                               revision_of=revision_of, stamp_export=writer)
    if not stamped["ok"]:
        return None, stamped
    out = api.add_version(g, "podio", use=VIEWER, packaging="file_set", files=files,
                          technique="format_conversion", parameters=params,
                          revise=revise)
    VS.record(g, out["version_id"], stamped)
    return out, stamped


def test_a_gltf_version_is_born_stamped_and_its_stamp_checks_its_files(tmp_path):
    g = _podio()
    files = _files_of(_write_set(tmp_path / "PODIO@lod0-heriverse-heriverse-x"))
    assert [f["path"] for f in files] == ["PODIO.gltf", "PODIO.bin", "textures/podio.jpg"]
    out, stamped = _born(g, files)
    v = g.find_node_by_id(out["version_id"])
    # the graph and the stamp name the same bytes: the members digest
    assert v.data["checksum"] == rd.members_digest(files) == stamped["stamp"]["self"]["digest"]
    assert v.data["url"].endswith("PODIO.gltf")
    assert v.data[VS.RECEIPT_KEY]["id"] == out["version_id"]
    assert v.data[VS.RECEIPT_KEY]["checksum"] == v.data["checksum"]
    stamp = json.loads(pathlib.Path(stamped["stamp_path"]).read_text())
    assert stamp["self"]["packaging"] == "file_set"
    assert stamp["how"]["dtc_kind"] in ("lod_generation", "decimation")
    assert stamp["how"]["parameters"]["format"] == "gltf_separate"
    assert stamp["how"]["parameters"]["transform"] == "world"
    assert [p["resource_id"] for p in stamp["from"]] == ["podio"]
    # «Where it comes from»: the stamp is there, the bytes are the stamped
    # ones, and its `from` is the step's input (the mother)
    st = VS.check(g, out["version_id"])
    assert st["state"] == "ok" and st["mother"], st
    assert VS.said(st).startswith("stamp ✓")
    # a texture changed behind the door: the stamp says so
    (tmp_path / "PODIO@lod0-heriverse-heriverse-x" / "textures" / "podio.jpg").write_bytes(b"other")
    import resource_seal
    resource_seal.forget()
    st = VS.check(g, out["version_id"])
    assert st["state"] == "differs" and "textures/podio.jpg" in st["line"]


def test_no_stamp_no_version(tmp_path):
    g = _podio()
    files = _files_of(_write_set(tmp_path / "v"))
    n = len(g.nodes)

    def failing(path, **kw):
        return {"state": "failed", "line": "the disk is read-only"}
    out, stamped = _born(g, files, writer=failing)
    assert out is None and "read-only" in stamped["why"]
    assert len(g.nodes) == n
    # a stamp that measures other bytes than the graph would register
    wrong = dict(files[1], checksum="sha256:" + "e" * 64)
    out, stamped = _born(g, [files[0], wrong, files[2]])
    assert out is None and "registers" in stamped["why"]


def test_made_again_with_another_recipe_it_is_a_revision_and_its_stamp_says_so(tmp_path):
    g = _podio()
    glb = tmp_path / "PODIO.glb"
    glb.write_bytes(b"glTF binary, the old version for Heriverse")
    old = api.add_version(g, "podio", use=VIEWER, files=[{
        "path": "PODIO.glb", "url": str(glb),
        "checksum": "sha256:" + hashlib.sha256(glb.read_bytes()).hexdigest()}])
    files = _files_of(_write_set(tmp_path / "set"))
    out, stamped = _born(g, files, revise=True)
    assert out["revises"] == old["version_id"]
    assert stamped["stamp"]["self"]["was_revision_of"]["resource_id"] == old["version_id"]
    choice = api.version_for(g, "rm", PH.USES)
    assert choice["entry"]["id"] == out["version_id"]


# ── the package on disk ─────────────────────────────────────────────────────

def test_the_package_carries_the_gltf_set_its_rmdoc_url_proxies_dosco_panorama(tmp_path):
    g = _podio()
    files = _files_of(_write_set(tmp_path / "cache" / "PODIO-set"))
    out, _ = _born(g, files)
    # an RMDoc whose version is the same set (Heriverse opens it by its own url)
    from s3dgraphy.nodes.representation_node import RepresentationModelDocNode
    g.add_node(RepresentationModelDocNode(node_id="D12_rm_doc", name="RM for D.12",
                                          type="RM", transform=None))
    g.add_edge("D12~podio", "D12_rm_doc", "podio", "has_linked_resource")
    proxy = tmp_path / "proxies" / "SU002.glb"
    proxy.parent.mkdir()
    proxy.write_bytes(b"proxy glb")
    api.add_resource(g, resource_id="px", name="SU002", kind="proxy_model", files=[{
        "path": "SU002.glb", "url": "proxies/SU002.glb",
        "checksum": "sha256:" + hashlib.sha256(b"proxy glb").hexdigest()}])
    dosco = tmp_path / "DosCo"
    dosco.mkdir()
    (dosco / "D.12.jpg").write_bytes(b"photo")
    api.add_resource(g, resource_id="photo", name="D.12", kind="image",
                     files=[{"path": "D.12.jpg", "url": str(dosco / "D.12.jpg")}])
    sky = tmp_path / "defsky.jpg"
    sky.write_bytes(b"sky")
    plan = PH.plan_for(g, [("rm", "PODIO", "rm"), ("D12_rm_doc", "D.12", "rmdoc")])
    assert [r["category"] for r in plan["ready"]] == ["rm", "rmdoc"]
    assert len(plan["ready"][0]["files"]) == 3
    disk = PH.disk_plan(plan, finder=lambda r: PH.local_bytes(r, roots=[str(tmp_path)]))
    assert [r["local_said"] for r in disk["rows"]] == ["on this disk"] * 2
    assert disk["rows"][0]["rel"] == "versions/PODIO@lod0-heriverse/PODIO.gltf"
    doc = {"graphs": {"g": json.loads(json.dumps(
        __import__("s3dgraphy.container", fromlist=["x"]).build_container(
            __import__("s3dgraphy.container", fromlist=["x"]).Container(
                graphs={"g": g}, active_graph_id="g"))["graphs"]["g"]))}}
    dest = tmp_path / "pkg"
    report = PH.write_package(str(dest), doc, disk["rows"], make_zip=True, extras={
        "proxies": [{"id": "px", "name": "SU002", "path": str(proxy),
                     "checksum": "sha256:" + hashlib.sha256(b"proxy glb").hexdigest()}],
        "dosco": {"folder": str(dosco), "resources": {"photo": str(dosco / "D.12.jpg")}},
        "panorama": str(sky)})
    assert not report["failed"], report["failed"]
    for rel in ("PODIO.gltf", "PODIO.bin", "textures/podio.jpg"):
        assert (dest / "versions" / "PODIO@lod0-heriverse" / rel).is_file()
    written = json.loads((dest / "em.json").read_text())
    nodes = {n["id"]: n for n in written["graphs"]["g"]["nodes"]}
    assert nodes[out["version_id"]]["data"]["url"] == "versions/PODIO@lod0-heriverse/PODIO.gltf"
    assert nodes["D12_rm_doc"]["data"]["url"] == "versions/PODIO@lod0-heriverse/PODIO.gltf"
    file_urls = sorted(n["data"]["url"] for n in nodes.values()
                       if n.get("node_type") == "resource_file")
    assert file_urls == ["versions/PODIO@lod0-heriverse/PODIO.bin",
                         "versions/PODIO@lod0-heriverse/PODIO.gltf",
                         "versions/PODIO@lod0-heriverse/textures/podio.jpg"]
    assert nodes["px"]["data"]["url"] == "proxies/SU002.glb"
    assert nodes["photo"]["data"]["url"] == "dosco/D.12.jpg"
    assert written["graphs"]["g"]["defaults"]["panorama"] == "panorama/defsky.jpg"
    assert (dest / "panorama" / "defsky.jpg").is_file() and (dest / "dosco" / "D.12.jpg").is_file()
    assert report["zip"] and os.path.isfile(report["zip"])
    # a texture that is not the registered one keeps the set out of the package
    bad = tmp_path / "cache" / "PODIO-set" / "textures" / "podio.jpg"
    bad.write_bytes(b"changed")
    disk = PH.disk_plan(plan, finder=lambda r: PH.local_bytes(r, roots=[str(tmp_path)]))
    assert "1 of 3 files not on this disk" in disk["rows"][0]["local_said"]


def test_the_rmdoc_textures_follow_the_settings_the_scene_kept():
    """Measured on Templu Mare v2: the .blend keeps max 1024 px, quality 60 —
    what the old exporter applied there, not its properties' defaults."""
    class Scene:
        heriverse_rmdoc_texture_max_res = 1024
        heriverse_rmdoc_texture_quality = 60
        heriverse_paradata_texture_compression = True
    doc = VR.defaults("rmdoc", VIEWER, VR.scene_values(Scene()))
    assert (doc["max_texture_px"], doc["jpeg_quality"]) == (1024, 60)
    Scene.heriverse_paradata_texture_compression = False
    doc = VR.defaults("rmdoc", VIEWER, VR.scene_values(Scene()))
    assert (doc["max_texture_px"], doc["jpeg_quality"]) == (0, 0)
    assert VR.defaults("rm", VIEWER, VR.scene_values(Scene()))["max_texture_px"] == 0


def test_the_package_document_leaves_out_the_models_not_published():
    """Measured on Templu Mare v2: left in, Heriverse asked for the versions of
    the 97 models not published, outside the package — a 404 each."""
    g = _podio()
    g.add_node(RepresentationModelNode("rm_off", name="OFF"))
    g.add_edge("rm_off~podio", "rm_off", "podio", "has_linked_resource")
    doc = PH.heriverse_document({"templu": g}, unpublished=["rm_off"])
    nodes = {n["id"] for n in doc["graphs"]["templu"]["nodes"]}
    edges = {e["id"] for e in doc["graphs"]["templu"]["edges"]}
    assert "rm" in nodes and "rm_off" not in nodes and "rm_off~podio" not in edges
