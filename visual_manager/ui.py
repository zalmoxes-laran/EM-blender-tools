"""
UI components for the Visual Manager - CLEAN VERSION
This module contains all UI classes for the Visual Manager, focusing on
core functionality: property management, color schemes, and label tools.
No references to the old visualization_modules system.
"""

import bpy
from bpy.types import Panel, UIList, Menu

from .color_ramps import COLOR_RAMPS


class VISUAL_UL_property_values(UIList):
    """UIList for displaying property values with color controls"""
    
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.prop(item, "value", text="")
        row.prop(item, "color", text="")
        op = row.operator("visual.select_proxies", text="", icon='RESTRICT_SELECT_OFF')
        op.value = item.value


class VISUAL_UL_camera_list(UIList):
    """UIList for displaying cameras with label management"""
    
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
                op = row.operator("visual.set_active_camera_safe", text="", icon='CAMERA_DATA', emboss=False)
                op.camera_name = item.name
            except:
                row.label(text="", icon='CAMERA_DATA')
            
            # Delete labels
            if item.has_labels:
                try:
                    op = row.operator("visual.delete_camera_labels_safe", text="", icon='TRASH', emboss=False)
                    op.camera_name = item.name
                except:
                    row.label(text="", icon='TRASH')
            
            # Move to CAMS
            try:
                op = row.operator("visual.move_camera_to_cams_safe", text="", icon='COLLECTION_NEW', emboss=False)
                op.camera_name = item.name
            except:
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


