"""Pure-Python WKB / SpatiaLite-BLOB parser for PyArchInit polygon imports.

Supports POLYGON (type 3) and MULTIPOLYGON (type 6), both 2D and 3D, in:

- standard WKB (PostGIS / OGC), and
- SpatiaLite native BLOB-Geometry format (39-byte header + 0x7C MBR
  end marker, 0x69 entity marker before each sub-geometry of a
  collection).

Return shape:
    parse_wkb(blob) -> list[polygon]
    polygon         = list[ring]
    ring            = list[(x, y, z)] tuples (z=0.0 for 2D inputs)
"""

import struct


WKB_TYPE_POLYGON = 3
WKB_TYPE_MULTIPOLYGON = 6
Z_FLAG = 0x80000000

SPATIALITE_START = 0x00
SPATIALITE_MBR_END = 0x7C
SPATIALITE_ENTITY = 0x69


class WKBParseError(ValueError):
    """Raised when the WKB blob cannot be parsed."""


def parse_wkb(blob):
    if not blob:
        raise WKBParseError("empty blob")
    if _looks_like_spatialite(blob):
        return _parse_spatialite(blob)
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
            return _read_multipolygon_standard(blob, 5, endian)
        raise WKBParseError(f"Unsupported WKB type {base_type}")
    except struct.error as e:
        raise WKBParseError(f"truncated or malformed WKB: {e}") from e


def _looks_like_spatialite(blob):
    return (
        len(blob) >= 44
        and blob[0] == SPATIALITE_START
        and blob[1] in (0x00, 0x01)
        and blob[38] == SPATIALITE_MBR_END
    )


def _parse_spatialite(blob):
    """Parse a SpatiaLite native BLOB-Geometry.

    Header layout:
        [0]      0x00 start marker
        [1]      endian (0x01 little, 0x00 big)
        [2..5]   SRID (uint32)
        [6..37]  MBR (4 doubles)
        [38]     0x7C MBR end marker
        [39..42] geometry type (uint32, no separate endian byte)
        [43..]   body (sub-geometries are prefixed with 0x69, not a
                 re-stated endian byte)
    """
    try:
        endian = "<" if blob[1] == 0x01 else ">"
        geom_type = struct.unpack_from(endian + "I", blob, 39)[0]
        has_z = bool(geom_type & Z_FLAG)
        base_type = geom_type & 0x000FFFFF
        offset = 43
        if base_type == WKB_TYPE_POLYGON:
            polygon, _ = _read_polygon(blob, offset, endian, has_z)
            return [polygon]
        if base_type == WKB_TYPE_MULTIPOLYGON:
            return _read_multipolygon_spatialite(blob, offset, endian)
        raise WKBParseError(
            f"Unsupported SpatiaLite geometry type {base_type}"
        )
    except struct.error as e:
        raise WKBParseError(
            f"truncated or malformed SpatiaLite blob: {e}"
        ) from e


def _read_polygon(blob, offset, endian, has_z):
    n_rings = struct.unpack_from(endian + "I", blob, offset)[0]
    offset += 4
    rings = []
    for _ in range(n_rings):
        ring, offset = _read_ring(blob, offset, endian, has_z)
        rings.append(ring)
    return rings, offset


def _read_multipolygon_standard(blob, offset, endian):
    """Standard WKB MULTIPOLYGON: each sub-polygon starts with its own
    endian byte + type uint32."""
    n_polygons = struct.unpack_from(endian + "I", blob, offset)[0]
    offset += 4
    polygons = []
    for _ in range(n_polygons):
        sub_endian = "<" if blob[offset] == 1 else ">"
        sub_type = struct.unpack_from(sub_endian + "I", blob, offset + 1)[0]
        sub_has_z = bool(sub_type & Z_FLAG)
        sub_base = sub_type & 0x000FFFFF
        if sub_base != WKB_TYPE_POLYGON:
            raise WKBParseError(
                f"MULTIPOLYGON contains non-polygon sub-type {sub_base}"
            )
        polygon, offset = _read_polygon(
            blob, offset + 5, sub_endian, sub_has_z
        )
        polygons.append(polygon)
    return polygons


def _read_multipolygon_spatialite(blob, offset, endian):
    """SpatiaLite MULTIPOLYGON: each sub-polygon is prefixed with 0x69
    (entity marker) instead of a re-stated endian byte. The sub-type
    uses the same endianness as the outer blob."""
    n_polygons = struct.unpack_from(endian + "I", blob, offset)[0]
    offset += 4
    polygons = []
    for _ in range(n_polygons):
        if blob[offset] != SPATIALITE_ENTITY:
            raise WKBParseError(
                f"expected SpatiaLite entity marker 0x69 at offset "
                f"{offset}, got {blob[offset]:#x}"
            )
        offset += 1
        sub_type = struct.unpack_from(endian + "I", blob, offset)[0]
        sub_has_z = bool(sub_type & Z_FLAG)
        sub_base = sub_type & 0x000FFFFF
        if sub_base != WKB_TYPE_POLYGON:
            raise WKBParseError(
                f"SpatiaLite MULTIPOLYGON contains non-polygon "
                f"sub-type {sub_base}"
            )
        offset += 4
        polygon, offset = _read_polygon(blob, offset, endian, sub_has_z)
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
