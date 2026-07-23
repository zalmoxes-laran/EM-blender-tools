"""Graph-level HDT-O (ECHOES D7.1) metadata on an s3dgraphy Graph — the Python
mirror of EMStudio's ``store.applyHdto`` / ``store.readHdto``.

A graph = a **Study** (HC9) whose proposition set (HC16 = the GraphNode) is
**about** a **Heritage Entity** (HC1, with its digital twin HC2), optionally
under a **Project** (HC13), optionally part of a parent HC1. These are graph-level
SINGLETONS living in the s3dgraphy graph (identity + multigraph + RDF projection)
— NEVER Blender scene objects. Singletons are keyed by ``data.hdto_role`` so
repeated applies never duplicate.

No ``bpy`` import here on purpose: this module is unit-testable outside Blender
(mirrors emjson_support.py). Node/edge TYPES are read from the datamodel — node
classes come from ``s3dgraphy.nodes`` (the datamodel's own classes), edge types
are resolved from ``allowed_connections`` via ``Graph.validate_connection`` — so
no edge-name string is hardcoded here.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

# role → the s3dgraphy datamodel CLASS that plays it (mirrors EMStudio's
# HDTO_ROLE_CLASS). The two HeritageEntity roles — the graph's subject ("about")
# and its optional whole ("parent") — are distinguished by the role marker.
HDTO_ROLE_CLASS = {
    "proposition_set": "GraphNode",       # HC16
    "about": "HeritageEntityNode",        # HC1 (subject)
    "parent": "HeritageEntityNode",       # HC1 (whole)
    "twin": "HDTNode",                    # HC2
    "study": "StudyNode",                 # HC9
    "project": "ProjectNode",             # HC13
}


class HdtoUnavailable(RuntimeError):
    """Raised when the active s3dgraphy lacks the HDT-O layer (stale bundle)."""


def hdto_supported() -> bool:
    """True if the importable s3dgraphy exposes the HDT-O node classes AND the
    authority resolver — i.e. a current build, not the stale vendored copy."""
    try:
        from s3dgraphy import nodes as _n  # noqa: F401
        for cls in set(HDTO_ROLE_CLASS.values()):
            if not hasattr(_n, cls):
                return False
        import s3dgraphy.authorities  # noqa: F401
        return True
    except Exception:
        return False


def _node_class(name: str):
    from s3dgraphy import nodes
    return getattr(nodes, name)


def _class_registry() -> Dict[str, Dict[str, Any]]:
    """The generated class hierarchy (class → {parent, node_type}) from the
    datamodel — the same file EMStudio's rules.ts consumes."""
    import json
    from importlib.resources import files
    path = files("s3dgraphy").joinpath("JSON_config/node_registry.generated.json")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f).get("node_types", {})


def _ancestry(node_type: str) -> List[str]:
    """Class-name ancestry for a runtime node_type (e.g. 'heritage_entity' →
    ['HeritageEntityNode', 'Node']). Mirrors rules.ts ancestorsOf."""
    reg = _class_registry()
    cls = next((c for c, e in reg.items() if e.get("node_type") == node_type), None)
    out: List[str] = []
    guard = 0
    while cls and guard < 20:
        out.append(cls)
        cls = reg.get(cls, {}).get("parent")
        guard += 1
    return out or ["Node"]


def _edge_type_between(source_type: str, target_type: str) -> Optional[str]:
    """The datamodel edge type allowed from source→target node_type, or None.

    Reads ``allowed_connections`` (which lists CLASS names) and intersects with
    each node's class-name ancestry — mirroring EMStudio's rules.ts
    ``allowedEdgeTypes``. (s3dgraphy's Graph.validate_connection is unusable here:
    it keys node_type_map by node_type strings while allowed_connections uses
    class names, so unknown keys fall back to ``object`` and match everything.)
    No hardcoded edge names — the six HDT-O pairs each resolve uniquely."""
    from s3dgraphy.edges import get_connections_datamodel

    sa = set(_ancestry(source_type))
    ta = set(_ancestry(target_type))
    dm = get_connections_datamodel()
    for name in dm.get_all_edge_names(canonical_only=True):
        if name == "generic_connection":
            continue
        ac = (dm.get_edge_definition(name) or {}).get("allowed_connections") or {}
        if set(ac.get("source", [])) & sa and set(ac.get("target", [])) & ta:
            return name
    return None


