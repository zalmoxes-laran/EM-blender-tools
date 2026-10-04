# anastylosis_manager/operators_files.py
"""Open the .blend a fragment is linked from. (Its LOD operators, which lived
beside it in operators_lod.py, are in _dead_code/: U1, the levels are the asset
versions'.)"""

import os
import subprocess

import bpy
from bpy.props import IntProperty
from bpy.types import Operator


class ANASTYLOSIS_OT_open_linked_file(Operator):
    """Open linked .blend file for this anastylosis object in a new Blender instance"""
    bl_idname = "anastylosis.open_linked_file"
    bl_label = "Open Linked File"
    bl_options = {"REGISTER", "UNDO"}

    anastylosis_index: IntProperty(
        name="Anastylosis Index",
        default=-1
    )  # type: ignore

    def execute(self, context):
        anastylosis = context.scene.em_tools.anastylosis
        index = self.anastylosis_index if self.anastylosis_index >= 0 else anastylosis.list_index
        if index < 0 or index >= len(anastylosis.list):
            self.report({'ERROR'}, "No anastylosis item selected")
            return {'CANCELLED'}

        item = anastylosis.list[index]
        obj = bpy.data.objects.get(item.name)
        if not obj:
            self.report({'ERROR'}, f"Object '{item.name}' not found in scene")
            return {'CANCELLED'}

        linked_file = None
        if obj.library:
            linked_file = obj.library.filepath
        elif obj.data and obj.data.library:
            linked_file = obj.data.library.filepath

        if not linked_file:
            self.report({'ERROR'}, f"Object '{obj.name}' is not linked from an external .blend")
            return {'CANCELLED'}

        linked_file = bpy.path.abspath(linked_file)
        if not os.path.exists(linked_file):
            self.report({'ERROR'}, f"Linked file not found: {linked_file}")
            return {'CANCELLED'}

        try:
            subprocess.Popen([bpy.app.binary_path, linked_file])
        except Exception as e:
            self.report({'ERROR'}, f"Failed to open linked file: {str(e)}")
            return {'CANCELLED'}

        self.report({'INFO'}, f"Opened linked file: {linked_file}")
        return {'FINISHED'}


classes = (
    ANASTYLOSIS_OT_open_linked_file,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
