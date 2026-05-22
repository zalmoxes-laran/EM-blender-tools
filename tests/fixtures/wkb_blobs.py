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
