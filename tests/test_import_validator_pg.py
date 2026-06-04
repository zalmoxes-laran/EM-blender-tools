"""ImportValidator accepts a PostgreSQL connection_url for pyArchInit (#27).

Regression guard for the 'Missing required field: filepath' error hit
when importing in PostgreSQL mode (settings carry connection_url, not
filepath).
"""

from import_operators.import_validator import ImportValidator


def test_pyarchinit_accepts_connection_url():
    settings = {
        "import_type": "pyarchinit",
        "connection_url": "postgresql+psycopg2://u:p@h:5432/db",
        "mapping_name": "pyarchinit_us",
    }
    ok, err = ImportValidator.validate("pyarchinit", settings)
    assert ok, err


def test_pyarchinit_accepts_sqlite_filepath():
    settings = {
        "import_type": "pyarchinit",
        "filepath": "/data/site.sqlite",
        "mapping_name": "pyarchinit_us",
    }
    ok, err = ImportValidator.validate("pyarchinit", settings)
    assert ok, err


def test_pyarchinit_rejects_when_no_connection_source():
    settings = {
        "import_type": "pyarchinit",
        "mapping_name": "pyarchinit_us",
    }
    ok, err = ImportValidator.validate("pyarchinit", settings)
    assert not ok
    assert "one of" in err.lower()


def test_pyarchinit_still_requires_mapping():
    settings = {
        "import_type": "pyarchinit",
        "connection_url": "postgresql://u:p@h/db",
        "mapping_name": "none",
    }
    ok, err = ImportValidator.validate("pyarchinit", settings)
    assert not ok
    assert "mapping" in err.lower()
