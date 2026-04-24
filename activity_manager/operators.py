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

        # Keep ``filtered_activities`` in sync — empty filter means
        # "no epoch restriction", i.e. every activity is admissible.
        _populate_filtered_activities(
            context.scene.activity_manager, epoch_name="")

        return {'FINISHED'}


def _populate_filtered_activities(activity_manager, epoch_name: str):
    """Clear + refill ``activity_manager.filtered_activities`` with
    the subset of ``activities`` whose ``epoch_name`` equals
    ``epoch_name``. An empty ``epoch_name`` means "no filter" — every
    activity is copied over.
    """
    activity_manager.filtered_activities.clear()
    for item in activity_manager.activities:
        if epoch_name and item.epoch_name != epoch_name:
            continue
        new = activity_manager.filtered_activities.add()
        new.name = item.name
        new.epoch_name = item.epoch_name
        new.description = item.description
        new.y_pos = item.y_pos


class ACTIVITY_OT_filter_by_epoch(Operator):
    """Re-populate ``scene.activity_manager.filtered_activities`` with
    the subset of activities that belong to ``epoch_name``. An empty
    epoch name means "no filter" (every activity shows). Called
    on-demand by the Add-US dialogs — directly as update callback on
    the epoch field, and via the refresh icon next to the picker.
    """
    bl_idname = "activity.filter_by_epoch"
    bl_label = "Filter activities by epoch"
    bl_options = {'INTERNAL'}

    epoch_name: bpy.props.StringProperty(default="")  # type: ignore

    def execute(self, context):
        amgr = getattr(context.scene, 'activity_manager', None)
        if amgr is None:
            return {'CANCELLED'}
        _populate_filtered_activities(amgr, self.epoch_name)
        return {'FINISHED'}


classes = (
    ACTIVITY_OT_refresh_list,
    ACTIVITY_OT_filter_by_epoch,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
