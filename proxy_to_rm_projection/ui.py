"""
UI components for Proxy to RM Projection
This module contains the user interface elements for the proxy projection system,
integrated into the Visual Manager panel.
"""

import bpy
from bpy.types import Panel

from . import is_system_available, get_system_status, check_prerequisites


class VIEW3D_PT_proxy_projection_panel(Panel):
    """Panel for Proxy to RM Projection in Visual Manager"""
    bl_label = "Proxy to RM Projection"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "EM"
    bl_parent_id = "VIEW3D_PT_visual_panel"  # Child of Visual Manager panel
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        """Show panel only when EM Tools is in advanced mode and system is available"""
        # Check if EM Tools is in advanced mode
        if not hasattr(context.scene, 'em_tools') or not context.scene.em_tools.mode_switch:
            return False
        
        # Check if projection system is available
        available, _ = is_system_available()
        return available

    def draw_header(self, context):
        """Draw panel header with status indicator"""
        layout = self.layout
        scene = context.scene
        
        if hasattr(scene, 'proxy_projection_settings'):
            settings = scene.proxy_projection_settings
            if settings.projection_active:
                layout.label(text="", icon='CHECKMARK')
            else:
                layout.label(text="", icon='RADIOBUT_OFF')

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        
        # Check if settings are available
        if not hasattr(scene, 'proxy_projection_settings'):
            layout.label(text="Projection system not initialized", icon='ERROR')
            return
        
        settings = scene.proxy_projection_settings
        
        # Check prerequisites
        prereqs_ok, issues = check_prerequisites()
        
        # Main toggle and status
        self.draw_main_controls(layout, settings, prereqs_ok)
        
        # Prerequisites warning
        if not prereqs_ok:
            self.draw_prerequisites_warning(layout, issues)
        
        # Settings (when expanded)
        if settings.projection_active or prereqs_ok:
            self.draw_projection_settings(layout, settings)
        
        # Advanced settings (collapsible)
        self.draw_advanced_settings(layout, settings)
        
        # Debug tools (only if experimental features enabled)
        em_tools = scene.em_tools
        if hasattr(em_tools, 'experimental_features') and em_tools.experimental_features:
            self.draw_debug_tools(layout, settings)

    def draw_main_controls(self, layout, settings, prereqs_ok):
        """Draw main control buttons"""
        
        # Main toggle button
        row = layout.row()
        row.scale_y = 1.3
        
        if settings.projection_active:
            row.operator("proxy_projection.clear", text="Clear Projection", icon='X')
        else:
            op = row.operator("proxy_projection.apply", text="Apply Projection", icon='PLAY')
            row.enabled = prereqs_ok
        
        # Status row
        status_row = layout.row()
        status_row.scale_y = 0.8
        
        if settings.projection_active:
            status_row.label(text="✓ Projection Active", icon='CHECKMARK')
            
            # Quick update button when active
            update_row = layout.row(align=True)
            update_row.operator("proxy_projection.update", text="Update", icon='FILE_REFRESH')
            update_row.operator("proxy_projection.toggle", text="Toggle", icon='LOOP_BACK')
        else:
            if prereqs_ok:
                status_row.label(text="Ready to apply", icon='RADIOBUT_OFF')
            else:
                status_row.label(text="Prerequisites not met", icon='ERROR')

    def draw_prerequisites_warning(self, layout, issues):
        """Draw warning box with prerequisite issues"""
        
        box = layout.box()
        box.alert = True
        
        col = box.column()
        col.label(text="Prerequisites not met:", icon='ERROR')
        
        for issue in issues[:3]:  # Show max 3 issues to avoid clutter
            row = col.row()
            row.scale_y = 0.8
            row.label(text=f"• {issue}")
        
        if len(issues) > 3:
            row = col.row()
            row.scale_y = 0.8
            row.label(text=f"... and {len(issues) - 3} more")

    def draw_projection_settings(self, layout, settings):
        """Draw projection settings"""
        
        box = layout.box()
        
        # Auto-update toggle
        row = box.row()
        row.prop(settings, "auto_update_enabled", text="Auto Update")
        
        # Projection method
        row = box.row()
        row.prop(settings, "projection_method", text="Method")
        
        # Blend strength
        row = box.row()
        row.prop(settings, "blend_strength", text="Strength", slider=True)
        
        # Hide non-intersected areas
        col = box.column()
        col.prop(settings, "hide_non_intersected", text="Hide Non-Intersected Areas")
        
        if settings.hide_non_intersected:
            sub_row = col.row()
            sub_row.prop(settings, "non_intersected_alpha", text="Alpha", slider=True)

    def draw_advanced_settings(self, layout, settings):
        """Draw advanced settings in collapsible section"""
        
        box = layout.box()
        
        # Collapsible header
        row = box.row()
        row.prop(settings, "show_advanced_settings", 
                text="Advanced Settings", 
                icon='TRIA_DOWN' if settings.show_advanced_settings else 'TRIA_RIGHT',
                emboss=False)
        
        if not settings.show_advanced_settings:
            return
        
        # Ray casting precision
        col = box.column()
        col.prop(settings, "ray_casting_precision", text="Precision")
        
        # Max ray distance
        col.prop(settings, "max_ray_distance", text="Max Distance")
        
        # Batch size
        col.prop(settings, "batch_size", text="Batch Size")
        
        # Linked object handling
        col.separator()
        col.prop(settings, "override_linked_materials", text="Override Linked Materials")
        
        # Show override info if any are active
        try:
            from .material_override import get_override_info
            override_info = get_override_info()
            
            if override_info['count'] > 0:
                info_row = col.row()
                info_row.scale_y = 0.8
                info_row.label(text=f"Active overrides: {override_info['count']}", icon='INFO')
                
        except Exception:
            pass

    def draw_debug_tools(self, layout, settings):
        """Draw debug and diagnostic tools"""
        
        box = layout.box()
        box.label(text="Debug Tools:", icon='TOOL_SETTINGS')
        
        # Diagnostic button
        row = box.row()
        row.operator("proxy_projection.diagnose", text="Run Diagnosis", icon='ZOOM_ALL')
        
        # System status
        try:
            status = get_system_status()
            
            info_col = box.column()
            info_col.scale_y = 0.8
            
            info_col.label(text=f"System: {'Available' if status['available'] else 'Unavailable'}")
            
            if 'override_count' in status:
                info_col.label(text=f"Overrides: {status['override_count']}")
                
        except Exception as e:
            box.label(text=f"Status error: {str(e)}", icon='ERROR')


