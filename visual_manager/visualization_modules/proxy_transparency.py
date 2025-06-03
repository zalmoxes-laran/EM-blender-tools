"""
Proxy Transparency Module
This module manages transparency of proxy objects based on visibility lists
and active selections within the EM-TOOLS system.
"""

import bpy
from bpy.types import Operator, PropertyGroup
from bpy.props import FloatProperty, BoolProperty, EnumProperty

from .utils import create_node_with_prefix, get_em_objects

class TransparencySettings(PropertyGroup):
    """Settings for proxy transparency system"""
    
    transparency_factor: FloatProperty(
        name="Transparency Factor",
        description="Amount of transparency to apply to inactive proxies",
        min=0.0,
        max=1.0,
        default=0.7,
        subtype='FACTOR'
    ) # type: ignore
    
    affect_selected_only: BoolProperty(
        name="Selected Objects Only",
        description="Apply transparency only to selected objects",
        default=False
    ) # type: ignore
    
    affect_visible_only: BoolProperty(
        name="Visible Objects Only", 
        description="Apply transparency only to visible objects in viewport",
        default=True
    ) # type: ignore
    
    transparency_mode: EnumProperty(
        name="Transparency Mode",
        description="How to determine which objects should be transparent",
        items=[
            ('SELECTION', "Selection Based", "Make non-selected objects transparent"),
            ('EM_LIST', "EM List Based", "Use EM list visibility to determine transparency"),
            ('EPOCH', "Epoch Based", "Make objects from non-active epochs transparent"),
            ('CUSTOM', "Custom List", "Use a custom list of objects to make transparent")
        ],
        default='SELECTION'
    ) # type: ignore
    
    auto_update: BoolProperty(
        name="Auto Update",
        description="Automatically update transparency when selection changes",
        default=False
    ) # type: ignore

def apply_transparency_to_material(material, transparency_value):
    """
    Apply transparency to a material using node modifications.
    
    Args:
        material: The material to modify
        transparency_value: Transparency factor (0.0 = opaque, 1.0 = transparent)
    """
    if not material.use_nodes:
        material.use_nodes = True
    
    node_tree = material.node_tree
    
    # Find or create Principled BSDF
    principled_node = None
    for node in node_tree.nodes:
        if node.type == 'BSDF_PRINCIPLED':
            principled_node = node
            break
    
    if not principled_node:
        return
    
    # Check if we already have a transparency node
    trans_node = None
    for node in node_tree.nodes:
        if node.name.startswith('TRANS_'):
            trans_node = node
            break
    
    if transparency_value > 0.001:  # Apply transparency
        # Set material blend mode
        material.blend_method = 'BLEND'
        
        if not trans_node:
            # Create transparency control node (Math node for mixing)
            trans_node = create_node_with_prefix(node_tree, 'ShaderNodeMath', 'TRANS', 'transparency_control')
            trans_node.operation = 'SUBTRACT'
            trans_node.location = (principled_node.location.x - 200, principled_node.location.y - 100)
            
            # Set up the math node: 1.0 - transparency_value = alpha
            trans_node.inputs[0].default_value = 1.0
        
        # Update transparency value
        trans_node.inputs[1].default_value = transparency_value
        
        # Connect to Alpha input of Principled BSDF
        if not principled_node.inputs['Alpha'].is_linked:
            node_tree.links.new(trans_node.outputs['Value'], principled_node.inputs['Alpha'])
        
    else:  # Remove transparency
        if trans_node:
            # Disconnect and remove transparency node
            node_tree.nodes.remove(trans_node)
            # Reset alpha to 1.0
            principled_node.inputs['Alpha'].default_value = 1.0
            # Reset blend method
            material.blend_method = 'OPAQUE'

def get_objects_for_transparency_mode(mode):
    """
    Get list of objects that should be made transparent based on the mode.
    
    Args:
        mode: Transparency mode
        
    Returns:
        list: Objects to make transparent
    """
    scene = bpy.context.scene
    objects_to_transparent = []
    
    if mode == 'SELECTION':
        # Make non-selected EM objects transparent
        selected_names = {obj.name for obj in bpy.context.selected_objects}
        em_objects = get_em_objects()
        objects_to_transparent = [obj for obj in em_objects if obj.name not in selected_names]
        
    elif mode == 'EM_LIST':
        # Use EM list visibility
        if hasattr(scene, 'em_list'):
            visible_names = {item.name for item in scene.em_list if not getattr(item, 'is_hidden', False)}
            em_objects = get_em_objects()
            objects_to_transparent = [obj for obj in em_objects if obj.name not in visible_names]
    
    elif mode == 'EPOCH':
        # Make objects from non-active epochs transparent
        if hasattr(scene, 'epoch_list') and hasattr(scene, 'epoch_list_index'):
            if scene.epoch_list_index >= 0 and len(scene.epoch_list) > 0:
                active_epoch = scene.epoch_list[scene.epoch_list_index]
                
                # Get objects not in active epoch
                if hasattr(scene, 'em_list'):
                    for item in scene.em_list:
                        if hasattr(item, 'epoch') and item.epoch != active_epoch.name:
                            obj = bpy.data.objects.get(item.name)
                            if obj and obj.type == 'MESH':
                                objects_to_transparent.append(obj)
    
    elif mode == 'CUSTOM':
        # Could be extended to use a custom property or collection
        pass
    
    return objects_to_transparent

