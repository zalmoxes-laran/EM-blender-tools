"""Issue #34 — ``fetch_polygons`` returns the unit's identity with the key.

One read of ``us_table`` (matched in Python on normalised sito/area/us)
adds ``node_uuid``, ``settore`` and ``unita_tipo`` to every polygon row,
so the caller can resolve the US without a second query. A missing
``us_table``, or missing columns on it, must degrade to ``None`` values —
never break the fetch.
"""

import sqlite3
from pathlib import Path

import pytest

from import_operators.pyarchinit_db_reader import (
    detect_geometry_column,
    fetch_polygons,
    open_readonly,
)

FIXTURE = Path(__file__).parent / "fixtures" / "pyarchinit_minimal.sqlite"

IDENTITY_KEYS = ("node_uuid", "settore", "unita_tipo")


def _spatial_db(path, us_value=10):
    c = sqlite3.connect(path)
    c.execute("CREATE TABLE pyunitastratigrafiche "
              "(id INTEGER, sito TEXT, area TEXT, us INTEGER, the_geom BLOB)")
    c.execute("INSERT INTO pyunitastratigrafiche VALUES (1, 'S', '1', ?, x'0102')",
              (us_value,))
    c.execute("CREATE TABLE geometry_columns "
              "(f_table_name TEXT, f_geometry_column TEXT, srid INTEGER)")
    c.execute("INSERT INTO geometry_columns VALUES "
              "('pyunitastratigrafiche', 'the_geom', 32633)")
    return c


def _fetch_all(path):
    conn = open_readonly(str(path))
    try:
        geom_col, _srid = detect_geometry_column(conn)
        return list(fetch_polygons(conn, geom_col))
    finally:
        conn.close()


def test_rows_carry_identity_from_us_table(tmp_path):
    db = tmp_path / "p.sqlite"
    c = _spatial_db(db)
    c.execute("CREATE TABLE us_table "
              "(sito TEXT, area TEXT, us INTEGER, settore TEXT, "
              "unita_tipo TEXT, node_uuid TEXT)")
    c.execute("INSERT INTO us_table VALUES ('S', '1', 10, '', 'US', '0190-aaaa')")
    c.commit(); c.close()

    rows = _fetch_all(db)
    assert len(rows) == 1
    assert rows[0]["node_uuid"] == "0190-aaaa"
    assert rows[0]["settore"] == ""
    assert rows[0]["unita_tipo"] == "US"


def test_identity_match_tolerates_type_mismatch(tmp_path):
    # Spatial table stores us as INTEGER, us_table as TEXT (or vice
    # versa) — the match normalises both sides to stripped strings.
    db = tmp_path / "p.sqlite"
    c = _spatial_db(db, us_value=10)
    c.execute("CREATE TABLE us_table "
              "(sito TEXT, area TEXT, us TEXT, node_uuid TEXT)")
    c.execute("INSERT INTO us_table VALUES ('S', '1', ' 10 ', '0190-bbbb')")
    c.commit(); c.close()

    rows = _fetch_all(db)
    assert rows[0]["node_uuid"] == "0190-bbbb"


def test_us_table_without_identity_columns_gives_none():
    # The shared fixture has us_table with only sito/area/us: the keys
    # must be present on every row, all None.
    rows = _fetch_all(FIXTURE)
    assert rows
    for row in rows:
        for key in IDENTITY_KEYS:
            assert key in row
            assert row[key] is None


def test_db_without_us_table_gives_none(tmp_path):
    db = tmp_path / "p.sqlite"
    c = _spatial_db(db)
    c.commit(); c.close()

    rows = _fetch_all(db)
    assert len(rows) == 1
    for key in IDENTITY_KEYS:
        assert rows[0][key] is None
