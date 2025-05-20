import bpy
from bpy.types import Panel, Operator
from bpy.props import BoolProperty, FloatProperty

# Helper function to create standardized modifier name
def get_inflate_name(obj_name):
    return f"{obj_name}_inflate"

class VIEW3D_PT_ProxyInflatePanel(Panel):
    bl_label = "Proxy Inflate Manager"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'EM'
    bl_parent_id = "VIEW3D_PT_VisualPanel"  # Adding as subpanel to Visual Manager
    bl_options = {'DEFAULT_CLOSED'}
    

    @classmethod
    def poll(cls, context):
        # Il pannello è visibile solo se experimental_features è abilitato
        return context.scene.em_tools.experimental_features

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        
        # Inflation settings
        box = layout.box()
        row = box.row()
        row.label(text="Inflation Settings:")
        
        # Check if properties exist before trying to access them
        if hasattr(scene, "proxy_inflate_thickness"):
            # Default parameters
            row = box.row()
            row.prop(scene, "proxy_inflate_thickness", text="Thickness")
            
            row = box.row()
            row.prop(scene, "proxy_inflate_offset", text="Offset")
            
        else:
            row = box.row()
            row.label(text="Settings not available. Please reload addon.")
        
        # Apply to selection
        box = layout.box()
        row = box.row()
        row.label(text="Modify Selection:")
        
        row = box.row(align=True)
        row.operator("em.proxy_add_inflate", text="Add", icon='ADD')
        row.operator("em.proxy_activate_inflate", text="Activate", icon='PLAY')
        row.operator("em.proxy_deactivate_inflate", text="Deactivate", icon='PAUSE')
        row.operator("em.proxy_remove_inflate", text="Remove", icon='X')
        
        # Global operations
        box = layout.box()
        row = box.row()
        row.label(text="Global Operations:")
        
        row = box.row()
        row.operator("em.proxy_inflate_all", text="Inflate All Proxies", icon='MOD_SOLIDIFY')
        
        # Export related
        if hasattr(scene, "proxy_auto_inflate_on_export"):
            row = box.row()
            row.prop(scene, "proxy_auto_inflate_on_export", text="Auto-Inflate on Export")
        
        # Status counter
        if hasattr(scene, "proxy_inflate_stats") and scene.proxy_inflate_stats:
            box = layout.box()
            row = box.row()
            row.label(text=f"Proxies with inflation: {scene.proxy_inflate_stats}")


class EM_OT_ProxyAddInflate(Operator):
    bl_idname = "em.proxy_add_inflate"
    bl_label = "Add Inflate Modifier"
    bl_description = "Add Solidify modifier to selected proxies"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        selection = context.selected_objects
        count = 0
        
        if not selection:
            self.report({'WARNING'}, "No objects selected")
            return {'CANCELLED'}
            
        for obj in selection:
            if obj.type == 'MESH':
                # Check if inflate modifier already exists
                if get_inflate_name(obj.name) not in obj.modifiers:
                    mod = obj.modifiers.new(name=get_inflate_name(obj.name), type='SOLIDIFY')
                    # Set properties from scene settings
                    mod.thickness = context.scene.proxy_inflate_thickness
                    mod.offset = context.scene.proxy_inflate_offset
                    mod.use_even_offset = True
                    mod.use_quality_normals = True
                    mod.use_rim = True
                    mod.use_rim_only = False
                    count += 1
        
        # Update stats
        self.update_stats(context)
        
        self.report({'INFO'}, f"Added inflation to {count} proxies")
        return {'FINISHED'}
    
    def update_stats(self, context):
        count = 0
        for obj in bpy.data.objects:
            if obj.type == 'MESH':
                for mod in obj.modifiers:
                    if "_inflate" in mod.name:
                        count += 1
                        break
        context.scene.proxy_inflate_stats = count


class EM_OT_ProxyActivateInflate(Operator):
    bl_idname = "em.proxy_activate_inflate"
    bl_label = "Activate Inflate Modifiers"
    bl_description = "Activate Solidify modifiers on selected proxies"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        selection = context.selected_objects
        count = 0
        
        if not selection:
            self.report({'WARNING'}, "No objects selected")
            return {'CANCELLED'}
            
        for obj in selection:
            if obj.type == 'MESH':
                for mod in obj.modifiers:
                    if "_inflate" in mod.name:
                        if not mod.show_viewport:
                            mod.show_viewport = True
                            count += 1
        
        self.report({'INFO'}, f"Activated inflation on {count} proxies")
        return {'FINISHED'}


