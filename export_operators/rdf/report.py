"""What an RDF export did, in two sizes: one line for Blender, the rest in a file.

``bpy``-free, so it is measured outside Blender (tests/test_rdf_export_report.py).

* the short line is ``exporter.summary()`` — s3Dgraphy's words, not a paraphrase;
* the detail goes in ``<name>.export-report.txt`` beside the ``.ttl``: the
  numbers, the language of each graph, and what was left out.

**The texts without a language are a WARNING, not information.** A literal
leaves untagged only when neither the node (``data.lang``) nor the study
(``GraphNode.data.language``) declares one, and s3Dgraphy never guesses it. The
remedy is one field, so the warning says where it is in EMtools.

**What was left out.** In ``publish`` the nodes made with AI that no person
verified stay out (s3Dgraphy's ``ai_validation.export_view``), translations
included; ``exporter.excluded`` lists them and the report counts them, the
translations apart, because a missing translation is the thing a reader of
a multilingual export looks for first.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Iterable, List, Optional, Tuple

#: where EMtools declares the study's language — said by the warning
WHERE_TO_DECLARE = "EM Setup ▸ Graph info ▸ Language"


def report_path(written_path: str) -> str:
    """``site.ttl`` → ``site.export-report.txt``, in the same folder."""
    root, _ext = os.path.splitext(written_path)
    return root + ".export-report.txt"


def graph_languages(graphs: Iterable[Any]) -> List[Tuple[str, Optional[str]]]:
    """``[(graph_id, working language or None)]`` for the exported graphs."""
    from s3dgraphy import api
    out = []
    for g in graphs:
        try:
            lang = api.working_language(g)
        except Exception:  # noqa: BLE001 — a wheel without the language API
            lang = None
        out.append((getattr(g, "graph_id", "?"), lang))
    return out


def excluded_counts(excluded: Iterable[Dict[str, Any]]) -> Dict[str, int]:
    """``{nodes, translations, fields}`` of what ``publish`` withheld."""
    counts = {"nodes": 0, "translations": 0, "fields": 0}
    for row in excluded or ():
        if row.get("fields"):
            counts["fields"] += 1
        elif row.get("node_type") == "translation":
            counts["translations"] += 1
        else:
            counts["nodes"] += 1
    return counts


def build(exporter: Any, written_path: str, graphs: Iterable[Any], *,
          mode: str) -> Dict[str, Any]:
    """``{line, level, warnings, text, path}`` — everything the operator says.

    ``level`` is ``WARNING`` when a text left without a language (or something
    was withheld, which the author should know before sending the file on),
    ``INFO`` otherwise."""
    stats = dict(getattr(exporter, "stats", {}) or {})
    summary = exporter.summary() if hasattr(exporter, "summary") else ""
    languages = graph_languages(graphs)
    withheld = excluded_counts(getattr(exporter, "excluded", []))

    warnings: List[str] = []
    untagged = int(stats.get("literals_untagged", 0) or 0)
    if untagged:
        undeclared = [gid for gid, lang in languages if not lang]
        whose = (f" ({', '.join(undeclared)} declares no language)"
                 if undeclared else "")
        warnings.append(
            f"{untagged} texts left without a language{whose}: declare the "
            f"study's language in {WHERE_TO_DECLARE}")
    if withheld["translations"]:
        warnings.append(f"{withheld['translations']} AI translations not verified "
                        f"left out")
    if withheld["nodes"] or withheld["fields"]:
        warnings.append(f"{withheld['nodes']} AI nodes and {withheld['fields']} "
                        f"AI fields not verified left out")

    name = os.path.basename(written_path)
    line = f"RDF export ({mode}) {name}: {summary}"
    if warnings:
        line += " — " + "; ".join(warnings)

    text = _detail(written_path, mode, summary, stats, languages, withheld,
                   getattr(exporter, "excluded", []) or [], warnings)
    return {"line": line, "level": "WARNING" if warnings else "INFO",
            "warnings": warnings, "text": text, "path": report_path(written_path)}


def write(report: Dict[str, Any]) -> str:
    with open(report["path"], "w", encoding="utf-8") as handle:
        handle.write(report["text"])
    return report["path"]


def _detail(written_path, mode, summary, stats, languages, withheld, excluded,
            warnings) -> str:
    try:
        import s3dgraphy
        version = getattr(s3dgraphy, "__version__", "?")
    except Exception:  # noqa: BLE001
        version = "?"
    lines = [
        "EMtools — RDF export report",
        f"file:      {written_path}",
        f"mode:      {mode}"
        + ("  (AI not verified and tombstones left out)" if mode == "publish"
           else "  (everything travels, so ttl → graph gives back what went in)"),
        f"s3dgraphy: {version}",
        "",
        "summary:",
        f"  {summary}",
        "",
    ]
    if warnings:
        lines.append("warnings:")
        lines += [f"  ▲ {w}" for w in warnings]
        lines.append("")
    lines.append("language of each graph (GraphNode.data.language):")
    for gid, lang in languages:
        lines.append(f"  {gid}: {lang or '— not declared (' + WHERE_TO_DECLARE + ')'}")
    lines += [
        "",
        "texts (literals the datamodel marks as natural language):",
        f"  tagged by the node:   {stats.get('literals_tagged_node', 0)}",
        f"  tagged by the study:  {stats.get('literals_tagged_study', 0)}",
        f"  untagged:             {stats.get('literals_untagged', 0)}",
        "",
        "translations:",
        f"  exported:             {stats.get('translations', 0)}",
        f"  literals beside the original: {stats.get('literals_translation', 0)}",
        f"  to realign (original changed): {stats.get('translations_stale', 0)}",
        f"  AI not verified, left out:     {withheld['translations']}",
        "",
        "withheld (publish):",
        f"  AI nodes: {withheld['nodes']}, AI fields: {withheld['fields']}, "
        f"AI translations: {withheld['translations']}",
    ]
    for row in excluded:
        what = ("fields " + ", ".join(row["fields"])) if row.get("fields") else "node"
        lines.append(f"    - {row.get('node_type', '?')} {row.get('name') or row.get('node')}"
                     f" ({what}; by {row.get('by') or '?'}"
                     + (f", {row['model']}" if row.get("model") else "") + ")")
    lines += ["", "all counters:"]
    lines += [f"  {k}: {v}" for k, v in sorted(stats.items())]
    return "\n".join(lines) + "\n"
