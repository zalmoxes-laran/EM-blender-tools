"""EM Shelf tool — pure, bpy-free bridge to the s3dgraphy Shelf + acquisition ops.

Session C1: a SEPARATE Shelf tool with a 3D-first project-folder search that
populates the shelf VIA THE ACQUISITION PIPELINE (in-process s3dgraphy). No logic
is reimplemented here — every step calls the s3dgraphy api:

  scan a folder → for each 3D file: fs_record(path) → apply_mapping("fs") →
  AcquisitionDescriptor → acquire_from_descriptor(descriptor, shelf)

so each entry lands with its acquisition DTC event + origin (tier). The shelf is a
standalone reusable em.json (save/load) — the ShelfGraph substrate (Session A).

Hatting (C2/C3) is here too, as thin passthroughs to the s3dgraphy facet ops: the
role picks the facet (RM / RMSF / RMDoc / Document) and the facets are NOT
exclusive — one Resource can carry several.

NO ``bpy`` here (unit-testable outside Blender), mirroring resource_backend.py.
The active shelf + its display cards are held per session.
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
    # C3 hatting facets + the datamodel-driven attach picker
    "hat_as_representation_model", "hat_as_rmsf", "hat_as_rmdoc", "hat_as_document",
    "attach_candidates",
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


# ── hatting facets (C2 = RM; C3 = RMSF / RMDoc / Document) ──────────────────────
# The ROLE picks the facet and facets are NOT exclusive: the same Resource can be
# an RM (of the epoch it depicts) AND a Document (a source in a paradata chain).
# All four are pure graph ops in s3dgraphy — the Blender mesh import + object bind
# stay in the operator, and the Document facet imports NOTHING (it is a source).
FACET_ITEMS = (
    ('RM', "Representation Model",
     "A 3D representation of a real or reconstructed STATE — binds to one or "
     "more Epochs (a photogrammetric model of the current state is the RM of "
     "the epoch it depicts). Imports the mesh"),
    ('RMSF', "RM Special Find",
     "The 3D representation of a Special Find (e.g. a scanned capital "
     "repositioned by an anastylosis hypothesis). Binds to an SF node. "
     "Imports the mesh"),
    ('RMDOC', "RM Document",
     "A Document instantiated in the 3D scene (e.g. a historical photo placed "
     "where it was taken). Binds to a Document; never anchored to an epoch or "
     "a stratigraphic unit — its placement is graded on the geometry axis. "
     "Imports the mesh"),
    ('DOCUMENT', "Document (source)",
     "The resource used as a SOURCE in a reasoning chain — the paradata entry "
     "an Extractor reads from. No mesh, no placement"),
)
#: facet enum id → the s3dgraphy facet name used by the api
FACET_KEY = {'RM': "rm", 'RMSF': "rmsf", 'RMDOC': "rmdoc", 'DOCUMENT': "document"}
#: the facets that put geometry in the scene (Document is a record, not a mesh)
MESH_FACETS = ('RM', 'RMSF', 'RMDOC')


def attach_candidates(facet: str, target_graph: Any) -> List[Dict[str, Any]]:
    """The nodes ``facet`` may attach to in ``target_graph`` — straight from
    s3dgraphy, which derives them from the datamodel's allowed_connections (the
    picker never hardcodes a type list). ``rm`` returns the epochs in
    chronological order (first = has_first_epoch)."""
    from s3dgraphy import api
    if target_graph is None:
        return []
    return api.attach_candidates(FACET_KEY.get(facet, facet), target_graph)


def hat_as_rm(target_graph: Any, resource_id: str, *, rm_id: Optional[str] = None,
              name: Optional[str] = None, epochs: Optional[List[str]] = None,
              attach_to: Optional[str] = None) -> Dict[str, Any]:
    """Hat a shelf resource as a RepresentationModel bound to one or more EPOCHS
    (ordered: first → has_first_epoch, rest → survive_in_epoch)."""
    from s3dgraphy import api
    return api.hat_as_representation_model(
        target_graph, resource_id, shelf=_active["graph"], rm_id=rm_id,
        name=name, epochs=epochs, attach_to=attach_to)


def hat_as_rmsf(target_graph: Any, resource_id: str, *, rmsf_id: Optional[str] = None,
                name: Optional[str] = None, attach_to: Optional[str] = None
                ) -> Dict[str, Any]:
    """Hat a shelf resource as an RMSF attached to a Special Find node."""
    from s3dgraphy import api
    return api.hat_as_rmsf(target_graph, resource_id, shelf=_active["graph"],
                           rmsf_id=rmsf_id, name=name, attach_to=attach_to)


def hat_as_rmdoc(target_graph: Any, resource_id: str, *,
                 rmdoc_id: Optional[str] = None, name: Optional[str] = None,
                 attach_to: Optional[str] = None,
                 geometry: Optional[str] = None) -> Dict[str, Any]:
    """Hat a shelf resource as an RMDoc attached to a Document node. No epoch, no
    stratigraphy: what grades an RMDoc is ``geometry``, the metric authority of
    its placement (Q-C) — reality_based / observable / asserted / symbolic. This
    replaces the C3 ``placement = manual|anchored`` literal, which stated a
    workflow fact instead of a qualia."""
    from s3dgraphy import api
    return api.hat_as_rmdoc(target_graph, resource_id, shelf=_active["graph"],
                            rmdoc_id=rmdoc_id, name=name, attach_to=attach_to,
                            geometry=geometry)


def hat_as_document(target_graph: Any, resource_id: str, *,
                    doc_id: Optional[str] = None, name: Optional[str] = None,
                    description: str = "", role: Optional[str] = None,
                    content_nature: Optional[str] = None,
                    geometry: Optional[str] = None,
                    attach_to: Optional[str] = None) -> Dict[str, Any]:
    """Wire an EXISTING DocumentNode (``doc_id``, built by the operator through
    ``canonical_document_helpers.create_canonical_document_node`` so EMTools keeps ONE
    document shape) to the Resource via has_linked_resource (P67), plus the
    optional attach. When ``doc_id`` is unknown the op creates the node itself
    with the same shape."""
    from s3dgraphy import api
    return api.hat_as_document(
        target_graph, resource_id, shelf=_active["graph"], doc_id=doc_id, name=name,
        description=description, role=role, content_nature=content_nature,
        geometry=geometry, attach_to=attach_to)


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
