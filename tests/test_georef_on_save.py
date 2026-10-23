"""MICRO georef al salvataggio (24 Oct 2026) — the scene's georeferencing is
written into the graph's GeoPositionNode at every save (decision of E.D.), not
only with «Push to GeoNode».

Measured before: no save wrote the node (the last automatic write was the
Heriverse export's DP-56 mirror, gone to ``_dead_code`` with 43cfb52 on 5 Oct).

Pinned here, outside Blender (``scene`` is a plain namespace with
``em_georef`` and ``em_tools.graphml_files``; the shift fields are 32-bit floats
as in Blender):

- save → reopen → the same values, 448682.65 exact;
- a scene that is not georeferenced leaves the node as it is;
- a graph that says something the scene was never aligned to is not written
  without a choice (Push / Pull / Keep);
- a scene changed after it agreed with the graph is written;
- the node goes into «Graph paradata»; another graph (G1) is never touched.
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
        "_emtools_test_graph_sync_save", _REPO / "georef_manager" / "graph_sync.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


graph_sync = _load_graph_sync()

GT16 = ("3844", 327372.56, 448682.65, 0.0)


class _Georef(types.SimpleNamespace):
    """``scene.em_georef`` as Blender keeps it: 32-bit shift fields."""

    def __setattr__(self, name, value):
        if name in ("shift_x", "shift_y", "shift_z"):
            value = graph_sync._f32(value)
        super().__setattr__(name, value)


def _scene(*graph_ids, ref=""):
    g = _Georef(epsg="", shift_x=0.0, shift_y=0.0, shift_z=0.0, rotation=0.0,
                graph_note="", reference_graph=ref, shift_exact="",
                graph_agreed="")
    rows = [types.SimpleNamespace(name=gid) for gid in graph_ids]
    return types.SimpleNamespace(
        em_georef=g,
        em_tools=types.SimpleNamespace(graphml_files=rows, active_file_index=0))


def _graph(gid="gt16", georef=GT16):
    graph = Graph(graph_id=gid)
    materialize_graph_scope(graph, author="E. D.", license="CC-BY-NC")
    node = graph_sync.get_geo_node(graph)
    if georef is not None:
        node.data.update({"epsg": int(georef[0]), "shift_x": georef[1],
                          "shift_y": georef[2], "shift_z": georef[3]})
    return graph


def _set(g, epsg, x, y, z, rotation=0.0):
    graph_sync.set_shift(g, x, y, z)
    g.rotation = rotation
    g.epsg = epsg


def _node(graph):
    return dict(graph_sync.get_geo_node(graph).data)


def _save(scene, graphs, choice="ASK"):
    by_id = {g.graph_id: g for g in graphs}
    return graph_sync.write_on_save(scene, list(by_id), by_id.get, choice,
                                    log=lambda *a, **k: None)


def _geo_edges(graph):
    node = graph_sync.get_geo_node(graph)
    return [e for e in graph.edges if e.edge_source == node.node_id
            and e.edge_type == "is_in_paradata_nodegroup"]


# ── save → reopen ────────────────────────────────────────────────────────────

def test_save_then_reopen_gives_the_same_values_exactly():
    graph = _graph(georef=None)                 # a graph that says nothing yet
    scene = _scene("gt16")
    _set(scene.em_georef, *GT16, rotation=1.25)
    assert scene.em_georef.shift_y == 448682.65625   # the field is a float32
    plan = _save(scene, [graph])
    assert plan["outcome"] == "written"
    doc = s3dgraphy_api.graph_to_emjson(graph)
    reloaded, _w = s3dgraphy_api.load_emjson(doc)
    node = _node(reloaded)
    assert (node["epsg"], node["shift_x"], node["shift_y"], node["shift_z"],
            node["rotation"]) == (3844, 327372.56, 448682.65, 0.0, 1.25)
    assert node["shift_y"] == 448682.65          # exact, not 448682.65625
    assert len(_geo_edges(reloaded)) == 1
    # reopened in an empty scene: the same values come back
    fresh = _scene("gt16")
    assert graph_sync.adopt_on_open(fresh.em_georef, reloaded)["outcome"] == "adopted"
    assert graph_sync.exact_shift(fresh.em_georef) == (327372.56, 448682.65, 0.0)
    assert fresh.em_georef.epsg == "3844" and fresh.em_georef.rotation == 1.25


def test_a_second_save_adds_no_second_edge():
    graph = _graph(georef=None)
    scene = _scene("gt16")
    _set(scene.em_georef, *GT16)
    _save(scene, [graph])
    assert _save(scene, [graph])["outcome"] == "same"
    assert len(_geo_edges(graph)) == 1


# ── the scene not georeferenced ──────────────────────────────────────────────

def test_an_empty_scene_leaves_the_node_as_it_is():
    graph = _graph()
    before = _node(graph)
    scene = _scene("gt16")
    plan = _save(scene, [graph])
    assert plan["outcome"] == "scene-empty"
    assert _node(graph) == before


def test_an_empty_scene_does_not_empty_a_node_that_says_nothing_either():
    graph = _graph(georef=None)
    before = _node(graph)
    assert _save(_scene("gt16"), [graph])["outcome"] == "scene-empty"
    assert _node(graph) == before and "epsg" not in before


# ── an unresolved discrepancy ────────────────────────────────────────────────

def _conflicted():
    graph = _graph()                              # says 3844 · 327372.56 …
    scene = _scene("gt16")
    _set(scene.em_georef, "31700", 327372.56, 448682.65, 500.0)  # never aligned
    return scene, graph


def test_a_discrepancy_is_not_written_without_a_choice():
    scene, graph = _conflicted()
    before = _node(graph)
    plan = _save(scene, [graph])
    assert plan["outcome"] == "conflict"
    assert {d[0] for d in plan["differences"]} == {"epsg", "shift_z"}
    assert "choose Push or Pull" in plan["sentence"]
    assert _node(graph) == before
    assert scene.em_georef.epsg == "31700"        # the scene untouched too
    assert graph_sync.save_conflict(scene, ["gt16"], {"gt16": graph}.get) is not None


def test_push_writes_the_scene_into_the_graph():
    scene, graph = _conflicted()
    assert _save(scene, [graph], "PUSH")["outcome"] == "pushed"
    node = _node(graph)
    assert (node["epsg"], node["shift_z"]) == (31700, 500.0)
    assert graph_sync.save_conflict(scene, ["gt16"], {"gt16": graph}.get) is None


def test_pull_writes_the_graph_into_the_scene():
    scene, graph = _conflicted()
    before = _node(graph)
    assert _save(scene, [graph], "PULL")["outcome"] == "pulled"
    assert scene.em_georef.epsg == "3844" and scene.em_georef.shift_z == 0.0
    assert _node(graph) == before


def test_keep_writes_neither():
    scene, graph = _conflicted()
    before = _node(graph)
    assert _save(scene, [graph], "KEEP")["outcome"] == "kept"
    assert _node(graph) == before and scene.em_georef.epsg == "31700"
    # and the next save still asks
    assert _save(scene, [graph])["outcome"] == "conflict"


# ── aligned once, then changed ───────────────────────────────────────────────

def test_a_scene_changed_after_it_agreed_is_written():
    graph = _graph()
    scene = _scene("gt16")
    g = scene.em_georef
    graph_sync.on_graph_opened(scene, graph, log=lambda *a, **k: None)
    assert g.epsg == "3844"                       # adopted on opening
    g.shift_z = 0.5                               # then edited in the panel
    plan = _save(scene, [graph])
    assert plan["outcome"] == "written"
    assert _node(graph)["shift_z"] == 0.5
    assert _node(graph)["shift_y"] == 448682.65   # the rest kept exact


def test_a_graph_changed_after_the_agreement_is_asked_about():
    graph = _graph()
    scene = _scene("gt16")
    graph_sync.on_graph_opened(scene, graph, log=lambda *a, **k: None)
    graph_sync.get_geo_node(graph).data["shift_x"] = 327000.0   # another hand
    assert _save(scene, [graph])["outcome"] == "conflict"


def test_push_and_pull_from_the_panel_count_as_an_agreement():
    scene, graph = _conflicted()
    graph_sync.write_scene(scene.em_georef, graph_sync.pull_from_geonode(graph))
    graph_sync.remember_agreement(scene.em_georef, graph)        # as «Pull»
    scene.em_georef.rotation = 2.0
    assert _save(scene, [graph])["outcome"] == "written"


# ── which graph ──────────────────────────────────────────────────────────────

def test_only_the_scenes_graph_is_written():
    ref, other = _graph("ref", georef=None), _graph("other", georef=None)
    scene = _scene("ref", "other", ref="ref")
    _set(scene.em_georef, *GT16)
    live = {"ref": ref, "other": other}.get
    plan = graph_sync.write_on_save(scene, ["ref", "other"], live,
                                    log=lambda *a, **k: None)
    assert plan["graph_id"] == "ref"
    assert _node(ref)["shift_x"] == 327372.56
    assert "epsg" not in _node(other)
    # a save of the other graph's file alone does not touch either
    assert graph_sync.write_on_save(scene, ["other"], live,
                                    log=lambda *a, **k: None) is None
    assert "epsg" not in _node(other)


def test_the_node_is_written_into_graph_paradata():
    graph = Graph(graph_id="bare")               # no GraphNode, no group
    scene = _scene("bare")
    _set(scene.em_georef, *GT16)
    assert _save(scene, [graph])["outcome"] == "written"
    assert len(_geo_edges(graph)) == 1
