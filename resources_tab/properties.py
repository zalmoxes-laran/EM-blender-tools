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
    show_revisions: BoolProperty(name="Revisions", default=True)
    show_seals: BoolProperty(name="Seals", default=True)
    #: the resource whose seal card is open ("" = none): one at a time
    active_seal: StringProperty(name="", default="")
    #: «Technical details» under the seal, closed to begin with
    show_seal_tech: BoolProperty(name="Technical details", default=False)
    #: VLONG-DEV27/D4 · a seal opened from a row of the DTC or of the Shelf.
    #: A shelf entry is not a resource of the graph, so the Seals section would
    #: not list it: the clicked one is carried here and shown with the others.
    seal_extra_id: StringProperty(name="", default="")
    seal_extra_name: StringProperty(name="", default="")
    seal_extra_path: StringProperty(name="", default="")

    # status line + last-scan summary (filled by the scan operator)
    status: StringProperty(name="", default="")
    scanned_folder: StringProperty(name="", default="")


class EM_CitationChoice(PropertyGroup):
    """One citation of an old revision, in the «which ones move» dialog."""
    edge_id: StringProperty()
    label: StringProperty()
    move: BoolProperty(name="Move", default=True)


classes = (EM_CitationChoice, EM_ResourcesProps,)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.em_resources = bpy.props.PointerProperty(type=EM_ResourcesProps)


def unregister():
    del bpy.types.Scene.em_resources
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
