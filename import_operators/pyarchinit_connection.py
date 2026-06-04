"""Build PyArchInit PostgreSQL connection specs and keep credentials
out of the .blend (issue #27, Sub-2).

The password is **never** persisted in the .blend. Two storage tiers,
in order of preference:

1. **OS keychain** via the optional ``keyring`` library — macOS
   Keychain, Windows Credential Locker, or the Linux Secret Service.
2. **Session memory** fallback — a process-local dict discarded when
   Blender quits. Used when ``keyring`` (or its platform backend) is
   unavailable, so the feature still works without ever touching disk.

The Blender ``StringProperty`` that backs the password field is
declared with ``options={'SKIP_SAVE'}`` (see ``em_props.py``), so even
the transient typed value is excluded from the saved file.

This module is import-safe outside Blender (no ``bpy`` import) so the
URL builder, redaction, and account-id logic stay unit-testable.
"""

from urllib.parse import quote

# Keychain service name (the "where" namespace under which all EMTools
# PyArchInit credentials are filed in the OS keychain).
KEYRING_SERVICE = "emtools-pyarchinit"

# Session-only fallback store: account_id -> password. Lives for the
# lifetime of the Blender process and is never written anywhere.
_MEMORY_FALLBACK = {}


def _keyring():
    """Return the ``keyring`` module, or None if unavailable.

    Importing keyring can fail (not bundled) and, even when importable,
    a usable backend may be missing (typical on headless Linux). Both
    cases return None so callers fall back to session memory.
    """
    try:
        import keyring
        from keyring.errors import NoKeyringError
        try:
            # Probe for a working backend without raising on the caller.
            backend = keyring.get_keyring()
            if backend is None:
                return None
        except NoKeyringError:
            return None
        return keyring
    except Exception:
        return None


def account_id(host, port, dbname, user):
    """Stable keychain account label for a connection's credentials."""
    return f"{user}@{host}:{port}/{dbname}"


def set_password(host, port, dbname, user, password):
    """Persist ``password`` for the connection.

    Returns the tier actually used: ``"keychain"`` or ``"memory"``.
    """
    acct = account_id(host, port, dbname, user)
    kr = _keyring()
    if kr is not None:
        try:
            kr.set_password(KEYRING_SERVICE, acct, password)
            _MEMORY_FALLBACK.pop(acct, None)
            return "keychain"
        except Exception:
            pass
    _MEMORY_FALLBACK[acct] = password
    return "memory"


def get_password(host, port, dbname, user):
    """Return the stored password (keychain first, then memory), or None."""
    acct = account_id(host, port, dbname, user)
    kr = _keyring()
    if kr is not None:
        try:
            pw = kr.get_password(KEYRING_SERVICE, acct)
            if pw is not None:
                return pw
        except Exception:
            pass
    return _MEMORY_FALLBACK.get(acct)


def forget_password(host, port, dbname, user):
    """Remove the stored password from both keychain and memory."""
    acct = account_id(host, port, dbname, user)
    _MEMORY_FALLBACK.pop(acct, None)
    kr = _keyring()
    if kr is not None:
        try:
            kr.delete_password(KEYRING_SERVICE, acct)
        except Exception:
            pass


def resolve_db_spec(em_tools):
    """Resolve a pyArchInit connection spec from the shared em_tools fields.

    Reads the same connection properties used by the 3D GIS import panel
    (``pyarchinit_connection_mode`` + SQLite path or PostgreSQL fields)
    so import and export (Sub-2 / Sub-3) share one connection config.

    Returns ``(db_spec, error)``:

    * ``db_spec`` — a SQLite file path (SQLite mode) or a
      ``postgresql+psycopg2://…`` URL (PostgreSQL mode).
    * ``error`` — None on success, or a user-facing message when the
      chosen mode is missing required fields.

    Blender-free: ``em_tools`` is read purely via ``getattr`` so this
    stays unit-testable with a plain object.
    """
    mode = getattr(em_tools, "pyarchinit_connection_mode", "sqlite")
    if mode == "postgres":
        host = (getattr(em_tools, "pyarchinit_pg_host", "") or "").strip()
        port = getattr(em_tools, "pyarchinit_pg_port", 5432)
        dbname = (getattr(em_tools, "pyarchinit_pg_dbname", "") or "").strip()
        user = (getattr(em_tools, "pyarchinit_pg_user", "") or "").strip()
        if not (host and dbname and user):
            return None, ("PostgreSQL connection needs host, database and "
                          "user. Fill them in the 3D GIS import panel.")
        password = getattr(em_tools, "pyarchinit_pg_password", "") or \
            get_password(host, port, dbname, user)
        if not password:
            return None, ("No PostgreSQL password set. Type it in the 3D GIS "
                          "panel (and optionally 'Save to keychain').")
        return build_connection_url(host, port, dbname, user, password), None

    path = getattr(em_tools, "pyarchinit_db_path", "")
    if not path:
        return None, "Select a pyArchInit SQLite database file."
    return path, None


def build_connection_url(host, port, dbname, user, password):
    """Build a psycopg2/SQLAlchemy URL with URL-encoded credentials.

    ``postgresql+psycopg2://<user>:<password>@<host>:<port>/<dbname>``

    User and password are percent-encoded so that ``@``, ``:``, ``/``
    and other reserved characters in a password don't corrupt the URL.
    A falsy ``password`` produces a URL with no password component
    (libpq may then read ``~/.pgpass`` or prompt — handled upstream).
    """
    userinfo = quote(str(user or ""), safe="")
    if password:
        userinfo += ":" + quote(str(password), safe="")
    host_port = host or "localhost"
    if port:
        host_port += f":{int(port)}"
    return (
        f"postgresql+psycopg2://{userinfo}@{host_port}"
        f"/{quote(str(dbname or ''), safe='')}"
    )
