"""Pure-Python WKB parser for PyArchInit polygon imports.

Supports POLYGON (type 3) and MULTIPOLYGON (type 6), both 2D and 3D.

Return shape:
    parse_wkb(blob) -> list[polygon]
    polygon         = list[ring]
    ring            = list[(x, y, z)] tuples (z=0.0 for 2D inputs)
"""

import struct


WKB_TYPE_POLYGON = 3
WKB_TYPE_MULTIPOLYGON = 6
Z_FLAG = 0x80000000


class WKBParseError(ValueError):
    """Raised when the WKB blob cannot be parsed."""


def parse_wkb(blob):
    if not blob:
        raise WKBParseError("empty blob")
    if len(blob) < 5:
        raise WKBParseError(f"WKB blob too short ({len(blob)} bytes)")
    try:
        endian = "<" if blob[0] == 1 else ">"
        geom_type = struct.unpack_from(endian + "I", blob, 1)[0]
        has_z = bool(geom_type & Z_FLAG)
        base_type = geom_type & 0x000FFFFF
        if base_type == WKB_TYPE_POLYGON:
            polygon, _ = _read_polygon(blob, 5, endian, has_z)
            return [polygon]
        if base_type == WKB_TYPE_MULTIPOLYGON:
            return _read_multipolygon(blob, 5, endian)
        raise WKBParseError(f"Unsupported WKB type {base_type}")
    except struct.error as e:
        raise WKBParseError(f"truncated or malformed WKB: {e}") from e


def _read_polygon(blob, offset, endian, has_z):
    n_rings = struct.unpack_from(endian + "I", blob, offset)[0]
    offset += 4
    rings = []
    for _ in range(n_rings):
        ring, offset = _read_ring(blob, offset, endian, has_z)
        rings.append(ring)
    return rings, offset


def _read_multipolygon(blob, offset, endian):
    n_polygons = struct.unpack_from(endian + "I", blob, offset)[0]
    offset += 4
    polygons = []
    for _ in range(n_polygons):
        sub_endian = "<" if blob[offset] == 1 else ">"
        sub_type = struct.unpack_from(sub_endian + "I", blob, offset + 1)[0]
        sub_has_z = bool(sub_type & Z_FLAG)
        sub_base = sub_type & 0x000FFFFF
        if sub_base != WKB_TYPE_POLYGON:
            raise WKBParseError(f"MULTIPOLYGON contains non-polygon sub-type {sub_base}")
        polygon, offset = _read_polygon(blob, offset + 5, sub_endian, sub_has_z)
        polygons.append(polygon)
    return polygons


def _read_ring(blob, offset, endian, has_z):
    n_points = struct.unpack_from(endian + "I", blob, offset)[0]
    offset += 4
    coords_per_pt = 3 if has_z else 2
    fmt = endian + ("d" * coords_per_pt)
    size = 8 * coords_per_pt
    points = []
    for _ in range(n_points):
        vals = struct.unpack_from(fmt, blob, offset)
        offset += size
        if has_z:
            points.append((vals[0], vals[1], vals[2]))
        else:
            points.append((vals[0], vals[1], 0.0))
    return points, offset
