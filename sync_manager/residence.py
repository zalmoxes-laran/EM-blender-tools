"""R1 · the residence of a 3D model follows its ORIGIN (invariant of E.D., 5 Oct
2026, `la-residenza-segue-l-origine.md`).

Until today EM Tools divided by «has versions or not»: a model with an
`asset_id` went into a library per asset, linked; one without was imported
resident into the working file. The origin of the geometry — the axis the
graph already declares — was never read. Now it decides:

* **reality-based** — survey models (photogrammetry, laser, tiles): invariant;
  a library linked per asset (`em_cache/<room>/<asset>.blend`), in versions,
  never resident. One with no versions is a library of its master alone;
* **source-based** — the reconstruction, made to be edited: RESIDENT in the
  working file, and its changes go up with «Sync the scene…» as a new
  revision of its resource (`scene_sync`). One WITH VERSIONS goes into a
  library like the others (Q4, E.D. 5 Oct 2026): its levels are the
  library's meshes, as for any asset with versions;
* **proxy** — a property of its unit with its glb as a resource: resident with
  its chain, as before.

Where the origin is read, in order: the **geometry axis** of the document the
model belongs to (`data.geometry` of a Document or an RMDoc linked to the
resource or to its RM — `reality_based` is reality-based; `observable`,
`asserted`, `symbolic`, `em_based` are placed by an argument, not by a sensor:
source-based — confirmed by E.D., Q3 of 5 Oct 2026); failing that, the **folders** of the standard tree
(`s3dgraphy/project_tree.py`): a file under `RB/` or `SB/`. A model with no
declared origin keeps today's rule, and the check counts it and says so.

No bpy here (`tests/test_residence.py`).
"""

from typing import Any, Dict, List, Optional, Tuple

ORIGIN_RB = "reality_based"
ORIGIN_SB = "source_based"
ORIGIN_PROXY = "proxy"
ORIGIN_UNKNOWN = ""

RESIDENCE_LIBRARY = "library"
RESIDENCE_RESIDENT = "resident"

#: the geometry axis (em_visual_rules → document_variant_styles) read as an origin
_AXIS = {"reality_based": ORIGIN_RB, "observable": ORIGIN_SB, "asserted": ORIGIN_SB,
         "symbolic": ORIGIN_SB, "em_based": ORIGIN_SB}


def origin_from(geometry: Optional[str], paths: List[str], *,
                proxy: bool = False) -> Tuple[str, str]:
    """→ `(origin, how)`: from the geometry axis, else the RB/ SB/ folders."""
    if proxy:
        return ORIGIN_PROXY, "a proxy of its unit"
    axis = str(geometry or "").strip()
    if axis in _AXIS:
        return _AXIS[axis], f"geometry {axis}"
    for path in paths:
        parts = [p for p in str(path or "").replace("\\", "/").split("/") if p]
        if "RB" in parts:
            return ORIGIN_RB, "in RB/"
        if "SB" in parts:
            return ORIGIN_SB, "in SB/"
    return ORIGIN_UNKNOWN, "no origin declared"


def residence(origin: str, has_versions: bool) -> str:
    """Where a model lives in Blender: a linked library or the working file.
    Q4 (E.D., 5 Oct 2026) · a source-based model with versions goes into a
    library like the others; without versions it stays resident."""
    if origin == ORIGIN_RB:
        return RESIDENCE_LIBRARY
    if origin == ORIGIN_PROXY:
        return RESIDENCE_RESIDENT
    return RESIDENCE_LIBRARY if has_versions else RESIDENCE_RESIDENT


def _data(node: Any) -> Dict[str, Any]:
    data = getattr(node, "data", None)
    return data if isinstance(data, dict) else {}


def _paths_of(graph: Any, node: Any) -> List[str]:
    data = _data(node)
    out = [str(data.get(k) or "") for k in ("path", "url", "filepath", "locator")]
    out.append(str(getattr(node, "url", "") or ""))
    try:
        from s3dgraphy import api
        out += [str(f.get("path") or "") for f in api.resource_files(graph, node.node_id)]
    except Exception:  # noqa: BLE001 — an older library: the fields only
        pass
    return [p for p in out if p]


def _upstream(graph: Any, node_id: str) -> List[Any]:
    found = []
    for e in getattr(graph, "edges", None) or []:
        if getattr(e, "edge_target", None) == node_id:
            n = graph.find_node_by_id(e.edge_source)
            if n is not None:
                found.append(n)
    return found


