"""N1 · le geometrie di PyArchInit trovano la loro US senza che il nome cambi.

L'etichetta resta quella del mapping (``{area}.{settore}.{unita_tipo}{us}``):
qui si prova che l'adattatore la ricompone come l'importer di s3Dgraphy, che
preferisce l'UUID quando la riga lo porta, e che un grafo coi numeri nudi
continua ad agganciarsi come prima. La prova sul database PyArchInit vero
(482 poligoni) è `blender_smoke_import_from_table.py`.
"""

import json
import pathlib
import sqlite3

import pytest

from import_operators.pyarchinit_us_adapter import (
    DEFAULT_TEMPLATE, USResolver, compose_label, parse_us_key, read_us_rows)


class _N:
    def __init__(self, name, node_id, node_type="US"):
        self.name, self.node_id, self.node_type = name, node_id, node_type


class _G:
    def __init__(self, *nodes):
        self.nodes = list(nodes)
        self.attributes = {}


def test_IL_TEMPLATE_E_QUELLO_DEL_MAPPING_DI_S3DGRAPHY():
    import s3dgraphy
    m = (pathlib.Path(s3dgraphy.__file__).parent / "mappings" / "pyarchinit"
         / "pyarchinit_us_mapping.json")
    if not m.exists():
        pytest.skip("mapping pyArchInit non nella s3dgraphy installata")
    tpl = json.loads(m.read_text())["table_settings"]["node_name_template"]
    assert tpl == DEFAULT_TEMPLATE


@pytest.mark.parametrize("row,label", [
    ({"area": "1", "settore": "", "unita_tipo": "US", "us": "10"}, "1.US10"),
    ({"area": "1", "settore": "1  ", "unita_tipo": "US", "us": "1"}, "1.1.US1"),
    ({"area": "", "settore": None, "unita_tipo": "USM", "us": 6}, "USM6"),
    ({"area": None, "settore": None, "unita_tipo": None, "us": "7"}, "7"),
])
def test_L_ETICHETTA_COME_LA_COMPONE_L_IMPORTER(row, label):
    assert compose_label(row, DEFAULT_TEMPLATE) == label


def test_COME_L_IMPORTER_DI_S3DGRAPHY():
    """La stessa regola, non una sua imitazione: confronto con il metodo vero."""
    from s3dgraphy.importer.pyarchinit_importer import PyArchInitImporter
    imp = PyArchInitImporter.__new__(PyArchInitImporter)
    imp.mapping = {"table_settings": {"node_name_template": DEFAULT_TEMPLATE}}
    for row in ({"area": "1", "settore": "", "unita_tipo": "US", "us": "10"},
                {"area": "2", "settore": "B", "unita_tipo": "USM", "us": "3"},
                {"area": "", "settore": "", "unita_tipo": "", "us": "9"}):
        assert compose_label(row, DEFAULT_TEMPLATE) == imp._resolve_node_name(dict(row), "us")


def test_LA_CHIAVE_DEL_LETTORE():
    assert parse_us_key("sito=Scavo,area=1,us=10") == {"sito": "Scavo", "area": "1", "us": "10"}


def test_RISOLVE_PER_ETICHETTA_E_PER_UUID_PRIMA():
    rows = [
        {"sito": "S", "area": "1", "settore": "", "unita_tipo": "US", "us": "10"},
        {"sito": "S", "area": "1", "settore": "", "unita_tipo": "USM", "us": "6",
         "node_uuid": "0190-aaaa"},
    ]
    us10 = _N("1.US10", "x1")
    usm6 = _N("un nome cambiato a mano", "0190-aaaa", "USM")
    prop = _N("10", "p1", "property")
    r = USResolver(rows)
    g = _G(prop, us10, usm6)
    assert r.resolve(g, "sito=S,area=1,us=10") is us10
    assert r.resolve(g, "sito=S,area=1,us=6") is usm6
    assert r.how == {"sito=S,area=1,us=10": "label", "sito=S,area=1,us=6": "uuid"}


def test_UN_GRAFO_COI_NUMERI_NUDI_SI_AGGANCIA_COME_PRIMA():
    r = USResolver([])
    n = _N("10", "x")
    assert r.resolve(_G(n), "sito=S,area=1,us=10") is n
    assert r.how["sito=S,area=1,us=10"] == "bare"
    assert r.resolve(_G(n), "sito=S,area=1,us=11") is None
    assert r.how["sito=S,area=1,us=11"] == "orphan"


def test_LEGGE_US_TABLE_IN_SOLA_LETTURA(tmp_path):
    db = tmp_path / "p.sqlite"
    c = sqlite3.connect(db)
    c.execute("CREATE TABLE us_table (sito, area, settore, unita_tipo, us)")
    c.executemany("INSERT INTO us_table VALUES (?,?,?,?,?)",
                  [("S", "1", "", "US", "10"), ("T", "1", "", "US", "10")])
    c.commit(); c.close()
    rows = read_us_rows(str(db), "S")
    assert len(rows) == 1 and rows[0]["sito"] == "S"
    assert USResolver(rows).label_for("sito=S,area=1,us=10") == "1.US10"
