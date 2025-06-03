"""
Clipping Section Module
This module creates clipping planes and volumes that render transparent everything
beyond the clipping boundary, with colored internal sections.
"""

import bpy
import bmesh
from mathutils import Vector, Matrix
from bpy.types import Operator, PropertyGroup
from bpy.props import FloatProperty, BoolProperty, EnumProperty, FloatVectorProperty

from .utils import create_node_with_prefix, get_em_objects

class ClippingSettings(PropertyGroup):
    """Settings for clipping system"""
    
    section_color: FloatVectorProperty(
        name="Section Color",
        description="Color for internal clipping sections",
        subtype='COLOR',
        size=3,
        min=0.0,
        max=1.0,
        default=(0.4, 0.2, 0.6)  # Prugna/Purple
    ) # type: ignore
    
    clipping_distance: FloatProperty(
        name="Clipping Distance",
        description="Distance from clipping plane/volume",
        min=0.1,
        max=100.0,
        default=10.0,
        unit='LENGTH'
    ) # type: ignore
    
    use_camera_clipping: BoolProperty(
        name="Use Camera Clipping",
        description="Generate clipping plane from active camera view",
        default=False
    ) # type: ignore
    
    affect_all_objects: BoolProperty(
        name="Affect All Objects",
        description="Apply clipping to all visible objects, not just EM objects",
        default=False
    ) # type: ignore
    
    clipping_mode: EnumProperty(
        name="Clipping Mode",
        description="Type of clipping to apply",
        items=[
            ('PLANE', "Plane", "Single clipping plane"),
            ('BOX', "Box Volume", "Box-shaped clipping volume"),
            ('SPHERE', "Sphere Volume", "Spherical clipping volume"),
            ('CUSTOM', "Custom Volume", "Use selected object as clipping volume")
        ],
        default='PLANE'
    ) # type: ignore
    
    auto_update_clipping: BoolProperty(
        name="Auto Update",
        description="Automatically update clipping when volume objects move",
        default=False
    ) # type: ignore

