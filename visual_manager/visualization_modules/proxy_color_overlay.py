"""
Proxy Color Overlay Module
This module applies additive color overlays to proxy objects using colors
from the Extended Matrix, Property, or Period systems.
"""

import bpy
from bpy.types import Operator, PropertyGroup
from bpy.props import FloatProperty, BoolProperty, EnumProperty, FloatVectorProperty

from .utils import create_node_with_prefix, get_em_objects

class ColorOverlaySettings(PropertyGroup):
    """Settings for color overlay system"""
    
    overlay_strength: FloatProperty(
        name="Overlay Strength",
        description="Strength of the color overlay effect",
        min=0.0,
        max=1.0,
        default=0.5,
        subtype='FACTOR'
    ) # type: ignore
    
    overlay_mode: EnumProperty(
        name="Overlay Mode",
        description="Source of colors for overlay",
        items=[
            ('EM_TYPE', "EM Type", "Use colors based on EM node types (US, USV, etc.)"),
            ('PROPERTY', "Property Values", "Use colors from selected property values"),
            ('EPOCH', "Epoch Colors", "Use colors assigned to epochs"),
            ('CUSTOM', "Custom Color", "Use a single custom color for all objects")
        ],
        default='EM_TYPE'
    ) # type: ignore
    
    custom_overlay_color: FloatVectorProperty(
        name="Custom Overlay Color",
        description="Custom color for overlay when using custom mode",
        subtype='COLOR',
        size=3,
        min=0.0,
        max=1.0,
        default=(1.0, 0.5, 0.0)  # Orange
    ) # type: ignore
    
    blend_mode: EnumProperty(
        name="Blend Mode",
        description="How to blend the overlay color with existing material",
        items=[
            ('ADD', "Add", "Additive blending"),
            ('MULTIPLY', "Multiply", "Multiply blending"),
            ('OVERLAY', "Overlay", "Overlay blending"),
            ('SCREEN', "Screen", "Screen blending"),
            ('COLOR', "Color", "Color blending")
        ],
        default='ADD'
    ) # type: ignore
    
    affect_emission: BoolProperty(
        name="Affect Emission",
        description="Apply overlay to emission channel as well",
        default=True
    ) # type: ignore
    
    preserve_original_alpha: BoolProperty(
        name="Preserve Original Alpha",
        description="Keep the original alpha values of materials",
        default=True
    ) # type: ignore

def get_em_type_color(node_type):
    """
    Get color for EM node type based on existing EM material system.
    
    Args:
        node_type: The EM node type (US, USV, etc.)
        
    Returns:
        tuple: RGB color tuple
    """
    # Import the color utility from the main system
    try:
        from ...s3Dgraphy.utils.utils import get_material_color
        color_values = get_material_color(node_type)
        if color_values:
            return color_values[:3]  # Return just RGB, not alpha
    except ImportError:
        pass
    
    # Fallback color mapping if import fails
    color_map = {
        'US': (0.7, 0.7, 0.7),      # Gray
        'USVs': (0.8, 0.6, 0.2),    # Orange
        'USVn': (0.2, 0.6, 0.8),    # Blue
        'VSF': (0.6, 0.8, 0.2),     # Green
        'SF': (0.8, 0.2, 0.6),      # Pink
        'USD': (0.5, 0.3, 0.7),     # Purple
    }
    
    return color_map.get(node_type, (0.5, 0.5, 0.5))  # Default gray

def get_property_color(obj_name, selected_property):
    """
    Get color for object based on property values from visual manager system.
    
    Args:
        obj_name: Name of the object
        selected_property: Currently selected property
        
    Returns:
        tuple: RGB color tuple or None if not found
    """
    scene = bpy.context.scene
    
    if not selected_property or not hasattr(scene, 'property_values'):
        return None
    
    # This would need to integrate with the existing property system
    # For now, return a placeholder
    return (0.5, 0.7, 0.9)  # Light blue

