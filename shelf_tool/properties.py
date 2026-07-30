"""PropertyGroup backing the EM Shelf tool.

UI buffer only — the single source of truth is the s3dgraphy ShelfGraph held by
shelf_backend (a standalone em.json). Nothing here is a Blender scene object.
"""

from __future__ import annotations

import bpy
from bpy.props import BoolProperty, StringProperty
from bpy.types import PropertyGroup


class EM_ShelfProps(PropertyGroup):
    folder: StringProperty(
        name="Project folder",
        description="Folder scanned (3D-first) to populate the Shelf",
        subtype='DIR_PATH', default="")  # type: ignore
    recursive: BoolProperty(
        name="Recursive", description="Scan sub-folders too", default=True)  # type: ignore
    status: StringProperty(name="", default="")  # type: ignore


classes = (EM_ShelfProps,)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.em_shelf = bpy.props.PointerProperty(type=EM_ShelfProps)


def unregister():
    del bpy.types.Scene.em_shelf
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
