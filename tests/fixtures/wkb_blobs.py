"""WKB blob literals used by parser tests. Generated offline once with shapely."""

# POLYGON((0 0, 10 0, 10 10, 0 10, 0 0)) — single square ring, little-endian, 2D
POLYGON_2D_SQUARE = bytes.fromhex(
    "01"                                       # little-endian
    "03000000"                                 # type 3 (POLYGON)
    "01000000"                                 # 1 ring
    "05000000"                                 # 5 points
    "0000000000000000" "0000000000000000"      # (0, 0)
    "0000000000002440" "0000000000000000"      # (10, 0)
    "0000000000002440" "0000000000002440"      # (10, 10)
    "0000000000000000" "0000000000002440"      # (0, 10)
    "0000000000000000" "0000000000000000"      # (0, 0)
)

# POLYGON 2D with one interior hole (outer 10x10 square, hole 2x2 inside)
POLYGON_2D_WITH_HOLE = bytes.fromhex(
    "01" "03000000" "02000000"
    # outer ring: 5 points
    "05000000"
    "0000000000000000" "0000000000000000"
    "0000000000002440" "0000000000000000"
    "0000000000002440" "0000000000002440"
    "0000000000000000" "0000000000002440"
    "0000000000000000" "0000000000000000"
    # inner ring: 5 points (hole at (4,4)..(6,6))
    "05000000"
    "0000000000001040" "0000000000001040"
    "0000000000001840" "0000000000001040"
    "0000000000001840" "0000000000001840"
    "0000000000001040" "0000000000001840"
    "0000000000001040" "0000000000001040"
)

# POLYGON Z (3D) single triangle at z=5
POLYGON_3D_TRIANGLE = bytes.fromhex(
    "01" "030000" "80"          # type = 3 | Z_FLAG (little-endian)
    "01000000"                  # 1 ring
    "04000000"                  # 4 points
    "0000000000000000" "0000000000000000" "0000000000001440"  # (0,0,5)
    "0000000000002440" "0000000000000000" "0000000000001440"  # (10,0,5)
    "0000000000002440" "0000000000002440" "0000000000001440"  # (10,10,5)
    "0000000000000000" "0000000000000000" "0000000000001440"  # (0,0,5)
)

# MULTIPOLYGON 2D with 2 parts (two unit squares)
MULTIPOLYGON_2D_TWO_PARTS = bytes.fromhex(
    "01" "06000000" "02000000"
    # part 1: POLYGON 2D
    "01" "03000000" "01000000" "05000000"
    "0000000000000000" "0000000000000000"
    "000000000000F03F" "0000000000000000"
    "000000000000F03F" "000000000000F03F"
    "0000000000000000" "000000000000F03F"
    "0000000000000000" "0000000000000000"
    # part 2: POLYGON 2D (shifted to (10,0))
    "01" "03000000" "01000000" "05000000"
    "0000000000002440" "0000000000000000"
    "0000000000002640" "0000000000000000"
    "0000000000002640" "000000000000F03F"
    "0000000000002440" "000000000000F03F"
    "0000000000002440" "0000000000000000"
)

# Malformed: truncated mid-ring
TRUNCATED_WKB = bytes.fromhex("01" "03000000" "01000000" "05000000" "00")

# Unsupported type: LINESTRING (2)
LINESTRING_WKB = bytes.fromhex("01" "02000000" "00000000")


# ─── SpatiaLite native BLOB-Geometry fixtures ───────────────────────────────
#
# SpatiaLite framing recap (see import_operators/wkb_parser.py docstring):
#   [0]      0x00 start marker
#   [1]      endian (0x01 little, 0x00 big)
#   [2..5]   SRID (uint32)
#   [6..37]  MBR (4 doubles: minX, minY, maxX, maxY)
#   [38]     0x7C MBR end marker
#   [39..42] geometry type (uint32; no re-stated endian byte)
#   [43..]   body — sub-geometries of MULTIPOLYGON are prefixed with
#            a single 0x69 entity marker (not a re-stated endian byte).
#
# Reference: https://www.gaia-gis.it/fossil/libspatialite/wiki?name=BLOB-Geometry
# Blobs below were generated with `python -c struct.pack(...)` and verified
# against parse_wkb() round-trip — see tests/test_wkb_parser.py.