def get_epoch_color(obj_name):
    """
    Get color for object based on its epoch assignment.
    
    Args:
        obj_name: Name of the object
        
    Returns:
        tuple: RGB color tuple or None if not found
    """
    scene = bpy.context.scene
    
    if not hasattr(scene, 'em_list') or not hasattr(scene, 'epoch_list'):
        return None
    
    # Find object in em_list and get its epoch
    for em_item in scene.em_list:
        if em_item.name == obj_name and hasattr(em_item, 'epoch'):
            # Find epoch color
            for epoch in scene.epoch_list:
                if epoch.name == em_item.epoch:
                    if hasattr(epoch, 'epoch_RGB_color'):
                        return tuple(epoch.epoch_RGB_color[:3])
                    break
            break
    
    return None

def get_overlay_color_for_object(obj, settings):
    """
    Get the appropriate overlay color for an object based on current settings.
    
    Args:
        obj: The object to get color for
        settings: Color overlay settings
        
    Returns:
        tuple: RGB color tuple
    """
    if settings.overlay_mode == 'CUSTOM':
        return tuple(settings.custom_overlay_color)
    
    elif settings.overlay_mode == 'EM_TYPE':
        # Get node type from em_list
        scene = bpy.context.scene
        if hasattr(scene, 'em_list'):
            for em_item in scene.em_list:
                if em_item.name == obj.name:
                    node_type = getattr(em_item, 'node_type', 'US')
                    return get_em_type_color(node_type)
        return get_em_type_color('US')  # Default
    
    elif settings.overlay_mode == 'PROPERTY':
        scene = bpy.context.scene
        selected_property = getattr(scene, 'selected_property', None)
        color = get_property_color(obj.name, selected_property)
        return color if color else (0.5, 0.5, 0.5)
    
    elif settings.overlay_mode == 'EPOCH':
        color = get_epoch_color(obj.name)
        return color if color else (0.5, 0.5, 0.5)
    
    return (0.5, 0.5, 0.5)  # Default gray

def apply_color_overlay_to_material(material, overlay_color, settings):
    """
    Apply color overlay to a material using node modifications.
    
    Args:
        material: The material to modify
        overlay_color: RGB color tuple for overlay
        settings: Color overlay settings
    """
    if not material.use_nodes:
        material.use_nodes = True
    
    node_tree = material.node_tree
    
    # Find Principled BSDF and Output nodes
    principled_node = None
    output_node = None
    
    for node in node_tree.nodes:
        if node.type == 'BSDF_PRINCIPLED':
            principled_node = node
        elif node.type == 'OUTPUT_MATERIAL':
            output_node = node
    
    if not principled_node:
        return
    
    # Check if overlay nodes already exist
    existing_overlay_nodes = [node for node in node_tree.nodes if node.name.startswith('OVERLAY_')]
    if existing_overlay_nodes:
        # Update existing overlay color
        for node in existing_overlay_nodes:
            if node.type == 'RGB':
                node.outputs[0].default_value = (*overlay_color, 1.0)
        return
    
    # Create overlay color node
    overlay_color_node = create_node_with_prefix(node_tree, 'ShaderNodeRGB', 'OVERLAY', 'color')
    overlay_color_node.location = (principled_node.location.x - 400, principled_node.location.y + 200)
    overlay_color_node.outputs[0].default_value = (*overlay_color, 1.0)
    
    # Create mix node for blending
    mix_node = create_node_with_prefix(node_tree, 'ShaderNodeMix', 'OVERLAY', 'blend')
    mix_node.location = (principled_node.location.x - 200, principled_node.location.y + 100)
    mix_node.data_type = 'RGBA'
    
    # Set blend mode
    blend_modes = {
        'ADD': 'ADD',
        'MULTIPLY': 'MULTIPLY', 
        'OVERLAY': 'OVERLAY',
        'SCREEN': 'SCREEN',
        'COLOR': 'COLOR'
    }
    mix_node.blend_type = blend_modes.get(settings.blend_mode, 'ADD')
    
    # Set blend factor
    mix_node.inputs['Fac'].default_value = settings.overlay_strength
    
    # Connect overlay color
    links = node_tree.links
    links.new(overlay_color_node.outputs['Color'], mix_node.inputs['Color1'])
    
    # Handle base color connection
    base_color_input = principled_node.inputs['Base Color']
    if base_color_input.is_linked:
        # Disconnect original and connect through mix node
        original_connection = base_color_input.links[0]
        links.remove(original_connection)
        links.new(original_connection.from_socket, mix_node.inputs['Color2'])
    else:
        # Use default base color value
        mix_node.inputs['Color2'].default_value = base_color_input.default_value
    
    # Connect mix result to base color
    links.new(mix_node.outputs['Result'], principled_node.inputs['Base Color'])
    
    # Apply to emission if requested
    if settings.affect_emission:
        emission_input = principled_node.inputs['Emission Color']
        if not emission_input.is_linked:
            # Create another mix node for emission
            emission_mix_node = create_node_with_prefix(node_tree, 'ShaderNodeMix', 'OVERLAY', 'emission_blend')
            emission_mix_node.location = (principled_node.location.x - 200, principled_node.location.y - 100)
            emission_mix_node.data_type = 'RGBA'
            emission_mix_node.blend_type = blend_modes.get(settings.blend_mode, 'ADD')
            emission_mix_node.inputs['Fac'].default_value = settings.overlay_strength * 0.5  # Reduce emission strength
            
            # Connect overlay color and original emission
            links.new(overlay_color_node.outputs['Color'], emission_mix_node.inputs['Color1'])
            emission_mix_node.inputs['Color2'].default_value = emission_input.default_value
            links.new(emission_mix_node.outputs['Result'], emission_input)

