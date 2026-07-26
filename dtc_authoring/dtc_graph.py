"""DTC (Digital Twin Chain) authoring on an s3dgraphy Graph — the EMTools mirror
of EMStudio's DTC authoring.

The DTC = digital provenance that produces documents, modelled as RESOURCES
connected by PROCESS events (ECHOES). ``DTCProcessNode`` is the ONLY DTC node
class; both INPUTS and OUTPUTS are **Resources** = ``LinkNode`` (E73/D1) carrying
``data.dtc_kind`` + ``data.resource_type``. A process links to its resources via:

    Process ─dtc_had_input [prov:used]→ input Resource
    Process ─dtc_had_output [prov:generated]→ output Resource
    output Resource ─dtc_derived_from [prov:wasDerivedFrom]→ input Resource

All of this is graph metadata living in the s3dgraphy graph / em.json — NEVER a
Blender 3D scene object. No ``bpy`` import here (unit-testable outside Blender,
mirrors graph_info/hdto_graph.py). Node classes come from ``s3dgraphy.nodes``; the
kind vocabulary from ``s3dgraphy.utils.get_dtc_kinds`` — no hardcoded kind lists.

The three chain-edge names are named explicitly (constants below), NOT resolved
from the node-type pair: input and output are BOTH Process→LinkNode edges, so a
pair-based lookup is ambiguous — the role IS the edge type. They are verified to
exist in the connections datamodel by :func:`dtc_supported`.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

PROCESS_CLASS = "DTCProcessNode"
RESOURCE_CLASS = "LinkNode"

# role → the DTC chain edge (structural constants of the profile; verified below)
EDGE_HAD_INPUT = "dtc_had_input"      # Process → input Resource
EDGE_HAD_OUTPUT = "dtc_had_output"    # Process → output Resource
EDGE_DERIVED_FROM = "dtc_derived_from"  # output Resource → input Resource


class DtcUnavailable(RuntimeError):
    """Raised when the active s3dgraphy lacks the DTC profile (stale bundle)."""


def dtc_supported() -> bool:
    """True if the importable s3dgraphy exposes the DTC profile — the process
    node class, the LinkNode Resource, a non-empty ``dtc_kinds`` vocabulary, and
    the three chain edges. False for the stale vendored copy."""
    try:
        from s3dgraphy import nodes as _n
        from s3dgraphy.utils.utils import get_dtc_kinds
        from s3dgraphy.edges import get_connections_datamodel
        if not (hasattr(_n, PROCESS_CLASS) and hasattr(_n, RESOURCE_CLASS)):
            return False
        if not get_dtc_kinds():
            return False
        dm = get_connections_datamodel()
        return all(
            dm.get_edge_definition(e) is not None
            for e in (EDGE_HAD_INPUT, EDGE_HAD_OUTPUT, EDGE_DERIVED_FROM)
        )
    except Exception:
        return False


def dtc_kinds() -> Dict[str, List[str]]:
    """The data-driven per-axis kind vocabulary
    ``{"input": [...], "process": [...], "output": [...]}`` from s3dgraphy."""
    from s3dgraphy.utils.utils import get_dtc_kinds
    return {k: list(v) for k, v in get_dtc_kinds().items()}


def _node_class(name: str):
    from s3dgraphy import nodes
    return getattr(nodes, name)


def _data(node: Any) -> Dict[str, Any]:
    d = getattr(node, "data", None)
    if not isinstance(d, dict):
        d = {}
        setattr(node, "data", d)
    return d


def _has_edge(graph: Any, s: str, t: str, et: str) -> bool:
    return any(
        e.edge_source == s and e.edge_target == t and e.edge_type == et
        for e in graph.edges
    )


def _fresh_name(graph: Any, base: str) -> str:
    names = {str(getattr(n, "name", "")) for n in graph.nodes}
    i = 1
    while f"{base} {i}" in names:
        i += 1
    return f"{base} {i}"


def _wire(graph: Any, src_id: str, tgt_id: str, edge_type: str) -> None:
    if _has_edge(graph, src_id, tgt_id, edge_type):
        return
    graph.add_edge(f"{src_id}__{edge_type}__{tgt_id}", src_id, tgt_id, edge_type)


# ── authoring ops ─────────────────────────────────────────────────────────────
def add_process(graph: Any, kind: Optional[str] = None, name: Optional[str] = None) -> str:
    """Create a DTCProcessNode (the transformation event). ``kind`` is validated
    against the datamodel's process vocabulary by the class constructor."""
    if not dtc_supported():
        raise DtcUnavailable("the active s3dgraphy has no DTC profile — re-vendor s3dgraphy")
    cls = _node_class(PROCESS_CLASS)
    node = cls(str(uuid.uuid4()), name=name or _fresh_name(graph, "DTC process"),
               dtc_kind=kind)
    graph.add_node(node)
    return node.node_id


