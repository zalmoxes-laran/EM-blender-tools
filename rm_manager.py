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
    epoch_mismatch: BoolProperty(
        name="Epoch Mismatch",
        description="Indicates if there's a mismatch between the graph and the object epochs",
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
            
            # Aggiungiamo un'icona di avviso se c'è un mismatch con le epoche
            if item.epoch_mismatch:
                obj_icon = 'ERROR'
            
            # Layout simplificato
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
            
            # Selezione oggetto (inline)
            op = row.operator("rm.select_from_list", text="", icon='RESTRICT_SELECT_OFF', emboss=False)
            op.rm_index = index
            
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
            op.rm_index = active_data.rm_list_index
            
        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.label(text=item.name)

# Operatore per aggiornare la lista dei modelli RM
class RM_OT_update_list(Operator):
    bl_idname = "rm.update_list"
    bl_label = "Update RM List"
    bl_description = "Update the list of RM models from the current graph and scene objects"
    
    from_graph: BoolProperty(
        name="Update from Graph",
        description="Update the list using graph data. If False, uses only scene objects.",
        default=True
    )
    
    def execute(self, context):
        scene = context.scene
        rm_list = scene.rm_list
        
        # Salva l'indice corrente per ripristinarlo dopo l'aggiornamento
        current_index = scene.rm_list_index
        
        # Dizionario per tracciare gli oggetti già presenti nella lista
        existing_objects = {}
        for i, item in enumerate(rm_list):
            existing_objects[item.name] = {
                "index": i,
                "epochs": [epoch.name for epoch in item.epochs],
                "is_publishable": item.is_publishable
            }
        
        # Ottieni il grafo attivo se stiamo aggiornando dal grafo
        graph = None
        if self.from_graph and context.scene.em_tools.active_file_index >= 0:
            graphml = context.scene.em_tools.graphml_files[context.scene.em_tools.active_file_index]
            graph = get_graph(graphml.name)
        
        # Aggiorna con i dati di scena se non stiamo usando il grafo o se non è disponibile
        if not self.from_graph or not graph:
            # Primo passo: aggiorna gli elementi dalla scena (proprietà personalizzate degli oggetti)
            scene_objects = [obj for obj in bpy.data.objects if obj.type == 'MESH' and hasattr(obj, "EM_ep_belong_ob") and len(obj.EM_ep_belong_ob) > 0]
            
            # Mantieni traccia degli oggetti già processati
            processed_objects = set()
            
            for obj in scene_objects:
                processed_objects.add(obj.name)
                
                # Se l'oggetto è già nella lista, aggiorna le epoche
                if obj.name in existing_objects:
                    item_index = existing_objects[obj.name]["index"]
                    item = rm_list[item_index]
                    
                    # Verifica la corrispondenza delle epoche
                    scene_epochs = [ep.epoch for ep in obj.EM_ep_belong_ob]
                    list_epochs = [ep.name for ep in item.epochs]
                    
                    # Se le epoche sono diverse, aggiorna
                    if set(scene_epochs) != set(list_epochs):
                        # Aggiorna il flag mismatch
                        item.epoch_mismatch = True
                        
                        # Aggiorna la prima epoca
                        if scene_epochs:
                            first_epoch_from_custom = scene_epochs[0]
                            if first_epoch_from_custom != "no_epoch":
                                item.first_epoch = first_epoch_from_custom
                        
                else:
                    # Crea un nuovo elemento per l'oggetto
                    item = rm_list.add()
                    item.name = obj.name
                    item.node_id = f"{obj.name}_model"  # Formato standard per gli ID di nodo RM
                    item.object_exists = True
                    item.is_publishable = True  # Default
                    
                    # Imposta l'epoca primaria
                    scene_epochs = [ep.epoch for ep in obj.EM_ep_belong_ob]
                    if scene_epochs:
                        first_epoch = scene_epochs[0]
                        if first_epoch != "no_epoch":
                            item.first_epoch = first_epoch
                        else:
                            item.first_epoch = "no_epoch"
                    else:
                        item.first_epoch = "no_epoch"
                    
                    # Popola la lista delle epoche
                    for ep_name in scene_epochs:
                        if ep_name != "no_epoch":
                            epoch_item = item.epochs.add()
                            epoch_item.name = ep_name
                            epoch_item.is_first_epoch = (ep_name == item.first_epoch)
            
            # Rimuovi gli oggetti che non esistono più nella scena
            for i in range(len(rm_list) - 1, -1, -1):
                if rm_list[i].name not in processed_objects:
                    rm_list.remove(i)
        
        # Aggiorna con i dati del grafo se disponibile
        if self.from_graph and graph:
            # Trova tutti i nodi RM nel grafo
            rm_nodes = [node for node in graph.nodes if node.node_type == "representation_model"]
            
            # Dizionario per tracciare oggetti processati
            processed_graph_objects = set()
            
            # Aggiorna o aggiungi gli oggetti dal grafo
            for node in rm_nodes:
                # Estrai il nome dell'oggetto dal node_id (rimuovendo il suffisso "_model")
                obj_name = node.name.replace(" Model for ", "").replace("Model for ", "")
                processed_graph_objects.add(obj_name)
                
                # Verifica se l'oggetto esiste nella scena
                obj_exists = obj_name in bpy.data.objects
                
                # Controlla se esiste già nella lista
                if obj_name in existing_objects:
                    item_index = existing_objects[obj_name]["index"]
                    item = rm_list[item_index]
                    
                    # Aggiorna lo stato di pubblicazione dal nodo del grafo
                    if hasattr(node, 'attributes') and 'is_publishable' in node.attributes:
                        item.is_publishable = node.attributes['is_publishable']
                    
                    # Trova tutte le epoche associate al nodo nel grafo
                    associated_epochs = []
                    first_epoch = None
                    first_epoch_time = float('inf')
                    
                    for edge in graph.edges:
                        if edge.edge_source == node.node_id and edge.edge_type == "has_representation_model":
                            epoch_node = graph.find_node_by_id(edge.edge_target)
                            if epoch_node and epoch_node.node_type == "epoch":
                                associated_epochs.append({
                                    "name": epoch_node.name,
                                    "id": epoch_node.node_id,
                                    "start_time": getattr(epoch_node, 'start_time', 0)
                                })
                                
                                # Identificazione dell'epoca più antica
                                if hasattr(epoch_node, 'start_time'):
                                    if epoch_node.start_time < first_epoch_time:
                                        first_epoch_time = epoch_node.start_time
                                        first_epoch = epoch_node.name
                    
                    # Confronta le epoche dal grafo con quelle nell'oggetto Blender
                    obj = bpy.data.objects.get(obj_name)
                    if obj and hasattr(obj, "EM_ep_belong_ob"):
                        graph_epochs = set([ep["name"] for ep in associated_epochs])
                        obj_epochs = set([ep.epoch for ep in obj.EM_ep_belong_ob if ep.epoch != "no_epoch"])
                        
                        # Imposta il flag di mismatch se le epoche non corrispondono
                        if graph_epochs != obj_epochs:
                            item.epoch_mismatch = True
                        else:
                            item.epoch_mismatch = False
                    
                    # Aggiorna la prima epoca se necessario
                    if first_epoch:
                        item.first_epoch = first_epoch
                
                else:
                    # Crea un nuovo elemento per l'oggetto dal grafo
                    item = rm_list.add()
                    item.name = obj_name
                    item.node_id = node.node_id
                    item.object_exists = obj_exists
                    
                    # Aggiungi attributo is_publishable
                    if hasattr(node, 'attributes') and 'is_publishable' in node.attributes:
                        item.is_publishable = node.attributes['is_publishable']
                    else:
                        item.is_publishable = True  # Default
                    
                    # Trova tutte le epoche associate
                    associated_epochs = []
                    first_epoch = None
                    first_epoch_time = float('inf')
                    
                    for edge in graph.edges:
                        if edge.edge_source == node.node_id and edge.edge_type == "has_representation_model":
                            epoch_node = graph.find_node_by_id(edge.edge_target)
                            if epoch_node and epoch_node.node_type == "epoch":
                                associated_epochs.append({
                                    "name": epoch_node.name,
                                    "id": epoch_node.node_id,
                                    "start_time": getattr(epoch_node, 'start_time', 0)
                                })
                                
                                # Trova l'epoca più antica
                                if hasattr(epoch_node, 'start_time'):
                                    if epoch_node.start_time < first_epoch_time:
                                        first_epoch_time = epoch_node.start_time
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
            
            # Aggiorna gli oggetti Blender con le epoche definite nel grafo
            for obj_name in processed_graph_objects:
                obj = bpy.data.objects.get(obj_name)
                if obj and hasattr(obj, "EM_ep_belong_ob"):
                    # Trova l'item corrispondente
                    item = None
                    for i, rm_item in enumerate(rm_list):
                        if rm_item.name == obj_name:
                            item = rm_item
                            break
                    
                    if item:
                        # Confronta e aggiorna le epoche nell'oggetto
                        graph_epochs = [ep.name for ep in item.epochs]
                        obj_epochs = [ep.epoch for ep in obj.EM_ep_belong_ob if ep.epoch != "no_epoch"]
                        
                        # Se c'è un mismatch, ma stiamo aggiornando dal grafo, aggiorna l'oggetto
                        if set(graph_epochs) != set(obj_epochs):
                            # Rimuovi tutte le epoche dall'oggetto eccetto no_epoch
                            i = 0
                            while i < len(obj.EM_ep_belong_ob):
                                if obj.EM_ep_belong_ob[i].epoch != "no_epoch":
                                    obj.EM_ep_belong_ob.remove(i)
                                else:
                                    i += 1
                            
                            # Aggiungi le epoche dal grafo all'oggetto
                            no_epoch_exists = False
                            for i, ep in enumerate(obj.EM_ep_belong_ob):
                                if ep.epoch == "no_epoch":
                                    no_epoch_exists = True
                                    break
                            
                            # Se non ci sono epoche da aggiungere e non c'è no_epoch, aggiungi no_epoch
                            if not graph_epochs and not no_epoch_exists:
                                ep_item = obj.EM_ep_belong_ob.add()
                                ep_item.epoch = "no_epoch"
                            else:
                                # Aggiungi le epoche dal grafo
                                for ep_name in graph_epochs:
                                    ep_item = obj.EM_ep_belong_ob.add()
                                    ep_item.epoch = ep_name
        
        # Ripristina l'indice se possibile, altrimenti imposta a 0
        scene.rm_list_index = min(current_index, len(rm_list)-1) if rm_list else 0
        
        if self.from_graph:
            self.report({'INFO'}, f"Updated RM list from graph: {len(rm_list)} models")
        else:
            self.report({'INFO'}, f"Updated RM list from scene objects: {len(rm_list)} models")
        
        return {'FINISHED'}

# Operatore per risolvere i mismatch di epoche
class RM_OT_resolve_mismatches(Operator):
    bl_idname = "rm.resolve_mismatches"
    bl_label = "Resolve Epoch Mismatches"
    bl_description = "Resolve mismatches between scene objects and graph epochs"
    
    use_graph_epochs: BoolProperty(
        name="Use Graph Epochs",
        description="If True, use epochs from graph. If False, use epochs from scene objects",
        default=True
    )
    
    def execute(self, context):
        scene = context.scene
        rm_list = scene.rm_list
        
        # Ottieni il grafo attivo
        graph = None
        if context.scene.em_tools.active_file_index >= 0:
            graphml = context.scene.em_tools.graphml_files[context.scene.em_tools.active_file_index]
            graph = get_graph(graphml.name)
        
        if not graph and self.use_graph_epochs:
            self.report({'ERROR'}, "No active graph available")
            return {'CANCELLED'}
        
        resolved_count = 0
        
        # Itera su tutti gli elementi della lista
        for i, item in enumerate(rm_list):
            if item.epoch_mismatch:
                obj = bpy.data.objects.get(item.name)
                if not obj:
                    continue
                
                if self.use_graph_epochs:
                    # Usa le epoche dal grafo
                    # Rimuovi tutte le epoche dall'oggetto tranne no_epoch
                    j = 0
                    while j < len(obj.EM_ep_belong_ob):
                        if obj.EM_ep_belong_ob[j].epoch != "no_epoch":
                            obj.EM_ep_belong_ob.remove(j)
                        else:
                            j += 1
                    
                    # Aggiungi le epoche dalla lista RM
                    for epoch_item in item.epochs:
                        ep_item = obj.EM_ep_belong_ob.add()
                        ep_item.epoch = epoch_item.name
                else:
                    # Usa le epoche dall'oggetto
                    obj_epochs = [ep.epoch for ep in obj.EM_ep_belong_ob if ep.epoch != "no_epoch"]
                    
                    # Aggiorna il grafo con le epoche dell'oggetto
                    model_node_id = f"{obj.name}_model"
                    model_node = graph.find_node_by_id(model_node_id)
                    
                    if model_node:
                        # Rimuovi tutti gli edge esistenti
                        edges_to_remove = []
                        for edge in graph.edges:
                            if edge.edge_source == model_node_id and edge.edge_type == "has_representation_model":
                                edges_to_remove.append(edge.edge_id)
                        
                        # Rimuovi gli edge
                        for edge_id in edges_to_remove:
                            graph.remove_edge(edge_id)
                        
                        # Aggiungi i nuovi edge
                        for epoch_name in obj_epochs:
                            epoch_node = None
                            for node in graph.nodes:
                                if node.node_type == "epoch" and node.name == epoch_name:
                                    epoch_node = node
                                    break
                            
                            if epoch_node:
                                edge_id = f"{model_node_id}_belongs_to_{epoch_node.node_id}"
                                if not graph.find_edge_by_id(edge_id):
                                    graph.add_edge(
                                        edge_id=edge_id,
                                        edge_source=model_node_id,
                                        edge_target=epoch_node.node_id,
                                        edge_type="has_representation_model"
                                    )
                
                # Marca come risolto
                item.epoch_mismatch = False
                resolved_count += 1
        
        # Aggiorna la lista RM
        bpy.ops.rm.update_list(from_graph=self.use_graph_epochs)
        
        action = "graph" if self.use_graph_epochs else "scene objects"
        self.report({'INFO'}, f"Resolved {resolved_count} mismatches using epochs from {action}")
        return {'FINISHED'}

# Operatore per visualizzare i dettagli di mismatch
class RM_OT_show_mismatch_details(Operator):
    bl_idname = "rm.show_mismatch_details"
    bl_label = "Show Mismatch Details"
    bl_description = "Show details about epoch mismatches for selected object"
    
    def execute(self, context):
        scene = context.scene
        
        if scene.rm_list_index < 0 or not scene.rm_list:
            self.report({'ERROR'}, "No RM model selected")
            return {'CANCELLED'}
        
        item = scene.rm_list[scene.rm_list_index]
        
        if not item.epoch_mismatch:
            self.report({'INFO'}, "No mismatch detected for this object")
            return {'FINISHED'}
        
        obj = bpy.data.objects.get(item.name)
        if not obj:
            self.report({'ERROR'}, "Object not found in scene")
            return {'CANCELLED'}
        
        # Get epochs from object
        obj_epochs = [ep.epoch for ep in obj.EM_ep_belong_ob if ep.epoch != "no_epoch"]
        
        # Get epochs from RM list
        list_epochs = [ep.name for ep in item.epochs]
        
        # Find differences
        obj_only = set(obj_epochs) - set(list_epochs)
        list_only = set(list_epochs) - set(obj_epochs)
        
        # Show dialog with details
        def draw(self, context):
            layout = self.layout
            layout.label(text=f"Mismatch details for {item.name}:")
            
            box = layout.box()
            box.label(text="Epochs in object but not in graph:")
            if obj_only:
                for epoch in sorted(obj_only):
                    box.label(text=f"- {epoch}")
            else:
                box.label(text="None")
            
            box = layout.box()
            box.label(text="Epochs in graph but not in object:")
            if list_only:
                for epoch in sorted(list_only):
                    box.label(text=f"- {epoch}")
            else:
                box.label(text="None")
        
        bpy.context.window_manager.popup_menu(draw, title="Epoch Mismatch Details", icon='INFO')
        
        return {'FINISHED'}

# Operatore per promuovere oggetti selezionati a RM
class RM_OT_promote_to_rm(Operator):
    bl_idname = "rm.promote_to_rm"
    bl_label = "Add to Active Epoch"
    bl_description = "Add selected objects to the active epoch as RM models"
    
    def execute(self, context):
        scene = context.scene
        selected_objects = [obj for obj in context.selected_objects if obj.type == 'MESH']
        
        if not selected_objects:
            self.report({'ERROR'}, "No mesh objects selected")
            return {'CANCELLED'}
        
        # Ottieni l'epoca attiva
        active_epoch = None
        if hasattr(scene, 'epoch_list') and len(scene.epoch_list) > 0 and scene.epoch_list_index >= 0:
            active_epoch = scene.epoch_list[scene.epoch_list_index]
        else:
            self.report({'ERROR'}, "No active epoch")
            return {'CANCELLED'}
        
        # Ottieni il grafo attivo
        graph = None
        if context.scene.em_tools.active_file_index >= 0:
            graphml = context.scene.em_tools.graphml_files[context.scene.em_tools.active_file_index]
            graph = get_graph(graphml.name)
        
        # Conta quanti oggetti sono stati promossi
        created_count = 0
        updated_count = 0
        
        # Per ogni oggetto selezionato
        for obj in selected_objects:
            # Controlla se l'oggetto ha già l'epoca attiva
            epoch_already_added = False
            for ep in obj.EM_ep_belong_ob:
                if ep.epoch == active_epoch.name:
                    epoch_already_added = True
                    break
            
            # Se l'epoca non è già associata, aggiungila
            if not epoch_already_added:
                # Rimuovi no_epoch se presente
                i = 0
                no_epoch_found = False
                while i < len(obj.EM_ep_belong_ob):
                    if obj.EM_ep_belong_ob[i].epoch == "no_epoch":
                        obj.EM_ep_belong_ob.remove(i)
                        no_epoch_found = True
                        break
                    i += 1
                
                # Aggiungi l'epoca all'oggetto
                ep_item = obj.EM_ep_belong_ob.add()
                ep_item.epoch = active_epoch.name
                updated_count += 1
            
            # Se il grafo è disponibile, aggiorna anche quello
            if graph:
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
                
                # Trova il nodo epoca nel grafo
                epoch_node = None
                for node in graph.nodes:
                    if node.node_type == "epoch" and node.name == active_epoch.name:
                        epoch_node = node
                        break
                
                if epoch_node:
                    # Crea un edge tra il modello e l'epoca se non esiste già
                    edge_id = f"{model_node_id}_belongs_to_{epoch_node.node_id}"
                    if not graph.find_edge_by_id(edge_id):
                        graph.add_edge(
                            edge_id=edge_id,
                            edge_source=model_node_id,
                            edge_target=epoch_node.node_id,
                            edge_type="has_representation_model"
                        )
                
                # Verifica se dobbiamo aggiornare gli edge "has_first_epoch"
                if epoch_node:
                    # Determina quale epoca è la più antica
                    oldest_epoch = None
                    oldest_epoch_time = float('inf')
                    
                    # Primo passo: trova tutte le epoche associate all'oggetto
                    associated_epochs = []
                    for ep in obj.EM_ep_belong_ob:
                        if ep.epoch != "no_epoch":
                            for node in graph.nodes:
                                if node.node_type == "epoch" and node.name == ep.epoch:
                                    associated_epochs.append(node)
                                    
                                    # Verifica se è l'epoca più antica
                                    if hasattr(node, 'start_time'):
                                        if node.start_time < oldest_epoch_time:
                                            oldest_epoch_time = node.start_time
                                            oldest_epoch = node
                    
                    # Secondo passo: aggiorna gli edge per ogni epoca
                    for epoch in associated_epochs:
                        edge_id = f"{model_node_id}_belongs_to_{epoch.node_id}"
                        existing_edge = graph.find_edge_by_id(edge_id)
                        
                        # Se l'edge non esiste, crealo
                        if not existing_edge:
                            graph.add_edge(
                                edge_id=edge_id,
                                edge_source=model_node_id,
                                edge_target=epoch.node_id,
                                edge_type="has_representation_model"
                            )
        
        # Aggiorna la lista RM
        bpy.ops.rm.update_list(from_graph=graph is not None)
        
        message = f"Added {updated_count} objects to epoch '{active_epoch.name}'"
        if created_count > 0:
            message += f" and created {created_count} new RM nodes in the graph"
        
        self.report({'INFO'}, message)
        return {'FINISHED'}

# Operatore per rimuovere oggetti selezionati dall'epoca attiva
class RM_OT_remove_from_epoch(Operator):
    bl_idname = "rm.remove_from_epoch"
    bl_label = "Remove from Active Epoch"
    bl_description = "Remove selected objects from the active epoch"
    
    def execute(self, context):
        scene = context.scene
        selected_objects = [obj for obj in context.selected_objects if obj.type == 'MESH']
        
        if not selected_objects:
            self.report({'ERROR'}, "No mesh objects selected")
            return {'CANCELLED'}
        
        # Ottieni l'epoca attiva
        active_epoch = None
        if hasattr(scene, 'epoch_list') and len(scene.epoch_list) > 0 and scene.epoch_list_index >= 0:
            active_epoch = scene.epoch_list[scene.epoch_list_index]
        else:
            self.report({'ERROR'}, "No active epoch")
            return {'CANCELLED'}
        
        # Ottieni il grafo attivo
        graph = None
        if context.scene.em_tools.active_file_index >= 0:
            graphml = context.scene.em_tools.graphml_files[context.scene.em_tools.active_file_index]
            graph = get_graph(graphml.name)
        
        # Conta quanti oggetti sono stati aggiornati
        removed_count = 0
        
        # Per ogni oggetto selezionato
        for obj in selected_objects:
            # Rimuovi l'epoca attiva dall'oggetto
            for i, ep in enumerate(obj.EM_ep_belong_ob):
                if ep.epoch == active_epoch.name:
                    obj.EM_ep_belong_ob.remove(i)
                    removed_count += 1
                    break
            
            # Se non ci sono più epoche, aggiungi "no_epoch"
            if len(obj.EM_ep_belong_ob) == 0:
                ep_item = obj.EM_ep_belong_ob.add()
                ep_item.epoch = "no_epoch"
            
            # Se il grafo è disponibile, aggiorna anche quello
            if graph:
                model_node_id = f"{obj.name}_model"
                model_node = graph.find_node_by_id(model_node_id)
                
                if model_node:
                    # Trova il nodo epoca nel grafo
                    epoch_node = None
                    for node in graph.nodes:
                        if node.node_type == "epoch" and node.name == active_epoch.name:
                            epoch_node = node
                            break
                    
                    if epoch_node:
                        # Rimuovi l'edge tra il modello e l'epoca
                        for edge in graph.edges:
                            if (edge.edge_source == model_node_id and 
                                edge.edge_target == epoch_node.node_id and 
                                edge.edge_type == "has_representation_model"):
                                graph.remove_edge(edge.edge_id)
                                break
        
        # Aggiorna la lista RM
        bpy.ops.rm.update_list(from_graph=graph is not None)
        
        self.report({'INFO'}, f"Removed {removed_count} objects from epoch '{active_epoch.name}'")
        return {'FINISHED'}

# Operatore per demote oggetti selezionati da RM
class RM_OT_demote_from_rm(Operator):
    bl_idname = "rm.demote_from_rm"
    bl_label = "Demote from RM"
    bl_description = "Remove selected objects completely from all epochs and the graph"
    
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
        
        # Conta quanti oggetti sono stati rimossi
        removed_count = 0
        
        for obj in selected_objects:
            # Rimuovi tutte le epoche dall'oggetto
            while len(obj.EM_ep_belong_ob) > 0:
                obj.EM_ep_belong_ob.remove(0)
            
            # Aggiungi "no_epoch"
            ep_item = obj.EM_ep_belong_ob.add()
            ep_item.epoch = "no_epoch"
            
            removed_count += 1
            
            # Se il grafo è disponibile, rimuovi anche il nodo e gli edge dal grafo
            if graph:
                model_node_id = f"{obj.name}_model"
                model_node = graph.find_node_by_id(model_node_id)
                
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
        
        # Aggiorna la lista RM
        bpy.ops.rm.update_list(from_graph=graph is not None)
        
        self.report({'INFO'}, f"Demoted {removed_count} objects from RM models")
        return {'FINISHED'}

# Operatore per selezionare l'oggetto RM dalla lista
class RM_OT_select_from_list(Operator):
    bl_idname = "rm.select_from_list"
    bl_label = "Select RM Object"
    bl_description = "Select the RM object in the 3D view"
    
    rm_index: IntProperty(
        name="RM Index",
        description="Index of the RM item in the list",
        default=-1
    )
    
    def execute(self, context):
        scene = context.scene
        
        # Usa l'indice fornito se valido, altrimenti l'indice selezionato nella lista
        index = self.rm_index if self.rm_index >= 0 else scene.rm_list_index
        
        # Verifica se abbiamo un indice valido
        if index >= 0 and index < len(scene.rm_list):
            item = scene.rm_list[index]
            
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
    
    rm_index: IntProperty(
        name="RM Index",
        description="Index of the RM item in the list",
        default=-1
    )
    
    def execute(self, context):
        scene = context.scene
        
        # Usa l'indice fornito se valido, altrimenti l'indice selezionato nella lista
        index = self.rm_index if self.rm_index >= 0 else scene.rm_list_index
        
        if index >= 0 and index < len(scene.rm_list):
            item = scene.rm_list[index]
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
    rm_index: IntProperty(
        name="RM Index",
        description="Index of the RM item in the list",
        default=-1
    )
    
    def execute(self, context):
        scene = context.scene
        
        # Usa l'indice fornito se valido, altrimenti l'indice selezionato nella lista
        index = self.rm_index if self.rm_index >= 0 else scene.rm_list_index
        
        if index >= 0 and index < len(scene.rm_list):
            rm_item = scene.rm_list[index]
            
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
    
    rm_index: IntProperty(
        name="RM Index",
        description="Index of the RM item in the list",
        default=-1
    )
    
    def execute(self, context):
        scene = context.scene
        
        # Usa l'indice fornito se valido, altrimenti l'indice selezionato nella lista
        index = self.rm_index if self.rm_index >= 0 else scene.rm_list_index
        
        # Verifica che ci sia un RM selezionato
        if index < 0 or index >= len(scene.rm_list):
            self.report({'ERROR'}, "No RM model selected")
            return {'CANCELLED'}
        
        # Verifica che ci sia un'epoca attiva
        if scene.epoch_list_index < 0 or not scene.epoch_list:
            self.report({'ERROR'}, "No active epoch")
            return {'CANCELLED'}
        
        rm_item = scene.rm_list[index]
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
    
    show_mismatches: BoolProperty(
        name="Show Epoch Mismatches",
        description="Highlight objects with mismatches between scene and graph epochs",
        default=True
    )
    
    auto_update_on_load: BoolProperty(
        name="Auto Update on Graph Load",
        description="Automatically update RM list when a graph is loaded",
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

        from .functions import is_graph_available

        # Mostra l'epoca attiva
        has_active_epoch = False
        if hasattr(scene, 'epoch_list') and len(scene.epoch_list) > 0 and scene.epoch_list_index >= 0:
            active_epoch = scene.epoch_list[scene.epoch_list_index]
            box = layout.box()
            box.label(text=f"Active Epoch: {active_epoch.name}")
            has_active_epoch = True
        
        # Controllo per aggiornamento lista e gestione mismatch
        row = layout.row(align=True)
        row.operator("rm.update_list", text="Update from Scene", icon='FILE_REFRESH').from_graph = False

        # Use the modular function to check graph availability
        graph_available, graph = is_graph_available(context)

        # Verifica se è disponibile un grafo
        if graph_available:
            row.operator("rm.update_list", text="Update from Graph", icon='NODE_MATERIAL').from_graph = True
        
        # Lista dei modelli RM
        row = layout.row()
        row.template_list(
            "RM_UL_List", "rm_list",
            scene, "rm_list",
            scene, "rm_list_index"
        )
        
        # Bottoni per le azioni principali
        if has_active_epoch:
            row = layout.row(align=True)
            row.operator("rm.promote_to_rm", icon='ADD')
            row.operator("rm.remove_from_epoch", icon='REMOVE')
            row.operator("rm.demote_from_rm", icon='TRASH')
        
        # Elenco delle epoche associate sempre visibile
        if scene.rm_list_index >= 0 and scene.rm_list and len(scene.rm_list):
            item = scene.rm_list[scene.rm_list_index]
            
            # Mostra la lista delle epoche associate
            box = layout.box()
            row = box.row()
            row.label(text=f"Epochs for {item.name}:")
            
            # Sublista delle epoche sempre visibile
            row = box.row()
            row.template_list(
                "RM_UL_EpochList", "rm_epochs",
                item, "epochs",
                item, "active_epoch_index"
            )
            
            # Bottoni per aggiungere/gestire epoche
            if has_active_epoch:
                row = box.row()
                row.operator("rm.add_epoch", icon='ADD').rm_index = scene.rm_list_index
            
            # Se c'è un mismatch, mostra un avviso e bottoni per risolverlo
            if item.epoch_mismatch:
                row = box.row()
                row.alert = True
                row.label(text="Epoch Mismatch Detected!", icon='ERROR')
                
                row = box.row(align=True)
                row.operator("rm.show_mismatch_details", icon='INFO')
                
                row = box.row(align=True)
                if graph_available:
                    row.operator("rm.resolve_mismatches", text="Use Graph Epochs", icon='NODE_MATERIAL').use_graph_epochs = True
                row.operator("rm.resolve_mismatches", text="Use Scene Epochs", icon='OBJECT_DATA').use_graph_epochs = False
            
            # Informazioni oggetto
            box = layout.box()
            box.label(text=f"Selected RM: {item.name}")
            row = box.row()
            row.label(text=f"First Epoch: {item.first_epoch}")
            row = box.row()
            row.prop(item, "is_publishable", text="Publishable")
        
        # Impostazioni
        box = layout.box()
        row = box.row()
        row.label(text="Settings")
        row = box.row()
        row.prop(scene.rm_settings, "zoom_to_selected")
        row = box.row()
        row.prop(scene.rm_settings, "show_mismatches")
        row = box.row()
        row.prop(scene.rm_settings, "auto_update_on_load")

# Handler per aggiornare automaticamente la lista RM quando viene caricato un grafo
@bpy.app.handlers.persistent
def update_rm_list_on_graph_load(dummy):
    """Update RM list when a graph is loaded"""
    
    # Ensure we're in a context where we can access scene
    if not bpy.context or not hasattr(bpy.context, 'scene'):
        return
        
    scene = bpy.context.scene
    
    # Check if auto update is enabled
    if not hasattr(scene, 'rm_settings') or not scene.rm_settings.auto_update_on_load:
        return
        
    # Only call the operator if we have an active file
    if hasattr(scene, 'em_tools') and scene.em_tools.active_file_index >= 0:
        try:
            # Run in a timer to ensure proper context
            bpy.app.timers.register(
                lambda: bpy.ops.rm.update_list(from_graph=True), 
                first_interval=0.5
            )
        except Exception as e:
            print(f"Error updating RM list on graph load: {e}")

# Registrazione delle classi
classes = [
    RMEpochItem,
    RMItem,
    RM_UL_List,
    RM_UL_EpochList,
    RM_OT_update_list,
    RM_OT_promote_to_rm,
    RM_OT_remove_from_epoch,
    RM_OT_demote_from_rm,
    RM_OT_select_from_list,
    RM_OT_toggle_publishable,
    RM_OT_remove_epoch,
    RM_OT_add_epoch,
    RM_OT_resolve_mismatches,
    RM_OT_show_mismatch_details,
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
    
    # Registra l'handler per aggiornare la lista quando viene caricato un grafo
    bpy.app.handlers.load_post.append(update_rm_list_on_graph_load)

def unregister():
    # Remove handler
    if update_rm_list_on_graph_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(update_rm_list_on_graph_load)
    
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    
    # Rimuovi le proprietà
    del bpy.types.Scene.rm_list
    del bpy.types.Scene.rm_list_index
    del bpy.types.Scene.rm_settings