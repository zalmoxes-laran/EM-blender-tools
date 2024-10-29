import bpy # type: ignore
from bpy.props import ( # type: ignore
    StringProperty,
    CollectionProperty,
    IntProperty,
    PointerProperty,
    FloatProperty,  # Aggiungi questo import

)
from bpy.types import (# type: ignore
    Panel,
    Operator,
    PropertyGroup,
    UIList,
)

# Importa le classi dal tuo modulo
from .s3Dgraphy.nodes.group_node import ActivityNodeGroup
from .s3Dgraphy.nodes.epoch_node import EpochNode
from .s3Dgraphy.importer import GraphMLImporter
from .s3Dgraphy.nodes.stratigraphic_node import StratigraphicNode

from .s3Dgraphy import get_graph


class ActivityItem(PropertyGroup):
    name: StringProperty(
        name="Nome Attività",
        description="Nome dell'attività",
    ) # type: ignore
    epoch_name: StringProperty(
        name="Nome Epoca",
        description="Nome dell'epoca",
    ) # type: ignore
    description: StringProperty(
        name="Descrizione",
        description="Descrizione dell'attività",
    ) # type: ignore
    y_pos: FloatProperty(
        name="Posizione Y",
        description="Posizione Y del nodo",
    ) # type: ignore

class ACTIVITY_UL_list(UIList):
    def draw_item(
        self, context, layout, data, item, icon, active_data, active_propname, index
    ):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            layout.label(text=item.name, icon='FILE_FOLDER')
            layout.label(text=f"Epoch: {item.epoch_name}")
            layout.label(text=f"{item.description}")
            #layout.label(text=f"{item.y_pos}")
        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.label(text="")


class ACTIVITY_OT_refresh_list(Operator):
    bl_idname = "activity.refresh_list"
    bl_label = "Aggiorna Lista Attività"
    bl_description = "Aggiorna la lista delle attività dai dati del grafo"

    # Aggiungiamo una proprietà per passare l'indice del file GraphML selezionato
    graphml_index: bpy.props.IntProperty() # type: ignore

    def execute(self, context):
        em_tools = context.scene.em_tools
        if self.graphml_index >= 0:
            graphml = em_tools.graphml_files[self.graphml_index]
            
            graph_data = get_graph(graphml.name)
            print("Eseguo l'update della lista delle attività")
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
                    print(f"Provo a cercare un nodo epoca per il nodo {node.name}")
                    epoch_node = graph_data.get_connected_epoch_node_by_edge_type(node, "has_first_epoch")
                    if epoch_node:
                        #print(epoch_node.name)
                        item.epoch_name = epoch_node.name
                    else:
                        item.epoch_name = 'Sconosciuta'
                    item.description = node.description
                    item.y_pos = node.attributes.get('y_pos', 0.0)

        return {'FINISHED'}

class ActivityManagerProperties(PropertyGroup):
    activities: CollectionProperty(type=ActivityItem) # type: ignore
    active_index: IntProperty() # type: ignore

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
