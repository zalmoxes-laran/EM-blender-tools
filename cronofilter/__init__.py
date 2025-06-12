"""
CronoFilter Module - Custom Chronological Horizons Manager
========================================================

This module provides functionality to create, manage, and save custom chronological horizons
that can be exported in the Heriverse format as part of the context section.

Features:
- Create custom chronological horizons with label, start_time, end_time
- Save/load horizons as .cf.json files
- Integrate with Heriverse export context section
- User-friendly UI panel for horizon management
"""

import bpy
from bpy.types import PropertyGroup, Panel, Operator, UIList
from bpy.props import StringProperty, IntProperty, CollectionProperty, BoolProperty
import json
import os
from bpy_extras.io_utils import ImportHelper, ExportHelper

# ============================
# PROPERTY GROUPS
# ============================

class CF_ChronologicalHorizon(PropertyGroup):
    """Individual chronological horizon data"""
    label: StringProperty(
        name="Label",
        description="Name/label for this chronological horizon",
        default="New Horizon"
    )
    
    start_time: IntProperty(
        name="Start Time",
        description="Start time (years, negative for BC)",
        default=0
    )
    
    end_time: IntProperty(
        name="End Time", 
        description="End time (years, negative for BC)",
        default=100
    )
    
    color: bpy.props.FloatVectorProperty(
        name="Color",
        description="Color for this horizon",
        subtype='COLOR',
        default=(0.5, 0.5, 0.5),
        min=0.0,
        max=1.0,
        size=3
    )
    
    enabled: BoolProperty(
        name="Enabled",
        description="Include this horizon in exports",
        default=True
    )

class CF_CronoFilterSettings(PropertyGroup):
    """Main settings for CronoFilter"""
    horizons: CollectionProperty(
        type=CF_ChronologicalHorizon,
        name="Chronological Horizons"
    )
    
    active_horizon_index: IntProperty(
        name="Active Horizon Index",
        default=0
    )
    
    expanded: BoolProperty(
        name="Panel Expanded",
        description="Show/hide CronoFilter panel",
        default=False
    )

# ============================
# UI LIST
# ============================

class CF_UL_HorizonList(UIList):
    """UI List for displaying chronological horizons"""
    
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        horizon = item
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)
            
            # Enabled checkbox
            row.prop(horizon, "enabled", text="")
            
            # Color indicator
            color_row = row.row()
            color_row.scale_x = 0.8
            color_row.prop(horizon, "color", text="")
            
            # Label
            label_row = row.row()
            label_row.prop(horizon, "label", text="", emboss=False)
            
            # Time range
            time_row = row.row()
            time_row.alignment = 'RIGHT'
            time_row.label(text=f"{horizon.start_time} - {horizon.end_time}")
            
        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.label(text=horizon.label)

# ============================
# OPERATORS
# ============================

class CF_OT_AddHorizon(Operator):
    """Add a new chronological horizon"""
    bl_idname = "cronofilter.add_horizon"
    bl_label = "Add Horizon"
    bl_description = "Add a new chronological horizon"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        cf_settings = context.scene.cf_settings
        new_horizon = cf_settings.horizons.add()
        new_horizon.label = f"Horizon_{len(cf_settings.horizons)}"
        cf_settings.active_horizon_index = len(cf_settings.horizons) - 1
        return {'FINISHED'}

class CF_OT_RemoveHorizon(Operator):
    """Remove the active chronological horizon"""
    bl_idname = "cronofilter.remove_horizon"
    bl_label = "Remove Horizon"
    bl_description = "Remove the selected chronological horizon"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        cf_settings = context.scene.cf_settings
        if cf_settings.horizons and cf_settings.active_horizon_index >= 0:
            cf_settings.horizons.remove(cf_settings.active_horizon_index)
            cf_settings.active_horizon_index = max(0, cf_settings.active_horizon_index - 1)
        return {'FINISHED'}

