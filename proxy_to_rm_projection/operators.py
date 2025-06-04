"""
Operators for Proxy to RM Projection
This module contains all operators for applying, clearing, and updating
the proxy-to-representation-model projection system.
"""

import bpy
from bpy.types import Operator
from bpy.props import BoolProperty, StringProperty

from .utils import (
    get_filtered_proxy_objects,
    get_rm_objects_for_epoch,
    calculate_vertex_proxy_intersection,
    apply_vertex_colors,
    setup_vertex_color_material,
    clear_vertex_colors,
    get_proxy_color
)
from .material_override import (
    create_temporary_override,
    restore_original_materials,
    get_override_manager
)


class PROXY_PROJECTION_OT_apply(Operator):
    """Apply proxy projection to RM objects"""
    bl_idname = "proxy_projection.apply"
    bl_label = "Apply Proxy Projection"
    bl_description = "Apply proxy colors to RM objects based on volume intersections"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        settings = scene.proxy_projection_settings
        
        # Check prerequisites
        if not self.check_prerequisites(scene):
            return {'CANCELLED'}
        
        # Get proxy objects from filtered list
        proxy_objects = get_filtered_proxy_objects(scene.em_list)
        if not proxy_objects:
            self.report({'WARNING'}, "No proxy objects found in filtered stratigraphy list")
            return {'CANCELLED'}
        
        # Get RM objects for current epoch
        rm_objects = get_rm_objects_for_epoch(scene)
        if not rm_objects:
            self.report({'WARNING'}, "No RM objects found for current epoch")
            return {'CANCELLED'}
        
        # Clear any existing projection first
        bpy.ops.proxy_projection.clear()
        
        self.report({'INFO'}, f"Processing {len(proxy_objects)} proxies and {len(rm_objects)} RM objects...")
        
        processed_count = 0
        error_count = 0
        
        # Process each RM object
        for rm_data in rm_objects:
            try:
                success = self.process_rm_object(rm_data, proxy_objects, settings)
                if success:
                    processed_count += 1
                else:
                    error_count += 1
                    
            except Exception as e:
                print(f"Error processing RM object {rm_data['name']}: {e}")
                error_count += 1
                continue
        
        # Mark projection as active
        settings.projection_active = True
        
        # Report results
        if processed_count > 0:
            message = f"Applied projection to {processed_count} RM objects"
            if error_count > 0:
                message += f" ({error_count} errors)"
            self.report({'INFO'}, message)
            return {'FINISHED'}
        else:
            self.report({'ERROR'}, f"Failed to process any RM objects ({error_count} errors)")
            return {'CANCELLED'}

    def check_prerequisites(self, scene):
        """Check if all prerequisites are met for projection"""
        
        # Check if RM temporal sync is active
        if not getattr(scene, 'sync_rm_visibility', False):
            self.report({'ERROR'}, 
                       "RM temporal sync must be active for projection to work. "
                       "Enable it in the Stratigraphy Manager.")
            return False
        
        # Check if there's an active epoch
        if scene.epoch_list_index < 0 or scene.epoch_list_index >= len(scene.epoch_list):
            self.report({'ERROR'}, "No active epoch selected")
            return False
        
        return True

    def process_rm_object(self, rm_data, proxy_objects, settings):
        """Process a single RM object"""
        obj = rm_data['object']
        
        # Handle linked objects
        if rm_data['is_linked'] and settings.override_linked_materials:
            # Create temporary override
            success = create_temporary_override(obj)
            if not success:
                print(f"Warning: Could not create material override for linked object {obj.name}")
                return False
        
        # Calculate vertex intersections
        vertex_colors = calculate_vertex_proxy_intersection(rm_data, proxy_objects, settings)
        
        if not vertex_colors:
            print(f"No intersections found for RM object {obj.name}")
            return True  # Not an error, just no intersections
        
        # Apply projection based on method
        if settings.projection_method == 'VERTEX_PAINT':
            self.apply_vertex_paint_projection(obj, vertex_colors, settings)
        elif settings.projection_method == 'NODE_SHADER':
            self.apply_node_shader_projection(obj, vertex_colors, settings)
        
        # Handle non-intersected areas if requested
        if settings.hide_non_intersected:
            self.apply_non_intersected_transparency(obj, vertex_colors, settings)
        
        return True

    def apply_vertex_paint_projection(self, obj, vertex_colors, settings):
        """Apply projection using vertex painting"""
        # Setup vertex color material
        setup_vertex_color_material(obj)
        
        # Apply vertex colors
        apply_vertex_colors(obj, vertex_colors, settings.blend_strength)

    def apply_node_shader_projection(self, obj, vertex_colors, settings):
        """Apply projection using shader nodes"""
        # TODO: Implement advanced shader node projection
        # For now, fall back to vertex painting
        print(f"Node shader projection not yet implemented for {obj.name}, using vertex paint")
        self.apply_vertex_paint_projection(obj, vertex_colors, settings)

    def apply_non_intersected_transparency(self, obj, vertex_colors, settings):
        """Apply transparency to non-intersected areas"""
        mesh = obj.data
        
        # This would require more complex implementation
        # For now, just print a message
        print(f"Transparency for non-intersected areas not yet implemented for {obj.name}")


