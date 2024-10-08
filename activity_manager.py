import bpy
from bpy.props import (
    StringProperty,
    CollectionProperty,
    IntProperty,
    PointerProperty,
)
from bpy.types import (
    Panel,
    Operator,
    PropertyGroup,
    UIList,
)

# Importa le classi dal tuo modulo
from .S3Dgraphy.graph import Graph
from .S3Dgraphy.node import ActivityNodeGroup, EpochNode
from .S3Dgraphy.import_graphml import GraphMLImporter

from .graph_registry import graph_manager


class ActivityItem(PropertyGroup):
    name: StringProperty(
        name="Nome Attività",
        description="Nome dell'attività",
    )
    epoch_name: StringProperty(
        name="Nome Epoca",
        description="Nome dell'epoca",
    )
    description: StringProperty(
        name="Descrizione",
        description="Descrizione dell'attività",
    )

class ACTIVITY_UL_list(UIList):
    def draw_item(
        self, context, layout, data, item, icon, active_data, active_propname, index
    ):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row()
            row.label(text=item.name, icon='FILE_FOLDER')
            row = layout.row()
            row.label(text=f"Epoch: {item.epoch_name}")
            row = layout.row()
            row.label(text=f"{item.description}")
        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.label(text="")

class ACTIVITY_OT_refresh_list(Operator):
    bl_idname = "activity.refresh_list"
    bl_label = "Aggiorna Lista Attività"
    bl_description = "Aggiorna la lista delle attività dai dati del grafo"

    def execute(self, context):
        graph_data = graph_manager.get_graph()

        context.scene.activity_manager.activities.clear()

        if graph_data is None:
            self.report({'ERROR'}, "Nessun dato del grafo caricato")
            return {'CANCELLED'}

        for node in graph_data.nodes:
            if isinstance(node, ActivityNodeGroup):
                item = context.scene.activity_manager.activities.add()
                item.name = node.name
                # Recupera gli EpochNode connessi all'attività
                #connected_epochs = graph_data.get_connected_epochs(node)

                epoch_node = graph_data.get_connected_epoch_node_by_edge_type(node, "has_first_epoch")
                if epoch_node:
                    print(epoch_node.name)
                    item.epoch_name = epoch_node.name
                else:
                    item.epoch_name = 'Sconosciuta'
                item.description = node.description

        return {'FINISHED'}

class ActivityManagerProperties(PropertyGroup):
    activities: CollectionProperty(type=ActivityItem)
    active_index: IntProperty()

class VIEW3D_PT_activity_manager(Panel):
    bl_label = "Activity Manager"
    bl_idname = "VIEW3D_PT_activity_manager"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'EM'

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        activity_manager = scene.activity_manager


        #row = layout.row()
        #row.operator('activity.refresh_list', text='Aggiorna Lista')

        layout.template_list(
            "ACTIVITY_UL_list", "activity_list",
            activity_manager, "activities",
            activity_manager, "active_index",
        )

classes = (
    ActivityItem,
    ActivityManagerProperties,
    ACTIVITY_UL_list,
    ACTIVITY_OT_refresh_list,
    VIEW3D_PT_activity_manager,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.activity_manager = PointerProperty(type=ActivityManagerProperties)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.activity_manager

if __name__ == "__main__":
    register()
