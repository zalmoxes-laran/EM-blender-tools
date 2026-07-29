"""PropertyGroup backing the EM Scene tab.

UI buffer only — the single source of truth is the s3dgraphy graph + the FS-index
manifest (see resource_backend.py). Nothing here is a Blender scene object.
"""

from __future__ import annotations

import bpy
from bpy.props import BoolProperty, StringProperty
from bpy.types import PropertyGroup


class EM_ResourcesProps(PropertyGroup):
    # section expanders
    show_documents: BoolProperty(name="Documents", default=False)
    show_rm: BoolProperty(name="Representation Models", default=False)
    show_dtc: BoolProperty(name="DTC", default=False)
    show_shelf: BoolProperty(name="Shelf", default=True)
    show_minio: BoolProperty(name="Object store (MinIO)", default=False)

    # status line + last-scan summary (filled by the scan operator)
    status: StringProperty(name="", default="")
    scanned_folder: StringProperty(name="", default="")


classes = (EM_ResourcesProps,)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.em_resources = bpy.props.PointerProperty(type=EM_ResourcesProps)


def unregister():
    del bpy.types.Scene.em_resources
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
