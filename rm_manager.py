import bpy
from bpy.props import (
    StringProperty,
    BoolProperty,
    CollectionProperty,
    IntProperty,
    PointerProperty,
    FloatVectorProperty,
)
from bpy.types import ( # type: ignore
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
    ) # type: ignore
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
        try:
            if self.layout_type in {'DEFAULT', 'COMPACT'}:
                # Oggetto esiste in scena?
                obj_icon = 'OBJECT_DATA' if item.object_exists else 'ERROR'
                
                # Aggiungiamo un'icona di avviso se c'è un mismatch con le epoche
                if hasattr(item, 'epoch_mismatch') and item.epoch_mismatch:
                    obj_icon = 'ERROR'
                
                # Layout simplificato
                row = layout.row(align=True)
                
                # Nome del modello RM
                row.prop(item, "name", text="", emboss=False, icon=obj_icon)
                
                # Epoca di appartenenza
                if hasattr(item, 'first_epoch'):
                    if item.first_epoch == "no_epoch":
                        row.label(text="[No Epoch]", icon='TIME')
                    else:
                        row.label(text=item.first_epoch, icon='TIME')
                else:
                    row.label(text="[Unknown]", icon='QUESTION')
                
                # Flag pubblicabile
                if hasattr(item, 'is_publishable'):
                    row.prop(item, "is_publishable", text="", icon='EXPORT' if item.is_publishable else 'CANCEL')
                
                # Selezione oggetto (inline)
                op = row.operator("rm.select_from_list", text="", icon='RESTRICT_SELECT_OFF', emboss=False)
                op.rm_index = index
                
            elif self.layout_type in {'GRID'}:
                layout.alignment = 'CENTER'
                layout.label(text="", icon=obj_icon)
                
        except Exception as e:
            # In caso di errore, mostra un elemento base
            row = layout.row()
            row.label(text=f"Error: {str(e)}", icon='ERROR')

