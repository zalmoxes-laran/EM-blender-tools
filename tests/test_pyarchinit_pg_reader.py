"""Unit tests for the PostgreSQL branch of pyarchinit_db_reader (#27).

The live psycopg2 paths need a real PostGIS server (covered by the
in-Blender / integration pass). Here we cover the pure-Python logic:
backend detection, credential redaction, and the ``%s`` filter-clause
builder — including its SQL-injection guard and alias translation.
"""

from import_operators.pyarchinit_db_reader import (
    is_postgres_spec,
    redacted_db_spec,
    _build_filter_clause_pg,
)


# --- backend detection ---------------------------------------------------

def test_is_postgres_spec_detects_urls():
    assert is_postgres_spec("postgresql://u:p@h/db")
    assert is_postgres_spec("postgresql+psycopg2://u:p@h/db")
    assert is_postgres_spec("postgres://u:p@h/db")


def test_is_postgres_spec_rejects_paths():
    assert not is_postgres_spec("/data/site.sqlite")
    assert not is_postgres_spec("sqlite:///data/site.sqlite")
    assert not is_postgres_spec("")
    assert not is_postgres_spec(None)


# --- credential redaction ------------------------------------------------

def test_redacted_strips_userinfo():
    assert (redacted_db_spec("postgresql://enzo:secret@db.example.org:5432/pyarch")
            == "postgresql://db.example.org:5432/pyarch")


def test_redacted_keeps_driver_tag():
    assert (redacted_db_spec("postgresql+psycopg2://u:p@h/db")
            == "postgresql+psycopg2://h/db")


def test_redacted_url_without_userinfo_is_unchanged():
    assert (redacted_db_spec("postgresql://h:5432/db")
            == "postgresql://h:5432/db")


def test_redacted_leaves_sqlite_paths():
    assert redacted_db_spec("/data/site.sqlite") == "/data/site.sqlite"


# --- %s filter clause ----------------------------------------------------

def test_filter_clause_empty():
    where, params = _build_filter_clause_pg(None, "us_s", "area_s", "scavo_s")
    assert where == ""
    assert params == []


def test_filter_clause_uses_percent_s_and_actual_columns():
    where, params = _build_filter_clause_pg(
        {"us": 5}, "us_s", "area_s", "scavo_s")
    assert where == " WHERE us_s = %s"
    assert params == [5]


def test_filter_clause_translates_aliases():
    # 'sito'/'scavo_s' both map to the detected sito column; 'area_s' to area.
    where, params = _build_filter_clause_pg(
        {"scavo_s": "SITE1", "area_s": "A"}, "us_s", "area_s", "scavo_s")
    assert "scavo_s = %s" in where
    assert "area_s = %s" in where
    assert set(params) == {"SITE1", "A"}


def test_filter_clause_skips_unknown_columns():
    # A US-table-only filter column with no spatial-table equivalent is
    # silently dropped (mirrors the SQLite builder).
    where, params = _build_filter_clause_pg(
        {"d_stratigrafica": "crollo"}, "us_s", "area_s", "scavo_s")
    assert where == ""
    assert params == []


def test_filter_clause_value_is_parameterised_not_interpolated():
    # SQL-injection guard: the malicious value travels as a bound param,
    # never spliced into the SQL text.
    evil = "'; DROP TABLE x; --"
    where, params = _build_filter_clause_pg(
        {"sito": evil}, "us_s", "area_s", "scavo_s")
    assert where == " WHERE scavo_s = %s"
    assert params == [evil]
    assert "DROP TABLE" not in where