class VIEW3D_PT_visual_panel(Panel):
    """Main panel for Visual Manager in 3D View"""
    bl_label = "Visual Manager"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "EM"
    bl_idname = "VIEW3D_PT_visual_panel"

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
        
        # RM Coloring (only in advanced mode, RM sync active, AND experimental features)
        if (hasattr(scene, 'em_tools') and scene.em_tools.mode_switch and 
            getattr(scene, 'sync_rm_visibility', False) and
            hasattr(scene.em_tools, 'experimental_features') and scene.em_tools.experimental_features):
            self.draw_rm_coloring(layout, context)

    def draw_property_manager(self, layout, context):
        """Draw property management UI"""
        scene = context.scene
        box = layout.box()
        
        if hasattr(scene, 'em_tools') and scene.em_tools.mode_switch:
            row = box.row()
            row.prop(scene, "show_all_graphs", text="Show All Graphs")
        
        row = box.row()
        if hasattr(scene, 'property_enum'):
            row.prop(scene, "property_enum", text="Select Property")

        if hasattr(scene, 'selected_property') and scene.selected_property:
            row = box.row()
            row.template_list("VISUAL_UL_property_values", "", 
                            scene, "property_values",
                            scene, "active_value_index")

            # Color scheme management
            row = box.row(align=True)
            row.operator("visual.save_color_scheme", text="Save Schema", icon='FILE_TICK')
            row.operator("visual.load_color_scheme", text="Load Schema", icon='FILE_FOLDER')

            # Color Ramp section
            if hasattr(scene, 'color_ramp_props'):
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

        # Shading mode buttons - with safety checks
        try:
            op = row.operator("epoch_manager.change_selected_objects", text="", emboss=False, icon='SHADING_BBOX')
            op.sg_objects_changer = 'BOUND_SHADE'
        except:
            row.label(text="", icon='SHADING_BBOX')

        try:
            op = row.operator("epoch_manager.change_selected_objects", text="", emboss=False, icon='SHADING_WIRE')
            op.sg_objects_changer = 'WIRE_SHADE'
        except:
            row.label(text="", icon='SHADING_WIRE')

        try:
            op = row.operator("epoch_manager.change_selected_objects", text="", emboss=False, icon='SHADING_SOLID')
            op.sg_objects_changer = 'MATERIAL_SHADE'
        except:
            row.label(text="", icon='SHADING_SOLID')

        try:
            op = row.operator("epoch_manager.change_selected_objects", text="", emboss=False, icon='SPHERE')
            op.sg_objects_changer = 'SHOW_WIRE'
        except:
            row.label(text="", icon='SPHERE')

        row = layout.row()
        try:
            row.operator("notinthematrix.material", icon="MOD_MASK", text='')
        except:
            row.label(text="Material", icon="MOD_MASK")

    def draw_rm_coloring(self, layout, context):
        """Draw RM coloring controls (renamed from proxy projection)"""
        scene = context.scene
        
        # Check if RM coloring system is available
        if not hasattr(scene, 'proxy_projection_settings'):
            return
        
        settings = scene.proxy_projection_settings
        
        # Collapsible section for RM coloring
        box = layout.box()
        row = box.row()
        
        row.prop(settings, "show_advanced_settings", 
                text="RM Coloring", 
                icon='TRIA_DOWN' if settings.show_advanced_settings else 'TRIA_RIGHT',
                emboss=False)
        
        # Show status indicator in header
        if settings.projection_active:
            row.label(text="", icon='CHECKMARK')
        else:
            row.label(text="", icon='RADIOBUT_OFF')

        if settings.show_advanced_settings:
            # Check prerequisites
            prereqs_ok = self.check_projection_prerequisites(scene)
            
            # Main controls
            col = box.column()
            
            if settings.projection_active:
                # Active coloring controls
                row = col.row(align=True)
                row.operator("proxy_projection.clear", text="Clear Coloring", icon='X')
                row.operator("proxy_projection.update", text="Update", icon='FILE_REFRESH')
                row.operator("proxy_projection.toggle", text="Toggle", icon='LOOP_BACK')
                
                # Settings when active
                col.separator()
                col.prop(settings, "auto_update_enabled", text="Auto Update")
                col.prop(settings, "blend_strength", text="Blend Strength", slider=True)
                
            else:
                # Apply button
                row = col.row()
                row.scale_y = 1.2
                op = row.operator("proxy_projection.apply", text="Apply RM Coloring", icon='PLAY')
                row.enabled = prereqs_ok
                
                if not prereqs_ok:
                    # Show prerequisites warning
                    warning_box = col.box()
                    warning_box.alert = True
                    warning_col = warning_box.column()
                    warning_col.label(text="Prerequisites not met:", icon='ERROR')
                    
                    # Check specific issues
                    if not getattr(scene, 'sync_rm_visibility', False):
                        warning_col.label(text="• RM temporal sync not active")
                    
                    if scene.epoch_list_index < 0 or scene.epoch_list_index >= len(scene.epoch_list):
                        warning_col.label(text="• No active epoch selected")
                    
                    if not hasattr(scene, 'em_list') or len(scene.em_list) == 0:
                        warning_col.label(text="• No proxy objects in list")
                    
                    if not hasattr(scene, 'rm_list') or len(scene.rm_list) == 0:
                        warning_col.label(text="• No RM objects available")
            
            # Additional settings
            col.separator()
            col.prop(settings, "projection_method", text="Method")
            col.prop(settings, "hide_non_intersected", text="Hide Non-Intersected Areas")
            
            # Debug button (always available in experimental mode)
            col.separator()
            col.operator("proxy_projection.diagnose", text="Run Diagnosis", icon='ZOOM_ALL')

    def check_projection_prerequisites(self, scene):
        """Check if projection prerequisites are met"""
        # Check RM sync
        if not getattr(scene, 'sync_rm_visibility', False):
            return False
        
        # Check active epoch
        if scene.epoch_list_index < 0 or scene.epoch_list_index >= len(scene.epoch_list):
            return False
        
        # Check for proxy objects
        if not hasattr(scene, 'em_list') or len(scene.em_list) == 0:
            return False
        
        # Check for RM objects
        if not hasattr(scene, 'rm_list') or len(scene.rm_list) == 0:
            return False
        
        return True

    def draw_label_tools(self, layout, context):
        """Draw label and camera management tools"""
        scene = context.scene
        
        if not hasattr(scene, 'label_settings'):
            return
            
        label_settings = scene.label_settings
        
        # Collapsible section for label tools
        box = layout.box()
        row = box.row()
        
        # When expanding, auto-update camera list
        was_collapsed = not label_settings.show_label_tools
        
        row.prop(label_settings, "show_label_tools", 
                text="Label Tools", 
                icon='TRIA_DOWN' if label_settings.show_label_tools else 'TRIA_RIGHT',
                emboss=False)

        if label_settings.show_label_tools:
            # Auto-update camera list when section is opened for the first time
            if was_collapsed:
                try:
                    bpy.ops.visual.update_camera_list_safe()
                except:
                    print("Could not auto-update camera list")
            
            # Label creation section
            col = box.column(align=True)
            
            # Check if there's an active camera
            has_active_camera = scene.camera is not None
            
            # Label creation button - disabled if no active camera
            row = col.row(align=True)
            row.enabled = has_active_camera
            try:
                row.operator("visual.label_creation_safe", text="Create Labels for Selected", icon='SYNTAX_OFF')
            except:
                row.label(text="Create Labels for Selected", icon='SYNTAX_OFF')
            
            if not has_active_camera:
                col.label(text="No active camera", icon='ERROR')
            else:
                # Show active camera info
                info_row = col.row()
                info_row.label(text=f"Active: {scene.camera.name}", icon='CAMERA_DATA')
            
            # Camera management
            camera_box = box.box()
            camera_box.label(text="Camera Management:")
            
            # Update camera list button
            row = camera_box.row()
            try:
                row.operator("visual.update_camera_list_safe", text="Refresh Camera List", icon='FILE_REFRESH')
            except:
                row.label(text="Refresh Camera List", icon='FILE_REFRESH')
            
            # Debug info
            debug_row = camera_box.row()
            debug_row.scale_y = 0.8
            cams_collection = bpy.data.collections.get("CAMS")
            if cams_collection:
                cams_count = len([obj for obj in cams_collection.objects if obj.type == 'CAMERA'])
                debug_row.label(text=f"CAMS collection: {cams_count} cameras", icon='INFO')
            else:
                debug_row.label(text="CAMS collection: not found", icon='ERROR')
            
            # Camera list
            if hasattr(scene, 'camera_em_list') and len(scene.camera_em_list) > 0:
                row = camera_box.row()
                row.template_list("VISUAL_UL_camera_list", "", 
                                scene, "camera_em_list",
                                scene, "active_camera_em_index")
            else:
                warning_row = camera_box.row()
                warning_row.alert = True
                warning_row.label(text="No cameras found - click Refresh", icon='ERROR')

            # Label settings (collapsible)
            settings_box = box.box()
            row = settings_box.row()
            
            # Check if show_settings property exists, create it if not
            if not hasattr(label_settings, 'show_settings'):
                # Add the property to the existing LabelSettings class
                from ..visual_manager.data import LabelSettings
                if not hasattr(LabelSettings, 'show_settings'):
                    LabelSettings.show_settings = bpy.props.BoolProperty(
                        name="Show Settings",
                        description="Show label creation settings", 
                        default=False
                    )
                    # Re-register to apply the new property
                    bpy.utils.unregister_class(LabelSettings)
                    bpy.utils.register_class(LabelSettings)
            
            show_settings = getattr(label_settings, 'show_settings', False)
            
            row.prop(label_settings, "show_settings", 
                    text="Label Settings", 
                    icon='TRIA_DOWN' if show_settings else 'TRIA_RIGHT',
                    emboss=False)
            
            if show_settings:
                col = settings_box.column()
                
                # Material settings
                col.label(text="Label Appearance:")
                col.prop(label_settings, "material_color", text="Color")
                col.prop(label_settings, "emission_strength", text="Emission")
                
                # Positioning settings
                col.separator()
                col.label(text="Label Positioning:")
                col.prop(label_settings, "label_distance", text="Distance")
                col.prop(label_settings, "label_scale", text="Scale")
                
                # Behavior settings
                col.separator()
                col.label(text="Behavior:")
                col.prop(label_settings, "auto_move_cameras", text="Auto Move Cameras to CAMS")


def register_ui():
    """Register UI classes."""
    classes = [
        VISUAL_UL_property_values,
        VISUAL_UL_camera_list,
        VISUAL_MT_display_mode_menu,
        VIEW3D_PT_visual_panel,
    ]
    
    # Unregister existing classes first (for reloading)
    for cls in classes:
        try:
            bpy.utils.unregister_class(cls)
        except:
            pass
    
    # Register classes
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
            print(f"Successfully registered: {cls.__name__}")
        except ValueError as e:
            print(f"Failed to register {cls.__name__}: {e}")


def unregister_ui():
    """Unregister UI classes."""
    classes = [
        VIEW3D_PT_visual_panel,
        VISUAL_MT_display_mode_menu,
        VISUAL_UL_camera_list,
        VISUAL_UL_property_values,
    ]
    
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except ValueError:
            pass