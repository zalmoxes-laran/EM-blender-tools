"""Il ritorno di una lettura da Blender (`readings_view.core.apply_back`), senza
Blender: quello che `gltf_to_geometry` rilegge → la regione nel grafo.

La parte Blender (export glTF delle letture selezionate) sta in
`tests/blender_smoke_readings.py`.
"""

import importlib.util
import math
import pathlib
import sys

import pytest

_REPO = pathlib.Path(__file__).resolve().parent.parent

s3dgraphy_api = pytest.importorskip("s3dgraphy.api")
if not hasattr(s3dgraphy_api, "set_field"):  # pragma: no cover
    pytest.skip("s3dgraphy without set_field", allow_module_level=True)

from s3dgraphy.graph import Graph  # noqa: E402
from s3dgraphy.nodes.annotation_region_node import AnnotationRegionNode  # noqa: E402

_spec = importlib.util.spec_from_file_location("readings_core_back", _REPO / "readings_view" / "core.py")
core = importlib.util.module_from_spec(_spec)
sys.modules["readings_core_back"] = core
_spec.loader.exec_module(core)

PL = [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [1.0, 1.0, 0.0], [1.0, 1.0, 2.0]]


def _graph():
    g = Graph("g")
    g.add_node(AnnotationRegionNode("reg-pt", "punto A", geometry_kind="point", coords=[[1.0, 2.0, 3.0]]))
    g.add_node(AnnotationRegionNode("reg-pl", "polilinea B", geometry_kind="polyline", coords=PL))
    return g


def test_un_vertice_spostato_cambia_coords_e_lunghezza():
    g = _graph()
    node = g.find_node_by_id("reg-pl")
    assert node.data["length"] == pytest.approx(4.0)
    moved = [list(p) for p in PL]
    moved[3] = [1.0, 1.0, 2.5]                     # l'ultimo vertice sale di 0,5
    r = core.apply_back(g, "reg-pl", {"geometry_kind": "polyline", "coords": moved})
    assert r["written"] and r["moved"] == 1
    assert r["max_shift"] == pytest.approx(0.5)
    assert node.data["coords"] == moved
    assert node.data["length"] == pytest.approx(4.5)
    assert node.coords == moved and node.length == pytest.approx(4.5)
    assert "length 4.0000 → 4.5000 m" in core.describe(r)


def test_ogni_campo_scritto_porta_il_suo_timbro():
    g = _graph()
    moved = [list(p) for p in PL]
    moved[0] = [0.0, 0.0, -1.0]
    core.apply_back(g, "reg-pl", {"geometry_kind": "polyline", "coords": moved})
    node = g.find_node_by_id("reg-pl")
    clocks = node.data.get("field_clocks") or {}
    assert {"data.coords", "data.length", "data.vertex_count"} <= set(clocks)
    assert not {"data.coords", "data.length", "data.vertex_count"} & \
        set(s3dgraphy_api.unstamped_fields(node))


def test_il_punto_torna():
    g = _graph()
    r = core.apply_back(g, "reg-pt", {"geometry_kind": "point", "coords": [[1.0, 2.0, 3.25]]})
    assert r["written"] and g.find_node_by_id("reg-pt").data["coords"] == [[1.0, 2.0, 3.25]]
    assert "length" not in g.find_node_by_id("reg-pt").data


def test_niente_di_cambiato_niente_di_scritto():
    g = _graph()
    before = repr(g.find_node_by_id("reg-pl").data)
    r = core.apply_back(g, "reg-pl", {"geometry_kind": "polyline",
                                      "coords": [[v + 1e-7 for v in p] for p in PL]})
    assert not r["written"] and r["reason"] == "unchanged"
    assert repr(g.find_node_by_id("reg-pl").data) == before


def test_due_pezzi_il_grafo_non_cambia_e_l_avviso_arriva():
    g = _graph()
    before = repr(g.find_node_by_id("reg-pl").data)
    back = {"geometry_kind": "polyline", "pieces": [PL[:2], PL[2:]],
            "warnings": ["the LINES are 2 chains, not one"]}
    r = core.apply_back(g, "reg-pl", back)
    assert not r["written"] and "2 pieces" in r["reason"]
    assert "the LINES are 2 chains, not one" in core.describe(r)
    assert repr(g.find_node_by_id("reg-pl").data) == before


def test_un_kind_diverso_non_si_scrive():
    g = _graph()
    r = core.apply_back(g, "reg-pl", {"geometry_kind": "point", "coords": [[0, 0, 0]]})
    assert not r["written"] and "polyline" in r["reason"]


def test_oltre_soglia_non_si_scrive(monkeypatch):
    from s3dgraphy.nodes import annotation_region_node as arn
    monkeypatch.setattr(arn, "inline_max_vertices", lambda: 3)
    g = _graph()
    r = core.apply_back(g, "reg-pl", {"geometry_kind": "polyline", "coords": PL})
    assert not r["written"] and "inline_max_vertices" in r["reason"]


def test_i_bracci_della_croce_non_toccano_il_punto():
    arms = core.cross_arms((1.0, 2.0, 3.0), 0.5)
    assert len(arms) == 3
    for a, b in arms:
        assert (1.0, 2.0, 3.0) not in (a, b)
        assert math.dist(a, b) == pytest.approx(1.0)
        assert [(u + v) / 2 for u, v in zip(a, b)] == [1.0, 2.0, 3.0]
