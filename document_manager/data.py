"""Data structures for the 3D Document Manager.

Follows the same pattern as rm_manager/data.py:
- PropertyGroups for list items and settings
- Scene-level CollectionProperty + IntProperty + PointerProperty
- sync function to bridge from em_sources_list (upstream) to doc_list (this module)
"""

import bpy
from bpy.props import (
    StringProperty,
    BoolProperty,
    IntProperty,
    FloatProperty,
    EnumProperty,
    CollectionProperty,
    PointerProperty,
)
from bpy.types import PropertyGroup


class DocItem(PropertyGroup):
    """A document item in the 3D Document Manager list.

    Combines paradata fields (from em_sources_list / EMListParadata)
    with 3D representation state (quad, camera, image).
    """

    # --- Identity (mirroring EMListParadata) ---
    name: StringProperty(name="Name", default="")  # type: ignore
    node_id: StringProperty(name="Node ID", default="")  # type: ignore
    description: StringProperty(name="Description", default="")  # type: ignore
    url: StringProperty(name="URL", default="")  # type: ignore

    # --- Master document attributes (from import Phase 1-2) ---
    is_master: BoolProperty(name="Is Master", default=False)  # type: ignore
    certainty_class: StringProperty(
        name="Certainty Class",
        description="Positioning methodology: direct (red), reconstructed (orange), hypothetical (yellow)",
        default="",
    )  # type: ignore
    border_color: StringProperty(name="Border Color", default="#000000")  # type: ignore
    epoch_name: StringProperty(name="Epoch", default="")  # type: ignore
    absolute_start_date: StringProperty(name="Absolute Start Date", default="")  # type: ignore
    source_type: StringProperty(
        name="Source Type",
        description="analytical (from context) or comparative (from analogues)",
        default="",
    )  # type: ignore

    # --- 3D representation state ---
    has_quad: BoolProperty(
        name="Has Quad",
        description="Whether a quad object exists in the scene for this document",
        default=False,
    )  # type: ignore
    quad_object_name: StringProperty(name="Quad Object", default="")  # type: ignore

    has_camera: BoolProperty(
        name="Has Camera",
        description="Whether a camera is associated with this document's quad",
        default=False,
    )  # type: ignore
    camera_object_name: StringProperty(name="Camera Object", default="")  # type: ignore

    image_path: StringProperty(
        name="Image Path",
        description="Resolved absolute path to the document image",
        subtype='FILE_PATH',
        default="",
    )  # type: ignore

    quad_width: FloatProperty(
        name="Width",
        description="Quad width in meters",
        default=1.0,
        min=0.001,
        soft_max=10.0,
        unit='LENGTH',
    )  # type: ignore
    quad_height: FloatProperty(
        name="Height",
        description="Quad height in meters",
        default=1.0,
        min=0.001,
        soft_max=10.0,
        unit='LENGTH',
    )  # type: ignore

    dimensions_type: EnumProperty(
        name="Dimensions",
        description="Whether quad dimensions are real metric or symbolic",
        items=[
            ('SYMBOLIC', "Symbolic", "Approximate/default dimensions"),
            ('METRIC', "Metric", "Real measured dimensions of the document"),
        ],
        default='SYMBOLIC',
    )  # type: ignore


class DocManagerSettings(PropertyGroup):
    """Settings for the 3D Document Manager panel."""

    filter_masters: BoolProperty(
        name="Masters Only",
        description="Show only master documents",
        default=False,
    )  # type: ignore
    filter_with_3d: BoolProperty(
        name="With 3D Only",
        description="Show only documents that have a 3D representation",
        default=False,
    )  # type: ignore
    zoom_to_selected: BoolProperty(
        name="Zoom to Selected",
        description="Zoom viewport to selected document's quad when changing selection",
        default=False,
    )  # type: ignore
    show_settings: BoolProperty(
        name="Show Settings",
        description="Expand settings section",
        default=False,
    )  # type: ignore
    default_focal_length: FloatProperty(
        name="Default Focal Length",
        description="Default focal length for new document cameras (mm)",
        default=35.0,
        min=1.0,
        max=500.0,
    )  # type: ignore
    default_alpha: FloatProperty(
        name="Default Alpha",
        description="Default transparency for document image quads",
        default=0.5,
        min=0.0,
        max=1.0,
    )  # type: ignore


# ============================================================================
# SYNC FUNCTION
# ============================================================================

def sync_doc_list(scene):
    """Synchronize scene.doc_list from scene.em_tools.em_sources_list.

    This is a one-way sync: em_sources_list (populated by populate_document_node)
    is the upstream source of truth for document metadata. doc_list adds 3D state
    on top (quad, camera, image path).

    Also scans the scene for objects with 'em_doc_node_id' custom property
    to detect existing quads and cameras.
    """
    em_tools = scene.em_tools
    sources = em_tools.em_sources_list
    doc_list = scene.doc_list

    # Build lookup of existing doc_list items by node_id
    existing = {item.node_id: i for i, item in enumerate(doc_list)}
    seen_ids = set()

    for src in sources:
        if not src.id_node:
            continue

        seen_ids.add(src.id_node)

        if src.id_node in existing:
            # Update existing entry
            item = doc_list[existing[src.id_node]]
        else:
            # Create new entry
            item = doc_list.add()

        # Copy paradata fields from upstream
        item.name = src.name
        item.node_id = src.id_node
        item.description = src.description
        item.url = src.url
        item.is_master = src.is_master
        item.certainty_class = src.certainty_class
        item.border_color = src.border_color
        item.epoch_name = src.epoch_name
        item.absolute_start_date = src.absolute_start_date
        item.source_type = src.source_type

    # Remove orphaned entries (no longer in em_sources_list)
    i = len(doc_list) - 1
    while i >= 0:
        if doc_list[i].node_id not in seen_ids:
            doc_list.remove(i)
        i -= 1

    # Scan scene for existing quad objects and cameras
    for item in doc_list:
        if not item.node_id:
            continue

        # Check if quad object exists
        quad_found = False
        for obj in bpy.data.objects:
            if obj.get('em_doc_node_id') == item.node_id:
                item.has_quad = True
                item.quad_object_name = obj.name
                quad_found = True

                # Check for child camera
                item.has_camera = False
                item.camera_object_name = ""
                cam_name = obj.get('em_camera_name', '')
                if cam_name and cam_name in bpy.data.objects:
                    cam_obj = bpy.data.objects[cam_name]
                    if cam_obj.type == 'CAMERA':
                        item.has_camera = True
                        item.camera_object_name = cam_name
                else:
                    # Also check children
                    for child in obj.children:
                        if child.type == 'CAMERA':
                            item.has_camera = True
                            item.camera_object_name = child.name
                            break
                break

        if not quad_found:
            item.has_quad = False
            item.quad_object_name = ""
            item.has_camera = False
            item.camera_object_name = ""


# ============================================================================
# REGISTRATION
# ============================================================================

classes = (
    DocItem,
    DocManagerSettings,
)


def register_data():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.doc_list = CollectionProperty(type=DocItem)
    bpy.types.Scene.doc_list_index = IntProperty(name="Active Document", default=0)
    bpy.types.Scene.doc_settings = PointerProperty(type=DocManagerSettings)


def unregister_data():
    if hasattr(bpy.types.Scene, 'doc_settings'):
        del bpy.types.Scene.doc_settings
    if hasattr(bpy.types.Scene, 'doc_list_index'):
        del bpy.types.Scene.doc_list_index
    if hasattr(bpy.types.Scene, 'doc_list'):
        del bpy.types.Scene.doc_list

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
