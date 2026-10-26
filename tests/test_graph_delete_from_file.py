"""MICRO contenuti-workspace-elimina-grafo · deleting a graph from its em.json
in EM Tools (bpy-free half: `graph_origins.remove_from_file`; the Blender half
is tests/blender_smoke_graph_delete.py). The report is s3Dgraphy's
`remove_graph`, on the container a save of the file would write.
"""

import importlib.util
import json
import pathlib
import sys

import pytest

_REPO = pathlib.Path(__file__).resolve().parent.parent
_CHECKOUT = _REPO.parent / "s3Dgraphy" / "src"
if _CHECKOUT.is_dir():
    sys.path.insert(0, str(_CHECKOUT))
pytest.importorskip("s3dgraphy.graph_removal")

from s3dgraphy.container import Container, load_container_file, save_container_file  # noqa: E402
from s3dgraphy.graph import Graph  # noqa: E402
from s3dgraphy.graph_removal import GraphRemovalError  # noqa: E402
from s3dgraphy.links import add_link, links_of_graph  # noqa: E402
from s3dgraphy.nodes.stratigraphic_node import StratigraphicUnit  # noqa: E402
from s3dgraphy.resources.files import add_resource  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "_emtools_graph_origins_del", _REPO / "graph_origins.py")
go = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = go
_spec.loader.exec_module(go)


def _graph(gid, *units):
    g = Graph(graph_id=gid, name=f"Saggio {gid}")
    for name in units:
        g.add_node(StratigraphicUnit(node_id=f"{gid}-{name}", name=name))
    return g


@pytest.fixture
def study(tmp_path):
    """A.em.json: ga1 (US1, a file of its own), ga2 (US2, links to ga1), ga3."""
    a = tmp_path / "A.em.json"
    ga1, ga2, ga3 = _graph("ga1", "US1"), _graph("ga2", "US2"), _graph("ga3", "US3")
    ga1.add_node(add_resource(None, resource_id="r1", name="pianta",
                              files=[{"path": "rilievi/pianta.dxf"}]))
    shelf = Graph(graph_id="shelf")
    shelf.data = {"em_collection": "ShelfGraph"}
    cont = Container(graphs={"ga1": ga1, "ga2": ga2, "ga3": ga3}, shelf=shelf,
                     active_graph_id="ga1", header={"visibility": "public"})
    add_link(cont, ("ga2", "ga2-US2"), ("ga1", "ga1-US1"), "is_after")
    save_container_file(cont, str(a))
    go.forget_all()
    loaded, _ = load_container_file(str(a))
    go.remember(str(a), loaded)
    # the scene: ga1 and ga2 have rows (their graphs live in the manager), ga3
    # was never opened here
    scene = {"ga1": loaded.graphs["ga1"], "ga2": loaded.graphs["ga2"]}
    return a, scene


def test_the_report_is_s3dgraphy_s_and_nothing_changes(study):
    a, scene = study
    before = a.read_bytes()
    rep = go.remove_from_file(str(a), "ga1", ["ga1", "ga2"], scene.get, dry_run=True)
    assert rep["applied"] is False and rep["graph_id"] == "ga1"
    assert [l["graph_id"] for l in rep["links_in"]] == ["ga2"]
    assert rep["files_alone"] == ["rilievi/pianta.dxf"]
    assert rep["active_graph_id"] == "ga2"
    assert a.read_bytes() == before
    assert "ga1" in go.remembered(str(a)).graphs


def test_the_next_save_no_longer_holds_it(study, tmp_path):
    a, scene = study
    rep = go.remove_from_file(str(a), "ga1", ["ga1", "ga2"], scene.get)
    assert rep["applied"] is True
    # the scene's ga2 carries the link, marked
    [link] = links_of_graph(scene["ga2"])
    assert link["attributes"]["target_graph_removed"] == "ga1"
    # the row of ga1 is gone from the scene: the save writes ga2 (scene) + ga3
    go.save_file(str(a), ["ga2"], scene.get)
    doc = json.loads(a.read_text())
    assert set(doc["graphs"]) == {"ga2", "ga3", "shelf"}
    assert doc["active_graph_id"] == "ga2"
    assert doc["header"]["visibility"] == "public"
    assert doc["graphs"]["ga2"]["links"][0]["attributes"]["target_graph_removed"] == "ga1"
    # the file on disk next to it is never touched
    assert not (tmp_path / "rilievi").exists()


def test_dropped_links_and_a_graph_never_opened(study):
    a, scene = study
    go.remove_from_file(str(a), "ga3", ["ga1", "ga2"], scene.get, links="drop")
    go.save_file(str(a), ["ga1", "ga2"], scene.get)
    assert set(json.loads(a.read_text())["graphs"]) == {"ga1", "ga2", "shelf"}


def test_refusals(study):
    a, scene = study
    with pytest.raises(GraphRemovalError):
        go.remove_from_file(str(a), "shelf", ["ga1", "ga2"], scene.get, dry_run=True)
    go.remove_from_file(str(a), "ga3", ["ga1", "ga2"], scene.get)
    go.remove_from_file(str(a), "ga2", ["ga1", "ga2"], scene.get)
    with pytest.raises(GraphRemovalError):
        go.remove_from_file(str(a), "ga1", ["ga1"], scene.get, dry_run=True)


def test_periodizations_survive_a_save(tmp_path):
    """Found on the way: save_file dropped a container's periodizations."""
    from s3dgraphy.periodization import new_periodizations, add_periodization
    a = tmp_path / "P.em.json"
    per = new_periodizations()
    add_periodization(per, "Roman")
    save_container_file(Container(graphs={"g": _graph("g", "US1")},
                                  periodizations=per, active_graph_id="g"), str(a))
    go.forget_all()
    loaded, _ = load_container_file(str(a))
    go.remember(str(a), loaded)
    go.save_file(str(a), ["g"], {"g": loaded.graphs["g"]}.get)
    back, _ = load_container_file(str(a))
    assert back.periodizations is not None


def test_objects_of_graph_by_name():
    g = _graph("ga1", "US1", "US2")
    names = ["GT16.US1", "US2", "Camera", "GT16.US99"]
    assert go.objects_of_graph(g, names, "GT16") == ["GT16.US1", "US2"]
    assert go.objects_of_graph(g, names) == ["US2"]
