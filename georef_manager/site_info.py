"""The site of the graph, as the Georeferencing panel shows it (MICRO lab sito
Sarmizegetusa, 30 Oct 2026).

READ ONLY, and PURE (no bpy): what the em.json says of the site — a
``LocationNodeGroup`` of level ``sito`` (D-LG4), its FOOTPRINT (a PropertyNode
of qualia ``footprint``, a WKT with its CRS inside) and its GIS LAYERS
(resources of url_type ``gis_layer`` it reaches with ``has_linked_resource``).
EM Tools keeps them on save without touching them (they live in the graph it
writes back); EMStudio makes them. Read from the nodes themselves, so the panel
works with an s3dgraphy that does not have ``s3dgraphy.gis`` yet.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

_WKT = re.compile(r"^\s*(?:<([^>]*)>\s*)?(POLYGON|MULTIPOLYGON)\s*(Z)?\s*\((.*)\)\s*$", re.S | re.I)


def _get(node, key):
    for src in (getattr(node, "attributes", None), getattr(node, "data", None)):
        if isinstance(src, dict) and src.get(key) is not None:
            return src[key]
    return getattr(node, key, None)


def _is_site(node) -> bool:
    return getattr(node, "node_type", None) == "LocationNodeGroup" and _get(node, "level") == "sito"


def footprint_words(wkt: Any) -> Optional[Dict[str, Any]]:
    """``{shape, crs, vertices}`` of a footprint WKT, or None."""
    m = _WKT.match(str(wkt or ""))
    if not m:
        return None
    iri = m.group(1) or ""
    e = re.search(r"/EPSG/0/(\d+)$", iri)
    crs = f"EPSG:{e.group(1)}" if e else ("local" if not iri or iri.endswith("LocalSceneFrame") else iri)
    vertices = len(re.findall(r"[-+\d.eE]+(?:\s+[-+\d.eE]+){1,2}\s*(?=[,)])", m.group(4)))
    return {"shape": m.group(2).upper() + (" Z" if m.group(3) else ""), "crs": crs, "vertices": vertices}


def site_summary(graph) -> Optional[Dict[str, Any]]:
    """``{id, name, footprint, layers}`` of the graph's site; None without one.
    The site is the one the study took place at, else the only one."""
    if graph is None:
        return None
    nodes = list(getattr(graph, "nodes", []) or [])
    edges = list(getattr(graph, "edges", []) or [])
    by_id = {n.node_id: n for n in nodes}
    site = None
    for e in edges:
        if e.edge_type == "study_took_place_at" and _is_site(by_id.get(e.edge_target)):
            site = by_id[e.edge_target]
            break
    if site is None:
        sites = [n for n in nodes if _is_site(n)]
        site = sites[0] if len(sites) == 1 else None
    if site is None:
        return None
    fp = None
    layers: List[Dict[str, Any]] = []
    for e in edges:
        if e.edge_source != site.node_id:
            continue
        t = by_id.get(e.edge_target)
        if t is None:
            continue
        d = getattr(t, "data", {}) or {}
        if e.edge_type == "has_property" and (d.get("property_type") or t.name) == "footprint":
            fp = footprint_words(getattr(t, "value", None) or d.get("value"))
        elif e.edge_type == "has_linked_resource" and d.get("url_type") == "gis_layer":
            layers.append({"name": t.name, "format": d.get("gis_format"), "crs": d.get("crs"),
                           "features": d.get("feature_count")})
    return {"id": site.node_id, "name": site.name, "virtual": bool(_get(site, "virtual")),
            "footprint": fp, "layers": sorted(layers, key=lambda x: str(x["name"]))}


def site_lines(summary: Optional[Dict[str, Any]]) -> List[str]:
    """The lines the panel writes (English; the panel translates them)."""
    if not summary:
        return []
    out = [f"Site: {summary['name']}" + (" (virtual)" if summary.get("virtual") else "")]
    fp = summary.get("footprint")
    out.append(f"Footprint: {fp['shape']}, {fp['crs']}, {fp['vertices']} vertices" if fp
               else "Footprint: none yet")
    for l in summary.get("layers") or []:
        n = f", {l['features']} features" if l.get("features") is not None else ""
        out.append(f"GIS layer: {l['name']} ({l.get('format') or '?'}, {l.get('crs') or 'no CRS'}{n})")
    return out
