import bpy
from bpy.props import (
    StringProperty,
    BoolProperty,
    CollectionProperty,
    IntProperty,
    PointerProperty,
    FloatVectorProperty,
)
from bpy.types import (
    Panel,
    Operator,
    PropertyGroup,
    UIList,
)

from .s3Dgraphy import get_graph
from .s3Dgraphy.nodes.representation_model_node import RepresentationModelNode

# Classe PropertyGroup per rappresentare un modello RM nella lista
class RMItem(PropertyGroup):
    """Properties for RM models in the list"""
    name: StringProperty(
        name="Name",
        description="Name of the RM model",
        default="Unnamed"
    )
    first_epoch: StringProperty(
        name="First Epoch",
        description="First epoch this RM belongs to",
        default=""
    )
    is_publishable: BoolProperty(
        name="Publishable",
        description="Whether this RM model is publishable",
        default=True
    )
    node_id: StringProperty(
        name="Node ID",
        description="ID of the RM node in the graph",
        default=""
    )
    object_exists: BoolProperty(
        name="Object Exists",
        description="Whether the object exists in the scene",
        default=False
    )

# UI List per mostrare i modelli RM
class RM_UL_List(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            # Oggetto esiste in scena?
            obj_icon = 'OBJECT_DATA' if item.object_exists else 'ERROR'
            
            # Split layout for better control
            row = layout.row(align=True)
            
            # Nome del modello RM
            row.prop(item, "name", text="", emboss=False, icon=obj_icon)
            
            # Epoca di appartenenza
            if item.first_epoch == "no_epoch":
                row.label(text="[No Epoch]", icon='TIME')
            else:
                row.label(text=item.first_epoch, icon='TIME')
            
            # Flag pubblicabile
            row.prop(item, "is_publishable", text="", icon='EXPORT' if item.is_publishable else 'CANCEL')
            
        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.label(text="", icon=obj_icon)

# Operatore per aggiornare la lista dei modelli RM
class RM_OT_update_list(Operator):
    bl_idname = "rm.update_list"
    bl_label = "Update RM List"
    bl_description = "Update the list of RM models from the current graph"
    
    def execute(self, context):
        scene = context.scene
        rm_list = scene.rm_list
        
        # Salva l'indice corrente per ripristinarlo dopo l'aggiornamento
        current_index = scene.rm_list_index
        
        # Cancella la lista attuale
        rm_list.clear()
        
        # Ottieni il grafo attivo
        graph = None
        if context.scene.em_tools.active_file_index >= 0:
            graphml = context.scene.em_tools.graphml_files[context.scene.em_tools.active_file_index]
            graph = get_graph(graphml.name)
        
        if not graph:
            self.report({'ERROR'}, "No active graph available")
            return {'CANCELLED'}
        
        # Trova tutti i nodi RM nel grafo
        rm_nodes = [node for node in graph.nodes if node.node_type == "representation_model"]
        
        # Prepara un dizionario per tracciare oggetti già aggiunti
        added_objects = {}
        
        # Popola la lista con i nodi RM trovati
        for node in rm_nodes:
            # Estrai il nome dell'oggetto dal node_id (rimuovendo il suffisso "_model")
            obj_name = node.name.replace(" Model for ", "").replace("Model for ", "")
            
            # Verifica se l'oggetto esiste nella scena
            obj_exists = obj_name in bpy.data.objects
            
            # Trova la prima epoca associata
            first_epoch = "no_epoch"
            for edge in graph.edges:
                if edge.edge_source == node.node_id and edge.edge_type == "has_representation_model":
                    epoch_node = graph.find_node_by_id(edge.edge_target)
                    if epoch_node and epoch_node.node_type == "epoch":
                        first_epoch = epoch_node.name
                        break
            
            # Aggiungi alla lista
            if obj_name not in added_objects:
                item = rm_list.add()
                item.name = obj_name
                item.first_epoch = first_epoch
                item.node_id = node.node_id
                item.object_exists = obj_exists
                item.is_publishable = True  # Default a True, può essere modificato dall'utente
                added_objects[obj_name] = True
        
        # Ripristina l'indice se possibile, altrimenti imposta a 0
        scene.rm_list_index = min(current_index, len(rm_list)-1) if rm_list else 0
        
        self.report({'INFO'}, f"Found {len(rm_list)} RM models in the graph")
        return {'FINISHED'}

# Operatore per promuovere oggetti selezionati a RM
class RM_OT_promote_to_rm(Operator):
    bl_idname = "rm.promote_to_rm"
    bl_label = "Promote to RM"
    bl_description = "Promote selected objects to RM models"
    
    def execute(self, context):
        scene = context.scene
        selected_objects = [obj for obj in context.selected_objects if obj.type == 'MESH']
        
        if not selected_objects:
            self.report({'ERROR'}, "No mesh objects selected")
            return {'CANCELLED'}
        
        # Ottieni il grafo attivo
        graph = None
        if context.scene.em_tools.active_file_index >= 0:
            graphml = context.scene.em_tools.graphml_files[context.scene.em_tools.active_file_index]
            graph = get_graph(graphml.name)
        
        if not graph:
            self.report({'ERROR'}, "No active graph available")
            return {'CANCELLED'}
        
        # Conta quanti oggetti sono stati promossi
        created_count = 0
        
        for obj in selected_objects:
            model_node_id = f"{obj.name}_model"
            model_node = graph.find_node_by_id(model_node_id)
            
            # Se il nodo non esiste, crealo
            if not model_node:
                model_node = RepresentationModelNode(
                    node_id=model_node_id,
                    name=f"Model for {obj.name}",
                    type="RM",
                    url=f"models/{obj.name}.gltf"
                )
                graph.add_node(model_node)
                created_count += 1
                
                # Crea una entry "no_epoch" se l'oggetto non ha epoche associate
                if len(obj.EM_ep_belong_ob) == 0:
                    obj.EM_ep_belong_ob.add()
                    obj.EM_ep_belong_ob[0].epoch = "no_epoch"
                
                # Altrimenti, usa la prima epoca associata all'oggetto
                # Non creiamo edges qui, lo farà update_graph_with_scene_data
        
        # Aggiorna la lista dopo la promozione
        bpy.ops.rm.update_list()
        
        self.report({'INFO'}, f"Promoted {created_count} objects to RM models")
        return {'FINISHED'}

# Operatore per demote oggetti selezionati da RM
class RM_OT_demote_from_rm(Operator):
    bl_idname = "rm.demote_from_rm"
    bl_label = "Demote from RM"
    bl_description = "Demote selected objects from RM models"
    
    def execute(self, context):
        scene = context.scene
        selected_objects = [obj for obj in context.selected_objects if obj.type == 'MESH']
        
        if not selected_objects:
            self.report({'ERROR'}, "No mesh objects selected")
            return {'CANCELLED'}
        
        # Ottieni il grafo attivo
        graph = None
        if context.scene.em_tools.active_file_index >= 0:
            graphml = context.scene.em_tools.graphml_files[context.scene.em_tools.active_file_index]
            graph = get_graph(graphml.name)
        
        if not graph:
            self.report({'ERROR'}, "No active graph available")
            return {'CANCELLED'}
        
        # Conta quanti oggetti sono stati rimossi
        removed_count = 0
        
        for obj in selected_objects:
            model_node_id = f"{obj.name}_model"
            model_node = graph.find_node_by_id(model_node_id)
            
            # Se il nodo esiste, rimuovilo e tutti i suoi edge
            if model_node:
                # Trova e rimuovi tutti gli edge associati al nodo
                edges_to_remove = []
                for edge in graph.edges:
                    if edge.edge_source == model_node_id or edge.edge_target == model_node_id:
                        edges_to_remove.append(edge.edge_id)
                
                # Rimuovi gli edge
                for edge_id in edges_to_remove:
                    graph.remove_edge(edge_id)
                
                # Rimuovi il nodo
                graph.remove_node(model_node_id)
                
                # Rimuovi tutte le epoche associate dall'oggetto
                while len(obj.EM_ep_belong_ob) > 0:
                    obj.EM_ep_belong_ob.remove(0)
                
                removed_count += 1
        
        # Aggiorna la lista dopo la rimozione
        bpy.ops.rm.update_list()
        
        self.report({'INFO'}, f"Demoted {removed_count} objects from RM models")
        return {'FINISHED'}

# Operatore per selezionare l'oggetto RM dalla lista
class RM_OT_select_from_list(Operator):
    bl_idname = "rm.select_from_list"
    bl_label = "Select RM Object"
    bl_description = "Select the RM object in the 3D view"
    
    def execute(self, context):
        scene = context.scene
        
        if scene.rm_list_index >= 0 and scene.rm_list:
            item = scene.rm_list[scene.rm_list_index]
            
            # Deseleziona tutti gli oggetti
            bpy.ops.object.select_all(action='DESELECT')
            
            # Se l'oggetto esiste, selezionalo
            obj = bpy.data.objects.get(item.name)
            if obj:
                obj.select_set(True)
                # Imposta l'oggetto attivo
                context.view_layer.objects.active = obj
                
                # Zoom sull'oggetto se l'opzione è abilitata
                if scene.rm_settings.zoom_to_selected:
                    # Zoom solo se sei in una vista 3D
                    for area in bpy.context.screen.areas:
                        if area.type == 'VIEW_3D':
                            ctx = bpy.context.copy()
                            ctx['area'] = area
                            ctx['region'] = area.regions[-1]
                            bpy.ops.view3d.view_selected(ctx)
                            break
                
                self.report({'INFO'}, f"Selected object: {item.name}")
                return {'FINISHED'}
            else:
                self.report({'ERROR'}, f"Object not found in scene: {item.name}")
                return {'CANCELLED'}
        
        self.report({'ERROR'}, "No item selected in the list")
        return {'CANCELLED'}

# Operatore per aggiornare lo stato di pubblicazione
class RM_OT_toggle_publishable(Operator):
    bl_idname = "rm.toggle_publishable"
    bl_label = "Toggle Publishable"
    bl_description = "Toggle the publishable status of the selected RM model"
    
    def execute(self, context):
        scene = context.scene
        
        if scene.rm_list_index >= 0 and scene.rm_list:
            item = scene.rm_list[scene.rm_list_index]
            item.is_publishable = not item.is_publishable
            
            # Aggiorna l'attributo nel nodo RM del grafo se necessario
            graph = None
            if context.scene.em_tools.active_file_index >= 0:
                graphml = context.scene.em_tools.graphml_files[context.scene.em_tools.active_file_index]
                graph = get_graph(graphml.name)
            
            if graph:
                rm_node = graph.find_node_by_id(item.node_id)
                if rm_node:
                    # Aggiorna l'attributo del nodo
                    rm_node.attributes['is_publishable'] = item.is_publishable
            
            self.report({'INFO'}, f"Set {item.name} publishable status to {item.is_publishable}")
            return {'FINISHED'}
        
        self.report({'ERROR'}, "No item selected in the list")
        return {'CANCELLED'}

# Classe per le impostazioni del RM Manager
class RMSettings(PropertyGroup):
    zoom_to_selected: BoolProperty(
        name="Zoom to Selected",
        description="Zoom to the selected object when clicked in the list",
        default=True
    )

# Il pannello principale RM Manager
class VIEW3D_PT_RM_Manager(Panel):
    bl_label = "RM Manager"
    bl_idname = "VIEW3D_PT_RM_Manager"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'EM'
    
    @classmethod
    def poll(cls, context):
        em_tools = context.scene.em_tools
        # Mostra solo se siamo in modalità EM avanzata
        return em_tools.mode_switch
    
    def draw(self, context):
        layout = self.layout
        scene = context.scene
        
        # Descrizione del pannello
        row = layout.row()
        row.label(text="Manage Representation Models (RM)")
        
        # Lista dei modelli RM
        row = layout.row()
        row.template_list(
            "RM_UL_List", "rm_list",
            scene, "rm_list",
            scene, "rm_list_index"
        )
        
        # Colonna di controllo accanto alla lista
        col = row.column(align=True)
        col.operator("rm.update_list", text="", icon='FILE_REFRESH')
        col.separator()
        col.operator("rm.select_from_list", text="", icon='RESTRICT_SELECT_OFF')
        col.operator("rm.toggle_publishable", text="", icon='EXPORT')
        
        # Bottoni per le azioni principali
        row = layout.row(align=True)
        row.operator("rm.promote_to_rm", icon='ADD')
        row.operator("rm.demote_from_rm", icon='REMOVE')
        
        # Impostazioni
        box = layout.box()
        box.label(text="Settings")
        box.prop(scene.rm_settings, "zoom_to_selected")
        
        # Informazioni oggetto
        if scene.rm_list_index >= 0 and scene.rm_list:
            item = scene.rm_list[scene.rm_list_index]
            box = layout.box()
            box.label(text="Selected RM Info")
            row = box.row()
            row.label(text=f"Object Name: {item.name}")
            row = box.row()
            row.label(text=f"First Epoch: {item.first_epoch}")
            row = box.row()
            row.label(text=f"Publishable: {'Yes' if item.is_publishable else 'No'}")

# Registrazione delle classi
classes = [
    RMItem,
    RM_UL_List,
    RM_OT_update_list,
    RM_OT_promote_to_rm,
    RM_OT_demote_from_rm,
    RM_OT_select_from_list,
    RM_OT_toggle_publishable,
    RMSettings,
    VIEW3D_PT_RM_Manager
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    
    # Registra le proprietà per la lista RM
    bpy.types.Scene.rm_list = bpy.props.CollectionProperty(type=RMItem)
    bpy.types.Scene.rm_list_index = bpy.props.IntProperty(name="Index for RM list", default=0)
    bpy.types.Scene.rm_settings = bpy.props.PointerProperty(type=RMSettings)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    
    # Rimuovi le proprietà
    del bpy.types.Scene.rm_list
    del bpy.types.Scene.rm_list_index
    del bpy.types.Scene.rm_settings
