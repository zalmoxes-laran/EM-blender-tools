"""
Data structures for the Visual Manager 
This module contains all PropertyGroup definitions and data structures
needed for the Visual Manager with renamed properties to avoid conflicts.
"""

import bpy
from bpy.props import (
    StringProperty,
    BoolProperty,
    FloatProperty,
    IntProperty,
    CollectionProperty,
    PointerProperty,
    FloatVectorProperty,
    EnumProperty
)
from bpy.types import PropertyGroup

class PropertyValueItem(PropertyGroup):
    """Property value item for color mapping"""
    value: StringProperty(name="Value")
    color: FloatVectorProperty(
        name="Color",
        subtype='COLOR',
        size=4,
        min=0.0,
        max=1.0,
        default=(0.5, 0.5, 0.5, 1.0)
    )

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
    )
    
    ramp_name: EnumProperty(
        name="Color Ramp",
        items=get_ramp_names,
        description="Selected color ramp"
    )

    advanced_options: BoolProperty(
        name="Show advanced options",
        description="Show advanced export options like compression settings",
        default=False
    )

class CameraItem(PropertyGroup):
    """Camera information for label management"""
    name: StringProperty(
        name="Camera Name",
        description="Name of the camera",
        default=""
    )
    has_labels: BoolProperty(
        name="Has Labels",
        description="Whether this camera has labels generated",
        default=False
    )
    label_count: IntProperty(
        name="Label Count",
        description="Number of labels for this camera",
        default=0
    )

class LabelSettings(PropertyGroup):
    """Settings for label creation and appearance"""
    material_color: FloatVectorProperty(
        name="Label Color",
        subtype='COLOR',
        size=3,
        min=0.0,
        max=1.0,
        default=(1.0, 1.0, 1.0)
    )
    
    emission_strength: FloatProperty(
        name="Emission Strength",
        description="Emission strength for label material",
        min=0.0,
        max=10.0,
        default=1.0
    )
    
    label_distance: FloatProperty(
        name="Label Distance",
        description="Distance from camera to place labels",
        min=0.1,
        max=10.0,
        default=1.0
    )
    
    label_scale: FloatVectorProperty(
        name="Label Scale",
        description="Scale factor for labels",
        size=3,
        min=0.001,
        max=1.0,
        default=(0.03, 0.03, 0.03)
    )
    
    auto_move_cameras: BoolProperty(
        name="Auto Move Cameras to CAMS",
        description="Automatically move cameras to CAMS collection when creating labels",
        default=True
    )
    
    show_label_tools: BoolProperty(
        name="Show Label Tools",
        description="Show/hide label management tools",
        default=False
    )

def register_data():
    """Register all data classes."""
    classes = [
        PropertyValueItem,
        ColorRampProperties,
        CameraItem,
        LabelSettings,
    ]
    
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except ValueError:
            # Class might already be registered
            pass
            
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
    """Unregister all data classes."""
    # Remove collection properties - UPDATED NAMES
    props_to_remove = [
        "property_values",
        "active_value_index", 
        "show_all_graphs",
        "color_ramp_props",
        "camera_em_list",  # RENAMED
        "active_camera_em_index",  # RENAMED
        "label_settings"
    ]
    
    for prop_name in props_to_remove:
        if hasattr(bpy.types.Scene, prop_name):
            delattr(bpy.types.Scene, prop_name)
    
    # Unregister classes in reverse order
    classes = [
        LabelSettings,
        CameraItem,
        ColorRampProperties,
        PropertyValueItem,
    ]
    
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except ValueError:
            # Class might already be unregistered
            pass