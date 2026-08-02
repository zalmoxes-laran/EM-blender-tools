"""EM Scene tab backend logic — the pure, bpy-free core.

Bridges the EMTools "EM Scene" tab to the s3dgraphy R1 FS-index backend
(``s3dgraphy.resources.FSIndexBackend``). Mirrors graph_info/hdto_graph.py and
dtc_authoring/dtc_graph.py: NO ``bpy`` import here (unit-testable outside
Blender), a capability guard for the stale-bundle case, and all reads/writes go
through the s3dgraphy graph (em.json = single source of truth).

Model (E.D.'s decision — ADOPT):
  * The DosCo / library folder is scanned by an :class:`FSIndexBackend`; each file
    gets a **stable ID** kept in a Tropy-like manifest persisted in the folder
    (``.em_resources_manifest.json``) so IDs survive across sessions.
  * The **Shelf** = the un-hatted resources (orphans): files with no matching
    graph node, applying the DosCo EM-id convention filters.
  * **Hatting** a Shelf orphan → a Document whose ``node_id`` **adopts the FS
    stable ID** — one ID space (FS manifest / node / references), no separate
    resource_id attribute. The existing DosCo→Document path is unaffected.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

# The Tropy-like manifest is persisted as a dotfile in the scanned folder so the
# stable IDs survive across sessions (FSIndexBackend.scan skips dotfiles, so the
# manifest never indexes itself).
MANIFEST_NAME = ".em_resources_manifest.json"

class ResourcesUnavailable(RuntimeError):
    """Raised when the active s3dgraphy lacks the R0/R1 resource layer."""


def resources_supported() -> bool:
    """True if the importable s3dgraphy exposes the R0/R1 resource layer
    (the FS-index backend). False for the stale vendored copy → the panel shows
    a blocker directing the user to activate the dev s3dgraphy (./em.sh s3d)."""
    try:
        from s3dgraphy.resources import FSIndexBackend  # noqa: F401
        return True
    except Exception:
        return False


# ── manifest-backed scan (stable IDs across sessions) ──────────────────────────
def _manifest_path(folder: str) -> str:
    return os.path.join(folder, MANIFEST_NAME)


def get_backend(folder: str):
    """Load-or-create an :class:`FSIndexBackend` for ``folder``, rescan it against
    disk, and persist the manifest so stable IDs survive across sessions.

    Returns the scanned backend. Raises :class:`ResourcesUnavailable` if the
    resource layer is missing, and lets the caller handle an invalid folder
    (an empty/absent folder simply yields an empty manifest)."""
    if not resources_supported():
        raise ResourcesUnavailable(
            "the active s3dgraphy has no resource layer — activate the dev s3dgraphy")
    from s3dgraphy.resources import FSIndexBackend

    mpath = _manifest_path(folder)
    if os.path.isfile(mpath):
        try:
            with open(mpath, encoding="utf-8") as fh:
                data = json.load(fh)
            backend = FSIndexBackend.from_manifest(data)
            # keep the manifest anchored to the current folder (it may have moved)
            backend.folder = os.path.abspath(folder)
        except Exception:
            backend = FSIndexBackend(folder)
    else:
        backend = FSIndexBackend(folder)

    backend.rescan()
    _save_manifest(backend)
    return backend


def _save_manifest(backend) -> None:
    """Persist the backend's manifest into its folder (best-effort)."""
    folder = getattr(backend, "folder", "")
    if not folder or not os.path.isdir(folder):
        return
    try:
        with open(_manifest_path(folder), "w", encoding="utf-8") as fh:
            json.dump(backend.to_manifest(), fh, indent=2)
    except Exception:
        pass


# ── Shelf (un-hatted resources) ────────────────────────────────────────────────
def _node_ids(graph: Any) -> set:
    return {getattr(n, "node_id", None) for n in getattr(graph, "nodes", []) or []}


def shelf_entries(graph: Any, backend, *, graph_code: Optional[str] = None
                  ) -> List[Dict[str, Any]]:
    """The Shelf = un-hatted resources. Built on the FS backend's orphan scan
    (DosCo EM-id convention filters + name-match against existing Document /
    Extractor / Combiner nodes) and additionally excludes any orphan whose FS
    **stable ID is already a node** in the graph — so a resource hatted under a
    different display name (ID adopted) still leaves the Shelf.

    ``graph`` may be ``None`` (then every on-convention Document-id file is on the
    Shelf). Returns dicts ``{resource_id, key_id, filename, rel_path}``."""
    existing_ids = _node_ids(graph) if graph is not None else set()
    out: List[Dict[str, Any]] = []
    for orphan in backend.orphans(graph, graph_code=graph_code):
        if orphan.resource_id in existing_ids:
            continue  # already hatted (ID adopted) — not on the Shelf
        out.append({
            "resource_id": orphan.resource_id,
            "key_id": orphan.key_id,
            "filename": orphan.filename,
            "rel_path": orphan.rel_path,
        })
    return out


