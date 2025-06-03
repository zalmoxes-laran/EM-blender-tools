"""
Label and Camera Tools for Visual Manager - SAFE VERSION
Questo modulo contiene gli operatori per le label con nomi unici per evitare conflitti.
"""

import bpy
from bpy.types import Operator
from bpy.props import StringProperty, BoolProperty
from bpy_extras.object_utils import world_to_camera_view


def update_camera_list_safe(context):
    """Update the camera list with cameras in CAMS collection - SAFE VERSION"""
    scene = context.scene
    
    # Clear existing camera list
    scene.camera_em_list.clear()
    
    # Get CAMS collection
    cams_collection = bpy.data.collections.get("CAMS")
    if not cams_collection:
        print("CAMS collection not found")
        return
    
    print(f"Found CAMS collection with {len(cams_collection.objects)} objects")
    
    # Find cameras in CAMS collection
    cameras_found = 0
    for obj in cams_collection.objects:
        if obj.type == 'CAMERA':
            print(f"Found camera: {obj.name}")
            # Add to camera list
            item = scene.camera_em_list.add()
            item.name = obj.name
            
            # Count labels for this camera
            label_count = 0
            for label_obj in cams_collection.objects:
                if label_obj.name.startswith(f'_generated.{obj.name}.'):
                    label_count += 1
            
            item.label_count = label_count
            item.has_labels = label_count > 0
            cameras_found += 1
    
    print(f"Added {cameras_found} cameras to camera_em_list")
    
    # Also check for cameras in the scene collection
    scene_cameras = []
    for obj in scene.objects:
        if obj.type == 'CAMERA' and obj.name not in [item.name for item in scene.camera_em_list]:
            scene_cameras.append(obj.name)
    
    if scene_cameras:
        print(f"Found {len(scene_cameras)} cameras outside CAMS collection: {scene_cameras}")


# ====================================================================
# OPERATOR CLASSES - SAFE VERSIONS WITH UNIQUE NAMES
# ====================================================================

class VISUAL_OT_label_creation_safe(Operator):
    """Create labels for objects (Safe version)"""
    bl_idname = "visual.label_creation_safe"
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
        
        print(f"Creating labels with camera: {cam.name}")
        
        # Switch to camera view
        try:
            # Find a 3D view and switch to camera view
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    for space in area.spaces:
                        if space.type == 'VIEW_3D':
                            space.region_3d.view_perspective = 'CAMERA'
                            break
                    break
        except:
            # If we can't switch to camera view, continue anyway
            pass
        
        # Ensure CAMS collection exists
        cams_collection = bpy.data.collections.get("CAMS")
        if not cams_collection:
            cams_collection = bpy.data.collections.new("CAMS")
            context.scene.collection.children.link(cams_collection)
            print("Created CAMS collection")
        
        # Move camera to CAMS collection if auto_move_cameras is enabled
        if label_settings.auto_move_cameras:
            # Remove camera from all other collections
            for collection in cam.users_collection:
                if collection != cams_collection:
                    collection.objects.unlink(cam)
            
            # Add to CAMS if not already there
            if cam.name not in cams_collection.objects:
                cams_collection.objects.link(cam)
                print(f"Moved camera {cam.name} to CAMS collection")
        
        # Set up label collection name
        label_collection_name = f"generated_labels_{cam.name}"
        
        # Get or create the specific label collection for this camera
        label_collection = bpy.data.collections.get(label_collection_name)
        if not label_collection:
            label_collection = bpy.data.collections.new(label_collection_name)
            # Link to CAMS collection instead of scene collection
            cams_collection.children.link(label_collection)
            print(f"Created label collection: {label_collection_name}")
        
        # Set active layer collection to the label collection
        try:
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
        except Exception as e:
            print(f"Warning: Could not set active layer collection: {e}")
        
        # Get or create label material
        mat = bpy.data.materials.get("_generated.Label")
        if not mat:
            mat = bpy.data.materials.new(name="_generated.Label")
            self.setup_label_material(mat, label_settings)
            print("Created label material")
        else:
            # Update existing material with current settings
            self.setup_label_material(mat, label_settings)
        
        # Get selected objects - EXCLUDE CAMERAS
        selection = [obj for obj in context.selected_objects if obj.type != 'CAMERA']
        
        if not selection:
            self.report({'WARNING'}, "No valid objects selected. Cameras are excluded from label creation.")
            return {'CANCELLED'}
        
        print(f"Creating labels for {len(selection)} objects")
        
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
        update_camera_list_safe(context)
        
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


