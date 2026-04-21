"""Shared helpers for creating Master Documents across EMtools flows.

Used by the DosCo Create Host operator (`AUX_OT_create_host_for_orphan`),
the Document Manager's standalone Create-Master-Document operator, and
the RM Manager container-creation flow. Centralises:

- DocumentNode + temporal-anchor chain construction (has_first_epoch
  + optional absolute_time_start PropertyNode with its own epoch
  anchor so the PN renders in the correct swimlane);
- UI list refresh (em_sources_list, doc_list, doc connection cache).

The three-axis classification (role / content_nature / geometry per
DP-07) is passed through unchanged to the :class:`DocumentNode`
constructor, which validates against ``em_visual_rules.json``.
"""

from __future__ import annotations

from typing import Optional


def create_master_document_node(
    graph,
    name: str,
    description: str = "",
    resolved_epoch=None,
    creation_year: Optional[int] = None,
    role: Optional[str] = None,
    content_nature: Optional[str] = None,
    geometry: Optional[str] = None,
    mark_as_master: bool = True,
):
    """Create a DocumentNode (plus temporal-anchor chain) in ``graph``
    and return it. No UI side effects — caller handles refresh.

    When ``resolved_epoch`` is given, adds a ``has_first_epoch`` edge
    from the document. When ``creation_year`` is also given, creates
    an ``absolute_time_start`` PropertyNode whose own
    ``has_first_epoch`` mirrors the document's — without this the PN
    would fall into the default swimlane in GraphML rendering.

    ``mark_as_master=True`` (default) sets
    ``attributes['em_master_document'] = True`` so the
    :class:`GraphMLPatcher` writes the node on Save.
    """
    from s3dgraphy.exporter.graphml.utils import generate_uuid
    from s3dgraphy.nodes.document_node import DocumentNode
    from s3dgraphy.nodes.property_node import PropertyNode

    node = DocumentNode(
        node_id=generate_uuid(),
        name=name,
        description=description,
        role=role,
        content_nature=content_nature,
        geometry=geometry,
    )
    if mark_as_master:
        if not hasattr(node, "attributes") or node.attributes is None:
            node.attributes = {}
        node.attributes["em_master_document"] = True
    graph.add_node(node)

    if resolved_epoch is not None:
        graph.add_edge(
            edge_id=(f"{node.node_id}_has_first_epoch_"
                     f"{resolved_epoch.node_id}"),
            edge_source=node.node_id,
            edge_target=resolved_epoch.node_id,
            edge_type="has_first_epoch",
        )
        if creation_year is not None:
            pn_id = generate_uuid()
            year_str = str(creation_year)
            pn = PropertyNode(
                node_id=pn_id,
                name="absolute_time_start",
                property_type="absolute_time_start",
                value=year_str,
                description=year_str,
            )
            graph.add_node(pn)
            graph.add_edge(
                edge_id=f"{node.node_id}_has_prop_{pn_id}",
                edge_source=node.node_id,
                edge_target=pn_id,
                edge_type="has_property",
            )
            graph.add_edge(
                edge_id=(f"{pn_id}_has_first_epoch_"
                         f"{resolved_epoch.node_id}"),
                edge_source=pn_id,
                edge_target=resolved_epoch.node_id,
                edge_type="has_first_epoch",
            )
    return node


def refresh_document_lists(context, node, graph) -> None:
    """Refresh the EMTools document-backed UI lists so a newly-created
    Master Document appears immediately in the Document Manager /
    EM tree without requiring a graphml reload.

    Best-effort: silently tolerates import failures (callers may
    still choose to report via ``operator.report``).
    """
    try:
        em_tools = context.scene.em_tools
        from .populate_lists import populate_document_node
        idx = len(em_tools.em_sources_list)
        populate_document_node(context.scene, node, idx, graph=graph)
        from .document_manager.data import sync_doc_list
        sync_doc_list(context.scene)
        try:
            from .document_manager.ui import (
                invalidate_doc_connection_cache,
            )
            invalidate_doc_connection_cache()
        except Exception:
            pass
    except Exception:
        pass


def resolve_epoch_from_year(graph, year: int):
    """Return the :class:`EpochNode` whose ``[start_time, end_time]``
    range contains ``year``, preferring the narrowest matching range
    when multiple epochs overlap. Returns ``None`` when no epoch
    covers the year.
    """
    if graph is None:
        return None
    best = None
    best_width = None
    for n in graph.nodes:
        if type(n).__name__ != "EpochNode":
            continue
        start = getattr(n, "start_time", None)
        end = getattr(n, "end_time", None)
        if start is None or end is None:
            continue
        if start <= year <= end:
            width = end - start
            if best is None or width < best_width:
                best = n
                best_width = width
    return best
