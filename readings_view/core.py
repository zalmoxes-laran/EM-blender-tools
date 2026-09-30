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


def signature(points) -> str:
    """L'impronta di dove sta una lettura in Blender: i vertici in coordinate
    del mondo, arrotondati al decimo di millimetro. Cambia se l'oggetto viene
    spostato, ruotato, scalato o se se ne muove un vertice."""
    return ";".join(",".join(f"{c:.4f}" for c in p) for p in points)
