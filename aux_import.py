"""Hybrid-C auxiliary-import adapters for EMtools (Blender addon).

The s3dgraphy library importers (``QualiaImporter``, ``PyArchInitImporter``)
are deliberately workflow-neutral: they import rows into a graph, record
unmatched rows into ``importer.orphans`` as structured data, and return.
They know nothing about Blender sessions, "volatile save", or "bake".

EMtools is the consumer that turns those neutral operations into a
**Hybrid-C auxiliary lifecycle** — new nodes and edges get tagged with
``injected_by=<injector_id>`` so a volatile GraphML save can strip them
cleanly, and the structured orphans list is lifted into
``graph.attributes['aux_orphans']`` for the UI layer to render.

The adapters here are a thin "diff and tag" wrapper around each s3dgraphy
importer. They are the sanctioned entry point for any Blender operator
that wants the Hybrid-C behaviour. Operators that do not want tagging
can still call the underlying s3dgraphy importer directly — the library
remains independently usable.

Design rationale (decision log 2026-04-20): we rejected putting the
tagging inside ``qualia_importer.py`` / ``pyarchinit_importer.py``
because that would force every non-Blender consumer of s3dgraphy — a
CLI converter, a headless web viewer, a different 3D tool — to pay for
a workflow concept they do not use.
"""

from __future__ import annotations

import os
from typing import Optional, Tuple, Dict, Any

# s3dgraphy imports are deferred inside the functions to stay compatible
# with cold-start paths where the library may not be available on disk
# (e.g. during addon install before the wheel is copied in).


def _diff_and_tag(graph, pre_node_ids, pre_edge_ids, injector_id):
    """Walk ``graph`` and tag any node/edge whose id is not in the
    pre-import snapshot as injected by ``injector_id``.

    Returns ``(tagged_nodes, tagged_edges)``.
    """
    from s3dgraphy.transforms import mark_as_injected

    tagged_nodes = 0
    for n in graph.nodes:
        if n.node_id in pre_node_ids:
            continue
        mark_as_injected(n, injector_id)
        tagged_nodes += 1

    tagged_edges = 0
    for e in graph.edges:
        if e.edge_id in pre_edge_ids:
            continue
        mark_as_injected(e, injector_id)
        tagged_edges += 1

    return tagged_nodes, tagged_edges


def _promote_orphans(graph, injector_id, orphans):
    """Copy structured orphan entries from ``importer.orphans`` into
    ``graph.attributes['aux_orphans']`` via :func:`push_orphan`."""
    if not orphans:
        return 0
    from s3dgraphy.transforms import push_orphan
    for entry in orphans:
        push_orphan(
            graph,
            injector_id=injector_id,
            key_id=str(entry.get("key_id", "")),
            payload=entry.get("payload") or {},
        )
    return len(orphans)


# ----------------------------------------------------------------------
# Public adapters
# ----------------------------------------------------------------------

def import_qualia_as_auxiliary(
    graph,
    xlsx_path: str,
    overwrite: bool = False,
    sheet_name: str = "Paradata",
    injector_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Run :class:`QualiaImporter` against ``graph`` and apply the
    Hybrid-C tagging policy after the fact.

    Parameters
    ----------
    graph:
        In-memory s3dgraphy graph that will be enriched in place.
    xlsx_path:
        Path to ``em_paradata.xlsx``.
    overwrite:
        Forwarded to :class:`QualiaImporter` (update vs skip
        duplicates).
    sheet_name:
        Paradata sheet name. Forwarded to :class:`QualiaImporter`.
    injector_id:
        Identifier written into ``attributes['injected_by']`` on every
        new node/edge. Defaults to ``f"emdb:{xlsx_path}"``.

    Returns
    -------
    dict
        Report with keys ``tagged_nodes``, ``tagged_edges``,
        ``orphans``, ``warnings`` (forwarded list from the importer).
    """
    from s3dgraphy.importer.qualia_importer import QualiaImporter

    if injector_id is None:
        injector_id = f"emdb:{os.path.abspath(xlsx_path)}"

    pre_node_ids = {n.node_id for n in graph.nodes}
    pre_edge_ids = {e.edge_id for e in graph.edges}

    qualia = QualiaImporter(
        filepath=xlsx_path,
        existing_graph=graph,
        overwrite=overwrite,
        sheet_name=sheet_name,
    )
    qualia.parse()

    tagged_nodes, tagged_edges = _diff_and_tag(
        graph, pre_node_ids, pre_edge_ids, injector_id)
    orphan_count = _promote_orphans(graph, injector_id,
                                    getattr(qualia, "orphans", []))

    return {
        "injector_id": injector_id,
        "tagged_nodes": tagged_nodes,
        "tagged_edges": tagged_edges,
        "orphans": orphan_count,
        "warnings": list(getattr(qualia, "warnings", []) or []),
    }


def import_pyarchinit_as_auxiliary(
    graph,
    db_path: str,
    mapping_name: str,
    overwrite: bool = False,
    injector_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Run :class:`PyArchInitImporter` against ``graph`` and apply the
    Hybrid-C tagging policy after the fact.

    Only enrichment mode (i.e. an existing graph already contains
    stratigraphic nodes that pyArchInit rows get matched to by name) is
    the typical Hybrid-C use case. The adapter still works when the
    importer creates new StratigraphicNodes, tagging those too — the
    caller chooses whether that's semantically correct by picking the
    injector_id.

    Returns the same report shape as
    :func:`import_qualia_as_auxiliary`.
    """
    from s3dgraphy.importer.pyarchinit_importer import PyArchInitImporter

    if injector_id is None:
        injector_id = f"pyarchinit:{os.path.abspath(db_path)}"

    pre_node_ids = {n.node_id for n in graph.nodes}
    pre_edge_ids = {e.edge_id for e in graph.edges}

    importer = PyArchInitImporter(
        filepath=db_path,
        mapping_name=mapping_name,
        overwrite=overwrite,
        existing_graph=graph,
    )
    importer.parse()

    tagged_nodes, tagged_edges = _diff_and_tag(
        graph, pre_node_ids, pre_edge_ids, injector_id)
    orphan_count = _promote_orphans(graph, injector_id,
                                    getattr(importer, "orphans", []))

    return {
        "injector_id": injector_id,
        "tagged_nodes": tagged_nodes,
        "tagged_edges": tagged_edges,
        "orphans": orphan_count,
        "warnings": list(getattr(importer, "warnings", []) or []),
    }
