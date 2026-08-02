"""S6 — the warning digest and the version banner.

Both modules are deliberately ``bpy``-free so the logic that decides what the
author reads can be tested outside Blender. What the panel then does with the
groups is a drawing detail; what must not regress is that nothing is lost and
that the biggest problem is the one shown first.
"""

import importlib.util
import pathlib

# ``em_setup/__init__.py`` is the addon's registration module and imports bpy at
# module level, so `from em_setup.x import y` cannot work outside Blender. The
# two modules under test import nothing from bpy on purpose — load them straight
# from their files, bypassing the package __init__.
_EM_SETUP = pathlib.Path(__file__).resolve().parent.parent / "em_setup"


def _load(name):
    spec = importlib.util.spec_from_file_location(
        f"_emtools_test_{name}", _EM_SETUP / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_digest = _load("warning_digest")
_banner = _load("version_banner")

digest_warnings = _digest.digest_warnings
summarise = _digest.summarise
format_banner = _banner.format_banner
read_graph_versions = _banner.read_graph_versions

UNTYPED = ("Node 'SF04.2' has no recognised EM type (its yEd shape/colour "
           "matches no node type): it and its connections stay untyped. "
           "Classify it in the source graph.")
GROUP = ("Group 'Vestibolo' has no EM role (not a ParadataNodeGroup / "
         "ActivityNodeGroup / TimeBranch / US-USD-VSF container): it is kept "
         "as an organisational box.")
DEGRADED = ("Connection 'is_in_activity' not allowed between 'Node' "
            "(name:SF04.2) and 'ActivityNodeGroup' (name:'Vestibolo'). "
            "Using 'generic_connection' instead.")


def test_families_are_recognised():
    groups = {g.key: g for g in digest_warnings([UNTYPED, GROUP, DEGRADED])}
    assert set(groups) == {"untyped_node", "unclassified_group", "degraded_edge"}
    assert groups["untyped_node"].count == 1


def test_nothing_is_lost():
    """The digest summarises; it must never filter."""
    warnings = [UNTYPED] * 18 + [DEGRADED] * 57 + ["something else entirely"]
    groups = digest_warnings(warnings)
    assert sum(g.count for g in groups) == len(warnings)
    # The unmatched line lands in "Other" rather than vanishing.
    assert any(g.key == "other" and g.count == 1 for g in groups)


def test_biggest_family_first():
    groups = digest_warnings([UNTYPED] * 3 + [DEGRADED] * 40 + [GROUP])
    assert [g.key for g in groups] == [
        "degraded_edge", "untyped_node", "unclassified_group"]


def test_blank_lines_are_dropped():
    assert digest_warnings(["", "   ", None]) == []
    assert digest_warnings([]) == []
    assert digest_warnings(None) == []


def test_order_is_stable_across_identical_inputs():
    """The panel must not reshuffle between two imports of the same file."""
    warnings = [UNTYPED] * 5 + [GROUP] * 5 + [DEGRADED] * 5
    first = [g.key for g in digest_warnings(warnings)]
    second = [g.key for g in digest_warnings(warnings)]
    assert first == second


def test_summary_line():
    groups = digest_warnings([UNTYPED] * 18 + [DEGRADED] * 57)
    text = summarise(groups)
    assert "57" in text and "18" in text
    assert summarise([]) == ""


# ── version banner ────────────────────────────────────────────────────────────

class _Graph:
    def __init__(self, attributes):
        self.attributes = attributes


def test_emjson_schema_version_is_read_from_the_graph():
    v = read_graph_versions(_Graph({"emjson_schema_version": 2}))
    assert v["emjson_schema"] == "2"


def test_graphml_source_declares_no_schema():
    """A GraphML has no schema of its own — the absence is the information."""
    v = read_graph_versions(_Graph({}))
    assert v["emjson_schema"] == ""
    assert v["stratigraph"] == ""


def test_banner_omits_what_is_not_declared():
    text = format_banner({"emjson_schema": "2", "em_datamodel": "1.6.0",
                          "stratigraph": ""}, source_label="em.json")
    assert text == "em.json · em.json schema 2 · EM 1.6.0"
    assert "StratiGraph" not in text


def test_banner_is_empty_when_nothing_is_known():
    assert format_banner({"emjson_schema": "", "em_datamodel": "",
                          "stratigraph": ""}) == ""


# ── structured records: grouping by kind, exactly ─────────────────────────────

REC_UNTYPED = {"kind": "untyped_node", "node_id": "n1",
               "message": "Node 'SF04.2' has no recognised EM type: …"}
REC_DEGRADED = {"kind": "degraded_edge", "node_id": "d1", "edge_id": "e1",
                "target_id": "d2",
                "message": "Connection D.1 → D.2 is 'generic_connection': …"}


def test_a_record_is_filed_by_its_kind_not_by_its_words():
    """The point of the records: the message can be reworded, translated or
    truncated and the family still lands right."""
    rec = {"kind": "untyped_node", "node_id": "n1",
           "message": "qualcosa di completamente diverso"}
    groups = digest_warnings([rec])
    assert [g.key for g in groups] == ["untyped_node"]


def test_records_and_strings_mix_in_one_pass():
    """A graph carries records for its state warnings and bare strings for the
    free-form ones; both must land in the right family together."""
    groups = {g.key: g for g in digest_warnings(
        [REC_UNTYPED, UNTYPED, "Please add a proper site ID in the header"])}
    assert groups["untyped_node"].count == 2
    assert groups["header"].count == 1


def test_the_record_travels_with_its_message():
    """Aligned by index, so a click-to-reveal knows which element each drawn
    line points at."""
    (group,) = digest_warnings([REC_DEGRADED])
    assert group.messages == [REC_DEGRADED["message"]]
    assert group.records == [REC_DEGRADED]
    assert group.node_ids() == ["d1"]


def test_a_string_has_no_record_and_says_so():
    """`None` is the truthful answer: for this line there is nothing to
    select."""
    (group,) = digest_warnings([UNTYPED])
    assert group.records == [None]
    assert group.node_ids() == []


def test_an_unknown_kind_is_visible_not_swallowed():
    """A kind added upstream that this build does not know must show up in
    "Other" rather than vanish."""
    rec = {"kind": "something_new_upstream", "node_id": "n9",
           "message": "a family this version has never heard of"}
    (group,) = digest_warnings([rec])
    assert group.key == "other"
    assert group.node_ids() == ["n9"]


def test_records_do_not_change_what_the_panel_draws():
    """Same messages either way — the records add addressing, not new text."""
    as_records = digest_warnings([REC_UNTYPED, REC_DEGRADED])
    as_strings = digest_warnings([REC_UNTYPED["message"],
                                  REC_DEGRADED["message"]])
    assert ([g.messages for g in as_records]
            == [g.messages for g in as_strings])


def test_a_record_without_a_message_is_dropped_like_a_blank_line():
    assert digest_warnings([{"kind": "untyped_node", "node_id": "n1",
                             "message": "   "}]) == []


# ── click-to-node: the panel must be able to address each line ────────────────

def test_records_stay_aligned_with_the_lines_the_panel_draws():
    """The panel walks `group.messages` by index and reaches for
    `group.records[i]`; if the two ever fell out of step a line would offer a
    button to the WRONG element, which is worse than no button."""
    mixed = [REC_UNTYPED, UNTYPED, REC_DEGRADED, "Please add a proper site ID"]
    for group in digest_warnings(mixed):
        assert len(group.records) == len(group.messages)
        for msg, rec in zip(group.messages, group.records):
            if rec is not None:
                assert rec["message"].strip() == msg


def test_a_degraded_record_offers_its_candidates_to_the_tooltip():
    rec = {**REC_DEGRADED, "candidates": ["abuts", "cuts"]}
    (group,) = digest_warnings([rec])
    assert group.records[0]["candidates"] == ["abuts", "cuts"]
