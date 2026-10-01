"""S6 — which language version am I working with?

Reading a graph is an act of interpretation, and two versions are always in
play: the one the FILE declares, and the one the tools use to READ it. When
they differ, everything downstream — a border colour, an edge that resolves or
degrades — depends on which of the two you were thinking of. The banner shows
both instead of making the author guess.

``bpy``-free on purpose, so it can be unit-tested outside Blender.
"""

from __future__ import annotations


def read_em_datamodel_version():
    """The EM node-datamodel version of the INSTALLED s3dgraphy — i.e. the
    version doing the reading. Returns "" when it cannot be determined, which
    the panel renders as a dash rather than as a fake value."""
    try:
        from s3dgraphy.nodes.base_node import load_json_mapping
        dm = load_json_mapping("s3Dgraphy_node_datamodel.json") or {}
        return str(dm.get("s3Dgraphy_data_model_version") or "")
    except Exception:
        return ""


def read_graph_versions(graph):
    """Extract the version facts a graph carries.

    Returns ``{"emjson_schema": str, "em_datamodel": str, "stratigraph": str}``
    with "" for anything the document does not declare. The em.json importer
    records ``emjson_schema_version`` on ``graph.attributes``; a GraphML source
    declares no schema at all, and that absence is shown as such.
    """
    attrs = getattr(graph, "attributes", None) or {}
    schema = attrs.get("emjson_schema_version")
    return {
        "emjson_schema": "" if schema in (None, "") else str(schema),
        "em_datamodel": read_em_datamodel_version(),
        # StratiGraph does not stamp a version into em.json yet. Read it if a
        # document ever starts declaring one; never invent it.
        "stratigraph": str(attrs.get("stratigraph_version") or ""),
    }


def format_banner(versions, source_label=""):
    """Compact one-line banner, e.g.
    ``"em.json schema 2 · EM 1.6.0"``. Fields the document does not declare are
    left out rather than shown empty."""
    parts = []
    if source_label:
        parts.append(source_label)
    if versions.get("emjson_schema"):
        parts.append(f"em.json schema {versions['emjson_schema']}")
    if versions.get("em_datamodel"):
        parts.append(f"EM {versions['em_datamodel']}")
    if versions.get("stratigraph"):
        parts.append(f"StratiGraph {versions['stratigraph']}")
    return " · ".join(parts)


# ── the datamodel the wheel carries, against the one the pin promises ─────────
# EMtools does not vendor the datamodel: it reads it from the s3dgraphy wheel.
# So "which datamodel am I reading?" has one honest answer — the fingerprint of
# the wheel actually imported — and one expectation, written next to the pin
# when the wheel was bundled. A version string cannot tell them apart (dev14 vs
# dev14 differed in Aug 2026); the RFC 8785 digest can.

#: written by ``scripts/rebundle_s3dgraphy.py --fingerprint``; never by hand
EXPECTED_FINGERPRINT_FILE = "datamodel.fingerprint.json"


def expected_fingerprint(path=None):
    """The fingerprint recorded with the pin, or None if the file is missing."""
    import json
    import os
    path = path or os.path.join(os.path.dirname(__file__), EXPECTED_FINGERPRINT_FILE)
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return None


def check_datamodel(expected=None, found=None):
    """``{state, differences, expected_version, found_version}``.

    ``state`` is ``aligned``, ``differs``, or ``unchecked`` (no expectation on
    disk, or a wheel too old to compute a fingerprint — dev24 and earlier). It
    warns, it never blocks: a graph read with a different datamodel is still a
    graph, but the author should know which language read it.
    """
    expected = expected if expected is not None else expected_fingerprint()
    found_version = ""
    try:
        import s3dgraphy
        found_version = str(getattr(s3dgraphy, "__version__", "") or "")
    except Exception:
        pass
    out = {"state": "unchecked", "differences": [],
           "expected_version": str((expected or {}).get("s3dgraphy") or ""),
           "found_version": found_version}
    if not expected:
        return out
    try:
        from s3dgraphy import api
        if found is None:
            found = api.datamodel_fingerprint()
        if found.get("digest") == expected.get("digest"):
            out["state"] = "aligned"
            return out
        out["state"] = "differs"
        out["differences"] = list(api.datamodel_differences(expected, found)) or [
            f"digest {expected.get('digest')} vs {found.get('digest')}"]
    except Exception as exc:  # noqa: BLE001 — older wheels lack the module
        out["differences"] = [f"cannot fingerprint the wheel: {exc}"]
    return out


def format_datamodel_check(result):
    """One line for the setup panel and the log; "" when aligned."""
    if result.get("state") == "aligned":
        return ""
    if result.get("state") == "unchecked":
        why = "; ".join(result.get("differences") or []) or "no expectation recorded"
        return f"Datamodel not checked ({why})"
    diffs = result.get("differences") or []
    head = ", ".join(diffs[:3]) + (" …" if len(diffs) > 3 else "")
    return (f"Datamodel differs from the pin "
            f"(s3dgraphy {result.get('found_version') or '?'} vs "
            f"{result.get('expected_version') or '?'}): {head}")


_CHECKED = None


def datamodel_check_once():
    """The check, computed once per session (the wheel does not change while
    Blender runs): read by the startup log and by every panel redraw."""
    global _CHECKED
    if _CHECKED is None:
        _CHECKED = check_datamodel()
    return _CHECKED
