"""Le letture 3D pronte per Blender (`readings_view.core`), senza Blender.

La parte Blender (import glTF, collezione, avviso di spostamento) sta in
`tests/blender_smoke_readings.py`.
"""

import importlib.util
import pathlib
import sys

import pytest

_REPO = pathlib.Path(__file__).resolve().parent.parent

s3dgraphy_api = pytest.importorskip("s3dgraphy.api")
if not hasattr(s3dgraphy_api, "geometry_to_gltf"):  # pragma: no cover
    pytest.skip("s3dgraphy without geometry_to_gltf", allow_module_level=True)

from s3dgraphy.graph import Graph  # noqa: E402
from s3dgraphy.nodes.annotation_region_node import AnnotationRegionNode  # noqa: E402

_spec = importlib.util.spec_from_file_location("readings_core", _REPO / "readings_view" / "core.py")
core = importlib.util.module_from_spec(_spec)
sys.modules["readings_core"] = core
_spec.loader.exec_module(core)


def _graph():
    g = Graph("g")
    g.add_node(AnnotationRegionNode("reg-pt", "punto A", geometry_kind="point",
                                    coords=[[1.0, 2.0, 3.0]]))
    g.add_node(AnnotationRegionNode("reg-pl", "polilinea B", geometry_kind="polyline",
                                    coords=[[0, 0, 0], [1, 0, 0], [1, 1, 0], [1, 1, 2]]))
    g.add_node(AnnotationRegionNode("reg-2d", "riquadro", rect=[0.1, 0.1, 0.2, 0.2]))
    return g


def test_un_punto_e_una_polilinea_sono_due_letture_da_mostrare():
    plan = core.plan_readings(_graph())
    assert [(r.region_id, r.kind, r.vertex_count) for r in plan.shown] == \
        [("reg-pt", "point", 1), ("reg-pl", "polyline", 4)]
    assert plan.skipped == []          # la regione 2D non è una lettura 3D


def test_i_byte_sono_il_gltf_di_s3dgraphy_e_tornano_uguali():
    plan = core.plan_readings(_graph())
    for r, coords in zip(plan.shown, ([[1.0, 2.0, 3.0]],
                                      [[0, 0, 0], [1, 0, 0], [1, 1, 0], [1, 1, 2]])):
        assert r.glb[:4] == b"glTF"
        back = s3dgraphy_api.gltf_to_geometry(r.glb, r.kind)
        assert back["coords"] == [[float(v) for v in p] for p in coords]


def test_una_regione_senza_coords_non_si_mostra_e_lo_dice():
    g = Graph("g")
    node = AnnotationRegionNode("reg-big", "tanti vertici", geometry_kind="polyline",
                                coords=[[0, 0, 0], [1, 0, 0]])
    node.data.pop("coords", None)       # oltre soglia: i vertici sono un glb
    g.add_node(node)
    plan = core.plan_readings(g)
    assert plan.shown == []
    assert plan.skipped[0]["region_id"] == "reg-big"
    assert "glb" in plan.skipped[0]["reason"]


def test_la_firma_cambia_se_la_lettura_si_sposta():
    a = core.signature([(1.0, 2.0, 3.0)])
    assert a == core.signature([(1.00001, 2.0, 3.0)])     # sotto il decimo di mm
    assert a != core.signature([(1.001, 2.0, 3.0)])