class VISUAL_OT_apply_proxy_transparency(Operator):
    """Apply transparency to proxy objects based on current settings"""
    bl_idname = "visual.apply_proxy_transparency"
    bl_label = "Apply Proxy Transparency"
    bl_description = "Apply transparency to proxy objects based on current mode and settings"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        scene = context.scene
        settings = scene.transparency_settings
        
        try:
            # Get objects to make transparent
            objects_to_transparent = get_objects_for_transparency_mode(settings.transparency_mode)
            
            # Filter by selection/visibility if needed
            if settings.affect_selected_only:
                selected_names = {obj.name for obj in context.selected_objects}
                objects_to_transparent = [obj for obj in objects_to_transparent if obj.name in selected_names]
            
            if settings.affect_visible_only:
                objects_to_transparent = [obj for obj in objects_to_transparent if not obj.hide_viewport]
            
            # Apply transparency
            materials_modified = 0
            for obj in objects_to_transparent:
                if obj.data and obj.data.materials:
                    for material in obj.data.materials:
                        if material:
                            apply_transparency_to_material(material, settings.transparency_factor)
                            materials_modified += 1
            
            self.report({'INFO'}, f"Applied transparency to {len(objects_to_transparent)} objects, {materials_modified} materials")
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Error applying transparency: {str(e)}")
            return {'CANCELLED'}

class VISUAL_OT_clear_proxy_transparency(Operator):
    """Clear transparency from all proxy objects"""
    bl_idname = "visual.clear_proxy_transparency"
    bl_label = "Clear Proxy Transparency"
    bl_description = "Remove transparency from all proxy objects"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        try:
            em_objects = get_em_objects()
            materials_modified = 0
            
            for obj in em_objects:
                if obj.data and obj.data.materials:
                    for material in obj.data.materials:
                        if material:
                            apply_transparency_to_material(material, 0.0)  # Remove transparency
                            materials_modified += 1
            
            self.report({'INFO'}, f"Cleared transparency from {len(em_objects)} objects, {materials_modified} materials")
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Error clearing transparency: {str(e)}")
            return {'CANCELLED'}

class VISUAL_OT_toggle_transparency_auto_update(Operator):
    """Toggle automatic transparency updates"""
    bl_idname = "visual.toggle_transparency_auto_update"
    bl_label = "Toggle Auto Update"
    bl_description = "Toggle automatic transparency updates when selection changes"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        scene = context.scene
        settings = scene.transparency_settings
        
        settings.auto_update = not settings.auto_update
        
        if settings.auto_update:
            # Enable auto-update (would need to register handlers)
            self.report({'INFO'}, "Auto-update enabled")
        else:
            # Disable auto-update
            self.report({'INFO'}, "Auto-update disabled")
        
        return {'FINISHED'}

# Auto-update handler (if enabled)
def transparency_selection_handler(scene):
    """Handler for automatic transparency updates on selection change"""
    if hasattr(scene, 'transparency_settings') and scene.transparency_settings.auto_update:
        try:
            bpy.ops.visual.apply_proxy_transparency()
        except:
            pass  # Ignore errors in handlers

def register_transparency():
    """Register transparency module classes and properties."""
    classes = [
        TransparencySettings,
        VISUAL_OT_apply_proxy_transparency,
        VISUAL_OT_clear_proxy_transparency,
        VISUAL_OT_toggle_transparency_auto_update,
    ]
    
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except ValueError:
            pass
    
    # Add settings to scene
    if not hasattr(bpy.types.Scene, "transparency_settings"):
        bpy.types.Scene.transparency_settings = bpy.props.PointerProperty(type=TransparencySettings)

def unregister_transparency():
    """Unregister transparency module classes and properties."""
    # Remove scene properties
    if hasattr(bpy.types.Scene, "transparency_settings"):
        del bpy.types.Scene.transparency_settings
    
    classes = [
        VISUAL_OT_toggle_transparency_auto_update,
        VISUAL_OT_clear_proxy_transparency,
        VISUAL_OT_apply_proxy_transparency,
        TransparencySettings,
    ]
    
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except ValueError:
            pass
