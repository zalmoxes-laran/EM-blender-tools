"""Generate tests/fixtures/pyarchinit_minimal.sqlite.

Run once with `.venv/bin/python tests/fixtures/build_fixture.py`. The
output file is committed; the script is kept for reproducibility.

The fixture emulates a minimal PyArchInit SQLite with us_table and
pyunitastratigrafiche, including:
  - 5 US in us_table
  - 3 polygons in pyunitastratigrafiche covering 3 of the 5 US
  - 1 orphan polygon referencing a non-existent US
  - so on re-import scenarios we have:
    * 3 happy-path matches
    * 2 US without geometry
    * 1 polygon orphan
"""

import sqlite3
import struct
from pathlib import Path

DB_PATH = Path(__file__).parent / "pyarchinit_minimal.sqlite"


def polygon_wkb(coords):
    """Build a 2D POLYGON WKB with one ring from a list of (x,y) coords."""
    closed = list(coords) + [coords[0]]
    body = struct.pack("<I", 1)              # 1 ring
    body += struct.pack("<I", len(closed))   # n points
    for x, y in closed:
        body += struct.pack("<dd", x, y)
    return b"\x01" + struct.pack("<I", 3) + body  # little-endian POLYGON


def main():
    if DB_PATH.exists():
        DB_PATH.unlink()
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    cur.execute(
        "CREATE TABLE us_table ("
        "id_us INTEGER PRIMARY KEY, sito TEXT, area TEXT, us INTEGER, "
        "d_stratigrafica TEXT)"
    )
    cur.execute(
        "CREATE TABLE pyunitastratigrafiche ("
        "id INTEGER PRIMARY KEY, sito TEXT, area TEXT, us INTEGER, "
        "the_geom BLOB)"
    )
    cur.execute(
        "CREATE TABLE geometry_columns ("
        "f_table_name TEXT, f_geometry_column TEXT, srid INTEGER)"
    )

    us_rows = [
        (1, "SITE1", "A", 1, "muro perimetrale"),
        (2, "SITE1", "A", 2, "crollo"),
        (3, "SITE1", "A", 3, "battuto pavimentale"),
        (4, "SITE1", "A", 4, "fossa"),
        (5, "SITE1", "A", 5, "riempimento"),
    ]
    cur.executemany("INSERT INTO us_table VALUES (?,?,?,?,?)", us_rows)

    polys = [
        ("SITE1", "A", 1, polygon_wkb([(0, 0), (4, 0), (4, 1), (0, 1)])),
        ("SITE1", "A", 2, polygon_wkb([(0, 2), (3, 2), (3, 4), (0, 4)])),
        ("SITE1", "A", 3, polygon_wkb([(5, 0), (8, 0), (8, 3), (5, 3)])),
        # Orphan: references a non-existent US 99
        ("SITE1", "A", 99, polygon_wkb([(10, 10), (11, 10), (11, 11), (10, 11)])),
    ]
    cur.executemany(
        "INSERT INTO pyunitastratigrafiche(sito, area, us, the_geom) "
        "VALUES (?,?,?,?)",
        polys,
    )
    cur.execute(
        "INSERT INTO geometry_columns VALUES (?,?,?)",
        ("pyunitastratigrafiche", "the_geom", 32633),
    )
    conn.commit()
    conn.close()
    print(f"Generated {DB_PATH} ({DB_PATH.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