def _data(node: Any) -> Dict[str, Any]:
    d = getattr(node, "data", None)
    if not isinstance(d, dict):
        d = {}
        setattr(node, "data", d)
    return d


def _singleton(graph: Any, role: str) -> Optional[Any]:
    for n in graph.nodes:
        if isinstance(getattr(n, "data", None), dict) and n.data.get("hdto_role") == role:
            return n
    return None


def _graph_display_name(graph: Any) -> str:
    nm = getattr(graph, "name", None)
    if isinstance(nm, dict):
        return str(nm.get("default") or "")
    return str(nm or "")


def _has_edge(graph: Any, s: str, t: str, et: str) -> bool:
    return any(
        e.edge_source == s and e.edge_target == t and e.edge_type == et
        for e in graph.edges
    )


# ── read ─────────────────────────────────────────────────────────────────────
def read_hdto(graph: Any) -> Dict[str, Any]:
    """Read the HDT-O singletons off the graph into a flat dict (inverse of
    :func:`apply_hdto`). Safe on a graph with no HDT-O content (all empty)."""
    study = _singleton(graph, "study")
    about = _singleton(graph, "about")
    parent = _singleton(graph, "parent")
    project = _singleton(graph, "project")
    twin = _singleton(graph, "twin")

    sd = _data(study) if study else {}
    ad = _data(about) if about else {}
    refs = ad.get("authority_refs") if isinstance(ad.get("authority_refs"), list) else []
    first = next((r for r in refs if isinstance(r, dict) and r.get("uri")), None)

    return {
        "study_title": str(getattr(study, "name", "") or ""),
        "study_authors": str(sd.get("authors", "") or ""),
        "study_date": str(sd.get("date", "") or ""),
        "heritage_name": str(getattr(about, "name", "") or ""),
        "heritage_uri": str((first or {}).get("uri", "") or ""),
        # only a resolved pick carries an `authority`; a bare free-text uri does not
        "heritage_authority_ref": first if (first and first.get("authority")) else None,
        "parent_name": str(getattr(parent, "name", "") or ""),
        "project_name": str(getattr(project, "name", "") or ""),
        "twin_name": str(getattr(twin, "name", "") or ""),
        "twin_id": str(getattr(twin, "node_id", "") or ""),
    }


