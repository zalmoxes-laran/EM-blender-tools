"""Best-effort PyArchInit ``node_uuid`` migration from EMTools (#27, Sub-3).

``s3dgraphy.sync.GraphIngestor`` requires a ``node_uuid`` column on the
PyArchInit tables (``us_table``, ``inventario_materiali_table``,
``periodizzazione_table``). That column is normally added by a
PyArchInit-side production migration — PyArchInit owns the DB schema.

When exporting to a database that hasn't been migrated yet, EMTools
attempts to apply the same change (add the column + a partial unique
index, then backfill unique ids). If it can't (e.g. missing DDL
privileges, no primary key on PostgreSQL), the caller falls back to a
clear message telling the user to update the database from PyArchInit.

Backend-agnostic via SQLAlchemy (SQLite + PostgreSQL). Blender-free.
This mirrors the logic of s3dgraphy's test-only ``_uuid_backfill``
helper but uses only SQLAlchemy so it carries no s3dgraphy-internal
imports.
"""

import uuid as _uuid


#: Tables that need a stable node identity for the s3dgraphy bridge.
TABLES = (
    "us_table",
    "inventario_materiali_table",
    "periodizzazione_table",
)

#: Canonical primary-key column per table (fallback for legacy PG dumps
#: that declare no PRIMARY KEY).
_CANONICAL_PK = {
    "us_table": "id_us",
    "inventario_materiali_table": "id_invmat",
    "periodizzazione_table": "id_perfas",
}


def _new_uuid():
    """A unique id string. Prefer s3dgraphy's uuid7 (time-ordered) when
    present, else fall back to uuid4 — the column only needs uniqueness."""
    try:
        from s3dgraphy.sync.uuid7 import uuid7
        return str(uuid7())
    except Exception:
        return str(_uuid.uuid4())


def apply_node_uuid_migration(sa_spec):
    """Add ``node_uuid`` columns + indexes and backfill them.

    ``sa_spec`` is a SQLAlchemy URL (``sqlite:///…`` or
    ``postgresql+psycopg2://…``). Only tables that actually exist are
    touched. Returns ``{table: backfilled_row_count}`` for the tables
    present. Raises on any failure so the caller can fall back to a
    user-facing message.
    """
    from sqlalchemy import create_engine, inspect, text

    engine = create_engine(sa_spec)
    insp = inspect(engine)
    existing = set(insp.get_table_names())
    targets = [t for t in TABLES if t in existing]
    if not targets:
        raise RuntimeError(
            "none of the PyArchInit tables (us_table, "
            "inventario_materiali_table, periodizzazione_table) were found"
        )
    is_pg = engine.dialect.name == "postgresql"

    # 1. Add column + partial unique index (idempotent).
    with engine.begin() as conn:
        for table in targets:
            cols = {c["name"] for c in insp.get_columns(table)}
            if "node_uuid" not in cols:
                conn.execute(
                    text(f"ALTER TABLE {table} ADD COLUMN node_uuid TEXT"))
            conn.execute(text(
                f"CREATE UNIQUE INDEX IF NOT EXISTS ix_{table}_node_uuid "
                f"ON {table}(node_uuid) WHERE node_uuid IS NOT NULL"))

    # 2. Backfill NULL node_uuid values.
    insp = inspect(engine)  # refresh after DDL
    counts = {}
    with engine.begin() as conn:
        for table in targets:
            pks = insp.get_pk_constraint(table).get("constrained_columns") or []
            if pks:
                pk_col = pks[0]
            elif is_pg:
                pk_col = _CANONICAL_PK.get(table)
                if not pk_col or pk_col not in {
                        c["name"] for c in insp.get_columns(table)}:
                    raise RuntimeError(
                        f"{table}: no primary key on PostgreSQL and no "
                        f"canonical id column — cannot backfill safely")
            else:
                pk_col = "rowid"  # SQLite implicit rowid

            rows = conn.execute(text(
                f"SELECT {pk_col} FROM {table} WHERE node_uuid IS NULL"
            )).fetchall()
            for (row_id,) in rows:
                conn.execute(
                    text(f"UPDATE {table} SET node_uuid = :u "
                         f"WHERE {pk_col} = :id"),
                    {"u": _new_uuid(), "id": row_id},
                )
            counts[table] = len(rows)
    return counts
