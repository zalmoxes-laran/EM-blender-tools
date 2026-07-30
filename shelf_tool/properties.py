"""PropertyGroups backing the EM Shelf tool.

UI buffer only — the single source of truth is the s3dgraphy ShelfGraph held by
shelf_backend (a standalone em.json). The `items` collection mirrors
shelf_backend.cards() for a scalable UIList presentation; it is repopulated
(``sync_items``) after every Scan / Load / New / Remove. Nothing here is a
Blender scene object.
"""

from __future__ import annotations

import bpy
from bpy.props import (BoolProperty, CollectionProperty, EnumProperty,
                       IntProperty, StringProperty)
from bpy.types import PropertyGroup


class EM_ShelfItem(PropertyGroup):
    """One shelf resource, mirrored from a backend card for UIList display."""
    resource_id: StringProperty(default="")  # type: ignore
    # `name` is the UIList's default filter/sort key (built-in name funnel).
    name: StringProperty(default="")  # type: ignore
    locator: StringProperty(default="")  # type: ignore  # local path (for Hat/import)
    media_type: StringProperty(default="")  # type: ignore
    resource_type: StringProperty(default="")  # type: ignore
    size_bytes: IntProperty(default=0)  # type: ignore
    size_text: StringProperty(default="")  # type: ignore
    tier_label: StringProperty(default="")  # type: ignore
    tier_short: StringProperty(default="")  # type: ignore
    exists: BoolProperty(default=True)  # type: ignore


def _scope_update(self, context):
    """Enum callback: register/unregister the active shelf as a member of the
    current project's multigraph (project-local) vs a standalone file."""
    from . import shelf_backend
    if self.shelf_scope == 'PROJECT':
        shelf_backend.link_to_multigraph(_project_shelf_id(context))
    else:
        shelf_backend.unlink_from_multigraph()


def _project_shelf_id(context) -> str:
    try:
        em = context.scene.em_tools
        item = em.graphml_files[em.active_file_index]
        base = getattr(item, "name", "") or "project"
    except Exception:
        base = "project"
    return f"{base}__shelf"


class EM_ShelfProps(PropertyGroup):
    folder: StringProperty(
        name="Project folder",
        description="Folder scanned (3D-first) to populate the Shelf",
        subtype='DIR_PATH', default="")  # type: ignore
    recursive: BoolProperty(
        name="Recursive", description="Scan sub-folders too", default=True)  # type: ignore
    status: StringProperty(name="", default="")  # type: ignore
    items: CollectionProperty(type=EM_ShelfItem)  # type: ignore
    active_index: IntProperty(name="", default=0)  # type: ignore
    shelf_scope: EnumProperty(
        name="Shelf",
        description="Where the Shelf lives: a standalone reusable em.json file, or "
                    "a member of the current project's multigraph (project-local)",
        items=[
            ('STANDALONE', "Standalone file",
             "Reusable .em.json saved/loaded on disk"),
            ('PROJECT', "Project multigraph",
             "Member of the current project's multigraph (co-persisted with it)"),
        ],
        default='STANDALONE', update=_scope_update)  # type: ignore


def _tier_short(tier_label: str) -> str:
    """'Tier 0 · import + origin' → 'T0' (compact badge for the list row)."""
    t = (tier_label or "").strip()
    if t.lower().startswith("tier ") and len(t) > 5 and t[5].isdigit():
        return "T" + t[5]
    return "T?"


def sync_items(scene) -> None:
    """Refill ``scene.em_shelf.items`` from the backend card cache. Clamps the
    active index. Called after Scan / Load / New / Remove — presentation only."""
    from . import shelf_backend
    p = getattr(scene, "em_shelf", None)
    if p is None:
        return
    cards = shelf_backend.cards()
    p.items.clear()
    for c in cards:
        it = p.items.add()
        it.resource_id = c.get("resource_id", "")
        it.name = c.get("name", "") or c.get("resource_id", "")[:8]
        it.locator = c.get("locator", "") or ""
        it.media_type = c.get("media_type", "") or c.get("resource_type", "")
        it.resource_type = c.get("resource_type", "")
        size = c.get("size")
        it.size_bytes = int(size) if isinstance(size, int) else 0
        it.size_text = shelf_backend.human_size(size)
        it.tier_label = c.get("tier", "")
        it.tier_short = _tier_short(c.get("tier", ""))
        it.exists = bool(c.get("exists", True))
    if p.active_index >= len(p.items):
        p.active_index = max(0, len(p.items) - 1)


classes = (EM_ShelfItem, EM_ShelfProps)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.em_shelf = bpy.props.PointerProperty(type=EM_ShelfProps)


def unregister():
    del bpy.types.Scene.em_shelf
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
