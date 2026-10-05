# export_operators/heriverse/collections_op.py
"""Operator to unhide all collections that contain RM objects (pre-export helper)."""

import bpy
from bpy.types import Operator

from .utils import find_layer_collection


class HERIVERSE_OT_make_collections_visible(Operator):
    bl_idname = "heriverse.make_collections_visible"
    bl_label = "Make Collections Visible"
    bl_description = "Make all collections containing RM objects visible"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        rm_objects = [obj for obj in bpy.data.objects if len(obj.EM_ep_belong_ob) > 0]

        for obj in rm_objects:
            for collection in bpy.data.collections:
                if obj.name in collection.objects:
                    layer_collection = find_layer_collection(context.view_layer.layer_collection, collection.name)
                    if layer_collection:
                        layer_collection.exclude = False

        self.report({'INFO'}, "All collections containing RM objects are now visible")
        return {'FINISHED'}


classes = (
    HERIVERSE_OT_make_collections_visible,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
