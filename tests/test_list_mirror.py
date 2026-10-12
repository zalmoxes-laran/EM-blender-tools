"""The panel's lists follow the room: a field that arrives lands on its row.

Measured on 12 Oct 2026 (prova 5 del tavolo): editor2 renamed US3, the graph
had the new name, the row of US3 in the panel still showed the old one. The row
was searched by the NEW name, or by `node_id` — which the populated rows leave
empty (units keep the id in `id_node`, epochs in `id`).
"""

from __future__ import annotations

import importlib.util
import pathlib
from types import SimpleNamespace as NS

ROOT = pathlib.Path(__file__).resolve().parent.parent
_sp = importlib.util.spec_from_file_location(
    "emt_list_mirror", ROOT / "sync_manager" / "list_mirror.py")
LM = importlib.util.module_from_spec(_sp)
_sp.loader.exec_module(LM)          # type: ignore[union-attr]


class Row(NS):
    """A row as populate_lists leaves it: the fields it has, nothing more."""


def unit_row(nid, name, **kw):
    return Row(name=name, id_node=nid, node_id="", description=kw.get("description", ""),
               epoch=kw.get("epoch", ""), parent_node_id=kw.get("parent_node_id", ""),
               contained_in_name=kw.get("contained_in_name", ""))


def tools(units=(), epochs=(), docs=(), props=(), extr=(), comb=(), reused=()):
    return NS(stratigraphy=NS(units=list(units), reused=list(reused)),
              epochs=NS(list=list(epochs)), em_sources_list=list(docs),
              em_properties_list=list(props), em_extractors_list=list(extr),
              em_combiners_list=list(comb))


def node(nid, name, kind="US", **kw):
    return NS(node_id=nid, name=name, node_type=kind,
              description=kw.pop("description", ""), attributes={}, **kw)


def test_A_RENAME_FROM_THE_ROOM_reaches_the_row_of_the_unit():
    """Prova 5: the node already has the new name; the row is found by id."""
    t = tools(units=[unit_row("US1", "US 1"), unit_row("US3", "US 3")])
    n = node("US3", "US 3 · da editor2")
    changed = LM.mirror(t, n, old_name="US 3")
    assert t.stratigraphy.units[1].name == "US 3 · da editor2"
    assert t.stratigraphy.units[0].name == "US 1"
    assert changed == ["units.name"]


def test_a_row_WITHOUT_its_id_is_found_by_the_name_it_had_BEFORE():
    t = tools(units=[Row(name="US 3", id_node="", description="")])
    LM.mirror(t, node("US3", "US 3 bis", description="d"), old_name="US 3")
    assert t.stratigraphy.units[0].name == "US 3 bis"
    assert t.stratigraphy.units[0].description == "d"


def test_a_row_with_ANOTHER_id_is_another_node_whatever_its_name():
    t = tools(units=[unit_row("US9", "US 3")])
    assert LM.mirror(t, node("US3", "US 3 bis"), old_name="US 3") == []
    assert t.stratigraphy.units[0].name == "US 3"


def test_a_value_ALREADY_THERE_is_not_written_again():
    """The description has an update callback that emits to the room."""
    t = tools(units=[unit_row("US3", "US 3", description="same")])
    assert LM.mirror(t, node("US3", "US 3", description="same")) == []


def test_name_is_written_BEFORE_description():
    """The description callback finds its node by name: with the new name in
    place it sees the value already there and does not echo."""
    order = []

    class Spy(Row):
        def __setattr__(self, k, v):
            order.append(k)
            super().__setattr__(k, v)

    r = Spy(name="US 3", id_node="US3", description="")
    order.clear()
    LM.mirror(tools(units=[r]), node("US3", "US 3 bis", description="new"), "US 3")
    assert order == ["name", "description"]


def test_an_EPOCH_follows_and_its_name_travels_to_the_units_that_show_it():
    ep = Row(name="Roman", id="E1", start_time=0.0, end_time=0.0,
             epoch_color="#FFFFFF", epoch_RGB_color=(1.0, 1.0, 1.0))
    t = tools(units=[unit_row("US3", "US 3", epoch="Roman")], epochs=[ep],
              reused=[Row(epoch="Roman", em_element="US 3")])
    n = node("E1", "Roman imperial", kind="EpochNode",
             start_time=-27.0, end_time=476.0, color="#FF0000")
    changed = LM.mirror(t, n, old_name="Roman")
    assert ep.name == "Roman imperial" and ep.start_time == -27.0 and ep.end_time == 476.0
    assert ep.epoch_color == "#FF0000" and ep.epoch_RGB_color[1] == 0.0
    assert t.stratigraphy.units[0].epoch == "Roman imperial"
    assert t.stratigraphy.reused[0].epoch == "Roman imperial"
    assert "units.epoch" in changed and "epochs.name" in changed


def test_a_unit_rename_travels_to_its_CONTAINED_units_and_to_the_reused_table():
    t = tools(units=[unit_row("US1", "US 1"),
                     unit_row("US2", "US 2", parent_node_id="US1", contained_in_name="US 1")],
              reused=[Row(epoch="Roman", em_element="US 1")])
    LM.mirror(t, node("US1", "US 1 bis"), old_name="US 1")
    assert t.stratigraphy.units[1].contained_in_name == "US 1 bis"
    assert t.stratigraphy.reused[0].em_element == "US 1 bis"


def test_a_DOCUMENT_follows_with_its_url():
    doc = Row(name="D.01", id_node="D01", description="", url="", icon_url="CHECKBOX_DEHLT")
    t = tools(docs=[doc])
    LM.mirror(t, node("D01", "D.01 plan", kind="document", url="https://x/y.pdf"))
    assert doc.name == "D.01 plan" and doc.url == "https://x/y.pdf"
    assert doc.icon_url == "CHECKBOX_HLT"


def test_a_PROPERTY_shows_its_original_name_and_its_value():
    p = Row(name="material", id_node="P1", description="", url="", icon_url="")
    n = node("P1", "material.US3", kind="property", value="travertine")
    n.attributes = {"original_name": "material"}
    LM.mirror(tools(props=[p]), n)
    assert p.name == "material" and p.url == "travertine"


def test_extractor_and_combiner_follow():
    e = Row(name="D.01.01", id_node="X1", description="", url="", icon_url="")
    c = Row(name="C.01", id_node="C1", description="", url="", icon_url="")
    t = tools(extr=[e], comb=[c])
    LM.mirror(t, node("X1", "D.01.02", kind="extractor", source="p. 4"))
    LM.mirror(t, node("C1", "C.02", kind="combiner", sources=["a", "b"]))
    assert (e.name, e.url) == ("D.01.02", "p. 4")
    assert (c.name, c.url) == ("C.02", "a")


def test_a_list_that_is_MISSING_is_skipped_not_a_crash():
    t = NS(stratigraphy=NS(units=[unit_row("US3", "US 3")]))
    assert LM.mirror(t, node("US3", "US 3 bis"), "US 3") == ["units.name"]
    assert LM.mirror(None, node("US3", "x")) == []