class VISUAL_OT_apply_color_overlay(Operator):
    """Apply color overlay to proxy objects"""
    bl_idname = "visual.apply_color_overlay"
    bl_label = "Apply Color Overlay"
    bl_description = "Apply color overlay to proxy objects based on current settings"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        scene = context.scene
        settings = scene.color_overlay_settings
        
        try:
            target_objects = get_em_objects()
            materials_modified = 0
            
            for obj in target_objects:
                if obj.data and obj.data.materials:
                    overlay_color = get_overlay_color_for_object(obj, settings)
                    
                    for material in obj.data.materials:
                        if material:
                            apply_color_overlay_to_material(material, overlay_color, settings)
                            materials_modified += 1
            
            self.report({'INFO'}, f"Applied color overlay to {len(target_objects)} objects, {materials_modified} materials")
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Error applying color overlay: {str(e)}")
            return {'CANCELLED'}

class VISUAL_OT_clear_color_overlay(Operator):
    """Clear color overlays from all objects"""
    bl_idname = "visual.clear_color_overlay"
    bl_label = "Clear Color Overlay"
    bl_description = "Remove color overlays from all objects"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        try:
            materials_modified = 0
            
            for material in bpy.data.materials:
                if not material.use_nodes:
                    continue
                
                # Find and remove overlay nodes
                overlay_nodes = [node for node in material.node_tree.nodes if node.name.startswith('OVERLAY_')]
                
                if overlay_nodes:
                    # Find principled node first
                    principled_node = None
                    for node in material.node_tree.nodes:
                        if node.type == 'BSDF_PRINCIPLED':
                            principled_node = node
                            break
                    
                    if principled_node:
                        # Restore original connections by finding the original source
                        base_color_input = principled_node.inputs['Base Color']
                        emission_input = principled_node.inputs['Emission Color']
                        
                        # Disconnect current connections
                        if base_color_input.is_linked:
                            # Find the original source through the chain
                            current_link = base_color_input.links[0]
                            source_node = current_link.from_node
                            
                            # If source is an overlay mix node, find its original input
                            if source_node.name.startswith('OVERLAY_') and source_node.type == 'MIX':
                                original_input = source_node.inputs['Color2']
                                if original_input.is_linked:
                                    # Reconnect original source directly
                                    material.node_tree.links.new(
                                        original_input.links[0].from_socket,
                                        base_color_input
                                    )
                                else:
                                    # Use default value
                                    base_color_input.default_value = original_input.default_value
                        
                        # Similar process for emission
                        if emission_input.is_linked:
                            current_link = emission_input.links[0]
                            source_node = current_link.from_node
                            
                            if source_node.name.startswith('OVERLAY_') and source_node.type == 'MIX':
                                original_input = source_node.inputs['Color2']
                                if not original_input.is_linked:
                                    # Reset to default
                                    emission_input.default_value = original_input.default_value
                                    # Disconnect
                                    material.node_tree.links.remove(current_link)
                    
                    # Remove overlay nodes
                    for node in overlay_nodes:
                        material.node_tree.nodes.remove(node)
                    
                    materials_modified += 1
            
            self.report({'INFO'}, f"Cleared color overlay from {materials_modified} materials")
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Error clearing color overlay: {str(e)}")
            return {'CANCELLED'}

