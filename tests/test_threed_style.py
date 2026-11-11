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
    assert us["faces"]["opacity"] == 1.0 and not us["edges"]["show"]


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
