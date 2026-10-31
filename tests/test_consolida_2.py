"""MICRO-CONSOLIDA-2 (31 Oct 2026) · EM Tools' half, bpy-free: the Deck's
«Consolidate for…» passes the measures of the files on this disk and the
files modified after their stamp, says why the web loads what it loads
(lightness by default), offers «Register as a new version» and «Declare the
master…» on the rows that ask for them."""

import hashlib
import importlib.util
import pathlib
import sys

import pytest

_REPO = pathlib.Path(__file__).resolve().parent.parent
_CHECKOUT = _REPO.parent / "s3Dgraphy" / "src"
if _CHECKOUT.is_dir():
    sys.path.insert(0, str(_CHECKOUT))

_spec = importlib.util.spec_from_file_location("_emtools_publication_heriverse_c2",
                                               _REPO / "publication_heriverse.py")
PH = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = PH
_spec.loader.exec_module(PH)

C = pytest.importorskip("s3dgraphy.resources.consolidate")
if not hasattr(C, "web_choice"):
    pytest.skip("s3dgraphy ≤ dev80: no lightness by default", allow_module_level=True)


def _sha(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _study(tmp_path):
    from s3dgraphy import api
    from s3dgraphy.graph import Graph
    from s3dgraphy.nodes.group_node import RepresentationModelNodeGroup
    from s3dgraphy.nodes.representation_node import RepresentationModelNode
    g = Graph("c2")
    api.add_resource(g, name="col", kind="3d_model", tier="master",
                     files=[{"path": "col.blend", "checksum": _sha(b"blend")}], resource_id="col")
    f = tmp_path / "col@lod0.glb"
    f.write_bytes(b"stamped")
    v0 = api.add_version(g, "col", level="lod0", use=["heriverse", "aton"],
                         primitives={"triangles": 1_200_000, "vertices": 600_000},
                         measures={"texture_count": 2, "texture_side_px": 4096},
                         files=[{"path": str(f), "checksum": _sha(b"stamped")}], size_bytes=7)
    v1 = api.add_version(g, v0["version_id"], level="lod1", use=["realtime", "web"],
                         primitives={"triangles": 26_682, "vertices": 15_000},
                         measures={"texture_count": 2, "texture_side_px": 1024},
                         files=[{"path": "col@lod1.glb", "checksum": _sha(b"lod1")}], size_bytes=3)
    g.add_node(RepresentationModelNode(node_id="rm_col", name="COL"))
    g.add_edge("rm_col_r", "rm_col", "col", "has_linked_resource")
    api.add_resource(g, name="tiles.zip", kind="3d_model", tier="master",
                     files=[{"path": "t.zip", "checksum": _sha(b"zip")}], resource_id="tz")
    t = api.add_version(g, "tz", level="lod0", use=["web", "heriverse"],
                        files=[{"path": "T/tileset.json", "checksum": _sha(b"tileset")}])
    g.add_node(RepresentationModelNodeGroup(node_id="grp", name="Survey"))
    g.add_edge("grp_tz", "grp", "tz", "has_linked_resource")
    return g, v0, v1, t, f


def test_the_deck_measures_says_why_and_offers_the_new_gestures(tmp_path):
    g, v0, v1, t, f = _study(tmp_path)
    f.write_bytes(b"touched after the stamp")
    from s3dgraphy.resources.locate import resolve_graph
    hasher = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()  # noqa: E731
    res = resolve_graph(g, base_dirs=[str(tmp_path)], hasher=hasher, verify=True)
    disk = PH.disk_measures(res)
    assert set(disk) == {"measure", "changed"} and v0["version_id"] in disk["changed"]
    got = PH.consolidation(g, [("rm_col", "COL"), ("grp", "")], measure=disk["measure"],
                           changed=disk["changed"])
    rows = {r["id"]: r for r in got["rows"]}
    col, grp = rows["rm_col"], rows["grp"]
    # no mobile base, the lod0 heavy (1,2 M, 4096 px: the scene over the band): the lightest for the web
    assert col["loaded_why"] == "lightest" and col["loaded"]["id"] == v1["version_id"]
    assert "(no base: the lightest for the web)" in PH.consolidation_row_line(col)
    acts = {a["kind"]: a for a in PH.row_actions(col)}
    assert acts["register_new_version"]["resource_id"] == v0["version_id"]
    assert acts["register_new_version"]["checksum_now"] == _sha(b"touched after the stamp")
    acts = {a["kind"]: a for a in PH.row_actions(grp)}
    assert acts["declare_master"]["resource_id"] == t["version_id"]
    assert acts["declare_master"]["container_id"] == "grp"
    assert grp["base"]["id"] == t["version_id"]       # a tileset's base: its lowest level


def test_an_older_consolidate_gets_no_new_keywords():
    seen = {}

    def old(graph, platform, *, models, states, in_room):
        seen.update(models=models)
        return {"rows": [], "counts": {}, "totals": {}, "say_it": ""}
    import types
    fake = types.SimpleNamespace(find_node_by_id=lambda i: object())
    got = PH.consolidation(fake, ["x"], fn=old, measure=lambda e: None, changed={})
    assert got["available"] and seen["models"] == ["x"]
