"""
Data structures for the Visual Manager 
This module contains all PropertyGroup definitions and data structures
needed for the Visual Manager with renamed properties to avoid conflicts.

REFACTORED: PropertyGroup classes are registered ONLY by em_props.py
This file now handles ONLY Scene property attachment/removal.
"""

import bpy # type: ignore
from bpy.props import ( # type: ignore
    StringProperty,
    BoolProperty,
    FloatProperty,
    IntProperty,
    CollectionProperty,
    PointerProperty,
    FloatVectorProperty,
    EnumProperty
)
from bpy.types import PropertyGroup # type: ignore


# =====================================================
# PROPERTY UPDATE CALLBACKS
# =====================================================
# Lightweight update hooks for label settings — kept here next to the
# PropertyGroup that uses them so the lambda factory stays self-contained.
#
# TODO(label-tool): the position math below assumes labels can be
# matched back to their source camera+target by parsing the object name
# (`_generated.<camera>.<target>`). This is the minimal fix tracked in
# issue #17 — enough to make the Distance / Scale sliders update existing
# labels live. The intended evolution is automatic positioning tied to
# the camera clipping planes (same pattern as `document_manager` uses
# for the RM-doc quads — see `document_manager/operators.py` around
# the `RMDOC_OT_autocrop_near` / `_far` operators). That evolution will
# be tracked as a dedicated Development Project (label-tool refactor)
# and will retire the name-parsing approach here.


def _refresh_existing_labels(context):
    """Reposition / rescale generated labels using current LabelSettings.

    Best-effort: labels whose source camera or target object have been
    renamed or removed are silently skipped (they remain at their old
    position). The intent is to give the Distance / Scale sliders
    immediate visual feedback for the common case where the user is
    just tuning the spacing of a fresh batch of labels.
    """
    # Lazy import to avoid the data.py ↔ label_tools.py module cycle that
    # would happen if label_tools is imported at module load time.
    try:
        from .label_tools import _reposition_label_by_name
    except Exception:
        return

    scene = getattr(context, "scene", None)
    if scene is None:
        return
    label_settings = getattr(scene, "label_settings", None)
    if label_settings is None:
        return

    cams_collection = bpy.data.collections.get("CAMS")
    if cams_collection is None:
        return

    for obj in list(cams_collection.objects):
        if obj.type != 'FONT' or not obj.name.startswith("_generated."):
            continue
        try:
            _reposition_label_by_name(obj, label_settings)
        except Exception:
            # Swallow per-label failures — one broken label must not
            # break the slider for the rest.
            continue


# =====================================================
# PROPERTY GROUP CLASSES
# =====================================================
# NOTE: These classes are registered by em_props.py
# We only define them here for import by other modules

class PropertyValueItem(PropertyGroup):
    """Property value item for color mapping"""
    value: StringProperty(name="Value") # type: ignore
    color: FloatVectorProperty(
        name="Color",
        subtype='COLOR',
        size=4,
        min=0.0,
        max=1.0,
        default=(0.5, 0.5, 0.5, 1.0)
    ) # type: ignore


def get_ramp_types(self, context):
    """Return color ramp types for the enum property"""
    from .color_ramps import COLOR_RAMPS
    return [(k, k.title(), k.title()) for k in COLOR_RAMPS.keys()]


def get_ramp_names(self, context):
    """Return color ramp names for the selected type"""
    from .color_ramps import COLOR_RAMPS
    ramp_type = context.scene.color_ramp_props.ramp_type
    if ramp_type in COLOR_RAMPS:
        return [(k, v["name"], v["description"]) 
                for k, v in COLOR_RAMPS[ramp_type].items()]
    return []


class ColorRampProperties(PropertyGroup):
    """Properties for color ramp selection"""
    ramp_type: EnumProperty(
        name="Scale Type",
        items=get_ramp_types,
        description="Type of color scale"
    ) # type: ignore
    
    ramp_name: EnumProperty(
        name="Color Ramp",
        items=get_ramp_names,
        description="Selected color ramp"
    ) # type: ignore

    advanced_options: BoolProperty(
        name="Show advanced options",
        description="Show advanced export options like compression settings",
        default=False
    ) # type: ignore


class CameraItem(PropertyGroup):
    """Camera information for label management"""
    name: StringProperty(
        name="Camera Name",
        description="Name of the camera",
        default=""
    ) # type: ignore
    has_labels: BoolProperty(
        name="Has Labels",
        description="Whether this camera has labels generated",
        default=False
    ) # type: ignore
    label_count: IntProperty(
        name="Label Count",
        description="Number of labels for this camera",
        default=0
    ) # type: ignore