class VISUAL_OT_update_overlay_colors(Operator):
    """Update overlay colors based on current system state"""
    bl_idname = "visual.update_overlay_colors"
    bl_label = "Update Overlay Colors"
    bl_description = "Update overlay colors to reflect current EM/Property/Epoch settings"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        scene = context.scene
        settings = scene.color_overlay_settings
        
        try:
            # Clear existing overlays and reapply with updated colors
            bpy.ops.visual.clear_color_overlay()
            bpy.ops.visual.apply_color_overlay()
            
            self.report({'INFO'}, "Updated overlay colors")
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Error updating overlay colors: {str(e)}")
            return {'CANCELLED'}

class VISUAL_OT_preview_overlay_color(Operator):
    """Preview overlay color on selected objects"""
    bl_idname = "visual.preview_overlay_color"
    bl_label = "Preview Overlay"
    bl_description = "Preview overlay color on currently selected objects"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        scene = context.scene
        settings = scene.color_overlay_settings
        
        try:
            selected_objects = [obj for obj in context.selected_objects if obj.type == 'MESH']
            
            if not selected_objects:
                self.report({'WARNING'}, "No mesh objects selected")
                return {'CANCELLED'}
            
            materials_modified = 0
            
            for obj in selected_objects:
                if obj.data and obj.data.materials:
                    overlay_color = get_overlay_color_for_object(obj, settings)
                    
                    for material in obj.data.materials:
                        if material:
                            apply_color_overlay_to_material(material, overlay_color, settings)
                            materials_modified += 1
            
            self.report({'INFO'}, f"Previewed overlay on {len(selected_objects)} objects")
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Error previewing overlay: {str(e)}")
            return {'CANCELLED'}

def register_overlay():
    """Register overlay module classes and properties."""
    classes = [
        ColorOverlaySettings,
        VISUAL_OT_apply_color_overlay,
        VISUAL_OT_clear_color_overlay,
        VISUAL_OT_update_overlay_colors,
        VISUAL_OT_preview_overlay_color,
    ]
    
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except ValueError:
            pass
    
    # Add settings to scene
    if not hasattr(bpy.types.Scene, "color_overlay_settings"):
        bpy.types.Scene.color_overlay_settings = bpy.props.PointerProperty(type=ColorOverlaySettings)

def unregister_overlay():
    """Unregister overlay module classes and properties."""
    # Remove scene properties
    if hasattr(bpy.types.Scene, "color_overlay_settings"):
        del bpy.types.Scene.color_overlay_settings
    
    classes = [
        VISUAL_OT_preview_overlay_color,
        VISUAL_OT_update_overlay_colors,
        VISUAL_OT_clear_color_overlay,
        VISUAL_OT_apply_color_overlay,
        ColorOverlaySettings,
    ]
    
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except ValueError:
            pass
