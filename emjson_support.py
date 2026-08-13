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


# ── the em.json CONTAINER (2026-08-13) ──────────────────────────────────────
#
# An em.json is always a CONTAINER: `{"graphs": {...}}`, 1..N study graphs plus
# the project shelf. A single graph is a container-of-one, and every file written
# before today is the legacy single-graph shape — both are read.
#
# For EM tools this changes two gestures:
#   * OPENING loads every graph of the project into the one Blender scene (which
#     is what the .blend already did with several files — now they arrive from
#     ONE file);
#   * SAVING writes every registered graph into that one file, instead of one
#     graph per file.
#
# Importing a GraphML keeps its meaning and gains one: it ADDS a graph-member to
# the open project rather than replacing it — the same semantics as EMStudio, so
# the two tools do not disagree about what an import is.


def import_container_from_emjson(filepath: str, *, replace: bool = False):
    """Load a whole project into the multigraph manager.

    Returns ``(container, warnings)``. `replace=True` is "open this project"
    (the manager is cleared first); the default ADDS, which is the offline
    "integrate later" and the less expensive mistake — losing what is already
    loaded costs more than having one graph too many.
    """
    from s3dgraphy.multigraph.multigraph import multi_graph_manager
    return multi_graph_manager.load_container(filepath, replace=replace)


def export_container_to_emjson(output_path: str, *, active_graph_id=None) -> str:
    """Write EVERY registered graph (plus the shelf) into ONE container file.

    This is the change of substance for EM tools: a .blend that holds four
    graphs used to export four files, and the project was only in somebody's
    head. Now the project is a file.
    """
    from s3dgraphy.multigraph.multigraph import multi_graph_manager
    return multi_graph_manager.save_container(output_path,
                                              active_graph_id=active_graph_id)


def merge_container_from_emjson(filepath: str):
    """Take another project's graphs into the loaded one — add + merge-by-UUID.

    Returns ``(report, warnings)``. DECLARED LIMIT: additive, not conflict
    resolution; `report.merged_nodes` is exactly the set where a divergent edit
    could have been overwritten, and it is the number to look at before trusting
    the result.
    """
    from s3dgraphy.api import load_container_file, merge_containers
    from s3dgraphy.container import Container, is_shelf_member
    from s3dgraphy.multigraph.multigraph import multi_graph_manager

    incoming, warnings = load_container_file(filepath)
    graphs, shelf = {}, None
    for graph_id, graph in multi_graph_manager.graphs.items():
        if is_shelf_member(graph):
            shelf = graph
        else:
            graphs[graph_id] = graph
    current = Container(graphs=graphs, shelf=shelf)
    report = merge_containers(current, incoming)
    # the manager is the scene's registry: whatever the merge produced is what
    # the scene must now hold
    for graph_id, graph in current.graphs.items():
        multi_graph_manager.graphs[graph_id] = graph
    if current.shelf is not None:
        multi_graph_manager.graphs[current.shelf.graph_id] = current.shelf
    return report, warnings


def is_container_file(filepath: str) -> bool:
    """Does this file carry several graphs? Read the marker, not the extension."""
    import json

    from s3dgraphy.container import is_container
    try:
        with open(filepath, encoding="utf-8") as fh:
            return is_container(json.load(fh))
    except Exception:
        return False


def import_graph_from_emjson(filepath: str) -> Tuple[object, List[str]]:
    """Load a .em.json file into ONE s3dgraphy Graph — the ACTIVE one.

    Returns (graph, warnings). Unknown node types degrade to base nodes with a
    warning instead of failing (forward compatibility).

    For a CONTAINER this returns the active member and says so in the warnings;
    the whole project comes from :func:`import_container_from_emjson`. Keeping
    the two apart is deliberate — handing back one graph out of four to a caller
    who does not know there are four is how data goes missing.
    """
    from s3dgraphy.importer.emjson_importer import import_emjson
    return import_emjson(filepath)
