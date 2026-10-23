"""MICRO georiferimento dal grafo (23 Oct 2026) — the graph's GeoPositionNode
is READ when a graph opens, not only written.

Measured before: the GT16 (``TempluMare_v4.em.json``) carries a GeoPositionNode
with an EPSG and a shift, and in Blender the Georeferencing panel showed an
empty EPSG and a zero shift — the node was a passive mirror, written by «Push to
GeoNode» and never read back.

Pinned here, outside Blender (``graph_sync`` imports ``bpy`` only inside
``get_active_graph``; ``scene.em_georef`` is a plain namespace):

- an empty scene (no EPSG, shift 0) takes the graph's values on opening;
- a scene already georeferenced with other values is NOT overwritten: the
  differences are listed, and the pull is an explicit second step;
- «Push to GeoNode» links the node to the graph's «Graph paradata» group with
  ``is_in_paradata_nodegroup`` (like author, licence, embargo), once;
- all of it survives an em.json round trip;
- G1: a graph that is not the scene's reference graph does not write the scene.
"""

import importlib.util
import pathlib
import sys
import types

import pytest

_REPO = pathlib.Path(__file__).resolve().parent.parent
_CHECKOUT = _REPO.parent / "s3Dgraphy" / "src"
if _CHECKOUT.is_dir():
    sys.path.insert(0, str(_CHECKOUT))

s3dgraphy_api = pytest.importorskip(
    "s3dgraphy.api", reason="s3dgraphy not importable (checkout or wheel)")
from s3dgraphy.graph import Graph  # noqa: E402
from s3dgraphy.importer.emjson_importer import materialize_graph_scope  # noqa: E402