class CF_OT_MoveHorizon(Operator):
    """Move horizon up or down in the list"""
    bl_idname = "cronofilter.move_horizon"
    bl_label = "Move Horizon"
    bl_description = "Move the selected horizon up or down"
    bl_options = {'REGISTER', 'UNDO'}
    
    direction: StringProperty(default="UP")
    
    def execute(self, context):
        cf_settings = context.scene.cf_settings
        current_index = cf_settings.active_horizon_index
        
        if self.direction == "UP" and current_index > 0:
            cf_settings.horizons.move(current_index, current_index - 1)
            cf_settings.active_horizon_index = current_index - 1
        elif self.direction == "DOWN" and current_index < len(cf_settings.horizons) - 1:
            cf_settings.horizons.move(current_index, current_index + 1)
            cf_settings.active_horizon_index = current_index + 1
            
        return {'FINISHED'}

class CF_OT_SaveHorizons(Operator, ExportHelper):
    """Save chronological horizons to .cf.json file"""
    bl_idname = "cronofilter.save_horizons"
    bl_label = "Save Horizons"
    bl_description = "Save chronological horizons to a .cf.json file"
    bl_options = {'REGISTER', 'UNDO'}
    
    filename_ext = ".cf.json"
    filter_glob: StringProperty(default="*.cf.json", options={'HIDDEN'})
    
    def execute(self, context):
        try:
            cf_settings = context.scene.cf_settings
            
            # Helper function to convert color to hex
            def color_to_hex(color_vector):
                r, g, b = color_vector
                return "#{:02x}{:02x}{:02x}".format(
                    int(r * 255), int(g * 255), int(b * 255)
                )
            
            # Prepare data for export
            export_data = {
                "version": "1.0",
                "type": "cronofilter_horizons",
                "horizons": {}
            }
            
            for i, horizon in enumerate(cf_settings.horizons):
                horizon_id = f"custom_horizon_{i}"
                export_data["horizons"][horizon_id] = {
                    "name": horizon.label,
                    "start": horizon.start_time,
                    "end": horizon.end_time,
                    "color": color_to_hex(horizon.color),
                    "enabled": horizon.enabled
                }
            
            # Save to file
            with open(self.filepath, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=4, ensure_ascii=False)
            
            self.report({'INFO'}, f"Horizons saved to {self.filepath}")
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Failed to save horizons: {str(e)}")
            return {'CANCELLED'}

