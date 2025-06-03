"""
UI components for the Visual Manager
This module contains all UI classes for the Visual Manager, including
panels, list UI elements, and visualization module controls.
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
            
            # Set as active camera - with safety check
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
            
            # Delete labels - with safety check
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
            
            # Move to CAMS - with safety check
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
        
        # Advanced Visualization Tools (NEW)
        self.draw_visualization_modules(layout, context)
        
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

    def draw_visualization_modules(self, layout, context):
        """Draw advanced visualization tools (UPDATED with all new features)"""
        scene = context.scene
        
        # Main visualization box
        main_box = layout.box()
        main_box.label(text="Advanced Visualization System", icon='VIEWZOOM')
        
        # Quick Actions Row (NEW) - Most used functions
        quick_row = main_box.row(align=True)
        quick_row.scale_y = 1.2
        
        # Smart suggestions button
        quick_row.operator("visual.suggestions_popup", text="Smart Tips", icon='LIGHTPROBE_PLANE')
        
        # Preset menu
        quick_row.operator("visual.preset_menu", text="Presets", icon='PRESET')
        
        # Global cleanup
        quick_row.operator("visual.clean_all_materials", text="Clean", icon='BRUSH_DATA')
        
        # Smart Presets Section (Enhanced)
        preset_box = main_box.box()
        preset_box.label(text="Smart Presets & Management:", icon='PRESET')
        
        # Quick preset buttons (top row)
        row = preset_box.row(align=True)
        row.operator("visual.smart_visualization_preset", text="Focus", icon='ZOOM_SELECTED').preset_type = 'FOCUS'
        row.operator("visual.smart_visualization_preset", text="Epoch", icon='TIME').preset_type = 'EPOCH'
        row.operator("visual.smart_visualization_preset", text="Property", icon='PROPERTIES').preset_type = 'PROPERTY'
        
        # Second row of presets
        row = preset_box.row(align=True) 
        row.operator("visual.smart_visualization_preset", text="Present", icon='CAMERA_DATA').preset_type = 'PRESENTATION'
        row.operator("visual.smart_visualization_preset", text="Analyze", icon='VIEWZOOM').preset_type = 'ANALYSIS'
        
        # Preset management (collapsible)
        show_preset_mgmt = getattr(scene, 'show_preset_management', False)
        row = preset_box.row()
        row.prop(scene, "show_preset_management", 
                text="Preset Management", 
                icon='TRIA_DOWN' if show_preset_mgmt else 'TRIA_RIGHT',
                emboss=False)
        
        if show_preset_mgmt:
            mgmt_box = preset_box.box()
            
            # Save current state as preset
            row = mgmt_box.row(align=True)
            row.operator("visual.save_preset", text="Save Current", icon='FILE_TICK')
            row.operator("visual.preset_menu", text="Load", icon='FILE_FOLDER')
            
            # Import/Export presets
            row = mgmt_box.row(align=True)
            row.operator("visual.import_preset", text="Import", icon='IMPORT')
            row.operator("visual.export_preset", text="Export", icon='EXPORT')
        
        # System Status & Controls (NEW)
        status_box = main_box.box()
        status_box.label(text="System Status:", icon='SETTINGS')
        
        try:
            from .visualization_modules import get_manager, is_visualization_active, get_system_status
            
            system_status = get_system_status()
            
            if system_status['manager_active']:
                # Active visualizations indicator
                if is_visualization_active():
                    active_modules = system_status['active_modules']
                    status_row = status_box.row()
                    status_row.alert = True
                    status_row.label(text=f"Active: {', '.join(active_modules)}", icon='CHECKMARK')
                    
                    # System health indicator
                    health = system_status['system_health']
                    if health == 'performance_mode':
                        status_box.label(text="Performance Mode: ON", icon='ERROR')
                    elif health == 'high_load':
                        status_box.label(text="High Load Detected", icon='ERROR')
                    
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
        
        # Temporal Analysis Section (NEW)
        if hasattr(scene, 'epoch_list') and len(scene.epoch_list) > 0:
            temporal_box = main_box.box()
            temporal_box.label(text="Temporal Analysis:", icon='TIME')
            
            if hasattr(scene, 'epoch_temporal_settings'):
                settings = scene.epoch_temporal_settings
                
                # Temporal mode selection
                row = temporal_box.row()
                row.prop(settings, "temporal_mode", text="Mode")
                
                # Temporal controls
                row = temporal_box.row(align=True)
                row.prop(settings, "show_temporal_context", text="Context")
                row.prop(settings, "use_chronological_colors", text="Chrono Colors")
                
                if settings.show_temporal_context:
                    row = temporal_box.row()
                    row.prop(settings, "context_transparency", text="Context Alpha")
                
                # Temporal action buttons
                row = temporal_box.row(align=True)
                row.operator("visual.temporal_analysis", text="Analyze Current", icon='PLAY')
                row.operator("visual.temporal_sequence", text="Start Sequence", icon='SEQUENCE_COLOR_01')
                
                # Sequence controls (if running)
                if settings.auto_advance:
                    row = temporal_box.row(align=True)
                    row.operator("visual.temporal_advance", text="Next", icon='NEXT_KEYFRAME')
                    row.operator("visual.temporal_stop", text="Stop", icon='PAUSE')
                    
                    row = temporal_box.row()
                    row.prop(settings, "auto_advance_interval", text="Interval")
                
                # Temporal analysis tools
                row = temporal_box.row()
                row.operator("visual.analyze_temporal_structure", text="Structure Analysis", icon='OUTLINER_DATA_GP_LAYER')
        
        # Setup Wizard & Tools (Enhanced)
        setup_box = main_box.box()
        setup_box.label(text="Setup & Tools:", icon='TOOL_SETTINGS')
        
        # Main setup wizard
        row = setup_box.row(align=True)
        row.operator("visual.create_visualization_setup", text="Complete Setup", icon='SCENE_DATA')
        row.operator("visual.suggestions_popup", text="Get Suggestions", icon='LIGHTPROBE_PLANAR')
        
        # System tools
        tools_row = setup_box.row(align=True)
        tools_row.operator("visual.run_validation", text="Validate", icon='CHECKMARK')
        tools_row.operator("visual.performance_benchmark", text="Benchmark", icon='TIME')
        tools_row.operator("visual.system_diagnostics", text="Diagnostics", icon='INFO')
        
        # Advanced options toggle
        if hasattr(scene, 'visualization_manager_settings'):
            settings = scene.visualization_manager_settings
            
            row = setup_box.row()
            row.prop(settings, "show_performance_info", text="Performance Info")
            row.prop(settings, "auto_update_on_selection", text="Auto Update")
        
        # Individual Module Controls (Collapsible) - Enhanced
        self.draw_individual_module_controls(main_box, context)
    
    def draw_individual_module_controls(self, layout, context):
        """Draw individual module controls in collapsible sections (ENHANCED)"""
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
            
            # Module control buttons (Enhanced)
            row = trans_box.row(align=True)
            op = row.operator("visual.unified_apply_visualization", text="Apply", icon='CHECKMARK')
            op.module_id = 'transparency'
            op = row.operator("visual.unified_clear_visualization", text="Clear", icon='X')
            op.module_id = 'transparency'
            
            # Quick presets for transparency
            row = trans_box.row(align=True)
            row.scale_y = 0.8
            op = row.operator("visual.unified_apply_visualization", text="Light")
            op.module_id = 'transparency'
            # Would set light transparency via properties
            
            op = row.operator("visual.unified_apply_visualization", text="Heavy")
            op.module_id = 'transparency'
            # Would set heavy transparency via properties
        
        # Color Overlay Controls (Enhanced)
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
            
            row = overlay_box.row(align=True)
            row.prop(settings, "affect_emission", text="Affect Emission")
            row.prop(settings, "preserve_original_alpha", text="Preserve Alpha")
            
            # Module control buttons (Enhanced)
            row = overlay_box.row(align=True)
            op = row.operator("visual.unified_apply_visualization", text="Apply", icon='CHECKMARK')
            op.module_id = 'color_overlay'
            op = row.operator("visual.unified_clear_visualization", text="Clear", icon='X')
            op.module_id = 'color_overlay'
            
            row = overlay_box.row(align=True)
            row.operator("visual.preview_overlay_color", text="Preview Selected", icon='HIDE_OFF')
            row.operator("visual.update_overlay_colors", text="Update", icon='FILE_REFRESH')
        
        # Clipping Section Controls (Enhanced)
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
            
            row = clip_box.row(align=True)
            row.prop(settings, "use_camera_clipping", text="From Camera")
            row.prop(settings, "affect_all_objects", text="All Objects")
            
            # Clipping creation buttons
            row = clip_box.row(align=True)
            row.operator("visual.create_clipping_volume", text="Create Volume", icon='CUBE')
            row.operator("visual.create_camera_clipping_plane", text="Camera Plane", icon='CAMERA_DATA')
            
            # Module control buttons (Enhanced)
            row = clip_box.row(align=True)
            op = row.operator("visual.unified_apply_visualization", text="Apply Effect", icon='CHECKMARK')
            op.module_id = 'clipping'
            op = row.operator("visual.unified_clear_visualization", text="Clear Effect", icon='X')
            op.module_id = 'clipping'
            
            # Clipping management
            row = clip_box.row()
            row.operator("visual.delete_clipping_volumes", text="Delete All Volumes", icon='TRASH')
    
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
        
        # Transparency Controls
        trans_box = layout.box()
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
            
            # Module control buttons (NEW)
            row = trans_box.row(align=True)
            op = row.operator("visual.unified_apply_visualization", text="Apply", icon='CHECKMARK')
            op.module_id = 'transparency'
            op = row.operator("visual.unified_clear_visualization", text="Clear", icon='X')
            op.module_id = 'transparency'
        
        # Color Overlay Controls
        overlay_box = layout.box()
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
            
            # Module control buttons (NEW)
            row = overlay_box.row(align=True)
            op = row.operator("visual.unified_apply_visualization", text="Apply", icon='CHECKMARK')
            op.module_id = 'color_overlay'
            op = row.operator("visual.unified_clear_visualization", text="Clear", icon='X')
            op.module_id = 'color_overlay'
            
            row = overlay_box.row(align=True)
            row.operator("visual.preview_overlay_color", text="Preview Selected", icon='HIDE_OFF')
            row.operator("visual.update_overlay_colors", text="Update", icon='FILE_REFRESH')
        
        # Clipping Section Controls
        clip_box = layout.box()
        clip_box.label(text="Clipping Module:", icon='MOD_BOOLEAN')
        
        if hasattr(scene, 'clipping_settings'):
            settings = scene.clipping_settings
            
            row = clip_box.row()
            row.prop(settings, "clipping_mode", text="Type")
            
            row = clip_box.row()
            row.prop(settings, "section_color", text="Section Color")
            
            row = clip_box.row()
            row.prop(settings, "clipping_distance", text="Distance")
            
            row = clip_box.row(align=True)
            row.prop(settings, "use_camera_clipping", text="From Camera")
            row.prop(settings, "affect_all_objects", text="All Objects")
            
            # Clipping creation buttons
            row = clip_box.row(align=True)
            row.operator("visual.create_clipping_volume", text="Create Volume", icon='CUBE')
            row.operator("visual.create_camera_clipping_plane", text="Camera Plane", icon='CAMERA_DATA')
            
            # Module control buttons (NEW)
            row = clip_box.row(align=True)
            op = row.operator("visual.unified_apply_visualization", text="Apply Effect", icon='CHECKMARK')
            op.module_id = 'clipping'
            op = row.operator("visual.unified_clear_visualization", text="Clear Effect", icon='X')
            op.module_id = 'clipping'
            
            # Clipping management
            row = clip_box.row()
            row.operator("visual.delete_clipping_volumes", text="Delete All Volumes", icon='TRASH')

    def draw_label_tools(self, layout, context):
        """Draw label and camera management tools"""
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
            
            # Camera management
            camera_box = box.box()
            camera_box.label(text="Camera Management:")
            
            # Update camera list button
            row = camera_box.row()
            row.operator("visual.update_camera_list", text="Refresh Camera List", icon='FILE_REFRESH')
            
            # Camera list
            if len(scene.camera_list) > 0:
                row = camera_box.row()
                row.template_list("VISUAL_UL_camera_list", "", 
                                scene, "camera_list",
                                scene, "active_camera_index")
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
    # Prima unregister eventuali classi esistenti
    try:
        if hasattr(bpy.types, 'VIEW3D_PT_visual_panel'):
            bpy.utils.unregister_class(bpy.types.VIEW3D_PT_visual_panel)
    except:
        pass
    
    classes = [
        VISUAL_UL_property_values,
        VISUAL_UL_camera_list,
        VISUAL_MT_display_mode_menu,
        VIEW3D_PT_visual_panel,
    ]
    
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
            print(f"Successfully registered: {cls.__name__}")
        except ValueError as e:
            print(f"Failed to register {cls.__name__}: {e}")
            # Prova a unregister e re-register
            try:
                bpy.utils.unregister_class(cls)
                bpy.utils.register_class(cls)
                print(f"Re-registered: {cls.__name__}")
            except:
                pass
    
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
    
    if not hasattr(bpy.types.Scene, "show_advanced_temporal"):
        bpy.types.Scene.show_advanced_temporal = bpy.props.BoolProperty(
            name="Show Advanced Temporal",
            description="Show advanced temporal analysis controls",
            default=False
        )
    
    # Force UI refresh
    try:
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
    except:
        pass


def unregister_ui():
    """Unregister UI classes."""
    # Remove UI-specific scene properties
    ui_properties = [
        "show_individual_viz_controls",
        "show_preset_management", 
        "show_advanced_temporal"
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
            # Class might already be unregistered
            pass