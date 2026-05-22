from fixtures.wkb_blobs import POLYGON_2D_SQUARE
from import_operators.wkb_parser import parse_wkb


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