# ── MinIO / shared object store (promote — mirrors EMStudio) ───────────────────
# Resources are LinkNodes (E73). Their locator (``data.url``) may be a local path,
# a file:// / s3:// URI, or an http(s) URL. "Promote to MinIO" uploads a LOCAL
# resource into the shared object store under its OWN stable ID (one ID space
# FS↔MinIO) and repoints its locator at the returned s3:// URI.
_LINK_TYPE = "link"
_REMOTE_PREFIXES = ("http://", "https://", "s3://", "file://")


def _link_url(node: Any) -> str:
    url = getattr(node, "url", None)
    if url is None:
        url = (getattr(node, "data", {}) or {}).get("url", "")
    return url or ""


def _locator_kind(url: str) -> str:
    low = (url or "").lower()
    if low.startswith(("http://", "https://")):
        return "http_url"
    if low.startswith("s3://"):
        return "s3_uri"
    if low.startswith("file://"):
        return "file_uri"
    return "local_path"


def minio_supported() -> bool:
    """True if promote is possible: the active s3dgraphy exposes the MinIO api op
    AND the optional ``minio`` SDK is installed. False → the button degrades with
    a clear message (like the FS resource-layer blocker)."""
    try:
        import importlib.util
        from s3dgraphy import api
        if not hasattr(api, "ingest_minio_resource"):
            return False
        return importlib.util.find_spec("minio") is not None
    except Exception:
        return False


def list_link_resources(graph: Any) -> List[Dict[str, Any]]:
    """List the graph's resources (LinkNodes) with id/name/locator/kind — the
    face the promote action acts on. Read-only."""
    out: List[Dict[str, Any]] = []
    for n in getattr(graph, "nodes", []) or []:
        if getattr(n, "node_type", None) != _LINK_TYPE:
            continue
        url = _link_url(n)
        out.append({
            "id": n.node_id,
            "name": str(getattr(n, "name", "") or ""),
            "locator": url,
            "kind": _locator_kind(url),
        })
    return out


def promote_resource_to_minio(graph: Any, resource_id: str) -> Dict[str, Any]:
    """Upload a LOCAL resource's bytes into the shared MinIO under its OWN stable
    ID (in-process s3dgraphy; api.ingest_minio_resource reads S3_* from env), then
    repoint its LinkNode locator to the returned ``s3_uri``. The stable ID and every
    graph reference are unchanged (one ID space FS↔MinIO). Returns
    ``{id, object_key, s3_uri}``. Raises ``ValueError`` for a non-local / non-link
    resource, or ``MissingDependency`` if the ``minio`` extra is absent."""
    from s3dgraphy import api
    node = graph.find_node_by_id(resource_id)
    if node is None or getattr(node, "node_type", None) != _LINK_TYPE:
        raise ValueError(f"{resource_id!r} is not a resource (LinkNode)")
    url = _link_url(node)
    if not url or _locator_kind(url) != "local_path":
        raise ValueError("resource has no local path to promote")
    # preserve the stable ID: pass resource_id through to the MinIO backend
    res = api.ingest_minio_resource(url, resource_id=resource_id)
    # repoint the locator at the shared-store URI (id + refs unchanged)
    d = getattr(node, "data", None)
    if not isinstance(d, dict):
        d = {}
        setattr(node, "data", d)
    d["url"] = res["s3_uri"]
    return res


# ── Hatting (Create-Host generalised — ADOPT the FS stable ID) ──────────────────
def hat_orphan_as_document(graph: Any, resource_id: str, name: str, *,
                           description: str = "", resolved_epoch=None,
                           creation_year: Optional[int] = None,
                           role: Optional[str] = None,
                           content_nature: Optional[str] = None,
                           geometry: Optional[str] = None):
    """Promote a Shelf orphan → a Canonical Document, ADOPTING ``resource_id`` (the
    FS stable ID) as the new node's ``node_id``. Delegates to the shared
    ``create_master_document_node`` (the existing DosCo→Document path) so the
    DocumentNode shape (attributes + temporal-anchor chain) stays identical —
    only the identity is pinned. Returns the created node.

    After this, the resource's stable ID is a node in the graph, so
    :func:`shelf_entries` no longer lists it (it has left the Shelf), while the
    FS backend still resolves the same ID to the file (one ID space)."""
    from ..master_document_helpers import create_master_document_node
    return create_master_document_node(
        graph, name=name, description=description, resolved_epoch=resolved_epoch,
        creation_year=creation_year, role=role, content_nature=content_nature,
        geometry=geometry, mark_as_canonical=True, node_id=resource_id)


# RM / DTC hatting are R4 stubs (Document is the R4 hat target). The FS stable ID
# is the identity for those too when implemented.
def hat_orphan_as_rm(*_args, **_kwargs):  # pragma: no cover - stub
    raise NotImplementedError("RM hatting arrives with R3/R5")


def hat_orphan_as_dtc(*_args, **_kwargs):  # pragma: no cover - stub
    raise NotImplementedError("DTC-resource hatting arrives with R3")
