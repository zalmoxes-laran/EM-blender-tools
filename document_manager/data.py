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
    absolute_time_start: StringProperty(name="Absolute Time Start", default="")  # type: ignore
    source_type: StringProperty(
        name="Source Type",
        description="analytical (from context) or comparative (from analogues)",
        default="",
    )  # type: ignore

    # --- Document typization ---
    doc_type: EnumProperty(
        name="Document Type",
        description="Type of the source document",
        items=[
            ('IMAGE', 'Image', 'Photograph, drawing, scan'),
            ('MODEL_3D', '3D Model', 'Photogrammetric or laser scan model'),
            ('TEXT', 'Textual', 'Written document'),
            ('PDF', 'PDF', 'PDF document'),
            ('CAD', 'CAD', 'CAD drawing (DWG, DXF)'),
            ('SHAPEFILE', 'Shapefile', 'GIS shapefile'),
            ('OTHER', 'Other', 'Other document type'),
        ],
        default='IMAGE'
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


class RMDocItem(PropertyGroup):
    """A scene object (quad) representing a spatialized document.

    Object-centric: each entry is a Blender object found in the scene
    with the 'em_doc_node_id' custom property. Follows the same pattern
    as RMItem (scene objects → epochs) and AnastylisisItem (scene objects → SF).
    """

    # --- Scene object identity ---
    name: StringProperty(name="Object Name", default="")  # type: ignore
    object_exists: BoolProperty(
        name="Object Exists",
        description="Whether the Blender object still exists in the scene",
        default=True,
    )  # type: ignore

    # --- Linked document (from graph) ---
    doc_node_id: StringProperty(
        name="Document Node ID",
        description="ID of the linked DocumentNode in the graph",
        default="",
    )  # type: ignore
    doc_name: StringProperty(
        name="Document Name",
        description="Name of the linked document (e.g. D.05)",
        default="",
    )  # type: ignore
    doc_description: StringProperty(
        name="Document Description",
        default="",
    )  # type: ignore

    # --- Certainty of spatial positioning ---
    certainty_class: StringProperty(
        name="Certainty Class",
        description="Positioning methodology: direct (red), reconstructed (orange), hypothetical (yellow)",
        default="",
    )  # type: ignore

    # --- Quad geometry ---
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

    # --- Camera ---
    has_camera: BoolProperty(
        name="Has Camera",
        description="Whether a camera is associated with this quad",
        default=False,
    )  # type: ignore
    camera_object_name: StringProperty(name="Camera Object", default="")  # type: ignore


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
    is_piloting_camera: BoolProperty(
        name="Pilot Camera",
        description="Navigate inside camera view, moving camera and quad together",
        default=False,
    )  # type: ignore

    rm_border_by_geometry: BoolProperty(
        name="Colour RM by geometry",
        description=(
            "Sync each RMDoc quad's viewport object colour with the "
            "linked DocumentNode's `geometry` axis (reality_based red, "
            "observable orange, asserted yellow). Requires the viewport "
            "shading to be set to Solid + Color: Object to visualise"
        ),
        default=False,
        update=lambda self, context: _on_rm_border_by_geometry_toggle(
            self, context),
    )  # type: ignore


# ============================================================================
# RM viewport colour sync (EM 1.6 — document geometry axis)
# ============================================================================

_GEOMETRY_RGBA_CACHE = None


def _load_geometry_rgba():
    """Read hex border colours for each geometry value from
    ``em_visual_rules.json`` and convert to RGBA tuples for Blender's
    ``object.color``. Cached once per Python process.
    """
    global _GEOMETRY_RGBA_CACHE
    if _GEOMETRY_RGBA_CACHE is not None:
        return _GEOMETRY_RGBA_CACHE
    out = {}
    try:
        from s3dgraphy.utils.utils import get_document_variant_style
        for key in ("reality_based", "observable", "asserted"):
            hex_c = get_document_variant_style(key).get(
                "border_color", "#000000")
            s = hex_c.lstrip("#")
            if len(s) == 6:
                r, g, b = (int(s[i:i + 2], 16) / 255.0
                           for i in (0, 2, 4))
                out[key] = (r, g, b, 1.0)
    except Exception:
        out = {
            "reality_based": (0.608, 0.200, 0.200, 1.0),
            "observable":    (0.847, 0.392, 0.000, 1.0),
            "asserted":      (0.847, 0.741, 0.188, 1.0),
        }
    _GEOMETRY_RGBA_CACHE = out
    return out


def _resolve_doc_geometry(scene, doc_node_id):
    """Return the ``geometry`` value on the DocumentNode identified by
    ``doc_node_id``, or ``None`` when unset / lookup fails.
    """
    if not doc_node_id:
        return None
    try:
        from s3dgraphy import get_graph
        em_tools = scene.em_tools
        if em_tools.active_file_index < 0:
            return None
        gi = em_tools.graphml_files[em_tools.active_file_index]
        g = get_graph(gi.name)
        if g is None:
            return None
        n = g.find_node_by_id(doc_node_id)
        if n is None:
            return None
        return (getattr(n, "data", None) or {}).get("geometry")
    except Exception:
        return None


def apply_rm_geometry_colors(scene, force_reset=False):
    """Walk ``scene.rmdoc_list`` and set each quad's viewport object
    colour from the linked DocumentNode's ``geometry`` axis. When
    ``force_reset`` is True or the toggle is off, reset colours to
    neutral white.
    """
    settings = getattr(scene, "doc_settings", None)
    toggle_on = bool(
        settings and getattr(settings, "rm_border_by_geometry", False))
    rgba_map = _load_geometry_rgba()
    neutral = (1.0, 1.0, 1.0, 1.0)
    for item in getattr(scene, "rmdoc_list", []):
        obj = bpy.data.objects.get(item.name)
        if obj is None:
            continue
        if not toggle_on or force_reset:
            obj.color = neutral
            continue
        geom = _resolve_doc_geometry(scene, item.doc_node_id)
        obj.color = rgba_map.get(geom, neutral)


def _on_rm_border_by_geometry_toggle(settings, context):
    """Update callback: refresh colours immediately when the toggle
    changes state, so the user sees the effect without waiting for a
    sync pass.
    """
    try:
        apply_rm_geometry_colors(context.scene,
                                 force_reset=not settings.rm_border_by_geometry)
    except Exception:
        pass


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
        item.absolute_time_start = src.absolute_time_start
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

    # After doc_list sync, also sync the object-centric rmdoc_list
    sync_rmdoc_list(scene)

    # EM 1.6: refresh RMDoc quad viewport colours if the user toggled
    # "Colour RM by geometry". Runs after rmdoc_list is up to date so
    # newly-added quads get coloured too.
    try:
        apply_rm_geometry_colors(scene)
    except Exception:
        pass


def sync_rmdoc_list(scene):
    """Synchronize scene.rmdoc_list from scene objects representing documents.

    Object-centric: each entry is a Blender object in the scene. Detection uses:
    1. Primary: objects with 'em_doc_node_id' custom property (set by Import Image)
    2. Fallback: objects whose name matches '{graph_code}.{doc_name}' or '{doc_name}'
       where doc_name is a known document in doc_list. This catches objects created
       by the old DosCo import or manually named.

    Pattern mirrors rm_manager: scene objects → list → linked graph entity.
    """
    rmdoc_list = scene.rmdoc_list

    # Build lookup of existing rmdoc_list items by object name
    existing = {item.name: i for i, item in enumerate(rmdoc_list)}
    seen_names = set()

    # Build doc_list lookup by node_id AND by name for fallback matching
    doc_by_node_id = {}
    doc_by_name = {}
    if hasattr(scene, 'doc_list'):
        for doc_item in scene.doc_list:
            if doc_item.node_id:
                doc_by_node_id[doc_item.node_id] = doc_item
            if doc_item.name:
                doc_by_name[doc_item.name] = doc_item

    # Determine active graph code for name matching
    graph_code = ""
    em_tools = scene.em_tools
    if (hasattr(em_tools, 'graphml_files') and em_tools.graphml_files
            and 0 <= em_tools.active_file_index < len(em_tools.graphml_files)):
        gf = em_tools.graphml_files[em_tools.active_file_index]
        graph_code = getattr(gf, 'graph_code', '') or ''

    def _process_object(obj, doc_node_id, doc_item):
        """Add or update an rmdoc_list entry for a scene object."""
        seen_names.add(obj.name)

        if obj.name in existing:
            item = rmdoc_list[existing[obj.name]]
        else:
            item = rmdoc_list.add()

        item.name = obj.name
        item.object_exists = True
        item.doc_node_id = doc_node_id or ""

        if doc_item:
            item.doc_name = doc_item.name
            item.doc_description = doc_item.description
            item.certainty_class = doc_item.certainty_class
        else:
            item.doc_name = ""
            item.doc_description = ""
            item.certainty_class = ""

        # Quad dimensions from object bounding box
        if obj.type == 'MESH' and obj.data:
            bb = obj.bound_box
            xs = [v[0] for v in bb]
            ys = [v[1] for v in bb]
            item.quad_width = (max(xs) - min(xs)) * obj.scale.x
            item.quad_height = (max(ys) - min(ys)) * obj.scale.y
        item.dimensions_type = obj.get('em_dimensions_type', 'SYMBOLIC')

        # Camera detection
        item.has_camera = False
        item.camera_object_name = ""
        cam_name = obj.get('em_camera_name', '')
        if cam_name and cam_name in bpy.data.objects:
            cam_obj = bpy.data.objects[cam_name]
            if cam_obj.type == 'CAMERA':
                item.has_camera = True
                item.camera_object_name = cam_name
        else:
            for child in obj.children:
                if child.type == 'CAMERA':
                    item.has_camera = True
                    item.camera_object_name = child.name
                    break

    # Pass 1: objects with em_doc_node_id (primary detection)
    for obj in bpy.data.objects:
        doc_node_id = obj.get('em_doc_node_id')
        if not doc_node_id:
            continue
        doc_item = doc_by_node_id.get(doc_node_id)
        _process_object(obj, doc_node_id, doc_item)

    # Pass 2: fallback — match object names to known documents
    # Patterns: "{graph_code}.{doc_name}" or just "{doc_name}"
    for obj in bpy.data.objects:
        if obj.name in seen_names:
            continue  # Already matched in pass 1

        obj_name = obj.name
        matched_doc = None

        # Try exact match: object name == document name
        if obj_name in doc_by_name:
            matched_doc = doc_by_name[obj_name]

        # Try prefix match: "{graph_code}.{doc_name}"
        if not matched_doc and graph_code:
            prefix = f"{graph_code}."
            if obj_name.startswith(prefix):
                suffix = obj_name[len(prefix):]
                if suffix in doc_by_name:
                    matched_doc = doc_by_name[suffix]

        if matched_doc:
            # Set the custom property for future consistency
            obj['em_doc_node_id'] = matched_doc.node_id
            _process_object(obj, matched_doc.node_id, matched_doc)

    # Remove orphaned entries (object no longer in scene)
    i = len(rmdoc_list) - 1
    while i >= 0:
        if rmdoc_list[i].name not in seen_names:
            rmdoc_list.remove(i)
        i -= 1


# ============================================================================
# REGISTRATION
# ============================================================================

classes = (
    DocItem,
    RMDocItem,
    DocManagerSettings,
)


def register_data():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.doc_list = CollectionProperty(type=DocItem)
    bpy.types.Scene.doc_list_index = IntProperty(name="Active Document", default=0)
    bpy.types.Scene.rmdoc_list = CollectionProperty(type=RMDocItem)
    bpy.types.Scene.rmdoc_list_index = IntProperty(name="Active RMDoc", default=0)
    bpy.types.Scene.doc_settings = PointerProperty(type=DocManagerSettings)
    # Transient shared buffer backing the Name field of the Create
    # Master Document dialog. The "+" suggest-next operator writes
    # here so the open dialog sees the update on next tick — a
    # dialog-internal operator property cannot be written from a
    # sub-operator while the dialog is still alive.
    bpy.types.Scene.em_pending_master_doc_name = StringProperty(
        name="Pending Master Doc Name",
        description="Transient buffer for the Create Master Document "
                    "dialog's Name field.",
        default="",
    )


def unregister_data():
    if hasattr(bpy.types.Scene, 'em_pending_master_doc_name'):
        del bpy.types.Scene.em_pending_master_doc_name
    if hasattr(bpy.types.Scene, 'doc_settings'):
        del bpy.types.Scene.doc_settings
    if hasattr(bpy.types.Scene, 'rmdoc_list_index'):
        del bpy.types.Scene.rmdoc_list_index
    if hasattr(bpy.types.Scene, 'rmdoc_list'):
        del bpy.types.Scene.rmdoc_list
    if hasattr(bpy.types.Scene, 'doc_list_index'):
        del bpy.types.Scene.doc_list_index
    if hasattr(bpy.types.Scene, 'doc_list'):
        del bpy.types.Scene.doc_list

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
