"""Unit tests for the PostgreSQL connection-spec helpers (issue #27).

All Blender-free: the connection module never imports ``bpy`` and the
keychain layer degrades to an in-memory fallback, so these run under a
plain pytest invocation.
"""

from import_operators.pyarchinit_connection import (
    build_connection_url,
    account_id,
    set_password,
    get_password,
    forget_password,
)


def test_build_url_basic():
    url = build_connection_url("localhost", 5432, "pyarch", "enzo", "secret")
    assert url == "postgresql+psycopg2://enzo:secret@localhost:5432/pyarch"


def test_build_url_percent_encodes_password():
    # A password with URL-reserved characters must not corrupt the URL.
    url = build_connection_url("h", 5432, "db", "user", "p@ss:w/rd?")
    assert "p%40ss%3Aw%2Frd%3F" in url
    # The single literal '@' separating userinfo from host stays.
    assert url.count("@") == 1


def test_build_url_percent_encodes_user():
    url = build_connection_url("h", 5432, "db", "do@main\\u", "pw")
    assert "do%40main" in url


def test_build_url_no_password():
    url = build_connection_url("h", 5432, "db", "user", "")
    assert url == "postgresql+psycopg2://user@h:5432/db"


def test_build_url_default_host_and_optional_port():
    url = build_connection_url("", None, "db", "user", "pw")
    assert url == "postgresql+psycopg2://user:pw@localhost/db"


def test_account_id_is_stable():
    assert account_id("h", 5432, "db", "u") == "u@h:5432/db"


def test_memory_fallback_roundtrip():
    # When no OS keychain is present (typical CI), the helpers fall back
    # to session memory — set/get/forget must still behave.
    set_password("h", 5432, "db", "u", "topsecret")
    assert get_password("h", 5432, "db", "u") == "topsecret"
    forget_password("h", 5432, "db", "u")
    assert get_password("h", 5432, "db", "u") is None