class VISUAL_OT_update_camera_list_safe(Operator):
    """Update the camera list (Safe version)"""
    bl_idname = "visual.update_camera_list_safe"
    bl_label = "Update Camera List"
    bl_description = "Refresh the list of cameras in CAMS collection"

    def execute(self, context):
        try:
            print("Updating camera list...")
            update_camera_list_safe(context)
            
            scene = context.scene
            camera_count = len(scene.camera_em_list)
            self.report({'INFO'}, f"Camera list updated - found {camera_count} cameras")
            return {'FINISHED'}
        except Exception as e:
            print(f"Error updating camera list: {e}")
            self.report({'ERROR'}, f"Error updating camera list: {str(e)}")
            return {'CANCELLED'}


class VISUAL_OT_delete_camera_labels_safe(Operator):
    """Delete all labels for a specific camera (Safe version)"""
    bl_idname = "visual.delete_camera_labels_safe"
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
        update_camera_list_safe(context)
        
        self.report({'INFO'}, f"Deleted {labels_deleted} labels for camera '{self.camera_name}'")
        return {'FINISHED'}


class VISUAL_OT_set_active_camera_safe(Operator):
    """Set the specified camera as active (Safe version)"""
    bl_idname = "visual.set_active_camera_safe"
    bl_label = "Set Active Camera"
    bl_description = "Set the specified camera as the active scene camera"
    bl_options = {'REGISTER', 'UNDO'}
    
    camera_name: StringProperty(
        name="Camera Name",
        description="Name of the camera to set as active"
    )

    def execute(self, context):
        if not self.camera_name:
            self.report({'ERROR'}, "No camera name specified")
            return {'CANCELLED'}
        
        camera = bpy.data.objects.get(self.camera_name)
        if not camera or camera.type != 'CAMERA':
            self.report({'ERROR'}, f"Camera '{self.camera_name}' not found")
            return {'CANCELLED'}
        
        # Set as active camera
        context.scene.camera = camera
        
        self.report({'INFO'}, f"Set '{self.camera_name}' as active camera")
        return {'FINISHED'}


class VISUAL_OT_move_camera_to_cams_safe(Operator):
    """Move selected camera to CAMS collection (Safe version)"""
    bl_idname = "visual.move_camera_to_cams_safe"
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
        update_camera_list_safe(context)
        
        self.report({'INFO'}, f"Moved camera '{self.camera_name}' to CAMS collection")
        return {'FINISHED'}


# ====================================================================
# REGISTRATION
# ====================================================================

def register_label_tools():
    """Register label tool classes with safe names."""
    classes = [
        VISUAL_OT_label_creation_safe,
        VISUAL_OT_update_camera_list_safe,
        VISUAL_OT_delete_camera_labels_safe,
        VISUAL_OT_set_active_camera_safe,
        VISUAL_OT_move_camera_to_cams_safe,
    ]
    
    registered_count = 0
    for cls in classes:
        try:
            # Try to unregister first (in case of reload)
            try:
                bpy.utils.unregister_class(cls)
            except:
                pass
            
            # Register
            bpy.utils.register_class(cls)
            registered_count += 1
            print(f"✓ Registered safe label operator: {cls.__name__}")
        except Exception as e:
            print(f"✗ Failed to register safe label operator {cls.__name__}: {e}")
    
    print(f"Registered {registered_count}/{len(classes)} safe label operators")


def unregister_label_tools():
    """Unregister label tool classes."""
    classes = [
        VISUAL_OT_move_camera_to_cams_safe,
        VISUAL_OT_set_active_camera_safe,
        VISUAL_OT_delete_camera_labels_safe,
        VISUAL_OT_update_camera_list_safe,
        VISUAL_OT_label_creation_safe,
    ]
    
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
            print(f"✓ Unregistered safe label operator: {cls.__name__}")
        except Exception as e:
            print(f"✗ Failed to unregister safe label operator {cls.__name__}: {e}")