def _load_graph_sync():
    spec = importlib.util.spec_from_file_location(
        "_emtools_test_graph_sync_open", _REPO / "georef_manager" / "graph_sync.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


graph_sync = _load_graph_sync()

#: the GT16 as corrected on 23 Oct (E.D.): EPSG:3844, shift Z 0
GT16 = ("3844", 327372.56, 448682.65, 0.0)


def _scene(epsg="", x=0.0, y=0.0, z=0.0, rotation=0.0):
    return types.SimpleNamespace(epsg=epsg, shift_x=x, shift_y=y, shift_z=z,
                                 rotation=rotation, graph_note="",
                                 reference_graph="")


def _graph(gid="gt16", georef=GT16, with_rights=True):
    graph = Graph(graph_id=gid)
    if with_rights:
        materialize_graph_scope(graph, author="E. D.", license="CC-BY-NC")
    node = graph_sync.get_geo_node(graph)
    if georef is not None:
        node.data.update({"epsg": int(georef[0]), "shift_x": georef[1],
                          "shift_y": georef[2], "shift_z": georef[3]})
    return graph


def _geo_edges(graph):
    node = graph_sync.get_geo_node(graph)
    return [e for e in graph.edges if e.edge_source == node.node_id
            and e.edge_type == "is_in_paradata_nodegroup"]


# ── opening ──────────────────────────────────────────────────────────────────

def test_an_empty_scene_takes_the_graphs_georeferencing():
    g = _scene()
    res = graph_sync.adopt_on_open(g, _graph())
    assert res["outcome"] == "adopted"
    assert (g.epsg, g.shift_x, g.shift_y, g.shift_z) == GT16
    assert "read from graph gt16" in res["sentence"]


def test_a_scene_with_the_same_values_is_left_alone():
    g = _scene(*GT16)
    assert graph_sync.adopt_on_open(g, _graph())["outcome"] == "same"


def test_a_different_scene_is_not_overwritten_and_the_difference_is_said():
    g = _scene("31700", 327300.0, 448370.0, 500.0)
    res = graph_sync.adopt_on_open(g, _graph())
    assert res["outcome"] == "differs"
    assert (g.epsg, g.shift_x, g.shift_y, g.shift_z) == ("31700", 327300.0, 448370.0, 500.0)
    fields = [d[0] for d in res["differences"]]
    assert fields == ["epsg", "shift_x", "shift_y", "shift_z"]
    assert res["differences"][0] == ("epsg", "31700", "3844")


def test_the_pull_is_explicit_and_then_the_two_agree():
    g = _scene("31700", 327300.0, 448370.0, 500.0)
    graph = _graph()
    graph_sync.write_scene(g, graph_sync.pull_from_geonode(graph))
    assert graph_sync.differences(graph_sync.scene_values(g),
                                  graph_sync.pull_from_geonode(graph)) == []
    assert g.epsg == "3844" and g.shift_z == 0.0


def test_a_shift_without_epsg_is_already_georeferenced():
    """«Not georeferenced» is EPSG unset AND shift 0: a scene with a shift but
    no EPSG was set by someone, and is not silently replaced."""
    g = _scene("", 100.0, 0.0, 0.0)
    assert graph_sync.adopt_on_open(g, _graph())["outcome"] == "differs"


def test_a_graph_without_georeferencing_changes_nothing():
    g = _scene()
    res = graph_sync.adopt_on_open(g, _graph(georef=None))
    assert res["outcome"] == "graph-empty"
    assert g.epsg == "" and g.shift_x == 0.0


def test_only_the_reference_graph_writes_the_scene():
    g = _scene()
    g.reference_graph = "other"
    em_tools = types.SimpleNamespace(graphml_files=[object(), object()])
    scene = types.SimpleNamespace(em_georef=g, em_tools=em_tools)
    logged = []
    res = graph_sync.on_graph_opened(scene, _graph(),
                                     log=lambda m, level="INFO": logged.append((level, m)))
    assert res["outcome"] == "not-reference"
    assert g.epsg == ""
    assert "not the scene's reference graph" in g.graph_note
    assert logged


def test_on_graph_opened_writes_the_panel_line():
    g = _scene()
    scene = types.SimpleNamespace(em_georef=g,
                                  em_tools=types.SimpleNamespace(graphml_files=[object()]))
    res = graph_sync.on_graph_opened(scene, _graph(), log=lambda *a, **k: None)
    assert res["outcome"] == "adopted"
    assert g.graph_note.startswith("Georeferencing read from graph gt16")


# ── push links the node to «Graph paradata» ──────────────────────────────────

def test_push_links_the_node_to_graph_paradata_like_the_licence():
    graph = _graph(georef=None)
    assert _geo_edges(graph) == []
    assert graph_sync.push_to_geonode(graph, *GT16) is True
    edges = _geo_edges(graph)
    assert len(edges) == 1
    pdg = graph.find_node_by_id(edges[0].edge_target)
    assert pdg.name == "Graph paradata"
    licence = [e for e in graph.edges if e.edge_type == "is_in_paradata_nodegroup"
               and graph.find_node_by_id(e.edge_source).node_type == "license"]
    assert licence and licence[0].edge_target == pdg.node_id, \
        "the same group as the licence"
    node = graph_sync.get_geo_node(graph)
    assert edges[0].edge_id == f"{node.node_id}__is_in_paradata_nodegroup__{pdg.node_id}"


def test_push_twice_links_once():
    graph = _graph(georef=None)
    graph_sync.push_to_geonode(graph, *GT16)
    graph_sync.push_to_geonode(graph, *GT16)
    assert len(_geo_edges(graph)) == 1


def test_push_on_a_graph_without_rights_creates_the_group():
    graph = _graph(georef=None, with_rights=False)
    graph_sync.push_to_geonode(graph, *GT16)
    edges = _geo_edges(graph)
    assert len(edges) == 1
    pdg = graph.find_node_by_id(edges[0].edge_target)
    assert pdg.node_id == "gt16_graph_paradata"
    roots = [n for n in graph.nodes if n.node_type == "graph"]
    assert len(roots) == 1
    assert any(e.edge_type == "has_paradata_nodegroup" and e.edge_source == roots[0].node_id
               and e.edge_target == pdg.node_id for e in graph.edges)


# ── em.json round trip ───────────────────────────────────────────────────────

def test_the_link_and_the_values_survive_an_emjson_round_trip():
    graph = _graph(georef=None)
    graph_sync.push_to_geonode(graph, *GT16)
    doc = s3dgraphy_api.graph_to_emjson(graph)
    reloaded, _w = s3dgraphy_api.load_emjson(doc)
    assert len(_geo_edges(reloaded)) == 1
    g = _scene()
    assert graph_sync.adopt_on_open(g, reloaded)["outcome"] == "adopted"
    assert (g.epsg, g.shift_x, g.shift_y, g.shift_z) == GT16
    # and pushing the reloaded graph again does not add a second edge
    graph_sync.push_to_geonode(reloaded, *GT16)
    assert len(_geo_edges(reloaded)) == 1


# ── the shift survives Blender's 32-bit FloatProperty ────────────────────────

class _Float32Scene(types.SimpleNamespace):
    """``scene.em_georef`` as Blender keeps it: the shift fields are 32-bit
    floats (measured: 448682.65 is read back as 448682.65625)."""

    def __setattr__(self, name, value):
        if name in ("shift_x", "shift_y", "shift_z"):
            value = graph_sync._f32(value)
        super().__setattr__(name, value)


def _f32_scene():
    return _Float32Scene(epsg="", shift_x=0.0, shift_y=0.0, shift_z=0.0,
                         rotation=0.0, graph_note="", reference_graph="",
                         shift_exact="")


def test_the_fields_alone_would_move_the_anchor():
    g = _f32_scene()
    g.shift_y = 448682.65
    assert g.shift_y == 448682.65625
    g.shift_y = 4640631.8                      # a UTM northing
    assert g.shift_y == 4640632.0


def test_read_from_the_graph_and_pushed_back_unchanged():
    g = _f32_scene()
    graph = _graph()
    assert graph_sync.adopt_on_open(g, graph)["outcome"] == "adopted"
    assert graph_sync.exact_shift(g) == (327372.56, 448682.65, 0.0)
    assert graph_sync.differences(graph_sync.scene_values(g),
                                  graph_sync.pull_from_geonode(graph)) == []
    graph_sync.push_to_geonode(graph, g.epsg, *graph_sync.exact_shift(g))
    node = graph_sync.get_geo_node(graph)
    assert (node.data["shift_x"], node.data["shift_y"]) == (327372.56, 448682.65)


def test_a_field_edited_by_hand_wins_over_the_exact_copy():
    g = _f32_scene()
    graph_sync.set_shift(g, 327372.56, 448682.65, 0.0)
    g.shift_x = 1000.0
    assert graph_sync.exact_shift(g) == (1000.0, 448682.65, 0.0)
