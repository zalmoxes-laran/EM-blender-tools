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


# Filter-column aliases. Filter dicts are populated from the
# US-table form's mapping (which may use ``us_s``/``area_s``/``scavo_s``
# or the bare ``us``/``area``/``sito`` depending on the schema). The
# pyunitastratigrafiche spatial table can use a different convention,
# so translate each incoming filter key to the actual column detected
# on the spatial table.
_FILTER_ALIASES = {
    "us": "us",
    "us_s": "us",
    "area": "area",
    "area_s": "area",
    "sito": "sito",
    "site": "sito",
    "scavo": "sito",
    "scavo_s": "sito",
}


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


def _build_filter_clause(filters, us_col, area_col, sito_col):
    """Build a parameterised WHERE clause from ``filters``.

    Filter keys are matched against a small whitelist
    (``us`` / ``us_s`` / ``area`` / ``area_s`` / ``sito`` / ``site`` /
    ``scavo`` / ``scavo_s``) and translated to the actual detected
    column name in the spatial table. Unknown keys are silently
    skipped (so a US-table-only filter, e.g. ``d_stratigrafica``, does
    not raise — it simply doesn't constrain the geometry query).

    Returns ``(where_sql, params)`` — ``where_sql`` is either an empty
    string or starts with ``" WHERE "``. Always returns parameterised
    placeholders; never interpolates user-supplied values into the SQL.
    """
    if not filters:
        return "", []

    semantic_to_actual = {
        "us": us_col,
        "area": area_col,
        "sito": sito_col,
    }

    clauses = []
    params = []
    for raw_col, value in filters.items():
        if not isinstance(raw_col, str):
            continue
        semantic = _FILTER_ALIASES.get(raw_col.strip().lower())
        if semantic is None:
            # Column has no equivalent on the spatial table — skip
            # silently so US-table-only filters don't break the geom
            # query.
            continue
        actual_col = semantic_to_actual.get(semantic)
        if not actual_col:
            continue
        clauses.append(f"{actual_col} = ?")
        params.append(value)

    if not clauses:
        return "", []
    return " WHERE " + " AND ".join(clauses), params


def fetch_polygons(conn, geom_column, filters=None):
    """Yield dicts {us_key, us, area, sito, wkb, wkb_hex_preview}.

    If ``filters`` is non-empty, narrow the query to rows matching
    every recognised ``column = value`` pair. Filter columns are
    matched against a whitelist (us / us_s / area / area_s /
    sito / site / scavo / scavo_s) and translated to the actual
    column name detected on the spatial table; unknown columns are
    ignored so US-table-only filters don't break here.
    """
    us_col, area_col, sito_col = detect_key_columns(conn)
    where_sql, params = _build_filter_clause(
        filters, us_col, area_col, sito_col
    )
    cur = conn.execute(
        f"SELECT {us_col}, {area_col}, {sito_col}, {geom_column} "
        f"FROM {TABLE_NAME}{where_sql}",
        params,
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
