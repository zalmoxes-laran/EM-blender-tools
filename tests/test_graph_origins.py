"""M1 · the tree «file or room → graphs», and saving each graph back to its own
file (bpy-free half; the Blender half is tests/blender_smoke_multigraph_tree.py).
"""

import hashlib
import importlib.util
import json
import pathlib
import sys
from types import SimpleNamespace as Row

import pytest

_REPO = pathlib.Path(__file__).resolve().parent.parent
_CHECKOUT = _REPO.parent / "s3Dgraphy" / "src"
if _CHECKOUT.is_dir():
    sys.path.insert(0, str(_CHECKOUT))
pytest.importorskip("s3dgraphy.container")

from s3dgraphy.container import (Container, load_container_file,  # noqa: E402
                                 save_container_file)
from s3dgraphy.graph import Graph  # noqa: E402
from s3dgraphy.nodes.stratigraphic_node import StratigraphicUnit  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "_emtools_graph_origins", _REPO / "graph_origins.py")
go = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = go
_spec.loader.exec_module(go)


def sha(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


def _graph(gid, *units):
    g = Graph(graph_id=gid)
    for name in units:
        g.add_node(StratigraphicUnit(node_id=f"{gid}-{name}", name=name))
    return g


def _shelf():
    s = Graph(graph_id="shelf")
    s.data = {"em_collection": "ShelfGraph"}
    return s


@pytest.fixture
def two_files(tmp_path):
    a = tmp_path / "A.em.json"
    b = tmp_path / "B.em.json"
    save_container_file(Container(graphs={"ga1": _graph("ga1", "US1"),
                                          "ga2": _graph("ga2", "US2")},
                                  shelf=_shelf(), active_graph_id="ga1",
                                  header={"visibility": "public"}), str(a))
    save_container_file(Container(graphs={"gb": _graph("gb", "US9")},
                                  shelf=_shelf(), active_graph_id="gb"), str(b))
    go.forget_all()
    return a, b


def test_a_slot_relative_to_the_blend_is_the_origin_after_a_move(tmp_path):
    """Templu Mare v2 (6 Oct 2026): the folder was handed on, the row kept the
    absolute origin recorded where it was born; the tree, «Save» and the study
    went there. The slot `//../EM/x.em.json` is where the graph is now."""
    born = tmp_path / "born" / "EM" / "x.em.json"
    here = tmp_path / "handed-on" / "SB"
    row = Row(name="g", origin_kind="FILE", origin_path=str(born),
              graphml_path="//../EM/x.em.json")
    abspath = lambda p: str(here / p[2:]) if p.startswith("//") else p  # noqa: E731
    origin = go.origin_of(row, abspath=abspath)
    assert origin.path == str(tmp_path / "handed-on" / "EM" / "x.em.json")
    assert go.file_path_of(row) == "//../EM/x.em.json"
    # an absolute slot keeps the recorded origin, as before
    fixed = Row(name="g", origin_kind="FILE", origin_path=str(born),
                graphml_path=str(tmp_path / "elsewhere.em.json"))
    assert go.origin_of(fixed).path == str(born)


def test_rows_without_an_origin_take_it_from_their_path(tmp_path):
    old = Row(name="g", graphml_path=str(tmp_path / "x.graphml"))
    origin = go.origin_of(old)
    assert origin.is_file and origin.path.endswith("x.graphml")
    assert go.origin_of(Row(name="h")).kind == go.KIND_NONE
    room = Row(name="r", origin_kind="ROOM", origin_room="tempio-grande",
               origin_node="https://em.localhost:8443", graphml_path="")
    assert go.origin_of(room).label == "room tempio-grande on em.localhost:8443"


def test_two_containers_make_a_two_branch_tree(two_files):
    a, b = two_files
    rows = [Row(name="ga1", origin_kind="FILE", origin_path=str(a)),
            Row(name="gb", origin_kind="FILE", origin_path=str(b)),
            Row(name="ga2", graphml_path=str(a))]          # an old row: migrated
    branches = go.tree(rows)
    assert [o.label for o, _ in branches] == ["A.em.json", "B.em.json"]
    assert [ix for _, ix in branches] == [[0, 2], [1]]
    assert go.members_of(rows, branches[0][0]) == ["ga1", "ga2"]


def test_saving_one_file_leaves_the_other_byte_identical(two_files):
    a, b = two_files
    live = {}
    for path in (a, b):
        container, _ = load_container_file(str(path))
        go.remember(str(path), container)
        live.update(container.graphs)
    before = {"A": sha(a), "B": sha(b)}

    # an edit to the graph of B only, then «Save» of B's origin
    live["gb"].add_node(StratigraphicUnit(node_id="gb-US10", name="US10"))
    res = go.save_file(str(b), ["gb"], live.get, active_graph_id="gb")

    assert sha(a) == before["A"], "A was not touched"
    assert sha(b) != before["B"], "B carries the edit"
    assert res.written == ["gb"] and res.shelf
    back, _ = load_container_file(str(b))
    assert set(back.graphs) == {"gb"}, "B holds its own graph only"
    assert any(n.node_id == "gb-US10" for n in back.graphs["gb"].nodes)
    assert back.shelf is not None


def test_a_graph_not_open_here_is_written_back_unchanged(two_files):
    a, _b = two_files
    container, _ = load_container_file(str(a))
    go.remember(str(a), container)
    live = {"ga1": container.graphs["ga1"]}          # ga2 closed in the scene
    res = go.save_file(str(a), ["ga1"], live.get)
    assert res.written == ["ga1"] and res.retained == ["ga2"]
    back, _ = load_container_file(str(a))
    assert set(back.graphs) == {"ga1", "ga2"}
    assert back.header.get("visibility") == "public", "the header survives"
    assert "kept unchanged" in res.sentence()


def test_the_same_graph_from_two_files_is_a_conflict(two_files, tmp_path):
    a, b = two_files
    rows = [Row(name="ga1", origin_kind="FILE", origin_path=str(a))]
    copy = tmp_path / "copy.em.json"
    copy.write_text(a.read_text())
    ids = go.peek_graph_ids(str(copy))
    assert ids == ["ga1", "ga2"], "the shelf is not a graph that can clash"
    clash = go.conflicts(ids, rows, go.file_origin(str(copy)))
    assert [g for g, _ in clash] == ["ga1"]
    # reloading the SAME file is not a conflict
    assert go.conflicts(ids, rows, go.file_origin(str(a))) == []


def test_a_legacy_single_graph_file_is_peeked_too(tmp_path):
    p = tmp_path / "one.em.json"
    p.write_text(json.dumps({"header": {}, "graph": {"graph_id": "solo",
                                                       "nodes": [], "edges": []}}))
    assert go.peek_graph_ids(str(p)) == ["solo"]
