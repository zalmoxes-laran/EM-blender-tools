"""Unit tests for the PyArchInit reverse-export helpers (issue #27, Sub-3).

Blender-free: the IngestResult formatter and the shared connection
resolver are exercised with duck-typed objects.
"""

import importlib.util
import os
import types

from import_operators.pyarchinit_connection import resolve_db_spec

# result_format lives inside a package whose __init__ imports bpy-bound
# operators; load the (Blender-free) module directly by path so this
# test runs outside Blender.
_RF_PATH = os.path.join(
    os.path.dirname(__file__), "..",
    "export_manager", "providers", "pyarchinit", "result_format.py",
)
_spec = importlib.util.spec_from_file_location("pyarchinit_result_format", _RF_PATH)
_rf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_rf)
format_ingest_result = _rf.format_ingest_result
is_node_uuid_error = _rf.is_node_uuid_error
node_uuid_help = _rf.node_uuid_help


# --- node_uuid error guidance --------------------------------------------

def test_is_node_uuid_error_detection():
    assert is_node_uuid_error("us_table.node_uuid column missing — run …")
    assert not is_node_uuid_error("some other failure")
    assert not is_node_uuid_error("")
    assert not is_node_uuid_error(None)


def test_node_uuid_help_mentions_pyarchinit():
    msg = node_uuid_help()
    assert "PyArchInit" in msg
    assert "node_uuid" in msg


def test_node_uuid_help_appends_failure_reason():
    msg = node_uuid_help("permission denied")
    assert "permission denied" in msg


class _Result:
    def __init__(self, **kw):
        self.applied = kw.get("applied", 0)
        self.inserted = kw.get("inserted", 0)
        self.updated = kw.get("updated", 0)
        self.skipped = kw.get("skipped", 0)
        self.epochs_created = kw.get("epochs_created", 0)
        self.conflicts = kw.get("conflicts", ())
        self.errors = kw.get("errors", ())
        self.dry_run = kw.get("dry_run", False)


# --- result formatter ----------------------------------------------------

def test_format_dry_run_heading():
    lines = format_ingest_result(_Result(inserted=3, applied=3), "sqlite:///x.sqlite", True)
    assert lines[0].startswith("DRY-RUN")
    assert any("Inserted:  3" in ln for ln in lines)


def test_format_write_heading():
    lines = format_ingest_result(_Result(applied=5), "postgresql://h/db", False)
    assert "Export complete" in lines[0]
    assert any("Target:" in ln and "postgresql://h/db" in ln for ln in lines)


def test_format_conflicts_truncated():
    conflicts = tuple(
        types.SimpleNamespace(field=f"f{i}", node_uuid=f"n{i}",
                              db_value="a", graph_value="b")
        for i in range(7)
    )
    lines = format_ingest_result(_Result(conflicts=conflicts), "t", True)
    assert any("Conflicts: 7" in ln for ln in lines)
    assert any("and 2 more" in ln for ln in lines)


def test_format_errors_listed():
    lines = format_ingest_result(_Result(errors=("boom",)), "t", False)
    assert any("Errors:" in ln for ln in lines)
    assert any("boom" in ln for ln in lines)


# --- shared connection resolver (export reuses the import config) --------

def _em_tools(**kw):
    defaults = dict(
        pyarchinit_connection_mode="sqlite",
        pyarchinit_db_path="",
        pyarchinit_pg_host="", pyarchinit_pg_port=5432,
        pyarchinit_pg_dbname="", pyarchinit_pg_user="",
        pyarchinit_pg_password="",
    )
    defaults.update(kw)
    return types.SimpleNamespace(**defaults)


def test_resolve_sqlite_ok():
    spec, err = resolve_db_spec(_em_tools(pyarchinit_db_path="/data/x.sqlite"))
    assert err is None
    assert spec == "/data/x.sqlite"


def test_resolve_sqlite_missing_path():
    spec, err = resolve_db_spec(_em_tools(pyarchinit_db_path=""))
    assert spec is None
    assert "SQLite" in err


def test_resolve_postgres_ok():
    spec, err = resolve_db_spec(_em_tools(
        pyarchinit_connection_mode="postgres",
        pyarchinit_pg_host="h", pyarchinit_pg_dbname="db",
        pyarchinit_pg_user="u", pyarchinit_pg_password="pw",
    ))
    assert err is None
    assert spec.startswith("postgresql+psycopg2://u:pw@h:5432/db")


def test_resolve_postgres_missing_fields():
    spec, err = resolve_db_spec(_em_tools(
        pyarchinit_connection_mode="postgres",
        pyarchinit_pg_host="h",  # missing db + user
    ))
    assert spec is None
    assert "host, database and user" in err


def test_resolve_postgres_missing_password():
    spec, err = resolve_db_spec(_em_tools(
        pyarchinit_connection_mode="postgres",
        pyarchinit_pg_host="h", pyarchinit_pg_dbname="db",
        pyarchinit_pg_user="u", pyarchinit_pg_password="",
    ))
    assert spec is None
    assert "password" in err.lower()
