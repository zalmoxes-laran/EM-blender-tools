"""
UI components for the Visual Manager - UPDATED FOR RENAMED PROPERTIES
This module contains all UI classes for the Visual Manager, including
panels and list UI elements using the new renamed properties.
"""

import bpy
from bpy.types import Panel, UIList, Menu

from .color_ramps import COLOR_RAMPS
from ..functions import get_compatible_icon


class VISUAL_UL_property_values(UIList):
    """UIList for displaying property values with color controls"""
    
    # Dizionario di classe per tenere traccia degli item disegnati
    _drawn_items = {}
    _last_property = None
    
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        # Reimposta il dizionario se la proprietà è cambiata
        current_property = context.scene.selected_property
        if current_property != self._last_property:
            self._drawn_items.clear()
            self._last_property = current_property
        
        # Crea una chiave unica per questo item
        item_key = f"{current_property}:{index}:{item.value}"
        
        # Disegna l'interfaccia normalmente
        row = layout.row(align=True)
        row.prop(item, "value", text="")
        row.prop(item, "color", text="")
        op = row.operator("visual.select_proxies", text="", icon='RESTRICT_SELECT_OFF')
        op.value = item.value


class VISUAL_UL_camera_em_list(UIList):
    """UIList for displaying cameras with label management - RENAMED VERSION"""
    
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        camera_icon = 'CAMERA_DATA'
        
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            # Camera name
            layout.label(text=item.name, icon=camera_icon)
            
            # Label count info
            row = layout.row()
            if item.has_labels:
                row.label(text=f"{item.label_count} labels", icon='CHECKMARK')
            else:
                row.label(text="No labels", icon='X')
            
            # Quick actions
            row = layout.row(align=True)
            
            # Set as active camera
            try:
                op = row.operator("visual.set_active_camera", text="", icon='CAMERA_DATA', emboss=False)
                if op:
                    op.camera_name = item.name
                else:
                    # Fallback: simple label if operator fails
                    row.label(text="", icon='CAMERA_DATA')
            except:
                # If operator doesn't exist, show simple label
                row.label(text="", icon='CAMERA_DATA')
            
            # Delete labels
            if item.has_labels:
                try:
                    op = row.operator("visual.delete_camera_labels", text="", icon='TRASH', emboss=False)
                    if op:
                        op.camera_name = item.name
                    else:
                        row.label(text="", icon='TRASH')
                except:
                    # If operator not available, show disabled icon
                    row.label(text="", icon='TRASH')
            
            # Move to CAMS
            try:
                op = row.operator("visual.move_camera_to_cams", text="", icon='COLLECTION_NEW', emboss=False)
                if op:
                    op.camera_name = item.name
                else:
                    row.label(text="", icon='COLLECTION_NEW')
            except:
                # If operator not available, show disabled icon
                row.label(text="", icon='COLLECTION_NEW')

        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.label(text=item.name, icon=camera_icon)


class VISUAL_MT_display_mode_menu(Menu):
    """Menu for display mode selection"""
    bl_label = "Display Mode Menu"
    bl_idname = "VISUAL_MT_display_mode_menu"

    def draw(self, context):
        layout = self.layout

        if context.scene.em_tools.mode_switch:
            layout.operator("emset.emmaterial", text="EM")
            layout.operator("emset.epochmaterial", text="Epochs")

        layout.operator("visual.set_property_materials", text="Properties")