class EM_OT_ProxyDeactivateInflate(Operator):
    bl_idname = "em.proxy_deactivate_inflate"
    bl_label = "Deactivate Inflate Modifiers"
    bl_description = "Deactivate Solidify modifiers on selected proxies"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        selection = context.selected_objects
        count = 0
        
        if not selection:
            self.report({'WARNING'}, "No objects selected")
            return {'CANCELLED'}
            
        for obj in selection:
            if obj.type == 'MESH':
                for mod in obj.modifiers:
                    if "_inflate" in mod.name:
                        if mod.show_viewport:
                            mod.show_viewport = False
                            count += 1
        
        self.report({'INFO'}, f"Deactivated inflation on {count} proxies")
        return {'FINISHED'}


class EM_OT_ProxyRemoveInflate(Operator):
    bl_idname = "em.proxy_remove_inflate"
    bl_label = "Remove Inflate Modifiers"
    bl_description = "Remove Solidify modifiers from selected proxies"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        selection = context.selected_objects
        count = 0
        
        if not selection:
            self.report({'WARNING'}, "No objects selected")
            return {'CANCELLED'}
            
        for obj in selection:
            if obj.type == 'MESH':
                for mod in obj.modifiers[:]:
                    if "_inflate" in mod.name:
                        obj.modifiers.remove(mod)
                        count += 1
        
        # Update stats
        context.scene.proxy_inflate_stats = max(0, context.scene.proxy_inflate_stats - count)
        
        self.report({'INFO'}, f"Removed inflation from {count} proxies")
        return {'FINISHED'}


class EM_OT_ProxyInflateAll(Operator):
    bl_idname = "em.proxy_inflate_all"
    bl_label = "Inflate All Proxies"
    bl_description = "Add Solidify modifier to all proxies without one"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        count = 0
        proxy_collection = bpy.data.collections.get('Proxy')
        
        if not proxy_collection:
            # Try to find proxies from em_list if collection doesn't exist
            if hasattr(context.scene, 'em_list'):
                proxy_objects = []
                for item in context.scene.em_list:
                    obj = bpy.data.objects.get(item.name)
                    if obj and obj.type == 'MESH':
                        proxy_objects.append(obj)
                        
                if not proxy_objects:
                    self.report({'WARNING'}, "No proxies found in em_list")
                    return {'CANCELLED'}
                    
                # Process found proxy objects
                for obj in proxy_objects:
                    if get_inflate_name(obj.name) not in obj.modifiers:
                        mod = obj.modifiers.new(name=get_inflate_name(obj.name), type='SOLIDIFY')
                        # Set properties from scene settings
                        if hasattr(context.scene, "proxy_inflate_thickness"):
                            mod.thickness = context.scene.proxy_inflate_thickness
                            mod.offset = context.scene.proxy_inflate_offset
                        else:
                            mod.thickness = 0.01
                            mod.offset = 0.0
                            mod.merge_threshold = 0.0001
                        
                        mod.use_even_offset = True
                        mod.use_quality_normals = True
                        mod.use_rim = True
                        mod.use_rim_only = False
                        count += 1
            else:
                self.report({'WARNING'}, "No 'Proxy' collection found and no em_list available")
                return {'CANCELLED'}
        else:
            # Process objects in Proxy collection
            for obj in proxy_collection.objects:
                if obj.type == 'MESH':
                    # Check if inflate modifier already exists
                    if get_inflate_name(obj.name) not in obj.modifiers:
                        mod = obj.modifiers.new(name=get_inflate_name(obj.name), type='SOLIDIFY')
                        # Set properties from scene settings
                        if hasattr(context.scene, "proxy_inflate_thickness"):
                            mod.thickness = context.scene.proxy_inflate_thickness
                            mod.offset = context.scene.proxy_inflate_offset
                        else:
                            mod.thickness = 0.01
                            mod.offset = 0.0
                            mod.merge_threshold = 0.0001
                            
                        mod.use_even_offset = True
                        mod.use_quality_normals = True
                        mod.use_rim = True
                        mod.use_rim_only = False
                        count += 1
        
        # Update stats
        count_updated = 0
        for obj in bpy.data.objects:
            if obj.type == 'MESH':
                for mod in obj.modifiers:
                    if "_inflate" in mod.name:
                        count_updated += 1
                        break
        
        # Update stats if property exists
        if hasattr(context.scene, "proxy_inflate_stats"):
            context.scene.proxy_inflate_stats = count_updated
        
        self.report({'INFO'}, f"Added inflation to {count} proxies")
        return {'FINISHED'}


