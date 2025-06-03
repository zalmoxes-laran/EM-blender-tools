"""
UI components for the Visual Manager - FIXED VERSION
This module contains all UI classes for the Visual Manager, including
panels, list UI elements, and visualization module controls.
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
                op = row.operator("visual.set_active_camera", text="", icon='CAMERA_DATA', emboss=False)
                op.camera_name = item.name
            except:
                row.label(text="", icon='CAMERA_DATA')
            
            # Delete labels
            if item.has_labels:
                try:
                    op = row.operator("visual.delete_camera_labels", text="", icon='TRASH', emboss=False)
                    op.camera_name = item.name
                except:
                    row.label(text="", icon='TRASH')
            
            # Move to CAMS
            try:
                op = row.operator("visual.move_camera_to_cams", text="", icon='COLLECTION_NEW', emboss=False)
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
        
        # Advanced Visualization Tools - ONLY if experimental features are enabled
        em_tools = scene.em_tools
        if em_tools.experimental_features:
            self.draw_visualization_modules(layout, context)

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

    def draw_visualization_modules(self, layout, context):
        """Draw advanced visualization tools"""
        scene = context.scene
        
        # Check if we should show advanced visualization
        show_advanced_viz = getattr(scene, 'show_advanced_visualization', False)
        
        # Main collapsible header
        main_box = layout.box()
        row = main_box.row()
        row.prop(scene, "show_advanced_visualization", 
                text="Advanced Visualization System", 
                icon='TRIA_DOWN' if show_advanced_viz else 'TRIA_RIGHT',
                emboss=False)
        
        # Only draw content if expanded
        if not show_advanced_viz:
            return
        # Content area (only shown when expanded)
        content_box = main_box.box()
        
        # Quick Actions Row
        quick_row = content_box.row(align=True)
        quick_row.scale_y = 1.2
        
        # Smart suggestions button
        try:
            quick_row.operator("visual.suggestions_popup", text="Smart Tips", icon='LIGHTPROBE_PLANE')
        except:
            quick_row.label(text="Smart Tips", icon='LIGHTPROBE_PLANE')
        
        # Preset menu
        try:
            quick_row.operator("visual.preset_menu", text="Presets", icon='PRESET')
        except:
            quick_row.label(text="Presets", icon='PRESET')
        
        # Global cleanup
        try:
            quick_row.operator("visual.clean_all_materials", text="Clean", icon='BRUSH_DATA')
        except:
            quick_row.label(text="Clean", icon='BRUSH_DATA')
        
        # Smart Presets Section
        preset_box = content_box.box()
        preset_box.label(text="Smart Presets:", icon='PRESET')
        
        # Quick preset buttons (top row)
        row = preset_box.row(align=True)
        try:
            row.operator("visual.smart_visualization_preset", text="Focus", icon='ZOOM_SELECTED').preset_type = 'FOCUS'
            row.operator("visual.smart_visualization_preset", text="Epoch", icon='TIME').preset_type = 'EPOCH'
            row.operator("visual.smart_visualization_preset", text="Property", icon='PROPERTIES').preset_type = 'PROPERTY'
        except:
            row.label(text="Focus", icon='ZOOM_SELECTED')
            row.label(text="Epoch", icon='TIME')
            row.label(text="Property", icon='PROPERTIES')
        
        # Second row of presets
        row = preset_box.row(align=True) 
        try:
            row.operator("visual.smart_visualization_preset", text="Present", icon='CAMERA_DATA').preset_type = 'PRESENTATION'
            row.operator("visual.smart_visualization_preset", text="Analyze", icon='VIEWZOOM').preset_type = 'ANALYSIS'
        except:
            row.label(text="Present", icon='CAMERA_DATA')
            row.label(text="Analyze", icon='VIEWZOOM')
        
        # System Status
        status_box = content_box.box()
        status_box.label(text="System Status:", icon='SETTINGS')
        
        try:
            from .visualization_modules import get_manager, is_visualization_active, get_system_status
            
            system_status = get_system_status()
            
            if system_status['manager_active']:
                if is_visualization_active():
                    active_modules = system_status['active_modules']
                    status_row = status_box.row()
                    status_row.alert = True
                    status_row.label(text=f"Active: {', '.join(active_modules)}", icon='CHECKMARK')
                    
                    # Control buttons for active system
                    row = status_box.row(align=True)
                    row.operator("visual.unified_update_all_visualizations", text="Update All", icon='FILE_REFRESH')
                    row.operator("visual.unified_clear_all_visualizations", text="Clear All", icon='X')
                else:
                    status_box.label(text="No active visualizations", icon='RADIOBUT_OFF')
            else:
                status_box.label(text="System not available", icon='ERROR')
                
        except Exception as e:
            status_box.label(text="Status unavailable", icon='QUESTION')
        
        # Individual Module Controls (Collapsible)
        self.draw_individual_module_controls(content_box, context)
    
    def draw_individual_module_controls(self, layout, context):
        """Draw individual module controls in collapsible sections"""
        scene = context.scene
        
        # Check if we should show individual controls
        show_individual = getattr(scene, 'show_individual_viz_controls', False)
        
        row = layout.row()
        row.prop(scene, "show_individual_viz_controls", 
                text="Individual Module Controls", 
                icon='TRIA_DOWN' if show_individual else 'TRIA_RIGHT',
                emboss=False)
        
        if not show_individual:
            return
        
        individual_box = layout.box()
        
        # Transparency Controls
        trans_box = individual_box.box()
        trans_box.label(text="Transparency Module:", icon='MOD_OPACITY')
        
        if hasattr(scene, 'transparency_settings'):
            settings = scene.transparency_settings
            
            row = trans_box.row()
            row.prop(settings, "transparency_mode", text="Mode")
            
            row = trans_box.row()
            row.prop(settings, "transparency_factor", text="Amount")
            
            row = trans_box.row(align=True)
            row.prop(settings, "affect_selected_only", text="Selected Only")
            row.prop(settings, "affect_visible_only", text="Visible Only")
            
            # Module control buttons
            row = trans_box.row(align=True)
            try:
                op = row.operator("visual.unified_apply_visualization", text="Apply", icon='CHECKMARK')
                op.module_id = 'transparency'
                op = row.operator("visual.unified_clear_visualization", text="Clear", icon='X')
                op.module_id = 'transparency'
            except:
                row.label(text="Apply", icon='CHECKMARK')
                row.label(text="Clear", icon='X')
        
        # Color Overlay Controls
        overlay_box = individual_box.box()
        overlay_box.label(text="Color Overlay Module:", icon='COLOR')
        
        if hasattr(scene, 'color_overlay_settings'):
            settings = scene.color_overlay_settings
            
            row = overlay_box.row()
            row.prop(settings, "overlay_mode", text="Source")
            
            if settings.overlay_mode == 'CUSTOM':
                row = overlay_box.row()
                row.prop(settings, "custom_overlay_color", text="Color")
            
            row = overlay_box.row()
            row.prop(settings, "overlay_strength", text="Strength")
            
            row = overlay_box.row()
            row.prop(settings, "blend_mode", text="Blend")
            
            # Module control buttons
            row = overlay_box.row(align=True)
            try:
                op = row.operator("visual.unified_apply_visualization", text="Apply", icon='CHECKMARK')
                op.module_id = 'color_overlay'
                op = row.operator("visual.unified_clear_visualization", text="Clear", icon='X')
                op.module_id = 'color_overlay'
            except:
                row.label(text="Apply", icon='CHECKMARK')
                row.label(text="Clear", icon='X')
        
        # Clipping Section Controls
        clip_box = individual_box.box()
        clip_box.label(text="Clipping Module:", icon='MOD_BOOLEAN')
        
        if hasattr(scene, 'clipping_settings'):
            settings = scene.clipping_settings
            
            row = clip_box.row()
            row.prop(settings, "clipping_mode", text="Type")
            
            row = clip_box.row()
            row.prop(settings, "section_color", text="Section Color")
            
            row = clip_box.row()
            row.prop(settings, "clipping_distance", text="Distance")
            
            # Module control buttons
            row = clip_box.row(align=True)
            try:
                op = row.operator("visual.unified_apply_visualization", text="Apply Effect", icon='CHECKMARK')
                op.module_id = 'clipping'
                op = row.operator("visual.unified_clear_visualization", text="Clear Effect", icon='X')
                op.module_id = 'clipping'
            except:
                row.label(text="Apply Effect", icon='CHECKMARK')
                row.label(text="Clear Effect", icon='X')

    def draw_label_tools(self, layout, context):
        """Draw label and camera management tools"""
        scene = context.scene
        
        if not hasattr(scene, 'label_settings'):
            return
            
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
            try:
                row.operator("visual.label_creation", text="Create Labels for Selected", icon='SYNTAX_OFF')
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
                row.operator("visual.update_camera_list", text="Refresh Camera List", icon='FILE_REFRESH')
            except:
                row.label(text="Refresh Camera List", icon='FILE_REFRESH')
            
            # Camera list - FIXED PROPERTY NAME
            if hasattr(scene, 'camera_em_list') and len(scene.camera_em_list) > 0:
                row = camera_box.row()
                row.template_list("VISUAL_UL_camera_list", "", 
                                scene, "camera_em_list",  # CORRECTED FROM camera_list
                                scene, "active_camera_em_index")  # CORRECTED FROM active_camera_index
            else:
                camera_box.label(text="No cameras in CAMS collection")


def register_ui():
    """Register UI classes."""
    classes = [
        VISUAL_UL_property_values,
        VISUAL_UL_camera_list,
        VISUAL_MT_display_mode_menu,
        VIEW3D_PT_visual_panel,
    ]
    
    # Unregister existing classes first
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
    
    # Add UI-specific scene properties
    if not hasattr(bpy.types.Scene, "show_individual_viz_controls"):
        bpy.types.Scene.show_individual_viz_controls = bpy.props.BoolProperty(
            name="Show Individual Controls",
            description="Show individual module controls instead of unified interface",
            default=False
        )
    
    if not hasattr(bpy.types.Scene, "show_preset_management"):
        bpy.types.Scene.show_preset_management = bpy.props.BoolProperty(
            name="Show Preset Management",
            description="Show preset save/load/import/export controls",
            default=False
        )
    
    if not hasattr(bpy.types.Scene, "show_advanced_visualization"):
        bpy.types.Scene.show_advanced_visualization = bpy.props.BoolProperty(
            name="Show Advanced Visualization",
            description="Show/hide the advanced visualization tools section",
            default=False  # Collapsed by default
        )
    
    # Add properties for collapsible subsections within Advanced Visualization
    if not hasattr(bpy.types.Scene, "show_viz_quick_actions"):
        bpy.types.Scene.show_viz_quick_actions = bpy.props.BoolProperty(
            name="Show Quick Actions",
            description="Show/hide the quick actions section",
            default=True
        )
    
    if not hasattr(bpy.types.Scene, "show_viz_presets"):
        bpy.types.Scene.show_viz_presets = bpy.props.BoolProperty(
            name="Show Smart Presets",
            description="Show/hide the smart presets section",
            default=True
        )
    
    if not hasattr(bpy.types.Scene, "show_viz_status"):
        bpy.types.Scene.show_viz_status = bpy.props.BoolProperty(
            name="Show System Status",
            description="Show/hide the system status section",
            default=True
        )


def unregister_ui():
    """Unregister UI classes."""
    # Remove UI-specific scene properties
    ui_properties = [
        "show_individual_viz_controls",
        "show_preset_management",
        "show_advanced_visualization",
        "show_viz_quick_actions",
        "show_viz_presets",
        "show_viz_status"
    ]
    
    for prop_name in ui_properties:
        if hasattr(bpy.types.Scene, prop_name):
            delattr(bpy.types.Scene, prop_name)
    
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