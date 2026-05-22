"""Verify the filter feature is plumbed through fetch_polygons.

Covers:
* No filters → all rows returned.
* Single-column filter → only matching rows.
* Multi-column AND filter → intersection.
* US-table-only filter column (e.g. ``d_stratigrafica``) → silently
  skipped, so the geom query returns all rows even when the caller
  passed an unsupported filter key.
* ``us_s`` / ``area_s`` / ``scavo_s`` aliases translate to the actual
  spatial-table column names detected by ``detect_key_columns``.
* No match → empty result.
"""

from pathlib import Path

import pytest

from import_operators.pyarchinit_db_reader import (
    open_readonly,
    detect_geometry_column,
    fetch_polygons,
)


FIXTURE = Path(__file__).parent / "fixtures" / "pyarchinit_minimal.sqlite"


def _us_values(rows):
    return sorted(r["us"] for r in rows)


@pytest.fixture
def conn():
    c = open_readonly(str(FIXTURE))
    yield c
    c.close()


@pytest.fixture
def geom_col(conn):
    col, _srid = detect_geometry_column(conn)
    return col


def test_no_filters_returns_all(conn, geom_col):
    rows = list(fetch_polygons(conn, geom_col))
    assert _us_values(rows) == [1, 2, 3, 99]


def test_filter_by_us(conn, geom_col):
    rows = list(fetch_polygons(conn, geom_col, filters={"us": 2}))
    assert _us_values(rows) == [2]


def test_filter_by_sito_and_area(conn, geom_col):
    rows = list(
        fetch_polygons(conn, geom_col, filters={"sito": "SITE1", "area": "A"})
    )
    # All fixture rows are SITE1/A — multi-column AND should not
    # narrow further on this fixture.
    assert len(rows) == 4


def test_unknown_filter_column_is_ignored(conn, geom_col):
    # 'd_stratigrafica' exists on us_table but NOT on
    # pyunitastratigrafiche. The filter must be silently dropped, not
    # raise, and the query must return all rows.
    rows = list(
        fetch_polygons(conn, geom_col, filters={"d_stratigrafica": "crollo"})
    )
    assert _us_values(rows) == [1, 2, 3, 99]


def test_us_s_alias_translates_to_us(conn, geom_col):
    # Real PyArchInit installs use the _s-suffixed column names on
    # us_table; the alias map must translate ``us_s`` to whatever the
    # spatial table actually uses (``us`` in this fixture).
    rows = list(fetch_polygons(conn, geom_col, filters={"us_s": 3}))
    assert _us_values(rows) == [3]


def test_no_match_returns_empty(conn, geom_col):
    rows = list(fetch_polygons(conn, geom_col, filters={"sito": "NOPE"}))
    assert rows == []


def test_filter_is_parameterised_no_sql_injection(conn, geom_col):
    # Passing a SQL-injection-y value must be safely parameterised
    # (the value won't match, no SQL error is raised).
    rows = list(
        fetch_polygons(conn, geom_col, filters={"sito": "'; DROP TABLE x; --"})
    )
    assert rows == []
