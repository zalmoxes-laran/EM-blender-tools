"""The code a graph's proxies are named by (``GT16.1.USM100``) — read once,
in one place, from s3Dgraphy.

E.D., 11 Oct 2026 («il codice di studio è stabile»): the code of a graph is
the code of its STUDY. EM-tools used to read only the GraphML header's
``graph.attributes['graph_code']`` (or ``graph.data['graph_code']`` for a
graph made from a table), so an em.json that carries the code only on its
study — every file written from now on, and the GraphML header itself once it
has been through an em.json, which does not carry ``attributes`` — re-attached
no proxy. Now the code is ``s3dgraphy.api.study_code``: the study's code,
else the GraphML header ID, else the retired ``em_id`` (read only). With an
older bundled s3dgraphy, which lacks some of that, the header fields are read
as before.

No bpy here: the importers, the room and the prefix helpers call it, and the
tests read it without Blender.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

#: codes that are not codes: s3dgraphy's MISSINGCODE, the template's site_id
NO_CODE = ("", "site_id", "site_ID", "MISSINGCODE", "empty slot")


def _clean(value: Any) -> Optional[str]:
    text = str(value).strip() if value is not None else ""
    return None if text in NO_CODE else text


def graph_code_of(graph: Any) -> Optional[str]:
    """The code of ``graph``, or None. Reading never writes, never proposes."""
    if graph is None:
        return None
    try:
        from s3dgraphy.api import study_code
        code = _clean(study_code(graph))
        if code:
            return code
    except Exception:  # noqa: BLE001 — a wheel from before the study's code
        pass
    attrs = getattr(graph, "attributes", None) or {}
    data = getattr(graph, "data", None) or {}
    return _clean(attrs.get("graph_code")) or _clean(
        data.get("graph_code") if isinstance(data, dict) else None)


def adopt_graph_code(graph: Any) -> Optional[str]:
    """:func:`graph_code_of`, and the same value written in memory on
    ``graph.attributes['graph_code']`` — where the rest of EM-tools (the
    Landscape badge, the DosCo match, the proxy check) has always looked.
    Never written to a file: the em.json does not carry ``attributes``."""
    code = graph_code_of(graph)
    attrs = getattr(graph, "attributes", None)
    if code and isinstance(attrs, dict) and _clean(attrs.get("graph_code")) != code:
        attrs["graph_code"] = code
    return code


def section_code(section: Dict[str, Any]) -> str:
    """The code of a graph SECTION of an em.json read as a dict (the graphs of
    a file that are listed and not loaded): the study's ``data.code``, else
    ``graph_code`` in its attributes or data, else the graph-self node's
    retired ``em_id``. ``""`` when none."""
    if not isinstance(section, dict):
        return ""
    nodes = [n for n in section.get("nodes") or [] if isinstance(n, dict)]
    for node in nodes:
        data = node.get("data") if isinstance(node.get("data"), dict) else {}
        if data.get("hdto_role") == "study" or node.get("node_type") == "study":
            code = _clean(data.get("code"))
            if code:
                return code
    data = section.get("data") if isinstance(section.get("data"), dict) else {}
    attrs = (section.get("attributes")
             if isinstance(section.get("attributes"), dict) else {})
    code = _clean(attrs.get("graph_code")) or _clean(data.get("graph_code"))
    if code:
        return code
    for node in nodes:
        if node.get("node_type") == "graph":
            data = node.get("data") if isinstance(node.get("data"), dict) else {}
            code = _clean(data.get("em_id"))
            if code:
                return code
    return ""
