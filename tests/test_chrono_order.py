"""The units' order comes from the chronology, not from ``y_pos``.

``y_pos`` is the vertical coordinate of a node in the yEd drawing (E.D.,
10 Oct 2026: a fossil of the GraphML). An em.json does not carry it, so the
order EM-tools gives the units must be the same whether the graph was read
from a GraphML or from its em.json — and must not change when ``y_pos`` does.

Two cases: Templu Mare (s3dgraphy's fixture, read back through a GraphML) and
a small graph over three epochs, with a re-used unit and units tied in time.
The module measured is ``chrono_order.py``, which does not import ``bpy``.
"""
import contextlib
import importlib.util
import io
import pathlib
import random
import sys

import pytest

_REPO = pathlib.Path(__file__).resolve().parent.parent
_S3D = _REPO.parent / "s3Dgraphy" / "src"
if _S3D.is_dir() and str(_S3D) not in sys.path:
    sys.path.insert(0, str(_S3D))

_TEMPLU = _REPO.parent / "s3Dgraphy" / "tests" / "fixtures" / "TempluMare.em.json"

spec = importlib.util.spec_from_file_location("_em_chrono_order", _REPO / "chrono_order.py")
co = importlib.util.module_from_spec(spec)
spec.loader.exec_module(co)


def _quiet(fn, *a, **kw):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a, **kw)


def _strip_drawing(obj):
    """What an em.json without the GraphML's drawing keys looks like."""
    if isinstance(obj, dict):
        obj.pop("y_pos", None)
        obj.pop("x_pos", None)
        for v in obj.values():
            _strip_drawing(v)
    elif isinstance(obj, list):
        for v in obj:
            _strip_drawing(v)


def _via_graphml_and_emjson(graph, tmp_path):
    """``(read from GraphML, read from that graph's em.json)``."""
    from s3dgraphy import api
    from s3dgraphy.exporter.graphml import GraphMLExporter
    from s3dgraphy.graph import Graph
    from s3dgraphy.importer.import_graphml import GraphMLImporter

    path = tmp_path / "g.graphml"
    _quiet(GraphMLExporter(graph).export, str(path))
    from_graphml = _quiet(GraphMLImporter(str(path), Graph(graph_id="g")).parse)
    doc = _quiet(api.graph_to_emjson, from_graphml)
    _strip_drawing(doc)
    from_emjson, _ = _quiet(api.load_emjson, doc)
    return from_graphml, from_emjson


def _order(graph):
    from s3dgraphy.nodes.stratigraphic_node import StratigraphicNode
    units = [n for n in graph.nodes if isinstance(n, StratigraphicNode)]
    return [n.name for n in co.chronological_order(graph, units)]


def _scramble_y_pos(graph):
    rnd = random.Random(10)
    for n in graph.nodes:
        n.attributes["y_pos"] = rnd.uniform(-5000, 5000)


def _three_epochs():
    from s3dgraphy.graph import Graph
    from s3dgraphy.nodes.epoch_node import EpochNode
    from s3dgraphy.nodes.stratigraphic_node import StratigraphicUnit

    g = Graph(graph_id="three_epochs")
    for eid, name, s, e in (("E1", "Roman", -100, 300),
                            ("E2", "Late antique", 300, 600),
                            ("E3", "Medieval", 600, 1200)):
        g.add_node(EpochNode(eid, name, s, e))
    units = {"US1": "E3", "US2": "E3", "US3": "E2", "US4": "E2",
             "US5": "E1", "US6": "E1", "US7": "E1"}
    for name, epoch in units.items():
        g.add_node(StratigraphicUnit(name, name))
        g.add_edge(f"{name}-{epoch}", name, epoch, "has_first_epoch")
    # US5 is re-used in the late antique and medieval phases
    g.add_edge("US5-E2", "US5", "E2", "survive_in_epoch")
    # inside the Roman epoch: US7 over US6 — same dates, US7 lies above
    g.add_edge("US7>US6", "US7", "US6", "is_after")
    g.add_edge("US3>US5", "US3", "US5", "is_after")
    g.add_edge("US1>US3", "US1", "US3", "is_after")
    return g


@pytest.mark.skipif(not _TEMPLU.is_file(), reason="s3Dgraphy is not next door")
def test_templu_mare_has_the_same_order_from_graphml_and_from_its_emjson(tmp_path):
    from s3dgraphy import api
    graph, _ = _quiet(api.load_emjson_file, str(_TEMPLU))
    from_graphml, from_emjson = _via_graphml_and_emjson(graph, tmp_path)
    order = _order(from_graphml)
    assert len(order) > 50
    assert _order(from_emjson) == order
    _scramble_y_pos(from_graphml)
    _scramble_y_pos(from_emjson)
    assert _order(from_graphml) == _order(from_emjson) == order


def test_three_epochs_most_recent_first_then_above_then_name(tmp_path):
    g = _three_epochs()
    order = _order(g)
    # medieval units first, tied in time and in position: by name
    assert order[:2] == ["US1", "US2"]
    # US5, re-used until 600, comes with the late antique ones
    assert order.index("US5") < order.index("US6")
    # US7 and US6 share the Roman dates; US7 lies above
    assert order.index("US7") < order.index("US6")
    # The GraphML writer materialises the epochs' continuity diamonds, so the
    # graph read back has more units than ``g``: compare the two readings.
    from_graphml, from_emjson = _via_graphml_and_emjson(g, tmp_path)
    read_back = _order(from_graphml)
    assert read_back[:2] == ["US1", "US2"]
    assert _order(from_emjson) == read_back
    _scramble_y_pos(from_graphml)
    _scramble_y_pos(from_emjson)
    assert _order(from_graphml) == _order(from_emjson) == read_back


def test_a_cycle_still_gives_an_order():
    g = _three_epochs()
    g.add_edge("US6>US7", "US6", "US7", "is_after")
    assert sorted(_order(g)) == sorted(f"US{i}" for i in range(1, 8))
