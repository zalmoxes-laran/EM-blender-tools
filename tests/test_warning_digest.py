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
