"""
.em.json support for EM tools (Blender add-on) — wiring entry point.

Added 2026-07-11 as the propagation hook of the .em.json v1 freeze
(s3Dgraphy: exporter/emjson_exporter.py, importer/emjson_importer.py;
format decision record in the EMStudio repository, docs/emjson-v1-draft.md).

Migration plan (EM tools 1.6):
  * import: offer .em.json alongside GraphML in the import operator;
    GraphML remains the legacy one-way path until EMStudio replaces yEd;
  * export: the Heriverse export switches to .em.json (flat graph
    section); the bucketed JSON payload remains available as legacy
    during the Heriverse 1.5.x transition;
  * the UI operators should call the two functions below — no other
    part of the add-on needs to know the format.

This module deliberately contains no Blender/bpy imports so it can be
unit-tested outside Blender.
"""

from __future__ import annotations

from typing import List, Tuple


def export_graph_to_emjson(graph, output_path: str, layout: dict | None = None) -> str:
    """Serialize an s3dgraphy Graph to .em.json v1. Returns the written path."""
    from s3dgraphy.exporter.emjson_exporter import export_emjson
    return export_emjson(graph, output_path, layout=layout)


def graph_to_emjson_dict(graph, layout: dict | None = None) -> dict:
    """Serialize an s3dgraphy Graph to an in-memory .em.json v1 doc (dict).

    Same content as ``export_graph_to_emjson`` but returned instead of written
    — used by the live-sync snapshot channel (ADR-002) to send the host's
    graph to a connecting client without touching disk."""
    from s3dgraphy.exporter.emjson_exporter import build_emjson
    return build_emjson(graph, layout=layout)


def import_graph_from_emjson(filepath: str) -> Tuple[object, List[str]]:
    """Load a .em.json v1 file into an s3dgraphy Graph.

    Returns (graph, warnings). Unknown node types degrade to base nodes
    with a warning instead of failing (forward compatibility).
    """
    from s3dgraphy.importer.emjson_importer import import_emjson
    return import_emjson(filepath)
