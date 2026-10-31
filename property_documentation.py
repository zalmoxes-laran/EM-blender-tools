"""A property is documented through its extractor (E.D., 28 Oct 2026).

In EM the chain is always explicit: property → extractor
(``has_data_provenance``) → document (``extracted_from``); the document, the
extractor and the property all show. The connections datamodel 1.6.51 keeps
the direct property → document ``has_documentation`` as READ-ONLY
(``allowed_connections.read_only_sources``, BUGFIX-CONN3): an old file keeps
it, no tool writes it. An operator that would write it calls
:func:`document_through_extractor` instead.

No ``bpy`` here: the module is tested without Blender.
"""

import uuid

from s3dgraphy.edges.connection_resolver import connection_read_only


def is_cache_path(path: str) -> bool:
    """A file of ``em_cache/local`` (the detail downloaded on request, D2)."""
    p = "/" + str(path or "").replace("\\", "/").strip("/") + "/"
    return "/em_cache/local/" in p


def documents_through_extractor(source_node, document_node) -> bool:
    """True when ``source ─has_documentation→ document`` is read-only in the
    datamodel: the link must go through an extractor."""
    return connection_read_only(source_node, document_node, "has_documentation")


def next_extractor_name(graph, doc_name: str) -> str:
    """``{doc_name}.{n}``, the next free number: the pattern of the proxy box
    and of the surface areas (``D.10016.1``, ``D.10016.2``)."""
    prefix = f"{doc_name}."
    top = 0
    for node in graph.nodes:
        if getattr(node, "node_type", None) != "extractor":
            continue
        name = getattr(node, "name", "")
        if not isinstance(name, str) or not name.startswith(prefix):
            continue
        head = name[len(prefix):].split(".")[0]
        if head.isdigit():
            top = max(top, int(head))
    return f"{doc_name}.{top + 1}"


def _has_edge(graph, source, target, edge_type) -> bool:
    return any(e.edge_source == source and e.edge_target == target
               and e.edge_type == edge_type for e in graph.edges)


def _add_edge(graph, source, target, edge_type) -> None:
    if not _has_edge(graph, source, target, edge_type):
        graph.add_edge(edge_id=f"{source}_{edge_type}_{target}",
                       edge_source=source, edge_target=target,
                       edge_type=edge_type)


def document_through_extractor(graph, property_node, document_node, *,
                               description: str = ""):
    """Link ``property_node`` to ``document_node`` through an extractor and
    return the extractor. Idempotent: an extractor of the property that
    already reads that document is reused. The new extractor joins the
    property's paradata group(s), as EMStudio's ``chain.extractBetween``."""
    from s3dgraphy.nodes.extractor_node import ExtractorNode
    url = str(getattr(document_node, "url", "") or (getattr(document_node, "data", None) or {}).get("url") or "")
    if is_cache_path(url):
        # MICRO-BLEND-OFFICINA-2 (E.D. 30 Oct) · a detail downloaded on request
        # is cache: the paradata cite the DOCUMENT it comes from, never it
        raise ValueError(f"{url} is in the detail cache (em_cache/local): cite the document it comes from")
    pid, did = property_node.node_id, document_node.node_id
    by_id = {n.node_id: n for n in graph.nodes}
    for e in graph.edges:
        if e.edge_source == pid and e.edge_type == "has_data_provenance":
            ext = by_id.get(e.edge_target)
            if (getattr(ext, "node_type", None) == "extractor"
                    and _has_edge(graph, ext.node_id, did, "extracted_from")):
                return ext
    ext = ExtractorNode(node_id=str(uuid.uuid4()),
                        name=next_extractor_name(graph, document_node.name),
                        description=description)
    graph.add_node(ext)
    _add_edge(graph, pid, ext.node_id, "has_data_provenance")
    _add_edge(graph, ext.node_id, did, "extracted_from")
    for e in list(graph.edges):
        if e.edge_source == pid and e.edge_type == "is_in_paradata_nodegroup":
            _add_edge(graph, ext.node_id, e.edge_target, "is_in_paradata_nodegroup")
    return ext