def create_clipping_material_nodes(material, clipping_object, settings):
    """
    Create clipping material nodes for a material.
    
    Args:
        material: The material to modify
        clipping_object: The object used for clipping reference
        settings: Clipping settings
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
    
    if not principled_node or not output_node:
        return
    
    # Check if clipping nodes already exist
    existing_clip_nodes = [node for node in node_tree.nodes if node.name.startswith('CLIP_')]
    if existing_clip_nodes:
        # Update existing nodes instead of creating new ones
        return
    
    # Create coordinate and mapping nodes for clipping
    coord_node = create_node_with_prefix(node_tree, 'ShaderNodeTexCoord', 'CLIP', 'coordinates')
    coord_node.location = (principled_node.location.x - 800, principled_node.location.y)
    
    mapping_node = create_node_with_prefix(node_tree, 'ShaderNodeMapping', 'CLIP', 'mapping')
    mapping_node.location = (principled_node.location.x - 600, principled_node.location.y)
    
    # Create gradient texture for clipping effect
    gradient_node = create_node_with_prefix(node_tree, 'ShaderNodeTexGradient', 'CLIP', 'gradient')
    gradient_node.location = (principled_node.location.x - 400, principled_node.location.y)
    gradient_node.gradient_type = 'LINEAR'
    
    # Create ColorRamp for controlling clipping threshold
    colorramp_node = create_node_with_prefix(node_tree, 'ShaderNodeValToRGB', 'CLIP', 'threshold')
    colorramp_node.location = (principled_node.location.x - 200, principled_node.location.y + 100)
    
    # Configure ColorRamp for sharp clipping
    colorramp = colorramp_node.color_ramp
    colorramp.elements[0].position = 0.5  # Clipping threshold
    colorramp.elements[0].color = (0, 0, 0, 0)  # Transparent
    colorramp.elements[1].position = 0.51
    colorramp.elements[1].color = (1, 1, 1, 1)  # Opaque
    
    # Create section color node
    section_color_node = create_node_with_prefix(node_tree, 'ShaderNodeRGB', 'CLIP', 'section_color')
    section_color_node.location = (principled_node.location.x - 200, principled_node.location.y - 100)
    section_color_node.outputs[0].default_value = (*settings.section_color, 1.0)
    
    # Create mix node for blending section color
    mix_node = create_node_with_prefix(node_tree, 'ShaderNodeMix', 'CLIP', 'color_mix')
    mix_node.location = (principled_node.location.x - 100, principled_node.location.y)
    mix_node.data_type = 'RGBA'
    mix_node.blend_type = 'MIX'
    
    # Create transparency control
    trans_node = create_node_with_prefix(node_tree, 'ShaderNodeMath', 'CLIP', 'transparency')
    trans_node.location = (principled_node.location.x - 100, principled_node.location.y - 200)
    trans_node.operation = 'MULTIPLY'
    
    # Connect nodes
    links = node_tree.links
    
    # Coordinate flow
    links.new(coord_node.outputs['Object'], mapping_node.inputs['Vector'])
    links.new(mapping_node.outputs['Vector'], gradient_node.inputs['Vector'])
    links.new(gradient_node.outputs['Fac'], colorramp_node.inputs['Fac'])
    
    # Color mixing
    links.new(colorramp_node.outputs['Color'], mix_node.inputs['Fac'])
    links.new(section_color_node.outputs['Color'], mix_node.inputs['Color1'])
    
    # Get original base color input
    original_base_color = principled_node.inputs['Base Color']
    if original_base_color.is_linked:
        # If base color is connected, mix with section color
        links.new(original_base_color.links[0].from_socket, mix_node.inputs['Color2'])
        links.new(mix_node.outputs['Result'], principled_node.inputs['Base Color'])
    else:
        # If base color is not connected, use default value
        mix_node.inputs['Color2'].default_value = original_base_color.default_value
        links.new(mix_node.outputs['Result'], principled_node.inputs['Base Color'])
    
    # Transparency control
    links.new(colorramp_node.outputs['Alpha'], trans_node.inputs[0])
    trans_node.inputs[1].default_value = 1.0  # Multiplier
    links.new(trans_node.outputs['Value'], principled_node.inputs['Alpha'])
    
    # Set material blend mode
    material.blend_method = 'BLEND'
    material.show_transparent_back = False

def setup_clipping_object_transform(clipping_object, settings):
    """
    Setup the clipping object transform based on current camera or user settings.
    
    Args:
        clipping_object: The object to use for clipping
        settings: Clipping settings
    """
    scene = bpy.context.scene
    
    if settings.use_camera_clipping and scene.camera:
        # Position clipping object based on camera
        camera = scene.camera
        
        # Set location at camera position + forward direction * distance
        forward = camera.matrix_world.to_quaternion() @ Vector((0, 0, -1))
        clipping_object.location = camera.location + forward * settings.clipping_distance
        
        # Match camera rotation
        clipping_object.rotation_euler = camera.rotation_euler

def create_clipping_volume(settings):
    """
    Create a clipping volume object based on settings.
    
    Args:
        settings: Clipping settings
        
    Returns:
        bpy.types.Object: Created clipping volume object
    """
    bpy.ops.object.select_all(action='DESELECT')
    
    if settings.clipping_mode == 'PLANE':
        # Create a plane
        bpy.ops.mesh.primitive_plane_add(size=2)
        clipping_object = bpy.context.active_object
        clipping_object.name = "CLIP_Plane"
        
    elif settings.clipping_mode == 'BOX':
        # Create a cube
        bpy.ops.mesh.primitive_cube_add(size=2)
        clipping_object = bpy.context.active_object
        clipping_object.name = "CLIP_Box"
        
    elif settings.clipping_mode == 'SPHERE':
        # Create a sphere
        bpy.ops.mesh.primitive_uv_sphere_add(radius=1)
        clipping_object = bpy.context.active_object
        clipping_object.name = "CLIP_Sphere"
        
    else:  # CUSTOM
        # Use selected object as clipping volume
        clipping_object = bpy.context.active_object
        if not clipping_object:
            return None
    
    # Setup transform
    setup_clipping_object_transform(clipping_object, settings)
    
    # Make it display as wireframe
    clipping_object.display_type = 'WIRE'
    
    # Add to CAMS collection if it exists (for organization)
    cams_collection = bpy.data.collections.get("CAMS")
    if cams_collection:
        # Remove from scene collection
        bpy.context.scene.collection.objects.unlink(clipping_object)
        # Add to CAMS collection
        cams_collection.objects.link(clipping_object)
    
    return clipping_object

class VISUAL_OT_create_clipping_volume(Operator):
    """Create a clipping volume for section visualization"""
    bl_idname = "visual.create_clipping_volume"
    bl_label = "Create Clipping Volume"
    bl_description = "Create a new clipping volume for section visualization"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        scene = context.scene
        settings = scene.clipping_settings
        
        try:
            clipping_object = create_clipping_volume(settings)
            
            if not clipping_object:
                self.report({'ERROR'}, "Failed to create clipping volume")
                return {'CANCELLED'}
            
            self.report({'INFO'}, f"Created clipping volume: {clipping_object.name}")
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Error creating clipping volume: {str(e)}")
            return {'CANCELLED'}

class VISUAL_OT_apply_clipping_effect(Operator):
    """Apply clipping effect to selected or EM objects"""
    bl_idname = "visual.apply_clipping_effect"
    bl_label = "Apply Clipping Effect"
    bl_description = "Apply clipping effect to objects using the active clipping volume"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        scene = context.scene
        settings = scene.clipping_settings
        
        try:
            # Find clipping object
            clipping_objects = [obj for obj in scene.objects if obj.name.startswith('CLIP_')]
            
            if not clipping_objects:
                self.report({'ERROR'}, "No clipping volume found. Create one first.")
                return {'CANCELLED'}
            
            clipping_object = clipping_objects[0]  # Use first found
            
            # Get target objects
            if settings.affect_all_objects:
                target_objects = [obj for obj in scene.objects if obj.type == 'MESH' and not obj.name.startswith('CLIP_')]
            else:
                target_objects = get_em_objects()
            
            materials_modified = 0
            
            for obj in target_objects:
                if obj.data and obj.data.materials:
                    for material in obj.data.materials:
                        if material:
                            create_clipping_material_nodes(material, clipping_object, settings)
                            materials_modified += 1
            
            self.report({'INFO'}, f"Applied clipping effect to {len(target_objects)} objects, {materials_modified} materials")
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Error applying clipping effect: {str(e)}")
            return {'CANCELLED'}

class VISUAL_OT_clear_clipping_effect(Operator):
    """Clear clipping effects from all objects"""
    bl_idname = "visual.clear_clipping_effect"
    bl_label = "Clear Clipping Effect"
    bl_description = "Remove clipping effects from all objects"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        try:
            materials_modified = 0
            
            for material in bpy.data.materials:
                if not material.use_nodes:
                    continue
                
                # Find and remove clipping nodes
                clip_nodes = [node for node in material.node_tree.nodes if node.name.startswith('CLIP_')]
                
                if clip_nodes:
                    for node in clip_nodes:
                        material.node_tree.nodes.remove(node)
                    
                    # Restore material settings
                    material.blend_method = 'OPAQUE'
                    
                    # Find Principled BSDF and reset alpha
                    for node in material.node_tree.nodes:
                        if node.type == 'BSDF_PRINCIPLED':
                            node.inputs['Alpha'].default_value = 1.0
                            break
                    
                    materials_modified += 1
            
            self.report({'INFO'}, f"Cleared clipping effects from {materials_modified} materials")
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Error clearing clipping effects: {str(e)}")
            return {'CANCELLED'}

class VISUAL_OT_delete_clipping_volumes(Operator):
    """Delete all clipping volume objects"""
    bl_idname = "visual.delete_clipping_volumes"
    bl_label = "Delete Clipping Volumes"
    bl_description = "Delete all clipping volume objects from the scene"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        scene = context.scene
        
        try:
            clipping_objects = [obj for obj in scene.objects if obj.name.startswith('CLIP_')]
            deleted_count = len(clipping_objects)
            
            for obj in clipping_objects:
                bpy.data.objects.remove(obj, do_unlink=True)
            
            self.report({'INFO'}, f"Deleted {deleted_count} clipping volumes")
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Error deleting clipping volumes: {str(e)}")
            return {'CANCELLED'}

class VISUAL_OT_create_camera_clipping_plane(Operator):
    """Create a clipping plane from the current camera view"""
    bl_idname = "visual.create_camera_clipping_plane"
    bl_label = "Create Camera Clipping Plane"
    bl_description = "Create a clipping plane positioned from the active camera viewpoint"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        scene = context.scene
        
        if not scene.camera:
            self.report({'ERROR'}, "No active camera found")
            return {'CANCELLED'}
        
        try:
            # Temporarily set clipping mode to plane and enable camera clipping
            settings = scene.clipping_settings
            old_mode = settings.clipping_mode
            old_camera_setting = settings.use_camera_clipping
            
            settings.clipping_mode = 'PLANE'
            settings.use_camera_clipping = True
            
            # Create the clipping volume
            clipping_object = create_clipping_volume(settings)
            
            # Restore original settings
            settings.clipping_mode = old_mode
            settings.use_camera_clipping = old_camera_setting
            
            if clipping_object:
                self.report({'INFO'}, f"Created camera clipping plane: {clipping_object.name}")
                return {'FINISHED'}
            else:
                self.report({'ERROR'}, "Failed to create camera clipping plane")
                return {'CANCELLED'}
                
        except Exception as e:
            self.report({'ERROR'}, f"Error creating camera clipping plane: {str(e)}")
            return {'CANCELLED'}

def register_clipping():
    """Register clipping module classes and properties."""
    classes = [
        ClippingSettings,
        VISUAL_OT_create_clipping_volume,
        VISUAL_OT_apply_clipping_effect,
        VISUAL_OT_clear_clipping_effect,
        VISUAL_OT_delete_clipping_volumes,
        VISUAL_OT_create_camera_clipping_plane,
    ]
    
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except ValueError:
            pass
    
    # Add settings to scene
    if not hasattr(bpy.types.Scene, "clipping_settings"):
        bpy.types.Scene.clipping_settings = bpy.props.PointerProperty(type=ClippingSettings)

def unregister_clipping():
    """Unregister clipping module classes and properties."""
    # Remove scene properties
    if hasattr(bpy.types.Scene, "clipping_settings"):
        del bpy.types.Scene.clipping_settings
    
    classes = [
        VISUAL_OT_create_camera_clipping_plane,
        VISUAL_OT_delete_clipping_volumes,
        VISUAL_OT_clear_clipping_effect,
        VISUAL_OT_apply_clipping_effect,
        VISUAL_OT_create_clipping_volume,
        ClippingSettings,
    ]
    
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except ValueError:
            pass
