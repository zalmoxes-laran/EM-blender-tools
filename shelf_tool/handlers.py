"""Project-scoped Shelf persistence (Session C2.1).

When the Shelf scope is PROJECT (a member of the project's multigraph), the shelf
is NOT part of the Heriverse dissemination export (which serializes only
``em_tools.graphml_files``). To persist it with the working project, a **sidecar**
em.json is written beside the .blend on save and auto-loaded on open — reusing the
Session-A ``save_shelf`` / ``load_shelf``. Least-invasive: two persistent app
handlers, no change to the project save/export flow.

Sidecar path: ``<blend-without-ext>_shelf.em.json``. Absent when the .blend is
unsaved → the UI warns to save the .blend (or to use "Save Shelf").
"""

from __future__ import annotations

import os

import bpy
from bpy.app.handlers import persistent

from . import shelf_backend


def sidecar_path() -> "str | None":
    bp = bpy.data.filepath
    if not bp:
        return None
    return os.path.splitext(bp)[0] + "_shelf.em.json"


@persistent
def _save_post(_dummy) -> None:
    """On .blend save: if the shelf is PROJECT-scoped, write it to the sidecar."""
    try:
        scene = bpy.context.scene
        p = getattr(scene, "em_shelf", None)
        if p is None or p.shelf_scope != 'PROJECT':
            return
        if shelf_backend.active_shelf() is None:
            return
        path = sidecar_path()
        if not path:
            return
        shelf_backend.save_shelf(path)
        print(f"[EM Shelf] project shelf saved → {os.path.basename(path)}")
    except Exception as exc:  # never break the user's save
        print(f"[EM Shelf] project-shelf save failed: {exc}")


@persistent
def _load_post(_dummy) -> None:
    """On .blend open: auto-load the sidecar shelf if present (→ PROJECT scope)."""
    try:
        path = sidecar_path()
        if not path or not os.path.isfile(path):
            return
        shelf_backend.load_shelf(path)
        from . import properties
        scene = bpy.context.scene
        p = getattr(scene, "em_shelf", None)
        if p is not None:
            p.shelf_scope = 'PROJECT'   # update callback links it into the multigraph
            properties.sync_items(scene)
        print(f"[EM Shelf] project shelf loaded ← {os.path.basename(path)}")
    except Exception as exc:
        print(f"[EM Shelf] project-shelf load failed: {exc}")


def register():
    if _save_post not in bpy.app.handlers.save_post:
        bpy.app.handlers.save_post.append(_save_post)
    if _load_post not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_load_post)


def unregister():
    if _save_post in bpy.app.handlers.save_post:
        bpy.app.handlers.save_post.remove(_save_post)
    if _load_post in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_load_post)
