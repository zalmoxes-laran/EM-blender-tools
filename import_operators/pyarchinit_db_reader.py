"""Read pyunitastratigrafiche rows from a PyArchInit database.

Handles schema detection (table presence, geometry column name, SRID)
and yields well-formed dicts ready for the WKB parser. Stays
Blender-free for easy testing.

Two backends are supported (issue #27, Sub-2):

* **SQLite / SpatiaLite** — the original path. The geometry column is
  read as a native BLOB and handed to ``wkb_parser`` directly.
* **PostgreSQL / PostGIS** — selected when the caller passes a
  ``postgresql://…`` / ``postgresql+psycopg2://…`` connection URL.
  The geometry is fetched as standard WKB via ``ST_AsBinary(<geom>)``
  so the very same ``wkb_parser`` works unchanged. Requires
  ``psycopg2`` (bundled as ``psycopg2-binary``).

The module-level ``open_readonly`` / ``detect_geometry_column`` /
``detect_key_columns`` / ``fetch_polygons`` helpers remain SQLite-only
and parameterised with ``?`` placeholders (their behaviour is frozen
for the existing test-suite). Backend-agnostic callers should use
:class:`PyArchInitReader`, which dispatches on the connection spec.
"""

import sqlite3


import re

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


# ---------------------------------------------------------------------------
# PostgreSQL / PostGIS backend (issue #27, Sub-2)
#
# Mirrors the SQLite helpers above but talks to PostGIS through psycopg2.
# The only material difference is that the geometry column is read with
# ``ST_AsBinary(<geom>)`` so the bytes on the wire are standard WKB —
# exactly what ``wkb_parser`` already understands. psycopg2 uses ``%s``
# placeholders (not ``?``), so the filter clause is rebuilt accordingly.
# ---------------------------------------------------------------------------

PG_URL_PREFIXES = (
    "postgresql://",
    "postgresql+psycopg2://",
    "postgres://",
)


def is_postgres_spec(db_spec):
    """Return True if ``db_spec`` is a PostgreSQL connection URL.

    Anything else (a filesystem path, ``sqlite:///…``) is treated as the
    SQLite/SpatiaLite path by the dispatcher.
    """
    return isinstance(db_spec, str) and db_spec.startswith(PG_URL_PREFIXES)


def redacted_db_spec(db_spec):
    """Return a copy of ``db_spec`` safe to persist as provenance.

    For a PostgreSQL URL the ``user:password@`` userinfo is stripped so
    the password is never written into the .blend (issue #27 explicitly
    forbids storing DB passwords there). SQLite paths are returned
    unchanged.

    ``postgresql://user:secret@host:5432/db`` → ``postgresql://host:5432/db``
    """
    if not is_postgres_spec(db_spec):
        return db_spec
    scheme, sep, rest = db_spec.partition("://")
    if not sep:
        return db_spec
    # rest = [userinfo@]host[:port]/db... — drop everything up to '@'.
    host_part = rest.split("@", 1)[1] if "@" in rest else rest
    return f"{scheme}://{host_part}"


# Match a postgres/postgresql URL with optional ``+driver`` tag and
# optional userinfo. Captures the scheme (group 1) and the host-onwards
# part (group 2) so the substitution can rebuild the URL without the
# ``user:password@`` segment. Tolerant of URLs embedded mid-sentence —
# used defensively to strip credentials out of exception messages.
_PG_URL_IN_TEXT = re.compile(
    r"(postgres(?:ql)?(?:\+[A-Za-z0-9_]+)?://)"  # scheme[+driver]://
    r"(?:[^@\s/'\"`<>]+@)?"                       # optional userinfo@
    r"([^\s'\"`<>]+)"                              # host[:port]/db...
)


def redact_url_from_message(msg):
    """Defensively strip ``user:password@`` from any postgres URL in *msg*.

    Exception messages from SQLAlchemy / psycopg2 / s3dgraphy.sync may
    or may not embed the connection URL today; the upstream contract
    can shift across versions. This helper rewrites every postgres URL
    substring it finds so a forwarded error popup cannot leak
    credentials regardless of how the upstream layer formats its
    message. Non-postgres messages pass through unchanged.

    ``"could not connect to postgres://u:p@db.example/foo: …"`` →
    ``"could not connect to postgres://db.example/foo: …"``
    """
    if msg is None:
        return msg
    return _PG_URL_IN_TEXT.sub(lambda m: m.group(1) + m.group(2), str(msg))


def _normalise_pg_dsn(url):
    """Strip the SQLAlchemy ``+psycopg2`` driver tag psycopg2 can't parse.

    ``postgresql+psycopg2://u:p@h/db`` → ``postgresql://u:p@h/db``.
    A bare ``postgres://`` is left untouched (libpq accepts it).
    """
    if url.startswith("postgresql+psycopg2://"):
        return "postgresql://" + url[len("postgresql+psycopg2://"):]
    return url


