"""EM Shelf tool — pure, bpy-free bridge to the s3dgraphy Shelf + acquisition ops.

Session C1: a SEPARATE Shelf tool with a 3D-first project-folder search that
populates the shelf VIA THE ACQUISITION PIPELINE (in-process s3dgraphy). No logic
is reimplemented here — every step calls the s3dgraphy api:

  scan a folder → for each 3D file: fs_record(path) → apply_mapping("fs") →
  AcquisitionDescriptor → acquire_from_descriptor(descriptor, shelf)

so each entry lands with its acquisition DTC event + origin (tier). The shelf is a
standalone reusable em.json (save/load) — the ShelfGraph substrate (Session A).

NO ``bpy`` here (unit-testable outside Blender), mirroring resource_backend.py.
NO hatting (that is C2). The active shelf + its display cards are held per session.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

# 3D-first: the search entry points are scene-placeable 3D assets (design §1c).
THREE_D_EXTS = ("glb", "gltf", "obj", "fbx", "ply", "stl", "3ds", "dae", "usd", "usdz")

# session-held active shelf: the s3dgraphy Graph, its on-disk path, cached cards,
# and the project-multigraph id when linked (Session C2).
_active: Dict[str, Any] = {"graph": None, "path": None, "cards": [], "mg_id": None}

# every s3dgraphy api op this tool drives (the capability guard checks them all).
_REQUIRED_API = (
    "new_shelf", "list_shelf", "remove_from_shelf", "save_shelf", "load_shelf",
    "acquire_from_descriptor", "apply_acquisition_mapping", "fs_acquisition_record",
)


def shelf_supported() -> bool:
    """True if the active s3dgraphy exposes the Shelf + acquisition ops AND the fs
    mapping. False for the stale vendored copy → the panel shows a blocker box
    directing the user to activate the dev s3dgraphy (./em.sh s3d)."""
    try:
        from s3dgraphy import api
        if not all(hasattr(api, fn) for fn in _REQUIRED_API):
            return False
        from s3dgraphy.acquisition import available_mappings
        return "fs" in available_mappings()
    except Exception:
        return False


# ── active shelf lifecycle ──────────────────────────────────────────────────────
def active_shelf():
    return _active["graph"]


def active_path() -> Optional[str]:
    return _active["path"]


def new_shelf(name: Optional[str] = None):
    from s3dgraphy import api
    _active["graph"] = api.new_shelf(name=name or "Shelf")
    _active["path"] = None
    _refresh_cards()
    return _active["graph"]


def ensure_shelf():
    if _active["graph"] is None:
        new_shelf()
    return _active["graph"]


def load_shelf(path: str):
    from s3dgraphy import api
    graph, warnings = api.load_shelf(path)
    _active["graph"] = graph
    _active["path"] = path
    _refresh_cards()
    return graph, warnings


def save_shelf(path: Optional[str] = None) -> str:
    from s3dgraphy import api
    graph = _active["graph"]
    if graph is None:
        raise RuntimeError("no active shelf to save")
    target = path or _active["path"]
    if not target:
        raise RuntimeError("no shelf path given")
    api.save_shelf(graph, target)
    _active["path"] = target
    return target


# ── 3D-first search → acquisition pipeline ──────────────────────────────────────
def is_three_d(filename: str) -> bool:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return ext in THREE_D_EXTS


def scan_folder(folder: str, *, recursive: bool = True) -> Dict[str, int]:
    """3D-first project-folder search: every 3D file is acquired onto the active
    shelf through the full acquisition pipeline (record → fs mapping → descriptor →
    acquire). Idempotent (re-scanning re-uses stable ids). Returns
    ``{scanned, acquired, shelf_count}``."""
    from s3dgraphy import api
    shelf = ensure_shelf()
    scanned = acquired = 0
    if os.path.isdir(folder):
        walker = os.walk(folder) if recursive else [
            (folder, [], [f for f in os.listdir(folder)
                          if os.path.isfile(os.path.join(folder, f))])]
        for root, _dirs, files in walker:
            for fn in sorted(files):
                if fn.startswith(".") or not is_three_d(fn):
                    continue
                scanned += 1
                path = os.path.join(root, fn)
                record = api.fs_acquisition_record(path)
                descriptor = api.apply_acquisition_mapping("fs", record)
                api.acquire_from_descriptor(descriptor, shelf)  # mutates in place
                acquired += 1
    _refresh_cards()
    return {"scanned": scanned, "acquired": acquired,
            "shelf_count": len(_active["cards"])}


# ── cards (reflect the mapping fields + tier badge) ─────────────────────────────
def tier_label(origin: Optional[Dict[str, Any]]) -> str:
    """The tier badge derived from source.capabilities / payload scope (design §1c).
    Tier 0 (opaque) = 'import + origin'."""
    caps = (origin or {}).get("capabilities") or []
    if "interpretation" in caps:
        return "Tier 2 · import + validated study"
    if "genesis" in caps:
        return "Tier 1 · import + how it was made"
    return "Tier 0 · import + origin"


def _card(entry: Dict[str, Any]) -> Dict[str, Any]:
    """One display card, reflecting exactly the fields the mapping offers (name,
    media_type, size, …) — size/media_type re-derived from the local locator via
    the SAME s3dgraphy fs helper (no duplicated logic)."""
    from s3dgraphy import api
    loc = entry.get("locator", "") or ""
    exists = bool(loc) and os.path.isfile(loc)
    rec = api.fs_acquisition_record(loc) if exists else {}
    fn = os.path.basename(loc)
    return {
        "resource_id": entry["id"],
        "name": entry.get("name") or fn or entry["id"][:8],
        "locator": loc,
        "kind": entry.get("kind", ""),
        "resource_type": entry.get("resource_type", ""),
        "media_type": rec.get("media_type", ""),
        "size": rec.get("size"),
        "exists": exists,
        "tier": tier_label(entry.get("origin")),
    }


def _refresh_cards() -> None:
    from s3dgraphy import api
    graph = _active["graph"]
    _active["cards"] = [_card(e) for e in api.list_shelf(graph)] if graph else []


def cards() -> List[Dict[str, Any]]:
    """The cached display cards for the active shelf."""
    return _active["cards"]


def remove(resource_id: str) -> Dict[str, Any]:
    """Remove a resource from the active shelf, cleaning up its orphan acquisition
    event (kept if the resource is still referenced — reuses
    api.remove_shelf_resource). Refreshes the cards. Returns the cleanup report."""
    from s3dgraphy import api
    graph = _active["graph"]
    if graph is None:
        return {"removed": False, "referenced": False, "events_removed": 0}
    rep = api.remove_shelf_resource(graph, resource_id)
    _refresh_cards()
    return rep


# ── hatting (C2): shelf resource → RepresentationModel in the study graph ───────
def hat_as_rm(target_graph: Any, resource_id: str, *, rm_id: Optional[str] = None,
              name: Optional[str] = None, attach_to: Optional[str] = None
              ) -> Dict[str, Any]:
    """Hat a shelf resource into ``target_graph`` as a RepresentationModel (pure;
    reuses api.hat_as_representation_model). The Blender mesh import + object bind
    are done by the operator; this only touches the graph."""
    from s3dgraphy import api
    return api.hat_as_representation_model(
        target_graph, resource_id, shelf=_active["graph"], rm_id=rm_id,
        name=name, attach_to=attach_to)


# ── shelf ↔ multigraph (C2): the shelf as a project-local member ────────────────
def link_to_multigraph(graph_id: str) -> Optional[str]:
    """Register the active shelf as a member of the project multigraph (so
    get_graph(graph_id) returns it and it co-persists with the project). Returns
    the id used, or None if there is no active shelf."""
    graph = ensure_shelf()
    try:
        from s3dgraphy.multigraph.multigraph import multi_graph_manager
        graph.graph_id = graph_id
        multi_graph_manager.graphs[graph_id] = graph
        _active["mg_id"] = graph_id
        return graph_id
    except Exception:
        return None


def unlink_from_multigraph() -> None:
    """Drop the shelf from the project multigraph (back to standalone-file mode)."""
    gid = _active.get("mg_id")
    if not gid:
        return
    try:
        from s3dgraphy.multigraph.multigraph import multi_graph_manager
        if multi_graph_manager.graphs.get(gid) is _active["graph"]:
            del multi_graph_manager.graphs[gid]
    except Exception:
        pass
    _active["mg_id"] = None


def multigraph_id() -> Optional[str]:
    return _active.get("mg_id")


def human_size(n: Optional[int]) -> str:
    if not n and n != 0:
        return "?"
    step = 1024.0
    units = ["B", "KB", "MB", "GB", "TB"]
    v = float(n)
    for u in units:
        if v < step or u == units[-1]:
            return f"{v:.0f} {u}" if u == "B" else f"{v:.1f} {u}"
        v /= step
    return f"{n} B"