class LabelSettings(PropertyGroup):
    """Settings for label creation and appearance"""
    material_color: FloatVectorProperty(
        name="Label Color",
        subtype='COLOR',
        size=3,
        min=0.0,
        max=1.0,
        default=(1.0, 1.0, 1.0)
    ) # type: ignore
    
    emission_strength: FloatProperty(
        name="Emission Strength",
        description="Emission strength for label material",
        min=0.0,
        max=10.0,
        default=1.0
    ) # type: ignore
    
    label_distance: FloatProperty(
        name="Label Distance",
        description="Distance from camera to place labels. Changing this "
                    "value also repositions any existing generated labels "
                    "by re-matching them with their source camera/proxy by "
                    "object name (best-effort).",
        min=0.1,
        max=10.0,
        default=1.0,
        update=lambda self, ctx: _refresh_existing_labels(ctx),
    ) # type: ignore

    label_scale: FloatVectorProperty(
        name="Label Scale",
        description="Scale factor for labels. Changing this value also "
                    "rescales any existing generated labels.",
        size=3,
        min=0.001,
        max=1.0,
        default=(0.03, 0.03, 0.03),
        update=lambda self, ctx: _refresh_existing_labels(ctx),
    ) # type: ignore
    
    auto_move_cameras: BoolProperty(
        name="Auto Move Cameras to CAMS collection",
        description="Automatically move cameras to CAMS collection when creating labels",
        default=True
    ) # type: ignore
    
    show_label_tools: BoolProperty(
        name="Show Label Tools",
        description="Show/hide label management tools",
        default=False
    ) # type: ignore

    show_proxy_inflate_tools: BoolProperty(
        name="Show Proxy Inflate Tools",
        description="Show/hide proxy inflate management tools",
        default=False
    ) # type: ignore

    show_settings: BoolProperty(
        name="Show Settings",
        description="Show label creation settings",
        default=False
    ) # type: ignore


# =====================================================
# REGISTRATION FUNCTIONS
# =====================================================

def register_data():
    """
    Register Visual Manager data structures.
    
    REFACTORED: PropertyGroup classes are registered by em_props.py
    This function now ONLY handles Scene property attachment.
    """
    # ✅ SOLO Scene properties NON gestite da em_props
    # Setup collection properties and other scene properties if not yet existing
    if not hasattr(bpy.types.Scene, "property_values"):
        bpy.types.Scene.property_values = CollectionProperty(type=PropertyValueItem)
    
    if not hasattr(bpy.types.Scene, "active_value_index"):
        bpy.types.Scene.active_value_index = IntProperty()
    
    if not hasattr(bpy.types.Scene, "show_all_graphs"):
        bpy.types.Scene.show_all_graphs = BoolProperty(
            name="Show All Graphs",
            description="Show properties from all loaded graphs",
            default=False
        )
    
    if not hasattr(bpy.types.Scene, "color_ramp_props"):
        bpy.types.Scene.color_ramp_props = PointerProperty(type=ColorRampProperties)
    
    # Camera and label management - RENAMED PROPERTIES to avoid conflicts
    if not hasattr(bpy.types.Scene, "camera_em_list"):
        bpy.types.Scene.camera_em_list = CollectionProperty(type=CameraItem)
        
    if not hasattr(bpy.types.Scene, "active_camera_em_index"):
        bpy.types.Scene.active_camera_em_index = IntProperty(
            name="Active Camera EM Index",
            default=0
        )
    
    if not hasattr(bpy.types.Scene, "label_settings"):
        bpy.types.Scene.label_settings = PointerProperty(type=LabelSettings)


def unregister_data():
    """
    Unregister Visual Manager data structures.
    
    REFACTORED: PropertyGroup classes are unregistered by em_props.py
    This function now ONLY handles Scene property removal.
    """
    # ✅ SOLO rimozione Scene properties
    props_to_remove = [
        "property_values",
        "active_value_index", 
        "show_all_graphs",
        "color_ramp_props",
        "camera_em_list",
        "active_camera_em_index",
        "label_settings"
    ]
    
    for prop_name in props_to_remove:
        if hasattr(bpy.types.Scene, prop_name):
            delattr(bpy.types.Scene, prop_name)
    
    # ❌ PropertyGroup unregistration rimosso (gestito da em_props.py)
