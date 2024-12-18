# /operators/update_graph.py
import bpy
from ..graph_updaters import update_graph_with_scene_data

class EM_OT_update_graph(bpy.types.Operator):
    bl_idname = "em.update_graph"
    bl_label = "Update Graph"
    bl_description = "Update graph with current scene data"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        active_file_index = context.scene.em_tools.active_file_index
        if active_file_index >= 0:
            graphml = context.scene.em_tools.graphml_files[active_file_index]
            if update_graph_with_scene_data(graphml.name):
                self.report({'INFO'}, "Graph updated successfully")
                return {'FINISHED'}
        
        self.report({'ERROR'}, "No active graph to update")
        return {'CANCELLED'}

def register():
    bpy.utils.register_class(EM_OT_update_graph)

def unregister():
    bpy.utils.unregister_class(EM_OT_update_graph)