"""Issue #34 — the reader resolves a US by identity: uuid → label → bare.

The resolution logic lives in ``pyarchinit_us_resolution`` (bpy-free,
same pattern as ``reimport_planner``) so the geometry importer can
delegate to it and these tests run under plain pytest. The label rule
is the mapping's own (``table_settings.node_name_template``), the same
``PyArchInitImporter._resolve_node_name`` applies.
"""

import pytest

from import_operators.geom_constants import GRAPH_ATTR_AUX_US_NO_GEOM
from import_operators.pyarchinit_us_resolution import (
    DEFAULT_NAME_TEMPLATE,
    RowIdentityResolver,
    compose_label,
    record_us_without_geometry,
    resolve_bare,
)


class _N:
    def __init__(self, name, node_id, node_type="US"):
        self.name, self.node_id, self.node_type = name, node_id, node_type


class _G:
    def __init__(self, *nodes):
        self.nodes = list(nodes)
        self.attributes = {}


def _poly(us, node_uuid=None, settore="", unita_tipo="US", area="1", sito="S"):
    return {
        "us": us, "area": area, "sito": sito,
        "us_key": f"sito={sito},area={area},us={us}",
        "node_uuid": node_uuid, "settore": settore, "unita_tipo": unita_tipo,
    }


# --- the label rule -------------------------------------------------------

def test_default_template_is_the_mapping_rule():
    assert DEFAULT_NAME_TEMPLATE == "{area}.{settore}.{unita_tipo}{us}"


@pytest.mark.parametrize("row,label", [
    ({"area": "1", "settore": "", "unita_tipo": "US", "us": "10"}, "1.US10"),
    ({"area": "1", "settore": "1  ", "unita_tipo": "US", "us": "1"}, "1.1.US1"),
    ({"area": "", "settore": None, "unita_tipo": "USM", "us": 6}, "USM6"),
    ({"area": None, "settore": None, "unita_tipo": None, "us": "7"}, "7"),
])
def test_compose_label_like_the_importer(row, label):
    assert compose_label(row, DEFAULT_NAME_TEMPLATE) == label


# --- the resolver: uuid → label → bare ------------------------------------

def test_resolves_by_uuid_first():
    renamed = _N("renamed by hand", "0190-aaaa", "USM")
    r = RowIdentityResolver([_poly("6", node_uuid="0190-aaaa", unita_tipo="USM")])
    assert r(_G(renamed), "sito=S,area=1,us=6") is renamed
    assert r.how["sito=S,area=1,us=6"] == "uuid"


def test_resolves_by_composed_label():
    us10 = _N("1.US10", "x1")
    r = RowIdentityResolver([_poly("10")])
    assert r(_G(us10), "sito=S,area=1,us=10") is us10
    assert r.how["sito=S,area=1,us=10"] == "label"


def test_label_prefers_stratigraphic_nodes():
    prop = _N("1.US10", "p1", "property")
    us10 = _N("1.US10", "x1")
    r = RowIdentityResolver([_poly("10")])
    assert r(_G(prop, us10), "sito=S,area=1,us=10") is us10


def test_falls_back_to_bare_number():
    bare = _N("10", "x1")
    r = RowIdentityResolver([_poly("10")])
    assert r(_G(bare), "sito=S,area=1,us=10") is bare
    assert r.how["sito=S,area=1,us=10"] == "bare"


def test_rows_without_identity_keys_still_resolve_bare():
    # A polygon dict from an older fetch (no node_uuid/settore/unita_tipo
    # keys at all) must not break the resolver.
    poly = {"us": "10", "area": "1", "sito": "S",
            "us_key": "sito=S,area=1,us=10"}
    bare = _N("10", "x")
    r = RowIdentityResolver([poly])
    assert r(_G(bare), "sito=S,area=1,us=10") is bare


def test_unknown_key_is_orphan():
    r = RowIdentityResolver([_poly("10")])
    assert r(_G(_N("1.US10", "x")), "sito=S,area=1,us=99") is None
    assert r.how["sito=S,area=1,us=99"] == "orphan"


def test_matched_by_counts():
    us10 = _N("1.US10", "a")
    usm6 = _N("renamed by hand", "0190-aaaa", "USM")
    bare7 = _N("7", "c")
    g = _G(us10, usm6, bare7)
    polys = [
        _poly("10"),
        _poly("6", node_uuid="0190-aaaa", unita_tipo="USM"),
        _poly("7"),
        _poly("99"),
    ]
    r = RowIdentityResolver(polys)
    for p in polys:
        r(g, p["us_key"])
    assert r.matched_by() == {"uuid": 1, "label": 1, "bare": 1, "orphan": 1}


def test_custom_template_is_used():
    n = _N("S-1-10", "x")
    r = RowIdentityResolver([_poly("10")], name_template="{sito}-{area}-{us}")
    assert r(_G(n), "sito=S,area=1,us=10") is n
    assert r.how["sito=S,area=1,us=10"] == "label"


# --- the bare resolver (the reader's historical behaviour) ----------------

def test_resolve_bare_prefers_stratigraphic():
    prop, us = _N("10", "p", "property"), _N("10", "x")
    assert resolve_bare(_G(prop, us), "sito=S,area=1,us=10") is us


def test_resolve_bare_none_when_absent():
    assert resolve_bare(_G(_N("11", "x")), "sito=S,area=1,us=10") is None
    assert resolve_bare(None, "sito=S,area=1,us=10") is None


# --- «without geometry» means «no polygon resolved on it» -----------------

def test_record_counts_only_nodes_no_polygon_resolved_on():
    us10 = _N("1.US10", "a")           # a polygon resolves on it by label
    us20 = _N("1.US20", "b")           # nothing resolves on it
    prop = _N("Interpretation", "p", "property")
    g = _G(us10, us20, prop)
    polys = [_poly("10")]
    report = {"us_without_geometry": []}
    record_us_without_geometry(polys, g, report, RowIdentityResolver(polys))
    assert report["us_without_geometry"] == ["1.US20"]
    assert g.attributes[GRAPH_ATTR_AUX_US_NO_GEOM] == ["b"]


def test_record_with_bare_resolver():
    # With the bare fallback a node named by number still counts as
    # «with geometry» when a polygon resolved on it.
    n10 = _N("10", "a")
    g = _G(n10)
    polys = [{"us": "10", "area": "1", "sito": "S",
              "us_key": "sito=S,area=1,us=10"}]
    report = {"us_without_geometry": []}
    record_us_without_geometry(polys, g, report, resolve_bare)
    assert report["us_without_geometry"] == []
