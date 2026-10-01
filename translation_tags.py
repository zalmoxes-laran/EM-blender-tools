"""The languages of a node's texts, as tags to read: ``la · it ✓ · en ✦``.

EMtools does not write translations (they are made in EMStudio), but it shows
them, read-only, where a document is described. ``bpy``-free, so it is measured
outside Blender (tests/test_traduzioni_in_lettura.py).

* the ORIGINAL first, with no mark: the node's own ``data.lang``, else the
  study's language (the cascade of s3Dgraphy's ``language.py``), else ``?``;
* then one tag per translation, in the order of the language, with what it
  still waits for — the reasons of ``ai_validation.needs_review``, the same
  vocabulary EMStudio and the RDF export use:

  ========  =================================================
  ``✓``     nothing waits for a person (manual, edition, verified)
  ``✦``     made with AI, nobody verified it (left out of a publication)
  ``?``     its author asked for a review, nobody signed it
  ``↻``     the original changed since: to realign
  ========  =================================================
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

MARKS = {"ai": "✦", "review_requested": "?", "stale": "↻"}
OK = "✓"
HINT = "Translations are made in EMStudio"


def tags(graph: Any, node: Any, field: Optional[str] = None) -> List[Dict[str, Any]]:
    """``[{lang, mark, original, reasons, method}]`` — the original first.

    Empty when the node has no translation: a lone language is not news, and
    the panel says nothing rather than a tag that only repeats the study's."""
    from s3dgraphy import api
    from s3dgraphy.ai_validation import needs_review
    from s3dgraphy.language import node_language

    found = api.translations(graph, node, field)
    if not found:
        return []
    original = node_language(node) or api.working_language(graph) or "?"
    out = [{"lang": original, "mark": "", "original": True, "reasons": [],
            "method": ""}]
    for t in sorted(found, key=lambda t: ((t.data or {}).get("lang") or "",
                                          (t.data or {}).get("field") or "")):
        reasons = needs_review(t, graph)
        mark = "".join(MARKS[r] for r in reasons if r in MARKS) or OK
        data = t.data or {}
        out.append({"lang": data.get("lang") or "?", "mark": mark, "original": False,
                    "reasons": reasons, "method": data.get("method") or "",
                    "field": data.get("field") or ""})
    return out


def line(graph: Any, node: Any, field: Optional[str] = None) -> str:
    """``la · it ✓ · en ✦`` — or ``""`` when there is no translation."""
    return " · ".join(f"{t['lang']} {t['mark']}".strip() for t in tags(graph, node, field))
