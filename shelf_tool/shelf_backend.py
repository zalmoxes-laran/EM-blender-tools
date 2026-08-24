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


#: The ops the ENRICHED list needs (Traccia A). Kept OUT of `_REQUIRED_API` on
#: purpose: an older s3dgraphy still gives a working shelf, it simply cannot
#: answer role/mode/residence — and turning the whole panel off over three extra
#: columns would be a worse trade than showing the shelf without them.
_TABLE_API = ("shelf_table", "shelf_table_columns", "shelf_entry_status",
              "resource_roles")


def table_supported() -> bool:
    """True when this s3dgraphy can answer the three columns only it knows:
    residence · role · mode. False → the list drops those cells and SAYS so,
    instead of computing them here (which would be a second answer)."""
    try:
        from s3dgraphy import api
        return all(hasattr(api, fn) for fn in _TABLE_API)
    except Exception:
        return False


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


# ── the shelf of the ACTIVE PROJECT (Traccia C) ─────────────────────────────────
#
# The correction that makes this tool part of the project instead of beside it:
# **Blender does not export the shelf**. The shelf is already a member of the
# container (a ShelfGraph in the em.json), so what Blender does is LIST it and
# bring one entry at a time into the scene. There is no export path here and
# there must not be one — that is the whole point of the change.

def project_shelf():
    """The ShelfGraph the open project already carries, or None.

    Found by its MARKER in the multigraph (`em_collection == "ShelfGraph"`), not
    by its id: the id is a convention (`<project>__shelf`) and a project that
    came from somewhere else will have used another one. A marker is what makes a
    shelf self-identifying, which is exactly why it exists.
    """
    try:
        from s3dgraphy.multigraph.multigraph import multi_graph_manager
        from s3dgraphy.shelf import is_shelf
    except Exception:
        return None
    for graph in (multi_graph_manager.graphs or {}).values():
        try:
            if is_shelf(graph):
                return graph
        except Exception:                       # noqa: BLE001 — a graph that will not answer
            continue
    return None


def adopt_project_shelf() -> Dict[str, Any]:
    """Make the project's own ShelfGraph the active one — no file, no import.

    This is the difference between browsing YOUR project's library and browsing a
    folder: the entries, their roles and their acquisition events came with the
    em.json, and hatting one of them references the resource the study already
    knows. Returns ``{adopted, graph_id, count}``.
    """
    graph = project_shelf()
    if graph is None:
        return {"adopted": False, "graph_id": None, "count": 0}
    _active["graph"] = graph
    _active["path"] = None                      # it lives in the project, not a file
    _active["mg_id"] = str(getattr(graph, "graph_id", "") or "") or None
    _refresh_cards()
    return {"adopted": True, "graph_id": _active["mg_id"],
            "count": len(_active["cards"])}


def table_subject(study_graph: Any = None) -> List[Any]:
    """What to ask the library ABOUT — the shelf plus the study graph(s).

    The mode column is the hatting reference-check, and a resource sits on the
    SHELF while it is hatted into a STUDY graph: asking the shelf alone answers
    "only_shelf" for everything, for ever. So the subject is both, and when the
    project multigraph is open it is all of it.
    """
    graphs: List[Any] = []
    shelf = _active["graph"]
    if shelf is not None:
        graphs.append(shelf)
    try:
        from s3dgraphy.multigraph.multigraph import multi_graph_manager
        for graph in (multi_graph_manager.graphs or {}).values():
            if graph is not None and all(graph is not g for g in graphs):
                graphs.append(graph)
    except Exception:                           # noqa: BLE001
        pass
    if study_graph is not None and all(study_graph is not g for g in graphs):
        graphs.append(study_graph)
    return graphs


def table_rows(study_graph: Any = None) -> List[Dict[str, Any]]:
    """The shelf as the library's own rows (`api.shelf_table`), or [].

    Read, never computed: residence, role and mode are the three things this side
    must not have a second opinion about.
    """
    if not table_supported() or _active["graph"] is None:
        return []
    from s3dgraphy import api
    try:
        return api.shelf_table(table_subject(study_graph), shelf=_active["graph"])
    except Exception:                           # noqa: BLE001 — a table that will not build
        return []


def entry_status(resource_id: str, study_graph: Any = None) -> Dict[str, Any]:
    """``{in_use, role, mode, used_by}`` for one entry — the library's answer."""
    if not table_supported():
        return {"in_use": False, "role": None, "mode": "", "used_by": []}
    from s3dgraphy import api
    try:
        return api.shelf_entry_status(table_subject(study_graph), resource_id)
    except Exception:                           # noqa: BLE001
        return {"in_use": False, "role": None, "mode": "", "used_by": []}


def resource_roles() -> List[str]:
    """The two roles, from the library that validates them (never a list here)."""
    if not table_supported():
        return []
    from s3dgraphy import api
    try:
        return list(api.resource_roles())
    except Exception:                           # noqa: BLE001
        return []


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
        # …filled in from the library's table when it can answer (see
        # `_refresh_cards`). Empty means "not answered", never "no".
        "role": "",
        "mode": "",
        "residence": "",
    }


def _refresh_cards(study_graph: Any = None) -> None:
    from s3dgraphy import api
    graph = _active["graph"]
    if graph is None:
        _active["cards"] = []
        return
    # ONE table read for the whole list (not one per card): the mode column walks
    # every graph's edges, and doing that per row would make a 200-entry shelf
    # quadratic in the size of the study.
    rows = {str(r.get("ID")): r for r in table_rows(study_graph)}
    cards = []
    for entry in api.list_shelf(graph):
        card = _card(entry)
        row = rows.get(str(entry.get("id")))
        if row:
            # verbatim from the library — this side does not interpret them
            card["role"] = str(row.get("ROLE") or "")
            card["mode"] = str(row.get("MODE") or "")
            card["residence"] = str(row.get("RESIDENCE") or "")
            if not card.get("media_type"):
                # a URI-only entry has no file on disk to re-derive it from, and
                # the library carries what the acquisition recorded
                card["media_type"] = str(row.get("MEDIA_TYPE") or "")
            if card.get("size") in (None, 0) and row.get("SIZE"):
                card["size"] = row.get("SIZE")
        cards.append(card)
    _active["cards"] = cards


def refresh(study_graph: Any = None) -> List[Dict[str, Any]]:
    """Re-read the cards (and the library's table) against a study graph. The
    panel calls this: `mode` cannot be right without the graph the resource may
    be hatted into."""
    _refresh_cards(study_graph)
    return _active["cards"]


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