def draw_projection_integration_in_visual_manager(self, context):
    """
    Integration function to add projection controls to existing Visual Manager UI.
    This can be called from the main Visual Manager panel.
    """
    layout = self.layout
    scene = context.scene
    
    # Only show if system is available and in advanced mode
    if not hasattr(scene, 'em_tools') or not scene.em_tools.mode_switch:
        return
    
    available, _ = is_system_available()
    if not available:
        return
    
    if not hasattr(scene, 'proxy_projection_settings'):
        return
    
    settings = scene.proxy_projection_settings
    
    # Quick projection controls in main Visual Manager
    box = layout.box()
    box.label(text="Proxy Projection:", icon='NODE_TEXTURE')
    
    row = box.row(align=True)
    
    if settings.projection_active:
        row.operator("proxy_projection.clear", text="Clear", icon='X')
        row.operator("proxy_projection.update", text="Update", icon='FILE_REFRESH')
    else:
        # Check prerequisites quickly
        prereqs_ok, _ = check_prerequisites()
        op = row.operator("proxy_projection.apply", text="Apply", icon='PLAY')
        row.enabled = prereqs_ok
        
        if not prereqs_ok:
            warning_row = box.row()
            warning_row.scale_y = 0.8
            warning_row.label(text="Check prerequisites in panel below", icon='INFO')


def register_ui():
    """Register UI classes."""
    classes = [
        VIEW3D_PT_proxy_projection_panel,
    ]
    
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
            print(f"Successfully registered UI class: {cls.__name__}")
        except ValueError as e:
            print(f"Failed to register UI class {cls.__name__}: {e}")


def unregister_ui():
    """Unregister UI classes."""
    classes = [
        VIEW3D_PT_proxy_projection_panel,
    ]
    
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except ValueError:
            pass