# UI List per mostrare le epoche associate a un RM
class RM_UL_EpochList(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)
            
            # Icona per indicare la prima/altre epoche
            if item.is_first_epoch:
                row.label(text="", icon='KEYFRAME_HLT')  # Prima epoch
            else:
                row.label(text="", icon='KEYFRAME')  # Altre epoche
            
            # Nome dell'epoca
            row.label(text=item.name)
            
            # Bottone per rimuovere l'associazione con l'epoca
            try:
                # Controlla se stiamo nel contesto RM Manager
                rm_list_index = getattr(context.scene, 'rm_list_index', -1)
                if rm_list_index >= 0 and len(context.scene.rm_list) > 0:
                    rm_item = context.scene.rm_list[rm_list_index]
                    
                    # Solo se ci sono più di una epoch
                    if len(rm_item.epochs) > 1:
                        op = row.operator("rm.remove_epoch", text="", icon='X', emboss=False)
                        op.epoch_name = item.name
                        op.rm_index = rm_list_index
                
            except Exception as e:
                print(f"Error in RM_UL_EpochList draw_item: {str(e)}")
                # Fallback con un'icona di errore
                row.label(text="", icon='ERROR')
            
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
        try:
            scene = context.scene
            rm_list = scene.rm_list
            
            # Salva l'indice corrente per ripristinarlo dopo l'aggiornamento
            current_index = scene.rm_list_index
            
            # Dizionario per tracciare gli oggetti già presenti nella lista
            existing_objects = {}
            for i, item in enumerate(rm_list):
                if hasattr(item, 'name'):
                    existing_objects[item.name] = {
                        "index": i,
                        "epochs": [epoch.name for epoch in item.epochs] if hasattr(item, 'epochs') else [],
                        "is_publishable": item.is_publishable if hasattr(item, 'is_publishable') else True
                    }
            
            # Ottieni il grafo attivo se stiamo aggiornando dal grafo
            graph = None
            if self.from_graph and hasattr(context.scene, 'em_tools'):
                if (hasattr(context.scene.em_tools, 'graphml_files') and
                    len(context.scene.em_tools.graphml_files) > 0 and
                    context.scene.em_tools.active_file_index >= 0):
                    
                    graphml = context.scene.em_tools.graphml_files[context.scene.em_tools.active_file_index]
                    from .s3Dgraphy import get_graph
                    graph = get_graph(graphml.name)
            
            # Se non stiamo usando il grafo o non è disponibile, usiamo gli oggetti di scena
            scene_objects = [obj for obj in bpy.data.objects if obj.type == 'MESH' and hasattr(obj, "EM_ep_belong_ob") and len(obj.EM_ep_belong_ob) > 0]
            
            processed_objects = set()
            
            for obj in scene_objects:
                processed_objects.add(obj.name)
                
                # Ottieni le epoche dell'oggetto, escludendo "no_epoch"
                scene_epochs = [ep.epoch for ep in obj.EM_ep_belong_ob if ep.epoch != "no_epoch"]
                
                # Se non ci sono epoche, passa al prossimo oggetto
                if not scene_epochs:
                    continue
                
                # Se l'oggetto è già nella lista, aggiorna
                if obj.name in existing_objects:
                    item_index = existing_objects[obj.name]["index"]
                    item = rm_list[item_index]
                    
                    # Debug print
                    print(f"Aggiornamento oggetto: {obj.name}")
                    print(f"Epoche trovate: {scene_epochs}")
                    
                    # Pulisci le epoche precedenti
                    while len(item.epochs) > 0:
                        item.epochs.remove(0)
                    
                    # Aggiungi le nuove epoche
                    if graph:
                        # Ordina le epoche dal grafo o dall'oggetto
                        ordered_epochs = []
                        for epoch_name in scene_epochs:
                            epoch_node = None
                            for node in graph.nodes:
                                if node.node_type == "epoch" and node.name == epoch_name:
                                    epoch_node = node
                                    break
                            
                            if epoch_node:
                                ordered_epochs.append({
                                    "name": epoch_name,
                                    "start_time": getattr(epoch_node, 'start_time', float('inf')),
                                    "node": epoch_node
                                })
                            else:
                                # Se non trova il nodo nel grafo, usa un tempo di default
                                ordered_epochs.append({
                                    "name": epoch_name,
                                    "start_time": float('inf'),
                                    "node": None
                                })
                        
                        # Ordina per tempo di inizio
                        ordered_epochs.sort(key=lambda x: x['start_time'])
                        
                        # Aggiungi le epoche all'item
                        for epoch_data in ordered_epochs:
                            epoch_item = item.epochs.add()
                            epoch_item.name = epoch_data['name']
                            # Imposta come prima epoch il primo elemento o se ha un tempo di inizio minimo
                            epoch_item.is_first_epoch = (epoch_data['start_time'] == min(e['start_time'] for e in ordered_epochs))
                    
                    else:
                        # Se non abbiamo il grafo, usa le epoche dell'oggetto
                        for i, epoch_name in enumerate(scene_epochs):
                            epoch_item = item.epochs.add()
                            epoch_item.name = epoch_name
                            epoch_item.is_first_epoch = (i == 0)
                    
                    # Aggiorna la prima epoch
                    if len(item.epochs) > 0:
                        item.first_epoch = item.epochs[0].name
                    else:
                        item.first_epoch = "no_epoch"
                    
                    # Debug print
                    print(f"Prima epoch aggiornata: {item.first_epoch}")
                
                else:
                    # Crea un nuovo elemento per l'oggetto
                    item = rm_list.add()
                    item.name = obj.name
                    item.node_id = f"{obj.name}_model"
                    item.object_exists = True
                    
                    # Aggiungi le epoche
                    if graph:
                        # Ordina le epoche dal grafo
                        ordered_epochs = []
                        for epoch_name in scene_epochs:
                            for node in graph.nodes:
                                if node.node_type == "epoch" and node.name == epoch_name:
                                    ordered_epochs.append({
                                        "name": epoch_name,
                                        "start_time": getattr(node, 'start_time', float('inf'))
                                    })
                                    break
                        
                        # Ordina per tempo di inizio
                        ordered_epochs.sort(key=lambda x: x['start_time'])
                        
                        # Aggiungi le epoche all'item
                        for epoch_data in ordered_epochs:
                            epoch_item = item.epochs.add()
                            epoch_item.name = epoch_data['name']
                            epoch_item.is_first_epoch = (epoch_data['name'] == ordered_epochs[0]['name'])
                    
                    else:
                        # Se non abbiamo il grafo, aggiungi le epoche nell'ordine corrente
                        for epoch_name in scene_epochs:
                            epoch_item = item.epochs.add()
                            epoch_item.name = epoch_name
                            # Imposta la prima come prima epoch
                            epoch_item.is_first_epoch = (epoch_name == scene_epochs[0])
                    
                    # Imposta la prima epoch
                    if len(item.epochs) > 0:
                        item.first_epoch = item.epochs[0].name
                    else:
                        item.first_epoch = "no_epoch"
                    
                    # Verifica pubblicabilità dal grafo
                    if graph:
                        rm_node = graph.find_node_by_id(item.node_id)
                        if rm_node and hasattr(rm_node, 'attributes'):
                            item.is_publishable = rm_node.attributes.get('is_publishable', True)
                        else:
                            item.is_publishable = True
            
            # Rimuovi gli oggetti non più presenti
            for i in range(len(rm_list) - 1, -1, -1):
                if rm_list[i].name not in processed_objects:
                    rm_list.remove(i)
            
            # Gestisci l'aggiornamento dal grafo
            if self.from_graph and graph:
                rm_nodes = [node for node in graph.nodes if node.node_type == "representation_model"]
                
                for node in rm_nodes:
                    # Estrai il nome dell'oggetto dal node_id
                    obj_name = node.name.replace(" Model for ", "").replace("Model for ", "")
                    
                    # Verifica se l'oggetto esiste nella scena
                    obj_exists = obj_name in bpy.data.objects
                    
                    # Trova o crea l'elemento nella lista
                    existing_item = None
                    for item in rm_list:
                        if item.name == obj_name:
                            existing_item = item
                            break
                    
                    # Se l'oggetto non esiste nella lista, crealo
                    if not existing_item:
                        new_item = rm_list.add()
                        new_item.name = obj_name
                        new_item.node_id = node.node_id
                        new_item.object_exists = obj_exists
                        
                        # Imposta la pubblicabilità 
                        new_item.is_publishable = node.attributes.get('is_publishable', True)
                        
                        # Trova le epoche associate
                        associated_epochs = []
                        for edge in graph.edges:
                            if edge.edge_source == node.node_id and edge.edge_type in ["has_first_epoch", "has_representation_model", "survive_in_epoch"]:
                                epoch_node = graph.find_node_by_id(edge.edge_target)
                                if epoch_node and epoch_node.node_type == "epoch":
                                    associated_epochs.append({
                                        "name": epoch_node.name,
                                        "node": epoch_node,
                                        "start_time": getattr(epoch_node, 'start_time', float('inf')),
                                        "edge_type": edge.edge_type
                                    })
                        
                        # Ordina le epoche
                        associated_epochs.sort(key=lambda x: x['start_time'])
                        
                        # Aggiungi le epoche all'item
                        for epoch_data in associated_epochs:
                            epoch_item = new_item.epochs.add()
                            epoch_item.name = epoch_data['name']
                            epoch_item.is_first_epoch = (epoch_data['edge_type'] == "has_first_epoch")
                        
                        # Imposta la prima epoch
                        if associated_epochs:
                            new_item.first_epoch = associated_epochs[0]['name']
                        else:
                            new_item.first_epoch = "no_epoch"
            
            # Ripristina l'indice se possibile
            scene.rm_list_index = min(current_index, len(rm_list)-1) if rm_list else 0
            
            # Report
            if self.from_graph:
                self.report({'INFO'}, f"Updated RM list from graph: {len(rm_list)} models")
            else:
                self.report({'INFO'}, f"Updated RM list from scene objects: {len(rm_list)} models")
            
            return {'FINISHED'}
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.report({'ERROR'}, f"Error updating RM list: {str(e)}")
            return {'CANCELLED'}

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
class RM_OT_promote_to_rm(bpy.types.Operator):
    bl_idname = "rm.promote_to_rm"
    bl_label = "Add to Active Epoch"
    bl_description = "Add selected objects to the active epoch as RM models"
    
    def execute(self, context):
        scene = context.scene
        selected_objects = [obj for obj in context.selected_objects if obj.type == 'MESH']
        
        if not selected_objects:
            self.report({'ERROR'}, "No mesh objects selected")
            return {'CANCELLED'}
        
        # Verifica che ci sia un'epoca attiva
        if scene.epoch_list_index < 0 or not scene.epoch_list:
            self.report({'ERROR'}, "No active epoch")
            return {'CANCELLED'}
        
        # Usa l'indice selezionato nella lista RM
        rm_item = scene.rm_list[scene.rm_list_index]
        active_epoch = scene.epoch_list[scene.epoch_list_index]
        
        # Ottieni il grafo attivo (opzionale)
        graph = None
        try:
            if context.scene.em_tools.active_file_index >= 0:
                graphml = context.scene.em_tools.graphml_files[context.scene.em_tools.active_file_index]
                graph = get_graph(graphml.name)
        except Exception as e:
            print(f"Warning: Could not retrieve graph: {e}")
            graph = None
        
        # Trova l'oggetto Blender
        obj = bpy.data.objects.get(rm_item.name)
        if not obj:
            self.report({'ERROR'}, f"Object not found in scene: {rm_item.name}")
            return {'CANCELLED'}
        
        # Trova le epoche esistenti dell'oggetto
        existing_epochs = [ep.epoch for ep in obj.EM_ep_belong_ob if ep.epoch != "no_epoch"]
        
        # Filtra le epoche esistenti per evitare duplicati
        filtered_epochs = list(set(existing_epochs))
        
        # Ordina le epoche 
        sorted_epochs = filtered_epochs.copy()
        
        # Aggiungi l'epoch attiva nell'ordine corretto
        if active_epoch.name not in sorted_epochs:
            sorted_epochs.append(active_epoch.name)
        
        # Rimuovi "no_epoch" se presente
        if "no_epoch" in sorted_epochs:
            sorted_epochs.remove("no_epoch")
        
        # Aggiorna gli EP_belong_ob dell'oggetto
        obj.EM_ep_belong_ob.clear()
        for epoch_name in sorted_epochs:
            ep_item = obj.EM_ep_belong_ob.add()
            ep_item.epoch = epoch_name
        
        # Aggiorna il grafo se disponibile (opzionale)
        if graph:
            try:
                model_node_id = f"{obj.name}_model"
                
                # Rimuovi vecchi edge
                edges_to_remove = []
                for edge in graph.edges:
                    if edge.edge_source == model_node_id and edge.edge_type in ["has_first_epoch", "has_representation_model", "survive_in_epoch"]:
                        edges_to_remove.append(edge.edge_id)
                
                for edge_id in edges_to_remove:
                    graph.remove_edge(edge_id)
                
                # Aggiungi nuovi edge
                for i, epoch_name in enumerate(sorted_epochs):
                    epoch_node = None
                    for node in graph.nodes:
                        if node.node_type == "epoch" and node.name == epoch_name:
                            epoch_node = node
                            break
                    
                    if epoch_node:
                        edge_type = "has_first_epoch" if i == 0 else "survive_in_epoch"
                        edge_id = f"{model_node_id}_belongs_to_{epoch_node.node_id}"
                        graph.add_edge(
                            edge_id=edge_id,
                            edge_source=model_node_id,
                            edge_target=epoch_node.node_id,
                            edge_type=edge_type
                        )
            except Exception as e:
                print(f"Warning: Could not update graph: {e}")
        
        # Aggiorna la lista RM
        bpy.ops.rm.update_list(from_graph=True)
        
        self.report({'INFO'}, f"Added epoch '{active_epoch.name}' to {rm_item.name}")
        return {'FINISHED'}

