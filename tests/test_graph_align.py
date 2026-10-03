"""G1 · where another graph's local system goes in the scene (bpy-free).

Same EPSG: the difference of the shifts, to the millimetre. Different EPSG: the
origin reprojected and the Z rotation = grid convergence, checked against
pyproj directly when pyproj is importable (it is not in Blender's Python, nor in
this venv by default — then the case is skipped, never faked).
"""

import importlib.util
import math
import pathlib
import sys

import pytest

_REPO = pathlib.Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "_emtools_graph_align", _REPO / "georef_manager" / "graph_align.py")
ga = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = ga  # dataclasses look their module up
_spec.loader.exec_module(ga)

MM = 1e-3


def test_same_epsg_relative_position_to_the_millimetre():
    ref = ga.Anchor(32633, 291960.5, 4640631.8, 12.0)
    other = ga.Anchor(32633, 292010.25, 4640600.3, 14.5)
    pl = ga.place(ref, other)
    assert pl.ok and pl.method == "same-epsg"
    # a corner of the other graph, local to its own anchor…
    local = (3.0, -7.5, 1.25)
    # …is, in the CRS, its shift plus itself; in the scene, that minus the
    # reference shift
    want = (other.shift_x + local[0] - ref.shift_x,
            other.shift_y + local[1] - ref.shift_y,
            other.shift_z + local[2] - ref.shift_z)
    got = ga.apply_point(pl, local)
    assert all(abs(a - b) < MM for a, b in zip(got, want)), (got, want)
    assert pl.rot_z_deg == 0.0
    assert "difference of the shifts" in pl.sentence()


def test_same_epsg_with_rotated_scenes():
    # the reference scene's +Y points 30° east of grid north; the other's 10°
    ref = ga.Anchor(32633, 1000.0, 2000.0, 0.0, rotation=30.0)
    other = ga.Anchor(32633, 1100.0, 2050.0, 0.0, rotation=10.0)
    pl = ga.place(ref, other)

    def to_grid(anchor, p):  # local → CRS: azimuth θ clockwise = Rz(-θ)
        x, y = ga._rot(p[0], p[1], -anchor.rotation)
        return (x + anchor.shift_x, y + anchor.shift_y)

    def to_scene(p):  # CRS → reference local
        return ga._rot(p[0] - ref.shift_x, p[1] - ref.shift_y, ref.rotation)

    for local in [(0, 0), (5, 0), (0, 5), (-3.3, 8.8)]:
        want = to_scene(to_grid(other, local))
        got = ga.apply_point(pl, (*local, 0.0))
        assert abs(got[0] - want[0]) < MM and abs(got[1] - want[1]) < MM


def test_the_reference_is_not_moved_and_no_epsg_is_refused():
    ref = ga.Anchor(32633, 1.0, 2.0, 3.0)
    assert ga.place(ref, ref).method == "reference"
    pl = ga.place(ref, ga.Anchor(None))
    assert not pl.ok and "no EPSG" in pl.sentence()


def test_different_epsg_without_a_reprojector_says_what_is_needed():
    pl = ga.place(ga.Anchor(32633), ga.Anchor(32632),
                  missing="server not reachable; pyproj is not installed")
    assert not pl.ok
    assert "reprojection is needed" in pl.sentence()
    assert "pyproj" in pl.sentence()


def test_convergence_from_a_synthetic_reprojector():
    # a target grid rotated 2° counter-clockwise from the source and shifted
    def fake(points, s, t):
        return [tuple(v + 1000.0 for v in ga._rot(x, y, 2.0)) for x, y in points]
    ref = ga.Anchor(2, 0.0, 0.0, 0.0)
    other = ga.Anchor(1, 10.0, 20.0, 5.0)
    pl = ga.place(ref, other, fake, via="test")
    assert pl.ok and pl.method == "reprojected"
    assert abs(pl.convergence_deg - 2.0) < 1e-9
    assert abs(pl.scale - 1.0) < 1e-12
    # a local point of the other graph lands where the exact transform puts it
    local = (7.0, -4.0, 0.0)
    want = fake([(other.shift_x + 7.0, other.shift_y - 4.0)], 1, 2)[0]
    got = ga.apply_point(pl, local)
    assert abs(got[0] - want[0]) < 1e-9 and abs(got[1] - want[1]) < 1e-9
    assert "grid convergence +2.0000°" in pl.sentence()


def test_different_epsg_checked_against_pyproj():
    pyproj = pytest.importorskip("pyproj")
    run = ga.pyproj_reprojector()
    assert run is not None
    # Templu Mare-like anchor in UTM 33N, scene in UTM 32N (the next zone)
    ref = ga.Anchor(32632, 789000.0, 4643000.0, 0.0)
    other = ga.Anchor(32633, 291960.5, 4640631.8, 12.0)
    pl = ga.place(ref, other, run, via="pyproj")
    assert pl.ok
    # independent: the meridian convergence of each zone at the point, from
    # pyproj's own Factors — the relative rotation is their difference
    from pyproj import CRS, Proj, Transformer
    lon, lat = Transformer.from_crs(32633, 4326, always_xy=True).transform(
        other.shift_x, other.shift_y)
    gam33 = Proj(CRS(32633)).get_factors(lon, lat).meridian_convergence
    gam32 = Proj(CRS(32632)).get_factors(lon, lat).meridian_convergence
    # pyproj's convergence is the angle from true north to grid north,
    # positive clockwise; the 33N grid north seen in the 32N grid is rotated
    # by gam32 - gam33 counter-clockwise
    assert abs(pl.convergence_deg - (gam32 - gam33)) < 1e-3, (
        pl.convergence_deg, gam32 - gam33)
    # the anchor itself lands on its reprojection
    x32, y32 = Transformer.from_crs(32633, 32632, always_xy=True).transform(
        other.shift_x, other.shift_y)
    assert abs(pl.dx - (x32 - ref.shift_x)) < MM
    assert abs(pl.dy - (y32 - ref.shift_y)) < MM