# ── apply (idempotent) ─────────────────────────────────────────────────────────
def apply_hdto(graph: Any, fields: Dict[str, Any]) -> Dict[str, Any]:
    """Create/update the graph-level HDT-O singletons + edges from ``fields``,
    idempotently (mirrors EMStudio applyHdto). Returns a small summary dict.

    Chain authored: Project(HC13) ─includes_study→ Study(HC9)
      ─study_about_heritage→ HC1 ─has_digital_twin→ HC2 ─contains_proposition_set→
      HC16(GraphNode); Study ─study_produced_proposition_set→ HC16;
      HC1(about) ─heritage_part_of→ HC1(parent).
    """
    if not hdto_supported():
        raise HdtoUnavailable(
            "the active s3dgraphy has no HDT-O layer — update/re-vendor s3dgraphy"
        )

    def trim(k: str) -> str:
        return str(fields.get(k, "") or "").strip()

    def ensure(role: str, name: str) -> Any:
        n = _singleton(graph, role)
        if n is not None:
            if name and getattr(n, "name", None) != name:
                n.name = name
            return n
        cls = _node_class(HDTO_ROLE_CLASS[role])
        n = cls(str(uuid.uuid4()), name=name or "")
        _data(n)["hdto_role"] = role
        graph.add_node(n)
        return n

    def remove_role(role: str) -> None:
        n = _singleton(graph, role)
        if n is not None:
            graph.remove_node(n.node_id)  # cascades its edges

    def ensure_edge(src: Any, tgt: Any) -> None:
        if not src or not tgt:
            return
        et = _edge_type_between(src.node_type, tgt.node_type)
        if not et or _has_edge(graph, src.node_id, tgt.node_id, et):
            return
        graph.add_edge(f"{src.node_id}__{et}__{tgt.node_id}",
                       src.node_id, tgt.node_id, et)

    has_heritage = bool(trim("heritage_name") or trim("heritage_uri"))
    has_study = bool(trim("study_title") or trim("study_authors") or trim("study_date"))
    need_set = has_heritage or has_study

    prop_set = (
        ensure("proposition_set", _graph_display_name(graph) or "Proposition set")
        if need_set else None
    )
    if not need_set:
        remove_role("proposition_set")

    about = twin = study = None
    if has_heritage:
        about = ensure("about", trim("heritage_name"))
        d = _data(about)
        d["hdto_role"] = "about"
        # authority: a resolved pick (uri matches the field) is stored verbatim;
        # else the free-text uri becomes a bare {uri}; else none.
        picked = fields.get("heritage_authority_ref")
        uri = trim("heritage_uri")
        if isinstance(picked, dict) and str(picked.get("uri", "")).strip() == uri and uri:
            d["authority_refs"] = [picked]
        elif uri:
            d["authority_refs"] = [{"uri": uri}]
        else:
            d["authority_refs"] = []
        twin = ensure("twin", f"{trim('heritage_name') or 'Heritage'} HDT")
        ensure_edge(about, twin)        # HC1 → HC2 (has_digital_twin)
        ensure_edge(twin, prop_set)     # HC2 → HC16 (contains_proposition_set)
    else:
        remove_role("about")
        remove_role("twin")
        remove_role("parent")

    if about and trim("parent_name"):
        parent = ensure("parent", trim("parent_name"))
        ensure_edge(about, parent)      # HC1 → HC1 (heritage_part_of)
    else:
        remove_role("parent")

    if has_study:
        study = ensure("study", trim("study_title"))
        sd = _data(study)
        sd["hdto_role"] = "study"
        sd["authors"] = trim("study_authors")
        sd["date"] = trim("study_date")
        ensure_edge(study, about)       # HC9 → HC1 (study_about_heritage)
        ensure_edge(study, prop_set)    # HC9 → HC16 (study_produced_proposition_set)
    else:
        remove_role("study")

    if trim("project_name"):
        project = ensure("project", trim("project_name"))
        ensure_edge(project, study)     # HC13 → HC9 (includes_study)
    else:
        remove_role("project")

    return read_hdto(graph)


# ── authority resolver passthrough (in-process, offline) ───────────────────────
def available_facets() -> List[str]:
    """Facets that currently have at least one bundled offline snapshot, so the
    UI can explain an empty result (no snapshot for this facet vs no match vs no
    snapshots bundled at all)."""
    try:
        import s3dgraphy.authorities.resolver as r
        return sorted({(s.get("facet") or "").upper()
                       for s in r._load_snapshots().values() if s.get("facet")})
    except Exception:
        return []


def resolve_authority(term: str, facet: str) -> List[Dict[str, Any]]:
    """Ranked offline candidates from s3dgraphy.authorities (P1-D). Returns [] if
    the resolver is unavailable or the term is empty — the caller degrades to
    free-text. No network, no em-bridge."""
    if not term or not term.strip():
        return []
    try:
        from s3dgraphy.authorities import resolve
        return list(resolve(term, facet))
    except Exception:
        return []