# Operatore per rimuovere oggetti selezionati dall'epoca attiva
class RM_OT_remove_from_epoch(Operator):
    bl_idname = "rm.remove_from_epoch"
    bl_label = "Remove from Active Epoch"
    bl_description = "Remove the selected RM model from the active epoch"
    
    rm_index: IntProperty(
        name="RM Index",
        description="Index of the RM item in the list",
        default=-1
    ) # type: ignore
    
    def execute(self, context):
        scene = context.scene
        
        # Usa l'indice fornito se valido, altrimenti l'indice selezionato nella lista
        index = self.rm_index if self.rm_index >= 0 else scene.rm_list_index
        
        # Verifica che ci sia un elemento RM selezionato
        if index < 0 or index >= len(scene.rm_list):
            self.report({'ERROR'}, "No RM model selected")
            return {'CANCELLED'}
        
        # Verifica che ci sia un'epoca attiva
        if scene.epoch_list_index < 0 or not scene.epoch_list:
            self.report({'ERROR'}, "No active epoch")
            return {'CANCELLED'}
        
        # Ottiene l'elemento RM e l'epoca attiva
        rm_item = scene.rm_list[index]
        active_epoch = scene.epoch_list[scene.epoch_list_index]
        
        # Ottieni il grafo attivo
        graph = None
        if context.scene.em_tools.active_file_index >= 0:
            graphml = context.scene.em_tools.graphml_files[context.scene.em_tools.active_file_index]
            graph = get_graph(graphml.name)
        
        # Trova l'oggetto Blender
        obj = bpy.data.objects.get(rm_item.name)
        if not obj:
            self.report({'ERROR'}, f"Object not found in scene: {rm_item.name}")
            return {'CANCELLED'}
        
        # Rimuovi l'epoca dall'oggetto
        epochs_removed = False
        for i in range(len(obj.EM_ep_belong_ob) - 1, -1, -1):
            if obj.EM_ep_belong_ob[i].epoch == active_epoch.name:
                obj.EM_ep_belong_ob.remove(i)
                epochs_removed = True
        
        # Se non ci sono più epoche, aggiungi "no_epoch"
        if len(obj.EM_ep_belong_ob) == 0:
            no_epoch_item = obj.EM_ep_belong_ob.add()
            no_epoch_item.epoch = "no_epoch"
        
        # Gestisci il grafo se disponibile
        if graph:
            # Identificativo del nodo RM
            model_node_id = f"{obj.name}_model"
            rm_node = graph.find_node_by_id(model_node_id)
            
            if rm_node:
                # Trova e rimuovi gli edge con l'epoca attiva
                edges_to_remove = []
                for edge in graph.edges:
                    if (edge.edge_source == model_node_id and 
                        edge.edge_type in ["has_first_epoch", "has_representation_model", "survive_in_epoch"]):
                        # Trova il nodo dell'epoca
                        epoch_node = graph.find_node_by_id(edge.edge_target)
                        if epoch_node and epoch_node.name == active_epoch.name:
                            edges_to_remove.append(edge.edge_id)
                
                # Rimuovi gli edge
                for edge_id in edges_to_remove:
                    graph.remove_edge(edge_id)
        
        # Aggiorna la lista RM
        # Rimuovi l'epoch dalla lista delle epoche dell'item
        for i in range(len(rm_item.epochs) - 1, -1, -1):
            if rm_item.epochs[i].name == active_epoch.name:
                rm_item.epochs.remove(i)
        
        # Se non ci sono più epoche, imposta a "no_epoch"
        if len(rm_item.epochs) == 0:
            rm_item.first_epoch = "no_epoch"
        else:
            # Rivaluta la prima epoch
            for i, epoch_item in enumerate(rm_item.epochs):
                epoch_item.is_first_epoch = (i == 0)
            rm_item.first_epoch = rm_item.epochs[0].name
        
        # Aggiorna la lista RM
        bpy.ops.rm.update_list(from_graph=graph is not None)
        
        # Messaggio di successo
        if epochs_removed:
            self.report({'INFO'}, f"Removed epoch '{active_epoch.name}' from {rm_item.name}")
            return {'FINISHED'}
        else:
            self.report({'WARNING'}, f"No epoch '{active_epoch.name}' found for {rm_item.name}")
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

        # Rimuovi gli elementi dalla lista RM prima
        objects_to_remove = [obj.name for obj in selected_objects]
        for i in range(len(scene.rm_list) - 1, -1, -1):
            if scene.rm_list[i].name in objects_to_remove:
                scene.rm_list.remove(i)


        for obj in selected_objects:
            # Rimuovi tutte le epoche dall'oggetto
            while len(obj.EM_ep_belong_ob) > 0:
                obj.EM_ep_belong_ob.remove(0)
            
            # Aggiungi "no_epoch"
            #ep_item = obj.EM_ep_belong_ob.add()
            #ep_item.epoch = "no_epoch"
            
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
        #bpy.ops.rm.update_list(from_graph=graph is not None)

        # Aggiorna l'indice della lista RM se necessario
        if scene.rm_list_index >= len(scene.rm_list):
            scene.rm_list_index = max(0, len(scene.rm_list) - 1)


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
        try:
            scene = context.scene
            
            # Use provided index if valid, otherwise the selected index in the list
            index = self.rm_index if self.rm_index >= 0 else scene.rm_list_index
            
            # Verify we have a valid index
            if index >= 0 and index < len(scene.rm_list):
                item = scene.rm_list[index]
                
                # Deselect all objects
                bpy.ops.object.select_all(action='DESELECT')
                
                # If the object exists, select it
                obj = bpy.data.objects.get(item.name)
                if obj:
                    obj.select_set(True)
                    # Set as active object
                    context.view_layer.objects.active = obj
                    
                    # Zoom to object if the option is enabled
                    if hasattr(scene, 'rm_settings') and scene.rm_settings.zoom_to_selected:
                        # Find a 3D view area
                        for area in bpy.context.screen.areas:
                            if area.type == 'VIEW_3D':
                                # Create a new context override that doesn't cause ValueError
                                override = {'area': area}
                                # Use this override to call view_selected
                                bpy.ops.view3d.view_selected(override)
                                break
                    
                    self.report({'INFO'}, f"Selected object: {item.name}")
                    return {'FINISHED'}
                else:
                    self.report({'ERROR'}, f"Object not found in scene: {item.name}")
                    return {'CANCELLED'}
            
            self.report({'ERROR'}, "No item selected in the list")
            return {'CANCELLED'}
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.report({'ERROR'}, f"Error selecting object: {str(e)}")
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
            
            # Rimuovi l'epoca dall'oggetto Blender
            removed_from_obj = False
            for i, ep in enumerate(obj.EM_ep_belong_ob):
                if ep.epoch == self.epoch_name:
                    obj.EM_ep_belong_ob.remove(i)
                    removed_from_obj = True
                    break
            
            # Se era l'ultima epoca, aggiungi "no_epoch"
            if len(obj.EM_ep_belong_ob) == 0:
                ep_item = obj.EM_ep_belong_ob.add()
                ep_item.epoch = "no_epoch"
            
            # Rimuovi il nodo RM se necessario
            model_node_id = f"{obj.name}_model"
            
            # Rimuovi l'edge dal grafo
            removed_from_graph = False
            edge_to_remove = None
            
            # Trova l'edge da rimuovere
            for edge in graph.edges:
                if (edge.edge_source == model_node_id and 
                    edge.edge_type in ["has_first_epoch", "has_representation_model", "survive_in_epoch"]):
                    # Trova il nodo epoch corrispondente
                    epoch_node = graph.find_node_by_id(edge.edge_target)
                    if epoch_node and epoch_node.name == self.epoch_name:
                        edge_to_remove = edge.edge_id
                        break
            
            # Rimuovi l'edge
            if edge_to_remove:
                graph.remove_edge(edge_to_remove)
                removed_from_graph = True
            
            # Aggiorna la lista RM
            # Rimuovi l'epoch dalla lista delle epoche dell'item
            for i, epoch_item in enumerate(rm_item.epochs):
                if epoch_item.name == self.epoch_name:
                    rm_item.epochs.remove(i)
                    break
            
            # Se non ci sono più epoche, imposta a "no_epoch"
            if len(rm_item.epochs) == 0:
                rm_item.first_epoch = "no_epoch"
            else:
                # Rivaluta la prima epoch
                rm_item.epochs[0].is_first_epoch = True
                rm_item.first_epoch = rm_item.epochs[0].name
            
            # Aggiorna la lista RM
            bpy.ops.rm.update_list(from_graph=True)
            
            # Messaggio di successo
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
    
    show_settings: BoolProperty(
        name="Show Settings",
        description="Show or hide the settings section",
        default=False
    )