class VISUAL_PT_base_panel:
    """Base panel for Visual Manager"""
    bl_label = "Visual manager"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        current_proxy_display_mode = context.scene.proxy_display_mode
        layout.alignment = 'LEFT'

        # Display Mode Selection
        row = layout.row(align=True)
        split = row.split()
        col = split.column()
        col.label(text="Display mode")
        col = split.column(align=True)
        
        col.menu(VISUAL_MT_display_mode_menu.bl_idname, text=current_proxy_display_mode, icon='COLOR')
    
        # Property-specific UI when in Properties mode
        if current_proxy_display_mode == "Properties":
            self.draw_property_manager(layout, context)
        
        # Display Controls
        self.draw_display_controls(layout, context)
        
        # Label Tools (collapsible section)
        self.draw_label_tools(layout, context)

    def draw_property_manager(self, layout, context):
        """Draw property management UI"""
        scene = context.scene
        box = layout.box()
        
        if scene.em_tools.mode_switch:
            row = box.row()
            row.prop(scene, "show_all_graphs", text="Show All Graphs")
        
        row = box.row()
        row.prop(scene, "property_enum", text="Select Property")

        if scene.selected_property:
            row = box.row()
            row.template_list("VISUAL_UL_property_values", "", 
                            scene, "property_values",
                            scene, "active_value_index")

            # Color scheme management
            row = box.row(align=True)
            row.operator("visual.save_color_scheme", text="Save Schema", icon='FILE_TICK')
            row.operator("visual.load_color_scheme", text="Load Schema", icon='FILE_FOLDER')

            # Color Ramp section
            row = box.row()
            row.prop(scene.color_ramp_props, "advanced_options", 
                    text="Color Ramp", 
                    icon='TRIA_DOWN' if scene.color_ramp_props.advanced_options else 'TRIA_RIGHT',
                    emboss=False)

            if scene.color_ramp_props.advanced_options:
                preview = box.box()
                preview.prop(scene.color_ramp_props, "ramp_type")
                preview.prop(scene.color_ramp_props, "ramp_name")
                
                # Preview della color ramp
                if (scene.color_ramp_props.ramp_type in COLOR_RAMPS and 
                    scene.color_ramp_props.ramp_name in COLOR_RAMPS[scene.color_ramp_props.ramp_type]):
                    
                    ramp_info = COLOR_RAMPS[scene.color_ramp_props.ramp_type][scene.color_ramp_props.ramp_name]
                    preview.label(text=f"Selected: {ramp_info['name']}")
                    preview.label(text=ramp_info['description'])
                
                    preview.operator("visual.apply_color_ramp", text="Apply Color Ramp")

            if scene.selected_property and len(scene.property_values) > 0:
                row = box.row()
                row.operator("visual.apply_colors", text="Apply Colors to Proxies", icon='COLOR')

    def draw_display_controls(self, layout, context):
        """Draw display control buttons"""
        scene = context.scene
        
        row = layout.row()
        row.prop(scene, "proxy_display_alpha")

        # Shading mode buttons
        op = row.operator("epoch_manager.change_selected_objects", text="", emboss=False, icon='SHADING_BBOX')
        op.sg_objects_changer = 'BOUND_SHADE'

        op = row.operator("epoch_manager.change_selected_objects", text="", emboss=False, icon='SHADING_WIRE')
        op.sg_objects_changer = 'WIRE_SHADE'

        op = row.operator("epoch_manager.change_selected_objects", text="", emboss=False, icon='SHADING_SOLID')
        op.sg_objects_changer = 'MATERIAL_SHADE'

        op = row.operator("epoch_manager.change_selected_objects", text="", emboss=False, icon='SPHERE')
        op.sg_objects_changer = 'SHOW_WIRE'

        row = layout.row()
        row.operator("notinthematrix.material", icon="MOD_MASK", text='')

    def draw_label_tools(self, layout, context):
        """Draw label and camera management tools - UPDATED FOR RENAMED PROPERTIES"""
        scene = context.scene
        label_settings = scene.label_settings
        
        # Collapsible section for label tools
        box = layout.box()
        row = box.row()
        row.prop(label_settings, "show_label_tools", 
                text="Label Tools", 
                icon='TRIA_DOWN' if label_settings.show_label_tools else 'TRIA_RIGHT',
                emboss=False)

        if label_settings.show_label_tools:
            # Label creation section
            col = box.column(align=True)
            
            # Check if there's an active camera
            has_active_camera = scene.camera is not None
            
            # Label creation button - disabled if no active camera
            row = col.row(align=True)
            row.enabled = has_active_camera
            row.operator("visual.label_creation", text="Create Labels for Selected", icon='SYNTAX_OFF')
            
            if not has_active_camera:
                col.label(text="No active camera", icon='ERROR')
            else:
                # Show active camera info
                info_row = col.row()
                info_row.label(text=f"Active: {scene.camera.name}", icon='CAMERA_DATA')
            
            # Object manipulation tools
            row = col.row(align=True)
            row.label(text="Object Tools:")
            
            op = row.operator("visual.center_mass", text="", emboss=False, icon='CURSOR')
            op.center_to = "cursor"

            op = row.operator("visual.center_mass", text="", emboss=False, icon='SNAP_FACE_CENTER')
            op.center_to = "mass"
            
            # Label appearance settings
            settings_box = box.box()
            settings_box.label(text="Label Appearance:")
            
            # Settings controls with real-time update button
            row = settings_box.row()
            row.prop(label_settings, "material_color", text="Color")
            
            row = settings_box.row()
            row.prop(label_settings, "emission_strength", text="Emission")
            
            row = settings_box.row()
            row.prop(label_settings, "label_distance", text="Distance")
            
            # Update existing labels button
            row = settings_box.row()
            row.operator("visual.update_label_settings", 
                        text="Update Existing Labels", 
                        icon='FILE_REFRESH')
            
            # Label behavior settings
            row = settings_box.row()
            row.prop(label_settings, "auto_move_cameras", text="Auto move cameras to CAMS")
            
            # Camera management - UPDATED TO USE RENAMED PROPERTIES
            camera_box = box.box()
            camera_box.label(text="Camera Management:")
            
            # Update camera list button
            row = camera_box.row()
            row.operator("visual.update_camera_list", text="Refresh Camera List", icon='FILE_REFRESH')
            
            # Camera list - UPDATED PROPERTY NAMES
            if len(scene.camera_em_list) > 0:
                row = camera_box.row()
                row.template_list("VISUAL_UL_camera_em_list", "", 
                                scene, "camera_em_list",
                                scene, "active_camera_em_index")
            else:
                camera_box.label(text="No cameras in CAMS collection")
                
                # Helper text if no cameras in CAMS
                if has_active_camera:
                    help_row = camera_box.row()
                    help_row.label(text=f"Move '{scene.camera.name}' to CAMS:", icon='INFO')
                    try:
                        move_op = help_row.operator("visual.move_camera_to_cams", 
                                        text="Move", 
                                        icon='COLLECTION_NEW')
                        if move_op:
                            move_op.camera_name = scene.camera.name
                    except:
                        # If operator doesn't exist, show simple label
                        help_row.label(text="(Move operator not available)")


class VIEW3D_PT_visual_panel(Panel, VISUAL_PT_base_panel):
    """Panel in the 3D View for the Visual Manager"""
    bl_category = "EM"
    bl_idname = "VIEW3D_PT_visual_panel"


def register_ui():
    """Register UI classes."""
    classes = [
        VISUAL_UL_property_values,
        VISUAL_UL_camera_em_list,  # RENAMED
        VISUAL_MT_display_mode_menu,
        VIEW3D_PT_visual_panel,
    ]
    
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except ValueError:
            # Class might already be registered
            pass


def unregister_ui():
    """Unregister UI classes."""
    classes = [
        VIEW3D_PT_visual_panel,
        VISUAL_MT_display_mode_menu,
        VISUAL_UL_camera_em_list,  # RENAMED
        VISUAL_UL_property_values,
    ]
    
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except ValueError:
            # Class might already be unregistered
            pass