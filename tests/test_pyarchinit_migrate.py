"""Tests for the EMTools-side node_uuid migration (issue #27, Sub-3).

Runs against a real temporary SQLite DB via SQLAlchemy (bundled), so it
exercises the actual ALTER/INDEX/backfill SQL — no Blender needed.
"""

import os
import tempfile

import pytest

sqlalchemy = pytest.importorskip("sqlalchemy")
from sqlalchemy import create_engine, inspect, text  # noqa: E402

from import_operators.pyarchinit_migrate import apply_node_uuid_migration  # noqa: E402


def _make_sqlite_with_us():
    fd, path = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    eng = create_engine(f"sqlite:///{path}")
    with eng.begin() as c:
        c.execute(text(
            "CREATE TABLE us_table (id_us INTEGER PRIMARY KEY, us INTEGER)"))
        c.execute(text(
            "INSERT INTO us_table (id_us, us) VALUES (1, 100), (2, 200)"))
    return path


def test_migration_adds_column_and_backfills():
    path = _make_sqlite_with_us()
    try:
        counts = apply_node_uuid_migration(f"sqlite:///{path}")
        assert counts.get("us_table") == 2
        eng = create_engine(f"sqlite:///{path}")
        cols = {c["name"] for c in inspect(eng).get_columns("us_table")}
        assert "node_uuid" in cols
        with eng.begin() as c:
            nulls = c.execute(text(
                "SELECT COUNT(*) FROM us_table WHERE node_uuid IS NULL")).scalar()
            distinct = c.execute(text(
                "SELECT COUNT(DISTINCT node_uuid) FROM us_table")).scalar()
        assert nulls == 0
        assert distinct == 2  # unique ids per row
    finally:
        os.remove(path)


def test_migration_is_idempotent():
    path = _make_sqlite_with_us()
    try:
        apply_node_uuid_migration(f"sqlite:///{path}")
        counts2 = apply_node_uuid_migration(f"sqlite:///{path}")
        assert counts2.get("us_table") == 0  # nothing left to backfill
    finally:
        os.remove(path)


def test_migration_raises_when_no_pyarchinit_tables():
    fd, path = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    try:
        with pytest.raises(Exception):
            apply_node_uuid_migration(f"sqlite:///{path}")
    finally:
        os.remove(path)
