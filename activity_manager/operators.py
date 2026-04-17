# activity_manager/operators.py

import bpy
from bpy.types import Operator

from s3dgraphy import get_graph
from s3dgraphy.nodes.group_node import ActivityNodeGroup


class ACTIVITY_OT_refresh_list(Operator):
    bl_idname = "activity.refresh_list"
    bl_label = "Aggiorna Lista Attività"
    bl_description = "Aggiorna la lista delle attività dai dati del grafo"

    # Indice del file GraphML selezionato
    graphml_index: bpy.props.IntProperty() # type: ignore

    def execute(self, context):
        em_tools = context.scene.em_tools
        if self.graphml_index < 0:
            return {'CANCELLED'}

        graphml = em_tools.graphml_files[self.graphml_index]
        graph_data = get_graph(graphml.name)

        if graph_data is None:
            self.report({'WARNING'}, f"Nessun grafo trovato con ID: {graphml.name}")
            return {'CANCELLED'}

        context.scene.activity_manager.activities.clear()

        for node in graph_data.nodes:
            if isinstance(node, ActivityNodeGroup):
                item = context.scene.activity_manager.activities.add()
                item.name = node.name

                epoch_node = graph_data.get_connected_epoch_node_by_edge_type(node, "has_first_epoch")
                item.epoch_name = epoch_node.name if epoch_node else 'Sconosciuta'
                item.description = node.description
                item.y_pos = node.attributes.get('y_pos', 0.0)

        return {'FINISHED'}


classes = (
    ACTIVITY_OT_refresh_list,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
