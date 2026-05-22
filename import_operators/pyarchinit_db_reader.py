"""Read pyunitastratigrafiche rows from a PyArchInit SQLite database.

Handles schema detection (table presence, geometry column name, SRID)
and yields well-formed dicts ready for the WKB parser. Stays
Blender-free for easy testing.
"""

import sqlite3


TABLE_NAME = "pyunitastratigrafiche"
GEOM_COLUMN_FALLBACKS = ("the_geom", "geom", "geometry")
US_COLUMN_FALLBACKS = ("us_s", "us")
AREA_COLUMN_FALLBACKS = ("area_s", "area")
SITO_COLUMN_FALLBACKS = ("scavo_s", "sito", "site")


class PyArchInitDBError(RuntimeError):
    """Raised for schema or connection problems the caller must surface."""


def open_readonly(db_path):
    return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)


def detect_geometry_column(conn):
    """Return (geom_column_name, srid). SRID may be 0 if unknown."""
    try:
        cur = conn.execute(
            "SELECT f_geometry_column, srid FROM geometry_columns "
            "WHERE f_table_name = ?",
            (TABLE_NAME,),
        )
        row = cur.fetchone()
        if row:
            return row[0], int(row[1] or 0)
    except sqlite3.Error:
        pass
    cur = conn.execute(f"PRAGMA table_info('{TABLE_NAME}')")
    cols = [r[1] for r in cur.fetchall()]
    for cand in GEOM_COLUMN_FALLBACKS:
        if cand in cols:
            return cand, 0
    raise PyArchInitDBError(
        f"could not locate a geometry column in '{TABLE_NAME}'"
    )


def table_exists(conn, name=TABLE_NAME):
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    )
    return cur.fetchone() is not None


def detect_key_columns(conn):
    """Detect which us/area/sito column naming convention this DB uses.

    Real PyArchInit installations use the _s-suffixed names
    (us_s, area_s, scavo_s) on the spatial pyunitastratigrafiche
    table. Older or custom schemas may use the bare names (us, area,
    sito). Probe the table info and return whichever set is present.
    """
    cur = conn.execute(f"PRAGMA table_info('{TABLE_NAME}')")
    cols = {r[1] for r in cur.fetchall()}
    us_col = next((c for c in US_COLUMN_FALLBACKS if c in cols), None)
    area_col = next((c for c in AREA_COLUMN_FALLBACKS if c in cols), None)
    sito_col = next((c for c in SITO_COLUMN_FALLBACKS if c in cols), None)
    missing = [n for n, v in (("us", us_col), ("area", area_col),
                              ("sito/scavo", sito_col)) if v is None]
    if missing:
        raise PyArchInitDBError(
            f"missing key columns in '{TABLE_NAME}': {', '.join(missing)}"
        )
    return us_col, area_col, sito_col


def fetch_polygons(conn, geom_column):
    """Yield dicts {us_key, us, area, sito, wkb, wkb_hex_preview}."""
    us_col, area_col, sito_col = detect_key_columns(conn)
    cur = conn.execute(
        f"SELECT {us_col}, {area_col}, {sito_col}, {geom_column} "
        f"FROM {TABLE_NAME}"
    )
    for us, area, sito, geom in cur:
        if geom is None:
            continue
        wkb = bytes(geom)
        yield {
            "us": us,
            "area": area,
            "sito": sito,
            "us_key": f"sito={sito},area={area},us={us}",
            "wkb": wkb,
            "wkb_hex_preview": wkb[:16].hex(),
        }
