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


#: Legacy aliases per canonical prefix. Users routinely mix the
#: Italian ``SU`` (stratigraphic unit) with the English ``US``
#: abbreviation in the same graphml; we treat them as numbering-
#: equivalent so :func:`get_next_numbered_name` doesn't propose
#: ``US.1`` while ``SU001`` already sits in the graph. Extend here
#: when new legacy variants surface.
PREFIX_ALIASES = {
    "US":  ("SU",),
    "USN": ("USNEG", "US_NEG"),
}


def get_next_numbered_name(graph, prefix: str,
                            node_type_filter: str = None) -> str:
    """Gap-aware next-number generator, shared across flows.

    Extracts the numeric suffix from every matching node, accepting
    both dot-separated (``D.41``) and concatenated (``D41``) styles.
    The effective prefix set is the canonical one plus any entries in
    :data:`PREFIX_ALIASES` — e.g. ``prefix="US"`` also counts
    ``SU001``, ``SU.5``, … as occupied slots so the next name doesn't
    accidentally collide with the Italian-style naming.

    Returns the **smallest free number starting from 1**:

    - ``used = {5, 6, 7}`` → returns ``1``.
    - ``used = {1, 2, 4, 5}`` → returns ``3``.
    - ``used = {1, 2, 3}`` → returns ``4`` (contiguous → max+1).

    The generated name reuses whichever separator dominates the
    existing names for the CANONICAL prefix (aliases don't vote for
    separator style — they're legacy and shouldn't bias new names).
    When the graph has no matching nodes, returns ``f"{prefix}.1"``.
    """
    import re
    if graph is None:
        return f"{prefix}.1"
    canonical_pat = re.compile(
        rf'^{re.escape(prefix)}(\.)?(\d+)$')
    alias_pats = [
        re.compile(rf'^{re.escape(a)}(\.)?(\d+)$')
        for a in PREFIX_ALIASES.get(prefix, ())
    ]
    used: set = set()
    sep_votes = {".": 0, "": 0}
    try:
        for node in graph.nodes:
            if not hasattr(node, 'name') \
                    or not isinstance(node.name, str):
                continue
            if node_type_filter and hasattr(node, 'node_type'):
                if node.node_type != node_type_filter:
                    continue
            m = canonical_pat.match(node.name)
            if m:
                used.add(int(m.group(2)))
                sep_votes[m.group(1) or ""] += 1
                continue
            # Legacy aliases count as occupied but DON'T vote for the
            # separator (we always emit the canonical prefix).
            for p in alias_pats:
                m = p.match(node.name)
                if m:
                    used.add(int(m.group(2)))
                    break
    except Exception:
        pass
    sep = "." if sep_votes["."] >= sep_votes[""] else ""
    if not used:
        return f"{prefix}.1"
    hi = max(used)
    # Scan from 1 upwards — any free slot below the current max is
    # claimed before we append a new one at max+1.
    for n in range(1, hi + 2):
        if n not in used:
            return f"{prefix}{sep}{n}"
    return f"{prefix}{sep}{hi + 1}"


def suggest_next_document_name(graph) -> str:
    """Propose the next available Master-Document name (e.g. ``D.42``).

    Thin wrapper over :func:`get_next_numbered_name` that pins the
    prefix to ``D`` and filters by ``node_type == 'document'``. The
    gap-aware logic is shared — if the graph has ``D.1..D.349`` plus
    ``D.351..D.400`` then this returns ``D.350`` (first gap), not
    ``D.401``.
    """
    return get_next_numbered_name(
        graph, prefix="D", node_type_filter="document")


def draw_document_picker_with_create_button(
        layout,
        scene,
        target_owner,
        target_prop_name: str,
        create_new_operator: str = None,
        create_new_label: str = "+ Add New Document...",
        search_label: str = "Search",
        search_icon: str = 'VIEWZOOM'):
    """Draw a reusable Document picker block in ``layout``:

    - When ``create_new_operator`` is provided, an ``ADD NEW`` button
      is drawn first. The operator handle is returned so the caller
      can set context-specific properties on it (e.g. a
      ``container_index`` for the RM container flow).
    - A ``prop_search`` over ``scene.doc_list`` follows, giving the
      user type-to-filter access to existing documents. When
      ``scene.doc_list`` is missing or empty, a neutral "(no
      documents yet)" hint is shown instead.

    Used by the RM Container link-or-create dialog. Can be reused by
    any future flow that needs the same pick-or-create UX (Surface
    Areas document step, Proxy Box Creator picker, etc.).
    """
    create_op = None
    if create_new_operator:
        add_row = layout.row()
        add_row.scale_y = 1.1
        create_op = add_row.operator(
            create_new_operator, text=create_new_label, icon='FILE_NEW')
        layout.separator()
    layout.label(text="Or pick an existing document:", icon='FILE_TEXT')
    if hasattr(scene, "doc_list") and len(scene.doc_list) > 0:
        layout.prop_search(
            target_owner, target_prop_name,
            scene, "doc_list",
            text=search_label, icon=search_icon)
    else:
        layout.label(
            text="(no documents in the catalog yet)",
            icon='INFO')
    return create_op


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
