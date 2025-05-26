"""
Label and Camera Tools for Visual Manager
This module contains operators for camera management and label creation.
"""

import bpy
from bpy.types import Operator
from bpy.props import StringProperty, BoolProperty
from bpy_extras.object_utils import world_to_camera_view

from .utils import update_camera_list


class VISUAL_OT_label_creation(Operator):
    """Create labels for objects (Fixed version with proper collection handling)"""
    bl_idname = "visual.label_creation"
    bl_label = "Create labels for objects"
    bl_description = "Create labels for selected objects using the active camera"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        cam = scene.camera
        label_settings = scene.label_settings
        
        # Check if there's an active camera
        if not cam:
            self.report({'ERROR'}, "No active camera found. Please set an active camera first.")
            return {'CANCELLED'}
        
        # Ensure CAMS collection exists
        cams_collection = bpy.data.collections.get("CAMS")
        if not cams_collection:
            cams_collection = bpy.data.collections.new("CAMS")
            context.scene.collection.children.link(cams_collection)
        
        # Move camera to CAMS collection if auto_move_cameras is enabled
        if label_settings.auto_move_cameras:
            # Remove camera from all other collections
            for collection in cam.users_collection:
                if collection != cams_collection:
                    collection.objects.unlink(cam)
            
            # Add to CAMS if not already there
            if cam.name not in cams_collection.objects:
                cams_collection.objects.link(cam)
        
        # Set up label collection name
        label_collection_name = f"generated_labels_{cam.name}"
        
        # Get or create the specific label collection for this camera
        label_collection = bpy.data.collections.get(label_collection_name)
        if not label_collection:
            label_collection = bpy.data.collections.new(label_collection_name)
            # Link to CAMS collection instead of scene collection
            cams_collection.children.link(label_collection)
        
        # Set active layer collection to the label collection
        # Navigate to the correct layer collection
        layer_collections = context.view_layer.layer_collection.children
        
        # Find CAMS layer collection
        cams_layer_collection = None
        for layer_col in layer_collections:
            if layer_col.name == "CAMS":
                cams_layer_collection = layer_col
                break
        
        if cams_layer_collection:
            # Find the specific label collection within CAMS
            for layer_col in cams_layer_collection.children:
                if layer_col.name == label_collection_name:
                    context.view_layer.active_layer_collection = layer_col
                    break
        
        # Get or create label material
        mat = bpy.data.materials.get("_generated.Label")
        if not mat:
            mat = bpy.data.materials.new(name="_generated.Label")
            self.setup_label_material(mat, label_settings)
        else:
            # Update existing material with current settings
            self.setup_label_material(mat, label_settings)
        
        # Get selected objects
        selection = context.selected_objects
        if not selection:
            self.report({'WARNING'}, "No objects selected. Please select objects to create labels for.")
            return {'CANCELLED'}
        
        # Remove old labels for selected objects
        labels_removed = 0
        for obj in selection:
            obj_generated = f'_generated.{cam.name}.{obj.name}'
            if obj_generated in bpy.data.objects:
                old_label = bpy.data.objects[obj_generated]
                bpy.data.objects.remove(old_label, do_unlink=True)
                labels_removed += 1
        
        # Create new labels
        labels_created = 0
        for obj in selection:
            # Create text object
            bpy.ops.object.text_add()
            text_obj = context.object
            
            # Set name and text content
            text_obj.name = f'_generated.{cam.name}.{obj.name}'
            text_obj.data.body = obj.name
            
            # Position label between camera and object
            self.position_label(text_obj, cam, obj, label_settings)
            
            # Assign material
            if text_obj.data.materials:
                text_obj.data.materials[0] = mat
            else:
                text_obj.data.materials.append(mat)
            
            labels_created += 1
        
        # Update camera list
        update_camera_list(context)
        
        # Report results
        if labels_removed > 0:
            self.report({'INFO'}, f"Replaced {labels_removed} existing labels, created {labels_created} new labels")
        else:
            self.report({'INFO'}, f"Created {labels_created} labels for camera '{cam.name}'")
        
        return {'FINISHED'}
    
    def setup_label_material(self, material, label_settings):
        """Set up the label material with BRDF and emission"""
        material.use_nodes = True
        material.node_tree.nodes.clear()
        
        # Create nodes
        links = material.node_tree.links
        nodes = material.node_tree.nodes
        
        # Output node
        output = nodes.new('ShaderNodeOutputMaterial')
        output.location = (300, 0)
        
        # Principled BSDF node
        principled = nodes.new('ShaderNodeBsdfPrincipled')
        principled.location = (0, 0)
        
        # Set base color and emission
        principled.inputs['Base Color'].default_value = (*label_settings.material_color, 1.0)
        principled.inputs['Emission Color'].default_value = (*label_settings.material_color, 1.0)
        principled.inputs['Emission Strength'].default_value = label_settings.emission_strength
        
        # Connect nodes
        links.new(principled.outputs['BSDF'], output.inputs['Surface'])
    
    def position_label(self, text_obj, camera, target_obj, label_settings):
        """Position the label between camera and target object"""
        # Calculate direction from camera to object
        diff_loc = target_obj.location - camera.location
        distance = diff_loc.length
        
        if distance == 0:
            text_obj.location = camera.location
        else:
            # Position at specified distance from camera
            normalized_dir = diff_loc.normalized()
            text_obj.location = camera.location + (normalized_dir * label_settings.label_distance)
        
        # Set rotation to match camera
        text_obj.rotation_euler = camera.rotation_euler
        
        # Set scale
        text_obj.scale = label_settings.label_scale


