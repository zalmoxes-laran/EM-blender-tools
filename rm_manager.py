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

# Classe PropertyGroup per rappresentare un'epoca associata a un modello RM
class RMEpochItem(PropertyGroup):
    """Properties for an epoch associated with an RM model"""
    name: StringProperty(
        name="Epoch Name",
        description="Name of the epoch",
        default=""
    )
    epoch_id: StringProperty(
        name="Epoch ID",
        description="ID of the epoch node in the graph",
        default=""
    )
    is_first_epoch: BoolProperty(
        name="Is First Epoch",
        description="Whether this is the first epoch for the RM",
        default=False
    )

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
    show_epochs: BoolProperty(
        name="Show Epochs",
        description="Show associated epochs for this RM",
        default=False
    )
    epochs: CollectionProperty(
        type=RMEpochItem,
        name="Associated Epochs"
    )
    active_epoch_index: IntProperty(
        name="Active Epoch Index",
        default=0
    )

# UI List per mostrare i modelli RM
class RM_UL_List(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            # Oggetto esiste in scena?
            obj_icon = 'OBJECT_DATA' if item.object_exists else 'ERROR'
            
            # Split layout for better control
            row = layout.row(align=True)
            
            # Espandi/comprimi epoche
            icon_expand = 'DISCLOSURE_TRI_DOWN' if item.show_epochs else 'DISCLOSURE_TRI_RIGHT'
            row.prop(item, "show_epochs", text="", icon=icon_expand, emboss=False)
            
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

# UI List per mostrare le epoche associate a un RM
class RM_UL_EpochList(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)
            
            # Mostra se è l'epoca principale
            if item.is_first_epoch:
                row.label(text="", icon='KEYFRAME_HLT')
            else:
                row.label(text="", icon='KEYFRAME')
                
            # Nome dell'epoca
            row.label(text=item.name)
            
            # Pulsante per rimuovere l'associazione
            op = row.operator("rm.remove_epoch", text="", icon='X', emboss=False)
            op.epoch_name = item.name
            
        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.label(text=item.name)

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
            
            # Se l'oggetto è già stato aggiunto, salta
            if obj_name in added_objects:
                continue
                
            # Aggiungi alla lista
            item = rm_list.add()
            item.name = obj_name
            item.node_id = node.node_id
            item.object_exists = obj_exists
            
            # Controlla se l'attributo is_publishable esiste
            if hasattr(node, 'attributes') and 'is_publishable' in node.attributes:
                item.is_publishable = node.attributes['is_publishable']
            else:
                item.is_publishable = True  # Default a True
                
            # Trova tutte le epoche associate
            associated_epochs = []
            first_epoch = None
            
            for edge in graph.edges:
                if edge.edge_source == node.node_id and edge.edge_type == "has_representation_model":
                    epoch_node = graph.find_node_by_id(edge.edge_target)
                    if epoch_node and epoch_node.node_type == "epoch":
                        associated_epochs.append({
                            "name": epoch_node.name,
                            "id": epoch_node.node_id
                        })
                        
                        # Se non abbiamo ancora trovato un'epoca principale, usa questa
                        if first_epoch is None:
                            first_epoch = epoch_node.name
            
            # Imposta l'epoca principale
            if first_epoch:
                item.first_epoch = first_epoch
            else:
                item.first_epoch = "no_epoch"
            
            # Popola la sublista delle epoche
            for epoch_data in associated_epochs:
                epoch_item = item.epochs.add()
                epoch_item.name = epoch_data["name"]
                epoch_item.epoch_id = epoch_data["id"]
                epoch_item.is_first_epoch = (epoch_data["name"] == first_epoch)
            
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
        
        # Ottieni l'epoca attiva
        active_epoch = None
        if hasattr(scene, 'epoch_list') and len(scene.epoch_list) > 0 and scene.epoch_list_index >= 0:
            active_epoch = scene.epoch_list[scene.epoch_list_index].name
        
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
                model_node.attributes['is_publishable'] = True
                graph.add_node(model_node)
                created_count += 1
                
                # Associa all'epoca attiva se disponibile, altrimenti usa "no_epoch"
                if active_epoch:
                    # Trova il nodo epoca nel grafo
                    epoch_node = None
                    for node in graph.nodes:
                        if node.node_type == "epoch" and node.name == active_epoch:
                            epoch_node = node
                            break
                    
                    if epoch_node:
                        # Aggiungi l'epoca all'oggetto Blender
                        epoch_already_added = False
                        for ep in obj.EM_ep_belong_ob:
                            if ep.epoch == active_epoch:
                                epoch_already_added = True
                                break
                                
                        if not epoch_already_added:
                            ep_item = obj.EM_ep_belong_ob.add()
                            ep_item.epoch = active_epoch
                        
                        # Crea un edge nel grafo
                        edge_id = f"{model_node_id}_belongs_to_{epoch_node.node_id}"
                        if not graph.find_edge_by_id(edge_id):
                            graph.add_edge(
                                edge_id=edge_id,
                                edge_source=model_node_id,
                                edge_target=epoch_node.node_id,
                                edge_type="has_representation_model"
                            )
                    else:
                        # Aggiungi "no_epoch" se l'epoca attiva non esiste nel grafo
                        if len(obj.EM_ep_belong_ob) == 0:
                            ep_item = obj.EM_ep_belong_ob.add()
                            ep_item.epoch = "no_epoch"
                else:
                    # Se non c'è un'epoca attiva, usa "no_epoch"
                    if len(obj.EM_ep_belong_ob) == 0:
                        ep_item = obj.EM_ep_belong_ob.add()
                        ep_item.epoch = "no_epoch"
        
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

# Operatore per rimuovere un'epoca da un RM
class RM_OT_remove_epoch(Operator):
    bl_idname = "rm.remove_epoch"
    bl_label = "Remove Epoch"
    bl_description = "Remove the epoch association from this RM model"
    
    epoch_name: StringProperty()
    
    def execute(self, context):
        scene = context.scene
        
        if scene.rm_list_index >= 0 and scene.rm_list:
            rm_item = scene.rm_list[scene.rm_list_index]
            
            # Ottieni il grafo attivo
            graph = None
            if context.scene.em_tools.active_file_index >= 0:
                graphml = context.scene.em_tools.graphml_files[context.scene.em_tools.active_file_index]
                graph = get_graph(graphml.name)
            
            if not graph:
                self.report({'ERROR'}, "No active graph available")
                return {'CANCELLED'}
            
            # Trova l'oggetto Blender
            obj = bpy.data.objects.get(rm_item.name)
            if not obj:
                self.report({'ERROR'}, f"Object not found in scene: {rm_item.name}")
                return {'CANCELLED'}
            
            # Rimuovi l'epoca dalla lista dell'oggetto
            removed_from_obj = False
            for i, ep in enumerate(obj.EM_ep_belong_ob):
                if ep.epoch == self.epoch_name:
                    obj.EM_ep_belong_ob.remove(i)
                    removed_from_obj = True
                    break
            
            # Se era l'unica epoca, aggiungi "no_epoch"
            if len(obj.EM_ep_belong_ob) == 0:
                ep_item = obj.EM_ep_belong_ob.add()
                ep_item.epoch = "no_epoch"
            
            # Trova l'epoca nel grafo
            epoch_node_id = None
            for node in graph.nodes:
                if node.node_type == "epoch" and node.name == self.epoch_name:
                    epoch_node_id = node.node_id
                    break
            
            # Rimuovi edge dal grafo
            if epoch_node_id:
                removed_from_graph = False
                edge_id_to_remove = None
                for edge in graph.edges:
                    if (edge.edge_source == rm_item.node_id and 
                        edge.edge_target == epoch_node_id and 
                        edge.edge_type == "has_representation_model"):
                        edge_id_to_remove = edge.edge_id
                        break
                
                if edge_id_to_remove:
                    graph.remove_edge(edge_id_to_remove)
                    removed_from_graph = True
            
            # Aggiorna la lista
            bpy.ops.rm.update_list()
            
            if removed_from_obj or removed_from_graph:
                self.report({'INFO'}, f"Removed epoch '{self.epoch_name}' from {rm_item.name}")
                return {'FINISHED'}
            else:
                self.report({'WARNING'}, f"Couldn't find epoch '{self.epoch_name}' to remove")
                return {'CANCELLED'}
        
        self.report({'ERROR'}, "No RM model selected")
        return {'CANCELLED'}

# Operatore per aggiungere un'epoca a un RM
class RM_OT_add_epoch(Operator):
    bl_idname = "rm.add_epoch"
    bl_label = "Add Epoch"
    bl_description = "Add the currently active epoch to this RM model"
    
    def execute(self, context):
        scene = context.scene
        
        # Verifica che ci sia un RM selezionato
        if scene.rm_list_index < 0 or not scene.rm_list:
            self.report({'ERROR'}, "No RM model selected")
            return {'CANCELLED'}
        
        # Verifica che ci sia un'epoca attiva
        if scene.epoch_list_index < 0 or not scene.epoch_list:
            self.report({'ERROR'}, "No active epoch")
            return {'CANCELLED'}
        
        rm_item = scene.rm_list[scene.rm_list_index]
        active_epoch = scene.epoch_list[scene.epoch_list_index]
        
        # Ottieni il grafo attivo
        graph = None
        if context.scene.em_tools.active_file_index >= 0:
            graphml = context.scene.em_tools.graphml_files[context.scene.em_tools.active_file_index]
            graph = get_graph(graphml.name)
        
        if not graph:
            self.report({'ERROR'}, "No active graph available")
            return {'CANCELLED'}
        
        # Trova l'oggetto Blender
        obj = bpy.data.objects.get(rm_item.name)
        if not obj:
            self.report({'ERROR'}, f"Object not found in scene: {rm_item.name}")
            return {'CANCELLED'}
        
        # Verifica se l'epoca è già associata
        for ep in obj.EM_ep_belong_ob:
            if ep.epoch == active_epoch.name:
                self.report({'WARNING'}, f"Epoch '{active_epoch.name}' already associated")
                return {'CANCELLED'}
        
        # Trova il nodo RM e il nodo epoca nel grafo
        rm_node = graph.find_node_by_id(rm_item.node_id)
        if not rm_node:
            self.report({'ERROR'}, f"RM node not found in graph: {rm_item.node_id}")
            return {'CANCELLED'}
        
        epoch_node = None
        for node in graph.nodes:
            if node.node_type == "epoch" and node.name == active_epoch.name:
                epoch_node = node
                break
        
        if not epoch_node:
            self.report({'ERROR'}, f"Epoch node not found in graph: {active_epoch.name}")
            return {'CANCELLED'}
        
        # Rimuovi "no_epoch" se presente
        for i, ep in enumerate(obj.EM_ep_belong_ob):
            if ep.epoch == "no_epoch":
                obj.EM_ep_belong_ob.remove(i)
                break
        
        # Aggiungi l'epoca all'oggetto
        ep_item = obj.EM_ep_belong_ob.add()
        ep_item.epoch = active_epoch.name
        
        # Crea un edge nel grafo
        edge_id = f"{rm_item.node_id}_belongs_to_{epoch_node.node_id}"
        if not graph.find_edge_by_id(edge_id):
            graph.add_edge(
                edge_id=edge_id,
                edge_source=rm_item.node_id,
                edge_target=epoch_node.node_id,
                edge_type="has_representation_model"
            )
        
        # Aggiorna la lista
        bpy.ops.rm.update_list()
        
        self.report({'INFO'}, f"Added epoch '{active_epoch.name}' to {rm_item.name}")
        return {'FINISHED'}

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
        
        # Mostra l'epoca attiva
        if hasattr(scene, 'epoch_list') and len(scene.epoch_list) > 0 and scene.epoch_list_index >= 0:
            active_epoch = scene.epoch_list[scene.epoch_list_index]
            box = layout.box()
            box.label(text=f"Active Epoch: {active_epoch.name}")
        
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
        
        # Se c'è un RM selezionato e sta mostrando le epoche, visualizza la sublista
        if scene.rm_list_index >= 0 and scene.rm_list:
            item = scene.rm_list[scene.rm_list_index]
            
            # Se stiamo mostrando le epoche, visualizza la sublista
            if item.show_epochs:
                box = layout.box()
                row = box.row()
                row.label(text="Associated Epochs:")
                
                # Sublista delle epoche
                row = box.row()
                row.template_list(
                    "RM_UL_EpochList", "rm_epochs",
                    item, "epochs",
                    item, "active_epoch_index"
                )
                
                # Bottone per aggiungere l'epoca attiva
                row = box.row()
                row.operator("rm.add_epoch", icon='ADD')
        
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
            row = box.row()
            row.label(text=f"Associated Epochs: {len(item.epochs)}")

# Registrazione delle classi
classes = [
    RMEpochItem,
    RMItem,
    RM_UL_List,
    RM_UL_EpochList,
    RM_OT_update_list,
    RM_OT_promote_to_rm,
    RM_OT_demote_from_rm,
    RM_OT_select_from_list,
    RM_OT_toggle_publishable,
    RM_OT_remove_epoch,
    RM_OT_add_epoch,
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