class PROXY_PROJECTION_OT_clear(Operator):
    """Clear proxy projection from all RM objects"""
    bl_idname = "proxy_projection.clear"
    bl_label = "Clear Proxy Projection"
    bl_description = "Remove proxy projection from all RM objects and restore original materials"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        settings = scene.proxy_projection_settings
        
        cleared_count = 0
        error_count = 0
        
        # Get all RM objects (not just current epoch)
        all_rm_objects = []
        for rm_item in scene.rm_list:
            obj = bpy.data.objects.get(rm_item.name)
            if obj and obj.type == 'MESH':
                all_rm_objects.append({
                    'object': obj,
                    'name': rm_item.name,
                    'is_linked': obj.library is not None
                })
        
        # Clear projection from each object
        for rm_data in all_rm_objects:
            try:
                obj = rm_data['object']
                
                # Clear vertex colors
                clear_vertex_colors(obj)
                
                # Restore original materials for linked objects
                if rm_data['is_linked']:
                    restore_original_materials(obj)
                
                cleared_count += 1
                
            except Exception as e:
                print(f"Error clearing projection from {rm_data['name']}: {e}")
                error_count += 1
                continue
        
        # Clear any temporary material overrides
        override_manager = get_override_manager()
        override_manager.clear_all_overrides()
        
        # Mark projection as inactive
        settings.projection_active = False
        
        # Report results
        if cleared_count > 0:
            message = f"Cleared projection from {cleared_count} objects"
            if error_count > 0:
                message += f" ({error_count} errors)"
            self.report({'INFO'}, message)
        else:
            self.report({'WARNING'}, "No projection to clear")
        
        return {'FINISHED'}


class PROXY_PROJECTION_OT_update(Operator):
    """Update proxy projection with current settings"""
    bl_idname = "proxy_projection.update"
    bl_label = "Update Proxy Projection"
    bl_description = "Update existing projection with current epoch, filters, and proxy colors"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        settings = scene.proxy_projection_settings
        
        if not settings.projection_active:
            self.report({'WARNING'}, "No active projection to update")
            return {'CANCELLED'}
        
        # Simply re-apply projection
        return bpy.ops.proxy_projection.apply()


class PROXY_PROJECTION_OT_update_strength(Operator):
    """Update only the blend strength of existing projection"""
    bl_idname = "proxy_projection.update_strength"
    bl_label = "Update Blend Strength"
    bl_description = "Update the blend strength of existing projection without recalculating intersections"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        settings = scene.proxy_projection_settings
        
        if not settings.projection_active:
            return {'CANCELLED'}
        
        # For now, do a full update
        # TODO: Implement optimized strength-only update
        return bpy.ops.proxy_projection.apply()


class PROXY_PROJECTION_OT_update_visibility(Operator):
    """Update visibility of non-intersected areas"""
    bl_idname = "proxy_projection.update_visibility"
    bl_label = "Update Visibility"
    bl_description = "Update transparency of non-intersected areas"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        settings = scene.proxy_projection_settings
        
        if not settings.projection_active:
            return {'CANCELLED'}
        
        # For now, do a full update
        # TODO: Implement optimized visibility-only update
        return bpy.ops.proxy_projection.apply()


class PROXY_PROJECTION_OT_toggle(Operator):
    """Toggle proxy projection on/off"""
    bl_idname = "proxy_projection.toggle"
    bl_label = "Toggle Proxy Projection"
    bl_description = "Toggle proxy projection on or off"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        settings = scene.proxy_projection_settings
        
        if settings.projection_active:
            return bpy.ops.proxy_projection.clear()
        else:
            return bpy.ops.proxy_projection.apply()