def open_pg_readonly(url):
    """Open a read-only psycopg2 connection from a connection URL.

    Raises :class:`PyArchInitDBError` (never leaks the password-bearing
    DSN in the message) when psycopg2 is missing or the connection
    fails.
    """
    try:
        import psycopg2  # noqa: F401  (bundled as psycopg2-binary)
    except ImportError as exc:
        raise PyArchInitDBError(
            "PostgreSQL import requires the 'psycopg2' driver, which is "
            "not available in this Blender build. Re-run './em.sh setup' "
            "to refresh the bundled wheels."
        ) from exc
    try:
        conn = psycopg2.connect(_normalise_pg_dsn(url))
        # Read-only + autocommit: we never write on the import path.
        conn.set_session(readonly=True, autocommit=True)
        return conn
    except Exception as exc:  # psycopg2.OperationalError et al.
        # Deliberately do NOT echo ``url`` — it embeds the password.
        raise PyArchInitDBError(
            f"could not connect to PostgreSQL database: {exc}"
        ) from exc


def _pg_columns(conn, table=TABLE_NAME):
    """Return the set of column names of ``table`` (empty if absent)."""
    cur = conn.cursor()
    cur.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = %s",
        (table,),
    )
    return {r[0] for r in cur.fetchall()}


def pg_table_exists(conn, name=TABLE_NAME):
    cur = conn.cursor()
    cur.execute(
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_name = %s LIMIT 1",
        (name,),
    )
    return cur.fetchone() is not None


def detect_geometry_column_pg(conn):
    """Return (geom_column_name, srid) for the PostGIS spatial table.

    Prefers the PostGIS ``geometry_columns`` view (authoritative SRID);
    falls back to ``information_schema`` column probing with srid 0.
    """
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT f_geometry_column, srid FROM geometry_columns "
            "WHERE f_table_name = %s",
            (TABLE_NAME,),
        )
        row = cur.fetchone()
        if row:
            return row[0], int(row[1] or 0)
    except Exception:
        # geometry_columns missing (PostGIS not installed) — fall back.
        pass
    cols = _pg_columns(conn)
    for cand in GEOM_COLUMN_FALLBACKS:
        if cand in cols:
            return cand, 0
    raise PyArchInitDBError(
        f"could not locate a geometry column in '{TABLE_NAME}'"
    )


def detect_key_columns_pg(conn):
    """PostgreSQL twin of :func:`detect_key_columns`."""
    cols = _pg_columns(conn)
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


def _build_filter_clause_pg(filters, us_col, area_col, sito_col):
    """``_build_filter_clause`` with ``%s`` placeholders for psycopg2.

    Same whitelist / alias translation / silent-skip semantics; only the
    placeholder style differs. Values stay parameterised — never
    interpolated — so the SQL-injection guard is identical.
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
            continue
        actual_col = semantic_to_actual.get(semantic)
        if not actual_col:
            continue
        clauses.append(f"{actual_col} = %s")
        params.append(value)

    if not clauses:
        return "", []
    return " WHERE " + " AND ".join(clauses), params


def fetch_polygons_pg(conn, geom_column, filters=None):
    """PostgreSQL twin of :func:`fetch_polygons`.

    Geometry is fetched as WKB via ``ST_AsBinary`` so the shared
    ``wkb_parser`` handles it unchanged.
    """
    us_col, area_col, sito_col = detect_key_columns_pg(conn)
    where_sql, params = _build_filter_clause_pg(
        filters, us_col, area_col, sito_col
    )
    cur = conn.cursor()
    cur.execute(
        f"SELECT {us_col}, {area_col}, {sito_col}, "
        f"ST_AsBinary({geom_column}) "
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


class PyArchInitReader:
    """Backend-agnostic reader for the ``pyunitastratigrafiche`` table.

    Pass either a SQLite/SpatiaLite file path or a PostgreSQL connection
    URL (``postgresql://…``); the reader dispatches to the matching
    backend and exposes one uniform interface to the geometry importer.
    Blender-free. Usable as a context manager::

        with PyArchInitReader(db_spec) as reader:
            if reader.table_exists():
                geom_col, srid = reader.detect_geometry_column()
                for row in reader.fetch_polygons(filters):
                    ...
    """

    def __init__(self, db_spec):
        self.db_spec = db_spec
        self.is_postgres = is_postgres_spec(db_spec)
        if self.is_postgres:
            self._conn = open_pg_readonly(db_spec)
        else:
            self._conn = open_readonly(db_spec)
        self._geom_col = None
        self._srid = None

    def table_exists(self):
        if self.is_postgres:
            return pg_table_exists(self._conn)
        return table_exists(self._conn)

    def detect_geometry_column(self):
        if self.is_postgres:
            self._geom_col, self._srid = detect_geometry_column_pg(self._conn)
        else:
            self._geom_col, self._srid = detect_geometry_column(self._conn)
        return self._geom_col, self._srid

    def fetch_polygons(self, filters=None):
        if self._geom_col is None:
            self.detect_geometry_column()
        if self.is_postgres:
            yield from fetch_polygons_pg(self._conn, self._geom_col, filters)
        else:
            yield from fetch_polygons(self._conn, self._geom_col, filters)

    def close(self):
        try:
            self._conn.close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
