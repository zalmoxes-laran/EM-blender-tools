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