# SpatiaLite POLYGON 2D, single square ring (0,0)-(10,10), SRID 4326
SPATIALITE_POLYGON_2D_SQUARE = bytes.fromhex(
    "0001e6100000"                             # start + LE + SRID 4326
    "00000000000000000000000000000000"         # MBR minX, minY = 0,0
    "00000000000024400000000000002440"         # MBR maxX, maxY = 10,10
    "7c"                                        # MBR end marker
    "03000000"                                 # geom type POLYGON
    "01000000"                                 # 1 ring
    "05000000"                                 # 5 points
    "0000000000000000" "0000000000000000"       # (0, 0)
    "0000000000002440" "0000000000000000"       # (10, 0)
    "0000000000002440" "0000000000002440"       # (10, 10)
    "0000000000000000" "0000000000002440"       # (0, 10)
    "0000000000000000" "0000000000000000"       # (0, 0)
)

# SpatiaLite POLYGON Z (3D) — closed triangle at z=5
SPATIALITE_POLYGON_3D_TRIANGLE = bytes.fromhex(
    "0001e6100000"
    "00000000000000000000000000000000"
    "00000000000024400000000000002440"
    "7c"
    "03000080"                                 # type 3 | Z_FLAG (0x80000003 LE)
    "01000000"                                 # 1 ring
    "04000000"                                 # 4 points
    "000000000000000000000000000000000000000000001440"  # (0, 0, 5)
    "000000000000244000000000000000000000000000001440"  # (10, 0, 5)
    "000000000000244000000000000024400000000000001440"  # (10, 10, 5)
    "000000000000000000000000000000000000000000001440"  # (0, 0, 5)
)

# SpatiaLite MULTIPOLYGON 2D — two unit squares with proper 0x69 markers
SPATIALITE_MULTIPOLYGON_2D_TWO_PARTS = bytes.fromhex(
    "0001e6100000"
    "00000000000000000000000000000000"
    "00000000000026400000000000002640"          # MBR (0,0)-(11,11)
    "7c"
    "06000000"                                 # MULTIPOLYGON
    "02000000"                                 # 2 sub-polygons
    # ── sub-polygon 1: unit square at (0,0)
    "69"                                       # SpatiaLite entity marker
    "03000000"                                 # sub-type POLYGON (no endian byte)
    "01000000" "05000000"
    "0000000000000000" "0000000000000000"
    "000000000000f03f" "0000000000000000"
    "000000000000f03f" "000000000000f03f"
    "0000000000000000" "000000000000f03f"
    "0000000000000000" "0000000000000000"
    # ── sub-polygon 2: unit square at (10,10)
    "69"
    "03000000"
    "01000000" "05000000"
    "0000000000002440" "0000000000002440"
    "0000000000002640" "0000000000002440"
    "0000000000002640" "0000000000002640"
    "0000000000002440" "0000000000002640"
    "0000000000002440" "0000000000002440"
)

# SpatiaLite MULTIPOLYGON 2D whose first sub-polygon is prefixed with 0xFF
# instead of the expected 0x69 entity marker. Must raise WKBParseError —
# this guards against the parser silently mis-framing a corrupted blob.
SPATIALITE_MALFORMED_MARKER = bytes.fromhex(
    "0001e6100000"
    "00000000000000000000000000000000"
    "00000000000026400000000000002640"
    "7c"
    "06000000" "02000000"
    "ff"                                       # WRONG marker (should be 0x69)
    "03000000"
    "01000000" "05000000"
    "0000000000000000" "0000000000000000"
    "000000000000f03f" "0000000000000000"
    "000000000000f03f" "000000000000f03f"
    "0000000000000000" "000000000000f03f"
    "0000000000000000" "0000000000000000"
    "69"
    "03000000"
    "01000000" "05000000"
    "0000000000002440" "0000000000002440"
    "0000000000002640" "0000000000002440"
    "0000000000002640" "0000000000002640"
    "0000000000002440" "0000000000002640"
    "0000000000002440" "0000000000002440"
)
