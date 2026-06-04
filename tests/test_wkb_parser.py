from fixtures.wkb_blobs import (
    POLYGON_2D_SQUARE,
    POLYGON_2D_WITH_HOLE,
    POLYGON_3D_TRIANGLE,
    MULTIPOLYGON_2D_TWO_PARTS,
    TRUNCATED_WKB,
    LINESTRING_WKB,
    SPATIALITE_POLYGON_2D_SQUARE,
    SPATIALITE_POLYGON_3D_TRIANGLE,
    SPATIALITE_MULTIPOLYGON_2D_TWO_PARTS,
    SPATIALITE_MALFORMED_MARKER,
)
from import_operators.wkb_parser import parse_wkb, WKBParseError
import pytest


def test_parse_polygon_2d_single_ring():
    polygons = parse_wkb(POLYGON_2D_SQUARE)
    assert len(polygons) == 1
    polygon = polygons[0]
    assert len(polygon) == 1, "single ring expected"
    ring = polygon[0]
    assert len(ring) == 5
    assert ring[0] == (0.0, 0.0, 0.0)
    assert ring[1] == (10.0, 0.0, 0.0)
    assert ring[2] == (10.0, 10.0, 0.0)
    assert ring[3] == (0.0, 10.0, 0.0)
    assert ring[4] == (0.0, 0.0, 0.0)


def test_parse_polygon_2d_with_hole():
    polygons = parse_wkb(POLYGON_2D_WITH_HOLE)
    assert len(polygons) == 1
    rings = polygons[0]
    assert len(rings) == 2
    assert len(rings[0]) == 5  # outer
    assert len(rings[1]) == 5  # hole
    assert rings[1][0] == (4.0, 4.0, 0.0)


def test_parse_polygon_3d():
    polygons = parse_wkb(POLYGON_3D_TRIANGLE)
    assert len(polygons) == 1
    rings = polygons[0]
    assert len(rings) == 1
    ring = rings[0]
    assert len(ring) == 4
    for pt in ring:
        assert pt[2] == 5.0


def test_parse_multipolygon_2d_two_parts():
    polygons = parse_wkb(MULTIPOLYGON_2D_TWO_PARTS)
    assert len(polygons) == 2
    assert len(polygons[0][0]) == 5
    assert len(polygons[1][0]) == 5
    assert polygons[1][0][0] == (10.0, 0.0, 0.0)


def test_truncated_blob_raises():
    with pytest.raises(WKBParseError):
        parse_wkb(TRUNCATED_WKB)


def test_unsupported_type_raises():
    with pytest.raises(WKBParseError) as exc_info:
        parse_wkb(LINESTRING_WKB)
    assert "Unsupported" in str(exc_info.value) or "type" in str(exc_info.value)


def test_empty_blob_raises():
    with pytest.raises(WKBParseError):
        parse_wkb(b"")


# ─── SpatiaLite native BLOB-Geometry tests ──────────────────────────────────
#
# The fixtures stored in pyArchInit's `pyunitastratigrafiche` table are
# SpatiaLite blobs, not standard WKB. The parser auto-detects via
# `_looks_like_spatialite` and dispatches to `_parse_spatialite`. These
# tests cover that branch so a regression to the SpatiaLite framing
# (header offsets, MBR end marker, sub-polygon 0x69 prefix) is caught
# by CI rather than at production-import time on a real DB.

def test_parse_spatialite_polygon_2d():
    polygons = parse_wkb(SPATIALITE_POLYGON_2D_SQUARE)
    assert len(polygons) == 1
    rings = polygons[0]
    assert len(rings) == 1, "single ring expected"
    ring = rings[0]
    assert len(ring) == 5
    assert ring[0] == (0.0, 0.0, 0.0)
    assert ring[2] == (10.0, 10.0, 0.0)


def test_parse_spatialite_polygon_3d():
    polygons = parse_wkb(SPATIALITE_POLYGON_3D_TRIANGLE)
    assert len(polygons) == 1
    rings = polygons[0]
    assert len(rings) == 1
    ring = rings[0]
    assert len(ring) == 4
    # Z FLAG must be honoured — every vertex carries z=5
    for pt in ring:
        assert pt[2] == 5.0


def test_parse_spatialite_multipolygon_2d_two_parts():
    # MULTIPOLYGON is the form that actually exercises the SpatiaLite
    # sub-geometry framing (0x69 marker + sub-type without endian byte).
    # If this regresses we get silent mis-framing on real pyArchInit DBs.
    polygons = parse_wkb(SPATIALITE_MULTIPOLYGON_2D_TWO_PARTS)
    assert len(polygons) == 2
    # First sub at origin, second shifted to (10, 10)
    assert polygons[0][0][0] == (0.0, 0.0, 0.0)
    assert polygons[1][0][0] == (10.0, 10.0, 0.0)


def test_parse_spatialite_malformed_marker_raises():
    # If a future change broke the 0x69 guard, the parser would happily
    # read garbage as ring counts. The fixture replaces the first 0x69
    # with 0xFF — the parser must raise WKBParseError.
    with pytest.raises(WKBParseError) as exc_info:
        parse_wkb(SPATIALITE_MALFORMED_MARKER)
    msg = str(exc_info.value)
    assert "0x69" in msg or "marker" in msg