class VISUAL_OT_center_mass(Operator):
    """Center object origin to mass or cursor"""
    bl_idname = "visual.center_mass"
    bl_label = "Center Mass"
    bl_description = "Center selected objects to mass center or 3D cursor"
    bl_options = {"REGISTER", "UNDO"}

    center_to: StringProperty(default="mass")

    def execute(self, context):
        selection = context.selected_objects
        
        if not selection:
            self.report({'WARNING'}, "No objects selected")
            return {'CANCELLED'}
        
        if self.center_to == "mass":
            for obj in selection:
                obj.select_set(True)
                bpy.ops.object.origin_set(type='ORIGIN_CENTER_OF_MASS')
        elif self.center_to == "cursor":
            bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
        
        return {'FINISHED'}


class VISUAL_OT_label_onoff(Operator):
    """Toggle object name labels on/off"""
    bl_idname = "visual.label_onoff"
    bl_label = "Label on / off"
    bl_description = "Toggle name labels for selected objects"
    bl_options = {"REGISTER", "UNDO"}

    onoff: BoolProperty(default=True)

    def execute(self, context):
        selection = context.selected_objects
        
        if not selection:
            self.report({'WARNING'}, "No objects selected")
            return {'CANCELLED'}
        
        for obj in selection:
            obj.show_name = self.onoff
        
        return {'FINISHED'}


class VISUAL_OT_delete_camera_labels(Operator):
    """Delete all labels for a specific camera"""
    bl_idname = "visual.delete_camera_labels"
    bl_label = "Delete Camera Labels"
    bl_description = "Delete all generated labels for the selected camera"
    bl_options = {'REGISTER', 'UNDO'}
    
    camera_name: StringProperty(
        name="Camera Name",
        description="Name of the camera whose labels to delete"
    )

    def execute(self, context):
        if not self.camera_name:
            # Use active camera if no specific camera name provided
            if context.scene.camera:
                self.camera_name = context.scene.camera.name
            else:
                self.report({'ERROR'}, "No camera specified and no active camera")
                return {'CANCELLED'}
        
        # Find and delete all labels for this camera
        labels_deleted = 0
        objects_to_delete = []
        
        for obj in bpy.data.objects:
            if obj.name.startswith(f'_generated.{self.camera_name}.'):
                objects_to_delete.append(obj)
        
        for obj in objects_to_delete:
            bpy.data.objects.remove(obj, do_unlink=True)
            labels_deleted += 1
        
        # Update camera list
        update_camera_list(context)
        
        self.report({'INFO'}, f"Deleted {labels_deleted} labels for camera '{self.camera_name}'")
        return {'FINISHED'}


class VISUAL_OT_update_camera_list(Operator):
    """Update the camera list"""
    bl_idname = "visual.update_camera_list"
    bl_label = "Update Camera List"
    bl_description = "Refresh the list of cameras in CAMS collection"

    def execute(self, context):
        update_camera_list(context)
        self.report({'INFO'}, "Camera list updated")
        return {'FINISHED'}


class VISUAL_OT_move_camera_to_cams(Operator):
    """Move selected camera to CAMS collection"""
    bl_idname = "visual.move_camera_to_cams"
    bl_label = "Move to CAMS"
    bl_description = "Move the selected camera to CAMS collection"
    bl_options = {'REGISTER', 'UNDO'}
    
    camera_name: StringProperty(
        name="Camera Name",
        description="Name of the camera to move"
    )

    def execute(self, context):
        if not self.camera_name:
            self.report({'ERROR'}, "No camera name specified")
            return {'CANCELLED'}
        
        camera = bpy.data.objects.get(self.camera_name)
        if not camera or camera.type != 'CAMERA':
            self.report({'ERROR'}, f"Camera '{self.camera_name}' not found")
            return {'CANCELLED'}
        
        # Ensure CAMS collection exists
        cams_collection = bpy.data.collections.get("CAMS")
        if not cams_collection:
            cams_collection = bpy.data.collections.new("CAMS")
            context.scene.collection.children.link(cams_collection)
        
        # Remove from other collections
        for collection in camera.users_collection:
            if collection != cams_collection:
                collection.objects.unlink(camera)
        
        # Add to CAMS
        if camera.name not in cams_collection.objects:
            cams_collection.objects.link(camera)
        
        # Update camera list
        update_camera_list(context)
        
        self.report({'INFO'}, f"Moved camera '{self.camera_name}' to CAMS collection")
        return {'FINISHED'}


def register_label_tools():
    """Register label tool classes."""
    classes = [
        VISUAL_OT_label_creation,
        VISUAL_OT_center_mass,
        VISUAL_OT_label_onoff,
        VISUAL_OT_delete_camera_labels,
        VISUAL_OT_update_camera_list,
        VISUAL_OT_move_camera_to_cams,
    ]
    
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except ValueError:
            # Class might already be registered
            pass


def unregister_label_tools():
    """Unregister label tool classes."""
    classes = [
        VISUAL_OT_move_camera_to_cams,
        VISUAL_OT_update_camera_list,
        VISUAL_OT_delete_camera_labels,
        VISUAL_OT_label_onoff,
        VISUAL_OT_center_mass,
        VISUAL_OT_label_creation,
    ]
    
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except ValueError:
            # Class might already be unregistered
            pass