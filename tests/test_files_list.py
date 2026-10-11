"""Storage list · `files_list.build_rows`: master, versions by level, files of a set.
Pure Python over a small graph; the UIList is measured in Blender."""
import importlib.util
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parent.parent
_S3D = _REPO.parent / "s3Dgraphy" / "src"
if _S3D.is_dir():
    sys.path.insert(0, str(_S3D))


class _N:
    def __init__(self, nid, name, ntype, **data):
        self.node_id, self.name, self.node_type, self.data = nid, name, ntype, data


class _E:
    def __init__(self, s, t, typ):
        self.edge_source, self.edge_target, self.edge_type, self.attributes = s, t, typ, {}


class _G:
    def __init__(self, nodes, edges):
        self.nodes, self.edges = nodes, edges

    def find_node_by_id(self, i):
        return next((n for n in self.nodes if n.node_id == i), None)


def _load():
    spec = importlib.util.spec_from_file_location("files_list", _REPO / "sync_manager" / "files_list.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_rows_group_master_then_versions_then_files():
    fl = _load()
    g = _G([_N("m", "Column", "resource", tier="master", url="a.blend"),
            _N("v", "Column LOD0", "resource", tier="distribution", use=["web", "realtime"], url="c.glb"),
            _N("f", "set", "resource", url="x"),
            _N("rm", "SM_Column", "representation_model")],
           [_E("rm", "m", "has_linked_resource")])
    results = [{"id": "v", "state": "on_disk", "node_type": "resource", "name": "Column LOD0"},
               {"id": "m", "state": "missing", "node_type": "resource", "name": "Column"}]
    rows = fl.build_rows(g, results, {})
    assert [r["kind"] for r in rows][0] == "master"
    assert rows[0]["rm"] == "SM_Column" and rows[0]["state"] == "missing"
    ver = next(r for r in rows if r["id"] == "v")
    assert ver["kind"] == "version" and ver["use"] == "web,realtime"
    assert "web" in ver["search"] and "column" in ver["search"]
