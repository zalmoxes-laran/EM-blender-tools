"""NIGHT-TAGLI-E-NEUTRE · the proxies drawn as their TYPE asks (em_visual_rules
1.6.44 `threed`), the pure part of ``threed_style.py``: the style read from
s3Dgraphy, the faces' alpha (type × slider), the feature edges of a mesh, and
the cut of the edges — the same dashes and ticks as EMStudio's cutEdges.
"""
import importlib.util
import math
import pathlib

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "threed_style", pathlib.Path(__file__).resolve().parent.parent / "threed_style.py")
T = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(T)

try:
    from s3dgraphy.utils.utils import get_threed_style  # noqa: F401
    HAS_RULE = True
except ImportError:
    HAS_RULE = False
need_rule = pytest.mark.skipif(not HAS_RULE, reason="s3dgraphy older than em_visual_rules 1.6.44")

# a cube 2 × 2 × 2, quads
CUBE_V = [(-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1), (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1)]
CUBE_F = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]


def _tris(faces):
    out = []
    for f in faces:
        out += [(f[0], f[1], f[2]), (f[0], f[2], f[3])]
    return out


@need_rule
def test_the_style_is_read_from_s3dgraphy():
    usn, usnt, us = T.threed_style_of("USN"), T.threed_style_of("USNt"), T.threed_style_of("US")
    assert usn["edges"]["show"] and usn["edges"]["style"] == "solid"
    assert not usnt["faces"]["show"] and usnt["edges"]["style"] == "dashed"
    assert us["faces"]["opacity"] == 1.0
    # 1.6.45 (decision 1): every type has edges, thin, continuous, at 1°
    assert us["edges"]["show"] and us["edges"]["style"] == "solid"
    assert us["edges"]["feature_angle_deg"] == 1.0
    # decision 2: the USN's edges dark grey (#8C8C8C), its faces as they were
    assert usn["edges"]["rgba_color"][:3] == (0.262, 0.262, 0.262)
    assert usn["faces"]["rgba_color"][:3] == (0.55, 0.55, 0.55)
    assert usn["edges"]["feature_angle_deg"] == usnt["edges"]["feature_angle_deg"] == 20.0


@need_rule
def test_the_slider_multiplies_the_type_opacity():
    for slider in (0.2, 0.5, 1.0):
        assert T.faces_alpha(T.threed_style_of("US"), slider) == pytest.approx(slider)
        assert T.faces_alpha(T.threed_style_of("USN"), slider) == pytest.approx(0.3 * slider)
        assert T.faces_alpha(T.threed_style_of("USNt"), slider) == 0.0
    assert T.faces_alpha(None, 0.4) == 0.4  # not an EM type: the slider, as before


def test_the_feature_edges_of_a_cube_are_its_twelve_edges_even_triangulated():
    assert len(T.feature_edges(CUBE_V, CUBE_F)) == 12
    assert len(T.feature_edges(CUBE_V, _tris(CUBE_F))) == 12  # no diagonal


def test_split_vertices_are_one_vertex():
    """A glb splits a cube's vertices by normal (24 for 8): still 12 edges."""
    verts, faces = [], []
    for f in CUBE_F:
        base = len(verts)
        verts += [CUBE_V[i] for i in f]
        faces.append(tuple(range(base, base + 4)))
    assert len(T.feature_edges(verts, faces)) == 12


def test_an_open_mesh_keeps_its_boundary():
    assert len(T.feature_edges(CUBE_V, CUBE_F[:1])) == 4


def test_the_cut_is_emstudios():
    seg = [((0, 0, 0), (10, 0, 0))]
    size = (10, 4, 2)
    diag = math.sqrt(100 + 16 + 4)
    assert T.cut_edges(seg, "solid", size) == [((0, 0, 0), (10, 0, 0))]
    dashed = T.cut_edges(seg, "dashed", size)
    assert dashed[0][0] == (0, 0, 0)
    assert dashed[0][1][0] == pytest.approx(0.04 * diag)
    assert dashed[1][0][0] == pytest.approx(0.065 * diag)
    assert len(dashed) == math.ceil(10 / (0.065 * diag))  # = check-threed-style.mjs
    corners = T.cut_edges(seg, "corners", size)
    assert [c[1][0] for c in corners] == pytest.approx([0.68, 10])
    assert T.cut_edges([((0, 0, 0), (1, 0, 0))], "corners", size)[0][1][0] == pytest.approx(0.5)


@need_rule
def test_the_segments_of_a_usnt_room():
    s = T.edge_segments(CUBE_V, CUBE_F, T.threed_style_of("USNt"))
    # 12 edges of 2 m, diagonal 2√3: dash+gap = 0.065 × 3.464 = 0.225 → 9 dashes each
    assert len(s) == 12 * math.ceil(2 / (0.065 * 2 * math.sqrt(3)))
    assert len(T.edge_segments(CUBE_V, CUBE_F, T.threed_style_of("USN"))) == 12


# ── MICRO-TAGLI-3D-DECISIONI (1.6.45) ──────────────────────────────────────

@need_rule
def test_the_type_decides_the_faces_in_every_mode():
    """Decision 3: the factor a mode material is multiplied by for a type."""
    assert T.faces_factor(T.threed_style_of("USNt")) == 0.0
    assert T.faces_factor(T.threed_style_of("USN")) == pytest.approx(0.3)
    assert T.faces_factor(T.threed_style_of("US")) == 1.0
    assert T.faces_factor(None) == 1.0


def test_a_faces_variant_says_its_type():
    n = T.variant_name("ep_Roman", "USNt")
    assert n.startswith("ep_")  # still read as an Epochs material
    assert T.type_of_material(n) == "USNt"
    assert T.type_of_material("prop_wall.EM_faces_USN") == "USN"
    assert T.type_of_material("ep_Roman") is None
    assert T.type_of_material("USNt") is None


def test_solid_edges_are_chained_into_polylines():
    feats = T.feature_edges(CUBE_V, _tris(CUBE_F), 1.0)
    runs = T.chain_segments(feats)
    # every segment is in exactly one run
    assert sum(len(r) - 1 for r in runs) == 12
    # a cube's corners have degree 3: runs stop there, no run is longer than an edge
    assert all(len(r) == 2 for r in runs)
    # a square ring (degree 2 everywhere) is one closed run
    ring = [((0, 0, 0), (1, 0, 0)), ((1, 0, 0), (1, 1, 0)), ((1, 1, 0), (0, 1, 0)), ((0, 1, 0), (0, 0, 0))]
    runs = T.chain_segments(ring)
    assert len(runs) == 1 and len(runs[0]) == 5 and runs[0][0] == runs[0][-1]
    # an open polyline from its end
    line = [((0, 0, 0), (1, 0, 0)), ((2, 0, 0), (1, 0, 0)), ((2, 0, 0), (3, 0, 0))]
    runs = T.chain_segments(line)
    assert len(runs) == 1 and len(runs[0]) == 4


def test_a_curved_proxy_at_1_and_at_20_degrees():
    """The thin contour (1°) keeps the creases of a faceted surface the type
    marks (20°) leave out: a 32-sided prism (11.25° per crease)."""
    n = 32
    v = [(math.cos(2 * math.pi * i / n), math.sin(2 * math.pi * i / n), z) for z in (0, 1) for i in range(n)]
    f = [tuple(range(n))[::-1], tuple(range(n, 2 * n))] + [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
    assert len(T.feature_edges(v, f, 1.0)) == 3 * n
    assert len(T.feature_edges(v, f, 20.0)) == 2 * n