def add_resource(graph: Any, kind: str, url: str = "", name: Optional[str] = None) -> str:
    """Create a Resource (LinkNode) carrying ``dtc_kind`` + ``resource_type`` (=
    the kind) + an optional file ``url``. Used for both inputs and outputs."""
    if not dtc_supported():
        raise DtcUnavailable("the active s3dgraphy has no DTC profile — re-vendor s3dgraphy")
    cls = _node_class(RESOURCE_CLASS)
    node = cls(str(uuid.uuid4()), name=name or _fresh_name(graph, kind or "resource"),
               url=url or "")
    d = _data(node)
    d["dtc_kind"] = kind
    d["resource_type"] = kind
    graph.add_node(node)
    return node.node_id


def add_input(graph: Any, process_id: str, kind: str, url: str = "") -> str:
    """Add an INPUT Resource and wire Process ─dtc_had_input→ it."""
    res_id = add_resource(graph, kind, url=url)
    _wire(graph, process_id, res_id, EDGE_HAD_INPUT)
    return res_id


def add_output(graph: Any, process_id: str, kind: str, url: str = "",
               derive_from_inputs: bool = True) -> str:
    """Add an OUTPUT Resource, wire Process ─dtc_had_output→ it, and (optionally)
    wire the output ─dtc_derived_from→ each of the process's current inputs."""
    res_id = add_resource(graph, kind, url=url)
    _wire(graph, process_id, res_id, EDGE_HAD_OUTPUT)
    if derive_from_inputs:
        for in_id in _resource_ids(graph, process_id, EDGE_HAD_INPUT):
            _wire(graph, res_id, in_id, EDGE_DERIVED_FROM)
    return res_id


def remove_node(graph: Any, node_id: str) -> None:
    """Remove a process or resource from the graph (cascades its edges)."""
    graph.remove_node(node_id)


# ── read-back ─────────────────────────────────────────────────────────────────
def _resource_ids(graph: Any, process_id: str, edge_type: str) -> List[str]:
    return [e.edge_target for e in graph.edges
            if e.edge_type == edge_type and e.edge_source == process_id]


def _resource_view(graph: Any, res_id: str) -> Dict[str, Any]:
    n = graph.find_node_by_id(res_id)
    d = _data(n) if n else {}
    return {
        "id": res_id,
        "name": str(getattr(n, "name", "") or ""),
        "kind": str(d.get("dtc_kind", "") or ""),
        "resource_type": str(d.get("resource_type", "") or ""),
        "url": str(d.get("url", "") or ""),
    }


def list_processes(graph: Any) -> List[Dict[str, Any]]:
    """All DTCProcessNodes with their input/output Resources — for the panel's
    read-back. Reads directly from the graph (em.json = source of truth)."""
    out: List[Dict[str, Any]] = []
    for n in graph.nodes:
        if getattr(n, "node_type", None) != "dtc_process":
            continue
        pid = n.node_id
        out.append({
            "id": pid,
            "name": str(getattr(n, "name", "") or ""),
            "kind": str((_data(n)).get("dtc_kind", "") or ""),
            "inputs": [_resource_view(graph, r) for r in _resource_ids(graph, pid, EDGE_HAD_INPUT)],
            "outputs": [_resource_view(graph, r) for r in _resource_ids(graph, pid, EDGE_HAD_OUTPUT)],
        })
    return out