# Function to automatically add inflation modifiers before export
def auto_inflate_for_export(context, objects_to_export):
    """
    Add inflation modifiers to objects that need them before export
    
    Args:
        context: Blender context
        objects_to_export: List of objects being exported
    
    Returns:
        List of objects that had modifiers added (for cleanup)
    """
    # Check if auto-inflate is enabled and the property exists
    if not (hasattr(context.scene, "proxy_auto_inflate_on_export") and 
            context.scene.proxy_auto_inflate_on_export):
        return []
    
    modified_objects = []
    
    for obj in objects_to_export:
        if obj.type == 'MESH':
            # Check if object already has an inflate modifier
            has_inflate = False
            for mod in obj.modifiers:
                if "_inflate" in mod.name:
                    has_inflate = True
                    break
            
            # If no inflate modifier, add one
            if not has_inflate:
                mod = obj.modifiers.new(name=get_inflate_name(obj.name), type='SOLIDIFY')
                
                # Set properties from scene settings if they exist
                if hasattr(context.scene, "proxy_inflate_thickness"):
                    mod.thickness = context.scene.proxy_inflate_thickness
                    mod.offset = context.scene.proxy_inflate_offset
                else:
                    # Default values if properties don't exist
                    mod.thickness = 0.01
                    mod.offset = 0.0
                
                mod.use_even_offset = True
                mod.use_quality_normals = True
                mod.use_rim = True
                mod.use_rim_only = False
                modified_objects.append(obj)
    
    return modified_objects


# Function to remove temporary inflation modifiers after export
def cleanup_auto_inflate(modified_objects):
    """
    Remove temporary inflation modifiers
    
    Args:
        modified_objects: List of objects that had modifiers added
    """
    for obj in modified_objects:
        for mod in obj.modifiers[:]:
            if "_inflate" in mod.name:
                obj.modifiers.remove(mod)


# Registration
classes = (
    VIEW3D_PT_ProxyInflatePanel,
    EM_OT_ProxyAddInflate,
    EM_OT_ProxyActivateInflate,
    EM_OT_ProxyDeactivateInflate,
    EM_OT_ProxyRemoveInflate,
    EM_OT_ProxyInflateAll,
)

def register():
    # First register the properties
    bpy.types.Scene.proxy_inflate_thickness = FloatProperty(
        name="Thickness",
        description="Thickness value for the Solidify modifier",
        default=0.01,
        min=0.0001,
        soft_max=0.1,
        unit='LENGTH'
    )
    
    bpy.types.Scene.proxy_inflate_offset = FloatProperty(
        name="Offset",
        description="Offset value for the Solidify modifier",
        default=0.0,
        min=-1.0,
        max=1.0
    )
       
    bpy.types.Scene.proxy_auto_inflate_on_export = BoolProperty(
        name="Auto-Inflate on Export",
        description="Automatically add inflation to proxies without it during export",
        default=False
    )
    
    bpy.types.Scene.proxy_inflate_stats = bpy.props.IntProperty(
        name="Inflated Proxy Count",
        default=0
    )
    
    # Then register the classes
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    # Remove scene properties
    del bpy.types.Scene.proxy_inflate_thickness
    del bpy.types.Scene.proxy_inflate_offset
    del bpy.types.Scene.proxy_auto_inflate_on_export
    del bpy.types.Scene.proxy_inflate_stats
    
    # Unregister classes
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


# Integration with export system
def export_pre_hook(self, context):
    """
    Function to be called before export to add inflation modifiers if needed
    """
    # Get objects to be exported (assuming self.objects_to_export exists)
    objects_to_export = getattr(self, 'objects_to_export', context.selected_objects)
    
    # Add inflation modifiers where needed and store modified objects
    modified_objects = auto_inflate_for_export(context, objects_to_export)
    
    # Store the list of modified objects for cleanup after export
    self.temp_inflated_objects = modified_objects

def export_post_hook(self):
    """
    Function to be called after export to clean up temporary modifiers
    """
    # Remove temporary inflation modifiers
    if hasattr(self, 'temp_inflated_objects'):
        cleanup_auto_inflate(self.temp_inflated_objects)
        del self.temp_inflated_objects


# Example integration with export operator
"""
def register_export_hooks():
    # Patch existing export operators
    from .export_manager import EM_export
    
    # Store original execute method
    original_execute = EM_export.execute
    
    # Create patched execute method with pre and post hooks
    def patched_execute(self, context):
        # Pre-export hook
        export_pre_hook(self, context)
        
        # Original execute method
        result = original_execute(self, context)
        
        # Post-export hook
        export_post_hook(self)
        
        return result
    
    # Replace the execute method
    EM_export.execute = patched_execute

# Call this in the plugin's register function
"""

if __name__ == "__main__":
    register()