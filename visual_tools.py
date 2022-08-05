# Script to automatically generate labels for all objects in the scene and position them in the camera view
# Generated labels are prefixed with '_generated.' and replaced each time the script is run.
# Note that any objects with name that happens to start with '_generated.' will be automatically deleted!
#
# This script will automatically create a material named '_generated.Label' and assign it to all generated labels.
# The generated material can be modified to affect the appearance of the labels.

import bpy
from bpy_extras.object_utils import world_to_camera_view


class EM_label_creation(bpy.types.Operator):

    """Create labels for objects"""
    bl_idname = "label.creation"
    bl_label = "Create labels for objects"
    bl_description = "Create labels for objects"
    bl_options = {'REGISTER', 'UNDO'}

    #group_em_idx: IntProperty()

    def execute(self, context):
        context = bpy.context
        scn = bpy.context.scene
        cam = scn.camera
        label_collection = "generated_labels_"+cam.name

        # Pickup the label material if it exists
        mat = bpy.data.materials.get("_generated.Label")

        if mat is None:
            # Material doesn't exist, create it
            mat = bpy.data.materials.new(name="_generated.Label")

        #current_collection_layer_col = context.view_layer.active_layer_collection
        #current_collection = bpy.data.collections.get(current_collection_layer_col.name)

        base_collection = context.scene.collection#.name 

        # Pickup the collection layer if exists

        collection_generated_label = bpy.data.collections.get(label_collection)

        if collection_generated_label is None:
            # Collection doesn't exist, create it
            collection_generated_label = bpy.data.collections.new(
                label_collection)
            collection_generated_label.name = label_collection
#            bpy.data.collections[0].children.link(
#                bpy.data.collections["generated_labels"])

            base_collection.children.link(
                bpy.data.collections[label_collection])

            context.scene.collection.children.link(collection_generated_label)

        # activate collection
        context.view_layer.active_layer_collection = bpy.context.scene.view_layers[0].layer_collection.children[label_collection]

        selection = context.selected_objects
        #bpy.ops.object.select_all(action='DESELECT')
        
        # get a list of objects in scene
        ob_in_scene = []
        for ob_generated in bpy.data.objects:
            if ob_generated.name.startswith('_generated.'):
                ob_in_scene.append(ob_generated.name)

        for obj in selection:
            obj_generated = '_generated.'+cam.name+'.'+obj.name
            if obj_generated in ob_in_scene:
                # Delete the old label
                obj_label_to_remove = bpy.data.objects[obj_generated]
                bpy.data.objects.remove(obj_label_to_remove, do_unlink=True)
            # Create a new label
            bpy.ops.object.text_add()
            tobj = bpy.context.object

            # Set the name of the label to include the prefix so we can identify them and set the text
            tobj.name = '_generated.'+cam.name+'.'+obj.name
            tobj.data.body = obj.name

            # Position the label between the camera and the object
            diffloc = obj.location - cam.location
            dist = (diffloc[0]**2 + diffloc[1]**2 + diffloc[2]**2)**0.5
            if dist == 0:
                tobj.location = cam.location
            else:
                # 1.0 blender unit from the camera
                tobj.location = cam.location + (diffloc / dist * 1.0)

            # Set the rotation the same as the camera and scale it appropriate to the distance
            tobj.rotation_euler = cam.rotation_euler
            tobj.scale = (0.03, 0.03, 0.03)

            # Assign material to object
            if tobj.data.materials:
                # assign to 1st material slot
                tobj.data.materials[0] = mat
            else:
                # no slots
                tobj.data.materials.append(mat)

        return {'FINISHED'}