class PROXY_PROJECTION_OT_update_proxy_colors(Operator):
    """Update projection when proxy colors change"""
    bl_idname = "proxy_projection.update_proxy_colors"
    bl_label = "Update Proxy Colors"
    bl_description = "Update projection when proxy colors change in Visual Manager"
    bl_options = {'REGISTER', 'UNDO'}

    proxy_name: StringProperty(
        name="Proxy Name",
        description="Name of the proxy whose color changed"
    )

    def execute(self, context):
        scene = context.scene
        settings = scene.proxy_projection_settings
        
        if not settings.projection_active or not settings.auto_update_enabled:
            return {'CANCELLED'}
        
        # For specific proxy updates, we could optimize by only updating
        # the areas affected by that proxy. For now, do full update.
        return bpy.ops.proxy_projection.update()


class PROXY_PROJECTION_OT_diagnose(Operator):
    """Diagnose projection system status"""
    bl_idname = "proxy_projection.diagnose"
    bl_label = "Diagnose Projection System"
    bl_description = "Check system status and report any issues"
    bl_options = {'REGISTER'}

    def execute(self, context):
        scene = context.scene
        settings = scene.proxy_projection_settings
        
        report_lines = []
        
        # Check basic requirements
        report_lines.append("=== PROXY PROJECTION DIAGNOSIS ===")
        
        # Check RM sync
        rm_sync = getattr(scene, 'sync_rm_visibility', False)
        report_lines.append(f"RM Temporal Sync: {'✓ Active' if rm_sync else '✗ Inactive'}")
        
        # Check active epoch
        has_epoch = scene.epoch_list_index >= 0 and scene.epoch_list_index < len(scene.epoch_list)
        if has_epoch:
            epoch_name = scene.epoch_list[scene.epoch_list_index].name
            report_lines.append(f"Active Epoch: ✓ {epoch_name}")
        else:
            report_lines.append("Active Epoch: ✗ None selected")
        
        # Check proxy objects
        proxy_objects = get_filtered_proxy_objects(scene.em_list)
        report_lines.append(f"Filtered Proxies: {len(proxy_objects)} objects")
        
        # Check RM objects
        rm_objects = get_rm_objects_for_epoch(scene) if has_epoch else []
        report_lines.append(f"Epoch RM Objects: {len(rm_objects)} objects")
        
        # Check projection status
        report_lines.append(f"Projection Active: {'✓ Yes' if settings.projection_active else '✗ No'}")
        report_lines.append(f"Auto Update: {'✓ Enabled' if settings.auto_update_enabled else '✗ Disabled'}")
        
        # Check for linked objects
        linked_count = sum(1 for rm in rm_objects if rm['is_linked'])
        if linked_count > 0:
            override_enabled = settings.override_linked_materials
            report_lines.append(f"Linked Objects: {linked_count} (Override: {'✓' if override_enabled else '✗'})")
        
        # Print diagnosis
        print("\n".join(report_lines))
        
        # Show popup with key info
        def draw_popup(self, context):
            layout = self.layout
            col = layout.column()
            col.label(text="Proxy Projection Diagnosis:")
            col.separator()
            col.label(text=f"RM Sync: {'Active' if rm_sync else 'Inactive'}", 
                     icon='CHECKMARK' if rm_sync else 'X')
            col.label(text=f"Proxies: {len(proxy_objects)}", icon='OBJECT_DATA')
            col.label(text=f"RM Objects: {len(rm_objects)}", icon='MESH_DATA')
            col.label(text=f"Status: {'Active' if settings.projection_active else 'Inactive'}", 
                     icon='CHECKMARK' if settings.projection_active else 'X')
        
        context.window_manager.popup_menu(draw_popup, title="Diagnosis Results", icon='INFO')
        
        self.report({'INFO'}, "Diagnosis complete - check console for details")
        return {'FINISHED'}


def register_operators():
    """Register all operator classes."""
    classes = [
        PROXY_PROJECTION_OT_apply,
        PROXY_PROJECTION_OT_clear,
        PROXY_PROJECTION_OT_update,
        PROXY_PROJECTION_OT_update_strength,
        PROXY_PROJECTION_OT_update_visibility,
        PROXY_PROJECTION_OT_toggle,
        PROXY_PROJECTION_OT_update_proxy_colors,
        PROXY_PROJECTION_OT_diagnose,
    ]
    
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except ValueError:
            # Class might already be registered
            pass


def unregister_operators():
    """Unregister all operator classes."""
    classes = [
        PROXY_PROJECTION_OT_diagnose,
        PROXY_PROJECTION_OT_update_proxy_colors,
        PROXY_PROJECTION_OT_toggle,
        PROXY_PROJECTION_OT_update_visibility,
        PROXY_PROJECTION_OT_update_strength,
        PROXY_PROJECTION_OT_update,
        PROXY_PROJECTION_OT_clear,
        PROXY_PROJECTION_OT_apply,
    ]
    
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except ValueError:
            # Class might already be unregistered
            pass