def _geometry_of(graph: Any, resource_id: str) -> Optional[str]:
    """The geometry axis of the document this model belongs to: a Document or
    an RMDoc linked to the resource, or to the RM that links it."""
    seen = set()
    frontier = [resource_id]
    for _depth in range(2):
        nxt = []
        for nid in frontier:
            for n in _upstream(graph, nid):
                if n.node_id in seen:
                    continue
                seen.add(n.node_id)
                kind = str(getattr(n, "node_type", "") or "")
                if kind in ("document", "representation_model_doc"):
                    axis = _data(n).get("geometry")
                    if axis:
                        return str(axis)
                if kind in ("representation_model", "representation_model_doc"):
                    nxt.append(n.node_id)
        frontier = nxt
    return None


def _first_revision(graph: Any, resource_id: str) -> str:
    """The resource a chain of revisions began with (`new ──was_revision_of──▶
    old`): a model sent again by Sync is a revision with a derived id, and its
    nature is the original's."""
    cur, seen = resource_id, set()
    while cur not in seen:
        seen.add(cur)
        older = next((e.edge_target for e in getattr(graph, "edges", None) or []
                      if getattr(e, "edge_type", "") == "was_revision_of"
                      and e.edge_source == cur), None)
        if older is None:
            return cur
        cur = older
    return cur


def is_proxy_resource(graph: Any, resource_id: str) -> bool:
    resource_id = _first_revision(graph, resource_id)
    node = graph.find_node_by_id(resource_id)
    data = _data(node)
    if str(data.get("role") or data.get("kind") or "") in ("proxy_model", "proxy"):
        return True
    return str(resource_id).endswith(".model") and _is_unit(
        graph.find_node_by_id(str(resource_id)[:-len(".model")]))


def _is_unit(node: Any) -> bool:
    try:
        from s3dgraphy.nodes.stratigraphic_node import StratigraphicNode
        return isinstance(node, StratigraphicNode)
    except Exception:  # noqa: BLE001
        return False


def origin_of_resource(graph: Any, resource_id: str) -> Tuple[str, str]:
    """The origin of the model a resource holds: its own, else its asset's."""
    from s3dgraphy import api
    ids = [resource_id]
    first = _first_revision(graph, resource_id)
    if first != resource_id:
        ids.append(first)            # a revision has its original's origin
    try:
        asset = api.asset_of(graph, resource_id)
        if asset != resource_id:
            ids.append(asset)
    except Exception:  # noqa: BLE001
        pass
    proxy = is_proxy_resource(graph, resource_id)
    for rid in ids:
        node = graph.find_node_by_id(rid)
        if node is None:
            continue
        origin, how = origin_from(_geometry_of(graph, rid), _paths_of(graph, node),
                                  proxy=proxy)
        if origin:
            return origin, how
    return ORIGIN_UNKNOWN, "no origin declared"


def apply_to_summary(graph: Any, summary: Dict[str, Any]) -> Dict[str, Any]:
    """The resident records with their origin and residence: a reality-based
    model without versions becomes the asset of its own library (`asset_id`
    = itself); a source-based one with versions keeps its library (Q4).
    → the summary, with `origins: {origin: count}`."""
    out = dict(summary)
    rows, counts = [], {ORIGIN_RB: 0, ORIGIN_SB: 0, ORIGIN_PROXY: 0, ORIGIN_UNKNOWN: 0}
    for record in summary.get("resident") or []:
        rid = str(record.get("resource_id") or "")
        origin, how = origin_of_resource(graph, rid) if rid else (ORIGIN_UNKNOWN, "")
        row = {**record, "origin": origin, "origin_how": how}
        where = residence(origin, bool(record.get("asset_id")))
        if where == RESIDENCE_LIBRARY and not row.get("asset_id"):
            row["asset_id"] = rid
        elif where == RESIDENCE_RESIDENT and row.get("asset_id"):
            row.pop("asset_id", None)
        row["residence"] = where
        counts[origin] += 1
        rows.append(row)
    out["resident"] = rows
    out["origins"] = counts
    return out


def sentence(counts: Dict[str, int]) -> str:
    """One line for the check: how many of each origin, and the undeclared."""
    if not counts:
        return ""
    parts = [f"{counts.get(ORIGIN_RB, 0)} reality-based (linked libraries)",
             f"{counts.get(ORIGIN_SB, 0)} source-based (resident; with versions "
             f"a library)",
             f"{counts.get(ORIGIN_PROXY, 0)} proxies"]
    line = "Origin: " + " · ".join(parts)
    if counts.get(ORIGIN_UNKNOWN):
        line += (f" · {counts[ORIGIN_UNKNOWN]} with no declared origin, kept as "
                 f"before (with versions: a library; without: resident)")
    return line
