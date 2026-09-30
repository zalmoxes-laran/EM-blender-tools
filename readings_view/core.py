"""Le letture 3D del grafo, pronte per Blender — senza `bpy`.

Dal MICRO-GEOMETRIA-ORIGINE di s3Dgraphy (30 set 2026) il punto, la linea e la
polilinea di una lettura stanno in ``data.coords`` della sua
`AnnotationRegionNode`, non in un glb. **Blender parla solo glTF** (E.D.): la
geometria arriva attraverso `s3dgraphy.api.geometry_to_gltf`, e Blender la
importa col suo importer, che fa lui la conversione Y-up → Z-up — la stessa
dei modelli, quindi la lettura cade sul modello.

Qui c'è solo la parte che non ha bisogno di Blender: quali regioni si mostrano,
con quali byte, e quali no e perché.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

#: la collezione di Blender dove stanno le letture mostrate
COLLECTION = "EM_readings"

#: i tipi di geometria di una lettura che hanno una forma in glTF
KINDS_3D = ("point", "line", "polyline")

#: le custom property con cui un oggetto di `EM_readings` ricorda da dove viene
PROP_ID = "em_reading_id"
PROP_KIND = "em_reading_kind"
PROP_SIGNATURE = "em_reading_signature"
PROP_MOVED = "em_reading_moved"

#: mezza lunghezza dei bracci della croce che rende visibile un punto (metri).
#: La croce sono tre spigoli che NON toccano il vertice del punto: quello resta
#: sciolto, e l'exporter glTF lo scrive come primitivo POINTS a parte, che è
#: l'unico che `gltf_to_geometry` legge per un punto (misurato, 5.2 e 5.0.1).
POINT_MARK_RADIUS = 0.025


@dataclass
class Reading:
    region_id: str
    name: str
    kind: str
    glb: bytes
    vertex_count: int


@dataclass
class ReadingsPlan:
    shown: List[Reading] = field(default_factory=list)
    #: ``{region_id, name, reason}`` — regioni 3D che NON si mostrano, dette
    skipped: List[Dict[str, str]] = field(default_factory=list)


def _data(node) -> Dict[str, Any]:
    data = getattr(node, "data", None)
    return data if isinstance(data, dict) else {}


def plan_readings(graph) -> ReadingsPlan:
    """Le regioni 3D del grafo: quelle che si mostrano (con il loro glb) e quelle
    che no, con la ragione.

    Una regione oltre ``coords.inline_max_vertices`` non ha coords: i suoi
    vertici sono un glb su disco (risorsa ``3d_model``), che è già il glTF, e
    per ora non si carica (lo dice `skipped`).
    """
    from s3dgraphy.api import geometry_to_gltf

    plan = ReadingsPlan()
    for node in graph.nodes:
        if getattr(node, "node_type", None) != "annotation_region":
            continue
        data = _data(node)
        kind = data.get("geometry_kind") or getattr(node, "geometry_kind", None)
        if kind not in KINDS_3D:
            continue
        name = getattr(node, "name", None) or node.node_id
        coords = data.get("coords") or []
        if not coords:
            plan.skipped.append({
                "region_id": node.node_id, "name": name,
                "reason": "no coords in the node (vertices in a .glb resource)"})
            continue
        try:
            glb = geometry_to_gltf(node)
        except Exception as exc:                 # ReadingGlbError, dati storti
            plan.skipped.append({"region_id": node.node_id, "name": name,
                                 "reason": str(exc)})
            continue
        plan.shown.append(Reading(region_id=node.node_id, name=name, kind=kind,
                                  glb=glb, vertex_count=len(coords)))
    return plan


def cross_arms(center, radius: float = POINT_MARK_RADIUS):
    """I tre bracci ``[(a, b), …]`` della croce attorno a `center`, uno per
    asse; nessuno passa per `center`, che resta un vertice sciolto."""
    arms = []
    for axis in range(3):
        a, b = list(center), list(center)
        a[axis] -= radius
        b[axis] += radius
        arms.append((tuple(a), tuple(b)))
    return arms


def _close(a, b, tol: float) -> bool:
    return len(a) == len(b) and all(
        abs(float(u) - float(v)) <= tol for pa, pb in zip(a, b) for u, v in zip(pa, pb))


def apply_back(graph, region_id: str, geometry: Dict[str, Any], *,
               author=None) -> Dict[str, Any]:
    """Quello che `gltf_to_geometry` ha riletto dall'export di Blender → la
    regione nel grafo. Un passo solo, e dice cosa è cambiato.

    Scrive ``data.coords`` (e, per linea e polilinea, ``data.length``
    ricalcolata, ``data.vertex_count``) con `s3dgraphy.api.set_field`, così ogni
    campo porta il suo timbro. **Non scrive** quando: il ritorno non ha
    ``coords`` (s3Dgraphy non ha trovato UNA catena aperta: due pezzi, un ramo,
    un anello — il grafo resta com'era e l'avviso è quello di s3Dgraphy); il
    kind non è quello della regione; i vertici sono più di
    ``inline_max_vertices`` (andrebbero in un glb: non da qui); niente è
    cambiato oltre ``stitch_tolerance``.

    Returns ``{region_id, written, reason, warnings, moved, max_shift,
    vertices_before, vertices_after, length_before, length_after}``.
    """
    from s3dgraphy.api import set_field
    from s3dgraphy.nodes.annotation_region_node import (
        chain_length, check_coords, inline_max_vertices, stitch_tolerance)

    out: Dict[str, Any] = {"region_id": region_id, "written": False, "reason": "",
                           "warnings": list(geometry.get("warnings") or []),
                           "moved": 0, "max_shift": 0.0}
    node = graph.find_node_by_id(region_id)
    if node is None or getattr(node, "node_type", None) != "annotation_region":
        out["reason"] = "the region is not in the active graph"
        return out
    data = _data(node)
    kind = data.get("geometry_kind") or getattr(node, "geometry_kind", None)
    before = [list(map(float, p)) for p in (data.get("coords") or [])]
    out.update(vertices_before=len(before), length_before=data.get("length"))

    if "coords" not in geometry:
        pieces = geometry.get("pieces") or []
        out["reason"] = (f"not one open chain ({len(pieces)} pieces): "
                         "the graph is unchanged")
        return out
    back_kind = geometry.get("geometry_kind")
    if back_kind != kind:
        out["reason"] = f"came back as {back_kind!r}, the region is a {kind!r}"
        return out
    after = check_coords(kind, geometry["coords"])
    out["vertices_after"] = len(after)
    if len(after) > inline_max_vertices():
        out["reason"] = (f"{len(after)} vertices is more than "
                         f"{inline_max_vertices()} (coords.inline_max_vertices): "
                         "they belong in a .glb, not written from here")
        return out
    tol = stitch_tolerance()
    if _close(before, after, tol):
        out["reason"] = "unchanged"
        out["length_after"] = data.get("length")
        return out

    import math
    if len(before) == len(after):
        shifts = [math.dist(a, b) for a, b in zip(before, after)]
        out["moved"] = sum(1 for d in shifts if d > tol)
        out["max_shift"] = max(shifts) if shifts else 0.0
    else:
        out["moved"] = len(after)
    set_field(node, "data.coords", after, author=author)
    if "vertex_count" in data:
        set_field(node, "data.vertex_count", len(after), author=author)
    if kind in ("line", "polyline"):
        length = chain_length(after)
        set_field(node, "data.length", length, author=author)
        out["length_after"] = length
    out["written"] = True
    return out


def describe(result: Dict[str, Any]) -> str:
    """Una riga di log per `apply_back`."""
    rid = result["region_id"]
    if not result["written"]:
        extra = ("; " + "; ".join(result["warnings"])) if result["warnings"] else ""
        return f"{rid}: not written — {result['reason']}{extra}"
    line = (f"{rid}: {result['moved']} of {result.get('vertices_after')} vertices "
            f"moved (max {result['max_shift'] * 1000:.1f} mm)")
    if result.get("vertices_before") != result.get("vertices_after"):
        line += f", {result.get('vertices_before')} → {result.get('vertices_after')} vertices"
    if result.get("length_after") is not None:
        lb = result.get("length_before")
        lb = f"{lb:.4f}" if isinstance(lb, (int, float)) else "—"
        line += f", length {lb} → {result['length_after']:.4f} m"
    return line


def signature(points) -> str:
    """L'impronta di dove sta una lettura in Blender: i vertici in coordinate
    del mondo, arrotondati al decimo di millimetro. Cambia se l'oggetto viene
    spostato, ruotato, scalato o se se ne muove un vertice."""
    return ";".join(",".join(f"{c:.4f}" for c in p) for p in points)