class CF_OT_LoadHorizons(Operator, ImportHelper):
    """Load chronological horizons from .cf.json file"""
    bl_idname = "cronofilter.load_horizons"
    bl_label = "Load Horizons"
    bl_description = "Load chronological horizons from a .cf.json file"
    bl_options = {'REGISTER', 'UNDO'}
    
    filename_ext = ".cf.json"
    filter_glob: StringProperty(default="*.cf.json", options={'HIDDEN'})
    
    def execute(self, context):
        try:
            cf_settings = context.scene.cf_settings
            
            # Helper function to convert hex to color
            def hex_to_color(hex_string):
                hex_string = hex_string.lstrip('#')
                if len(hex_string) != 6:
                    return (0.5, 0.5, 0.5)  # Default gray
                try:
                    r = int(hex_string[0:2], 16) / 255.0
                    g = int(hex_string[2:4], 16) / 255.0  
                    b = int(hex_string[4:6], 16) / 255.0
                    return (r, g, b)
                except ValueError:
                    return (0.5, 0.5, 0.5)  # Default gray on error
            
            # Load from file
            with open(self.filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Validate file format
            if data.get("type") != "cronofilter_horizons":
                self.report({'ERROR'}, "Invalid file format - not a CronoFilter horizons file")
                return {'CANCELLED'}
            
            # Clear existing horizons
            cf_settings.horizons.clear()
            
            # Load horizons
            horizons_data = data.get("horizons", {})
            for horizon_id, horizon_data in horizons_data.items():
                new_horizon = cf_settings.horizons.add()
                new_horizon.label = horizon_data.get("name", "Unnamed")
                new_horizon.start_time = horizon_data.get("start", 0)
                new_horizon.end_time = horizon_data.get("end", 100)
                new_horizon.color = hex_to_color(horizon_data.get("color", "#808080"))
                new_horizon.enabled = horizon_data.get("enabled", True)
            
            cf_settings.active_horizon_index = 0
            self.report({'INFO'}, f"Loaded {len(cf_settings.horizons)} horizons from {self.filepath}")
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Failed to load horizons: {str(e)}")
            return {'CANCELLED'}

# ============================
# PANELS
# ============================

class CF_PT_CronoFilterPanel(Panel):
    """Main CronoFilter panel"""
    bl_label = "CronoFilter"
    bl_idname = "CF_PT_cronofilter"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "EM"
    bl_options = {'DEFAULT_CLOSED'}
    
    def draw_header(self, context):
        layout = self.layout
        cf_settings = context.scene.cf_settings
        layout.prop(cf_settings, "expanded", 
                   icon='TRIA_DOWN' if cf_settings.expanded else 'TRIA_RIGHT',
                   text="", emboss=False)
    
    def draw(self, context):
        layout = self.layout
        cf_settings = context.scene.cf_settings
        
        if not cf_settings.expanded:
            return
        
        # Header info
        box = layout.box()
        row = box.row()
        row.label(text="Custom Chronological Horizons", icon='TIME')
        
        # File operations
        file_box = layout.box()
        row = file_box.row()
        row.label(text="File Operations:")
        row = file_box.row()
        row.operator("cronofilter.save_horizons", text="Save Horizons", icon='FILE_TICK')
        row.operator("cronofilter.load_horizons", text="Load Horizons", icon='FILE_FOLDER')
        
        # Horizons list
        list_box = layout.box()
        row = list_box.row()
        row.label(text=f"Horizons ({len(cf_settings.horizons)}):")
        
        # List controls
        row = list_box.row()
        col = row.column()
        col.template_list("CF_UL_HorizonList", "horizons_list",
                         cf_settings, "horizons",
                         cf_settings, "active_horizon_index",
                         rows=4)
        
        # List buttons
        col = row.column(align=True)
        col.operator("cronofilter.add_horizon", text="", icon='ADD')
        col.operator("cronofilter.remove_horizon", text="", icon='REMOVE')
        col.separator()
        op = col.operator("cronofilter.move_horizon", text="", icon='TRIA_UP')
        op.direction = "UP"
        op = col.operator("cronofilter.move_horizon", text="", icon='TRIA_DOWN')
        op.direction = "DOWN"
        
        # Edit active horizon
        if cf_settings.horizons and cf_settings.active_horizon_index < len(cf_settings.horizons):
            active_horizon = cf_settings.horizons[cf_settings.active_horizon_index]
            
            edit_box = layout.box()
            row = edit_box.row()
            row.label(text="Edit Selected Horizon:", icon='GREASEPENCIL')
            
            row = edit_box.row()
            row.prop(active_horizon, "label")
            
            row = edit_box.row()
            col = row.column()
            col.prop(active_horizon, "start_time")
            col = row.column()
            col.prop(active_horizon, "end_time")
            
            row = edit_box.row()
            row.prop(active_horizon, "color")
            row.prop(active_horizon, "enabled")
        
        # Status
        status_box = layout.box()
        enabled_count = sum(1 for h in cf_settings.horizons if h.enabled)
        row = status_box.row()
        row.label(text=f"Status: {enabled_count}/{len(cf_settings.horizons)} horizons enabled")
        
        if enabled_count > 0:
            row = status_box.row()
            row.label(text="✅ Horizons will be included in Heriverse export", icon='INFO')

# ============================
# REGISTRATION
# ============================

classes = [
    CF_ChronologicalHorizon,
    CF_CronoFilterSettings,
    CF_UL_HorizonList,
    CF_OT_AddHorizon,
    CF_OT_RemoveHorizon,
    CF_OT_MoveHorizon,
    CF_OT_SaveHorizons,
    CF_OT_LoadHorizons,
    CF_PT_CronoFilterPanel,
]

def register():
    """Register all classes and properties"""
    for cls in classes:
        bpy.utils.register_class(cls)
    
    # Add properties to Scene
    bpy.types.Scene.cf_settings = bpy.props.PointerProperty(type=CF_CronoFilterSettings)

def unregister():
    """Unregister all classes and properties"""
    # Remove properties from Scene
    if hasattr(bpy.types.Scene, 'cf_settings'):
        delattr(bpy.types.Scene, 'cf_settings')
    
    # Unregister classes in reverse order
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()