# Il pannello principale RM Manager
class VIEW3D_PT_RM_Manager(Panel):
    bl_label = "RM Manager"
    bl_idname = "VIEW3D_PT_RM_Manager"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'EM'
    bl_options = {'DEFAULT_CLOSED'}
        
    @classmethod
    def poll(cls, context):
        em_tools = context.scene.em_tools
        # Show only if we're in advanced EM mode
        return em_tools.mode_switch
    
    def draw(self, context):
        layout = self.layout
        scene = context.scene

        from .functions import is_graph_available
        
        # Check if a graph is available
        graph_available, graph = is_graph_available(context)

        # Update controls
        row = layout.row(align=True)
        row.operator("rm.update_list", text="Update from Scene", icon='FILE_REFRESH').from_graph = False

        # Check if a graph is available
        if graph_available:
            row.operator("rm.update_list", text="Update from Graph", icon='NODE_MATERIAL').from_graph = True
        
        # List of RM models
        row = layout.row()
        row.template_list(
            "RM_UL_List", "rm_list",
            scene, "rm_list",
            scene, "rm_list_index"
        )
        
        # Show active epoch
        has_active_epoch = False
        if hasattr(scene, 'epoch_list') and len(scene.epoch_list) > 0 and scene.epoch_list_index >= 0:
            active_epoch = scene.epoch_list[scene.epoch_list_index]
            box = layout.box()
            box.label(text=f"Active Epoch: {active_epoch.name}")
            has_active_epoch = True


        
        # Main action buttons
        if has_active_epoch:
            row = layout.row(align=True)
            row.operator("rm.promote_to_rm", icon='ADD')
            row.operator("rm.remove_from_epoch", icon='REMOVE')
            row.operator("rm.demote_from_rm", icon='TRASH')
        else:
            box = layout.box()
            box.label(text="Select an epoch to manage RM objects", icon='INFO')
        
        # List of associated epochs only if an RM is selected
        if scene.rm_list_index >= 0 and len(scene.rm_list) > 0:
            item = scene.rm_list[scene.rm_list_index]
            
            # Show the list of associated epochs
            box = layout.box()
            row = box.row()
            row.label(text=f"Epochs for {item.name}:")
            
            # Sublist of epochs
            row = box.row()
            row.template_list(
                "RM_UL_EpochList", "rm_epochs",
                item, "epochs",
                item, "active_epoch_index",
                rows=3  # Limit to 3 rows by default
            )
            
            # If there's a mismatch, show a warning and buttons to resolve it
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
        
        # Settings (collapsible)
        box = layout.box()
        row = box.row()
        row.prop(scene.rm_settings, "show_settings", 
                icon="TRIA_DOWN" if scene.rm_settings.show_settings else "TRIA_RIGHT",
                text="Settings", 
                emboss=False)
                
        if scene.rm_settings.show_settings:
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
    if (hasattr(scene, 'em_tools') and 
        hasattr(scene.em_tools, 'graphml_files') and 
        len(scene.em_tools.graphml_files) > 0 and 
        scene.em_tools.active_file_index >= 0):
        
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