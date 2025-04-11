import bpy
import xml.etree.ElementTree as ET
import os
import bpy.props as prop
from bpy.types import Panel
from .populate_lists import populate_blender_lists_from_graph

from bpy.props import (BoolProperty,
                       FloatProperty,
                       StringProperty,
                       EnumProperty,
                       CollectionProperty,
                       IntProperty,
                       PointerProperty,
                       FloatVectorProperty,
                       )

from bpy.types import (
        AddonPreferences,
        PropertyGroup,
        )

from .functions import *
from .s3Dgraphy.nodes import StratigraphicNode
from .populate_lists import populate_stratigraphic_node, EM_list_clear, check_if_current_obj_has_brother_inlist, select_3D_obj, update_icons, check_material_presence, em_setup_mat_cycles

class EM_filter_lists(bpy.types.Operator):
    bl_idname = "em.filter_lists"
    bl_label = "Filter Lists"
    bl_description = "Apply filters to stratigraphy list"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        scene = context.scene
        em_tools = scene.em_tools
        
        # Verifica se c'è un grafo attivo
        from .functions import is_graph_available as check_graph
        graph_exists, graph = check_graph(context)

        if not graph_exists:
            self.report({'WARNING'}, "No active graph found. Please load a GraphML file first.")
            return {'CANCELLED'}
        
        # Lista temporanea per memorizzare tutti gli elementi filtrati
        filtered_items = []
        
        # Ottieni i nodi stratigrafici dal grafo
        strat_nodes = [node for node in graph.nodes if hasattr(node, 'node_type') and 
                      node.node_type in ['US', 'USVs', 'USVn', 'VSF', 'SF', 'USD', 'serSU', 'serUSVn', 'serUSVs']]
        
        # Debug: Print active epoch
        active_epoch_name = None
        if scene.filter_by_epoch and scene.epoch_list_index >= 0 and len(scene.epoch_list) > 0:
            active_epoch_name = scene.epoch_list[scene.epoch_list_index].name
            print(f"Active epoch: {active_epoch_name}")
        
        # Debug: Print active activity
        active_activity_name = None  
        if scene.filter_by_activity and scene.activity_manager.active_index >= 0 and len(scene.activity_manager.activities) > 0:
            active_activity_name = scene.activity_manager.activities[scene.activity_manager.active_index].name
            print(f"Active activity: {active_activity_name}")
        
        for node in strat_nodes:
            print(f"\nEvaluating node: {node.name} (UUID: {node.node_id})")
            include_node = True
            
            # Applica filtro per epoca se attivo
            if scene.filter_by_epoch and active_epoch_name:
                include_node = False 

                # Trova gli edge che collegano questo nodo alle epoche
                created_in_epoch = False
                survives_in_epoch = False
                
                # Trova tutte le epoche connesse a questo nodo
                connected_epochs = []
                
                # Cerca direttamente per ID del nodo negli archi
                for edge in graph.edges:
                    if edge.edge_source == node.node_id:
                        target_node = graph.find_node_by_id(edge.edge_target)
                        
                        if target_node and hasattr(target_node, 'node_type') and target_node.node_type == "epoch":
                            if edge.edge_type == "has_first_epoch":
                                connected_epochs.append({"name": target_node.name, "type": "created"})
                                if target_node.name == active_epoch_name:
                                    created_in_epoch = True
                                    print(f"  Node was created in active epoch: {active_epoch_name}")
                                    
                            elif edge.edge_type == "survive_in_epoch":
                                connected_epochs.append({"name": target_node.name, "type": "survives"})
                                if target_node.name == active_epoch_name:
                                    survives_in_epoch = True
                                    print(f"  Node survives in active epoch: {active_epoch_name}")
                
                # Debug: mostro tutte le epoche connesse a questo nodo
                if connected_epochs:
                    print(f"  Connected epochs: {connected_epochs}")
                else:
                    print(f"  No epochs connected to this node")
                
                # Includi il nodo se è stato creato in questa epoca o sopravvive in questa epoca (quando l'opzione è attivata)
                include_node = created_in_epoch or (survives_in_epoch and scene.include_surviving_units)
                
                if include_node:
                    print(f"  Node INCLUDED for epoch filter")
                else:
                    print(f"  Node EXCLUDED for epoch filter")
            
            # Applica filtro per attività se attivo e se il nodo è ancora incluso
            if scene.filter_by_activity and include_node and active_activity_name:
                in_activity = False
                
                # Cerca connessioni con l'attività attiva
                for edge in graph.edges:
                    if edge.edge_source == node.node_id and edge.edge_type == "is_in_activity":
                        activity_node = graph.find_node_by_id(edge.edge_target)
                        if activity_node and hasattr(activity_node, 'name') and activity_node.name == active_activity_name:
                            in_activity = True
                            print(f"  Node is in active activity: {active_activity_name}")
                            break
                
                include_node = in_activity
                
                if include_node:
                    print(f"  Node INCLUDED for activity filter")
                else:
                    print(f"  Node EXCLUDED for activity filter")
            
            # Se il nodo passa tutti i filtri, aggiungilo alla lista
            if include_node:
                filtered_items.append(node)
                print(f"  FINAL RESULT: Node {node.name} INCLUDED in filtered list")
            else:
                print(f"  FINAL RESULT: Node {node.name} EXCLUDED from filtered list")
        
        # Aggiorna la lista em_list con gli elementi filtrati
        # Salva l'elemento attualmente selezionato (se presente)
        current_selected = None
        if scene.em_list_index >= 0 and scene.em_list_index < len(scene.em_list):
            try:
                current_selected = scene.em_list[scene.em_list_index].name
                print(f"Current selection: {current_selected}")
            except IndexError:
                print(f"IndexError: index {scene.em_list_index} out of range for list with {len(scene.em_list)} items")
                current_selected = None
        
        # Pulisci la lista attuale
        EM_list_clear(context, "em_list")
        
        # Ricostruisci la lista con gli elementi filtrati
        print(f"\nPopulating em_list with {len(filtered_items)} filtered items")
        for i, node in enumerate(filtered_items):
            # Usa la funzione esistente per popolare la lista
            populate_stratigraphic_node(scene, node, i, graph)
          
        
        # IMPORTANTE: Reimposta l'indice in modo sicuro
        if len(scene.em_list) == 0:
            scene.em_list_index = -1
            self.report({'INFO'}, "No items match the current filters")
        else:
            # Prima imposta a 0, poi prova a ripristinare la selezione
            scene.em_list_index = 0
            
            # Ripristina la selezione se possibile
            if current_selected:
                for i, item in enumerate(scene.em_list):
                    if item.name == current_selected:
                        scene.em_list_index = i
                        print(f"Restored selection to index {i}: {item.name}")
                        break
        
        # Se la sincronizzazione è attiva, aggiorna la visibilità degli oggetti
        if scene.sync_list_visibility:
            bpy.ops.em.strat_sync_visibility()
        
        return {'FINISHED'}

class EM_reset_filters(bpy.types.Operator):
    bl_idname = "em.reset_filters"
    bl_label = "Reset Filters"
    bl_description = "Reset all filters and reload the complete list"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        scene = context.scene
        
        # Importante: memorizza lo stato attuale dei filtri
        previous_epoch_filter = scene.filter_by_epoch
        previous_activity_filter = scene.filter_by_activity
        
        # Disattiva temporaneamente i callback di aggiornamento
        # impostando una flag che sarà controllata nei callback
        if hasattr(filter_list_update, "is_running"):
            filter_list_update.is_running = True
        
        try:
            # Disattiva i filtri senza innescare nuovi aggiornamenti
            scene.filter_by_epoch = False
            scene.filter_by_activity = False
            
            # Ricarica SOLO la lista em_list, non le altre liste!
            em_tools = scene.em_tools
            if em_tools.active_file_index >= 0:
                graphml = em_tools.graphml_files[em_tools.active_file_index]
                graph = get_graph(graphml.name)
                
                if graph:
                    # Pulisci SOLO la lista em_list
                    EM_list_clear(context, "em_list")
                    
                    # Estrai solo i nodi stratigrafici dal grafo
                    strat_nodes = [node for node in graph.nodes if hasattr(node, 'node_type') and 
                                  node.node_type in ['US', 'USVs', 'USVn', 'VSF', 'SF', 'USD', 'serSU', 'serUSVn', 'serUSVs']]
                    
                    # Ripopola SOLO la lista em_list
                    for i, node in enumerate(strat_nodes):
                        populate_stratigraphic_node(scene, node, i, graph)
                    
                    # Assicura che l'indice sia valido
                    if len(scene.em_list) > 0:
                        scene.em_list_index = 0
                    else:
                        scene.em_list_index = -1
                    
                    self.report({'INFO'}, "Filters reset, showing all items")
                else:
                    self.report({'WARNING'}, "No active graph found")
        finally:
            # Ripristina la possibilità di aggiornamenti
            if hasattr(filter_list_update, "is_running"):
                filter_list_update.is_running = False
        
        return {'FINISHED'}

class EM_strat_toggle_visibility(bpy.types.Operator):
    bl_idname = "em.strat_toggle_visibility"
    bl_label = "Toggle Stratigraphy Visibility"
    bl_description = "Toggle visibility of the selected proxy in the scene"
    bl_options = {"REGISTER", "UNDO"}
    
    index: IntProperty(default=-1)  # type: ignore # -1 means use the active index
    
    def execute(self, context):
        scene = context.scene
        index = self.index if self.index >= 0 else scene.em_list_index
        
        if index >= 0 and index < len(scene.em_list):
            item = scene.em_list[index]
            obj = bpy.data.objects.get(item.name)
            
            if obj:
                # Toggle visibility
                obj.hide_viewport = not obj.hide_viewport
                item.is_visible = not obj.hide_viewport
                
                # Se l'oggetto è nascosto in una collezione, attivala
                if not obj.hide_viewport:
                    self.activate_object_collections(obj, context)
                    
                return {'FINISHED'}
            else:
                self.report({'WARNING'}, f"Object '{item.name}' not found in scene")
        
        return {'CANCELLED'}
    
    def is_in_hidden_collection(self, obj, context):
        """Verifica se l'oggetto è in una collezione nascosta."""
        for collection in bpy.data.collections:
            if obj.name in collection.objects and collection.hide_viewport:
                return True
        return False
    
    def activate_object_collections(self, obj, context):
        """Attiva tutte le collezioni che contengono l'oggetto."""
        activated_collections = []
        
        for collection in bpy.data.collections:
            if obj.name in collection.objects and collection.hide_viewport:
                collection.hide_viewport = False
                activated_collections.append(collection.name)
        
        if activated_collections:
            self.show_activation_message(", ".join(activated_collections))
    
    def show_activation_message(self, collection_names):
        def draw(self, context):
            self.layout.label(text="The following collections have been activated:")
            self.layout.label(text=collection_names)
        
        bpy.context.window_manager.popup_menu(draw, title="Collections Activated", icon='INFO')




class EM_strat_sync_visibility(bpy.types.Operator):
    bl_idname = "em.strat_sync_visibility"
    bl_label = "Sync Stratigraphy Visibility"
    bl_description = "Synchronize visibility of proxies and RM objects with the current selections"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        scene = context.scene
        
        # Handle proxy visibility sync
        if scene.sync_list_visibility:
            self.sync_proxy_visibility(context)
            
        # Handle RM visibility sync
        if scene.sync_rm_visibility:
            self.sync_rm_visibility(context)
            
        return {'FINISHED'}
    
    def sync_proxy_visibility(self, context):
        """Synchronize proxy object visibility with the em_list"""
        scene = context.scene
        
        # Create a set of proxy names that should be visible
        visible_proxy_names = {item.name for item in scene.em_list}
        
        # Process only objects that match proxy names or are in the 'Proxy' collection
        proxy_collection = bpy.data.collections.get('Proxy')
        proxy_objects = []
        
        # Build list of proxy objects
        if proxy_collection:
            # Add objects from Proxy collection
            proxy_objects.extend(proxy_collection.objects)
        
        # Also add any objects with matching names from em_list
        for obj_name in visible_proxy_names:
            obj = bpy.data.objects.get(obj_name)
            if obj and obj.type == 'MESH' and obj not in proxy_objects:
                proxy_objects.append(obj)
        
        # Hide/Show only proxy objects based on the list
        hidden_count = 0
        shown_count = 0
        
        for obj in proxy_objects:
            if obj.type == 'MESH':  # Ensure we only process mesh objects
                if obj.name in visible_proxy_names:
                    if obj.hide_viewport:
                        obj.hide_viewport = False
                        shown_count += 1
                else:
                    if not obj.hide_viewport:
                        obj.hide_viewport = True
                        hidden_count += 1
        
        # Update visibility icons in the em_list
        for item in scene.em_list:
            obj = bpy.data.objects.get(item.name)
            if obj:
                item.is_visible = not obj.hide_viewport
        
        self.report({'INFO'}, f"Proxy visibility synchronized: {shown_count} shown, {hidden_count} hidden")

    def sync_rm_visibility(self, context):
        """Synchronize RM object visibility based on active epoch"""
        scene = context.scene
        
        # Check if we have an active epoch
        if scene.epoch_list_index < 0 or scene.epoch_list_index >= len(scene.epoch_list):
            self.report({'WARNING'}, "No active epoch selected")
            return
            
        active_epoch = scene.epoch_list[scene.epoch_list_index]
        active_epoch_name = active_epoch.name
        
        # Get RM objects from the RM list
        rm_objects = []
        
        # Find objects in the scene that are registered as RM in the rm_list
        for item in scene.rm_list:
            obj = bpy.data.objects.get(item.name)
            if obj and obj.type == 'MESH':
                rm_objects.append((obj, item))
        
        # Also check for objects in the RM collection
        rm_collection = bpy.data.collections.get('RM')
        if rm_collection:
            for obj in rm_collection.objects:
                if obj.type == 'MESH' and not any(o[0] == obj for o in rm_objects):
                    # Try to find matching RM item
                    rm_item = None
                    for item in scene.rm_list:
                        if item.name == obj.name:
                            rm_item = item
                            break
                    
                    if rm_item:
                        rm_objects.append((obj, rm_item))
        
        # Hide/Show RM objects based on epoch association
        hidden_count = 0
        shown_count = 0
        
        for obj, rm_item in rm_objects:
            # Check if this RM belongs to the active epoch
            belongs_to_active_epoch = False
            
            # Check the first epoch and any additional epochs
            if rm_item.first_epoch == active_epoch_name:
                belongs_to_active_epoch = True
            else:
                # Check additional epochs
                for epoch_item in rm_item.epochs:
                    if epoch_item.name == active_epoch_name:
                        belongs_to_active_epoch = True
                        break
            
            # Handle visibility
            if belongs_to_active_epoch:
                if obj.hide_viewport:
                    obj.hide_viewport = False
                    shown_count += 1
            else:
                if not obj.hide_viewport:
                    obj.hide_viewport = True
                    hidden_count += 1
        
        self.report({'INFO'}, f"RM visibility synchronized: {shown_count} shown, {hidden_count} hidden for epoch '{active_epoch_name}'")

class EM_strat_activate_collections(bpy.types.Operator):
    bl_idname = "em.strat_activate_collections"
    bl_label = "Activate Stratigraphy Collections"
    bl_description = "Activate all collections containing proxies in the current list"
    bl_options = {"REGISTER", "UNDO"}
    
    def execute(self, context):
        scene = context.scene
        
        # Create a set of names that are in the list
        proxy_names = {item.name for item in scene.em_list}
        activated_collections = []
        
        # Process all collections
        for collection in bpy.data.collections:
            contains_proxy = False
            
            for obj in collection.objects:
                if obj.name in proxy_names:
                    contains_proxy = True
                    break
            
            if contains_proxy and collection.hide_viewport:
                collection.hide_viewport = False
                activated_collections.append(collection.name)
        
        if activated_collections:
            self.show_activation_message(", ".join(activated_collections))
            self.report({'INFO'}, f"Activated {len(activated_collections)} collections")
        else:
            self.report({'INFO'}, "No hidden collections with proxies found")
        
        return {'FINISHED'}
    
    def show_activation_message(self, collection_names):
        def draw(self, context):
            self.layout.label(text="The following collections have been activated:")
            self.layout.label(text=collection_names)
        
        bpy.context.window_manager.popup_menu(draw, title="Collections Activated", icon='INFO')


#####################################################################
# Stratigraphy Manager (formerly US/USV Manager)

class EM_ToolsPanel:
    bl_label = "Stratigraphy Manager"  # Renamed from "US/USV Manager"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        em_settings = scene.em_settings
        obj = context.object
        
        # Aggiungiamo i controlli per i filtri
        box = layout.box()
        row = box.row(align=True)
        row.label(text=" Rows: " + str(len(scene.em_list)))
        
        # Verifichiamo che le proprietà esistano prima di usarle
        if hasattr(scene, "filter_by_epoch"):
            row.prop(scene, "filter_by_epoch", text="", toggle=True, icon='SORTTIME')
            
            # Se il filtro per epoca è attivo, mostra l'opzione per includere unità sopravvissute
            # Nota: abbiamo migliorato l'UI dell'opzione "Include Surviving Units"
            if scene.filter_by_epoch:
                sub_row = box.row(align=True)
                # Usa l'operatore invece della proprietà
                icon = 'CHECKBOX_HLT' if scene.include_surviving_units else 'CHECKBOX_DEHLT'
                op = sub_row.operator("em.toggle_include_surviving", 
                                    text="Include Surviving Units", 
                                    icon=icon)                
                # etichetta informativa per chiarire cosa fa questa opzione
                sub_box = box.box()
                sub_box.label(text="Survival Filter:", icon='INFO')
                sub_box.label(text="- When enabled: Shows all units that exist in this epoch")
                sub_box.label(text="- When disabled: Shows only units created in this epoch")

        if hasattr(scene, "filter_by_activity"):
            row.prop(scene, "filter_by_activity", text="", toggle=True, icon='NETWORK_DRIVE')
        
        # Reset filtri
        if hasattr(scene, "filter_by_epoch") and hasattr(scene, "filter_by_activity"):
            if scene.filter_by_epoch or scene.filter_by_activity:
                row.operator("em.reset_filters", text="", icon='X')


        if hasattr(scene, "sync_list_visibility"):
            row.prop(scene, "sync_list_visibility", text="Sync", 
                    icon='HIDE_OFF' if scene.sync_list_visibility else 'HIDE_ON')

        # Add new toggle for RM sync
        row.prop(scene, "sync_rm_visibility", text="", 
                icon= 'OBJECT_DATA') # 'RESTRICT_VIEW_OFF' if scene.sync_rm_visibility else 'RESTRICT_VIEW_ON')

        # Tasto per attivare tutte le collezioni con proxy
        row.operator("em.strat_activate_collections", text="", icon='OUTLINER_COLLECTION')

        # After the other filter buttons:
        if hasattr(scene, "filter_by_epoch") and hasattr(scene, "filter_by_activity"):
            if scene.filter_by_epoch or scene.filter_by_activity:
                row.operator("em.reset_filters", text="", icon='X')
                
            # Add debug button
            row.operator("em.debug_filters", text="", icon='CONSOLE')

        if obj:
            #split = row.split()

            if check_if_current_obj_has_brother_inlist(obj.name, "em_list"):
                #col = split.column(align=True)
                op = row.operator("select.listitem", text='', icon="LONGDISPLAY")
                if op:
                    op.list_type = "em_list"
            else:
                #col = split.column()
                row.label(text="", icon='LONGDISPLAY')    

        box = layout.box()
        row = box.row(align=True)
        split = row.split()
        col = split.column()

        if len(scene.epoch_list) > 0 and scene.epoch_list_index < len(scene.epoch_list):
                current_epoch = scene.epoch_list[scene.epoch_list_index].name
                col.label(text=current_epoch, icon="SORTTIME")
        else:
            # Solo visualizza un messaggio
            col.label(text="No epoch", icon="SORTTIME")
            # Aggiungi un pulsante per resettare l'indice
            op = col.operator("epoch_manager.reset_index", text="Reset Index", icon="FILE_REFRESH")
            
        
        col = split.column()
        if len(scene.activity_manager.activities) > 0:

            if len(scene.activity_manager.activities) > 0 and scene.activity_manager.active_index < len(scene.activity_manager.activities):
                current_activity = scene.activity_manager.activities[scene.activity_manager.active_index].name
                col.label(text=current_activity, icon="NETWORK_DRIVE")
            else:
                col.label(text="No activities", icon="ERROR")

        else:
            col.label(text="No activities", icon="ERROR")

        row = layout.row()

        if scene.em_list and ensure_valid_index(scene.em_list, "em_list_index"):
            row.template_list("EM_STRAT_UL_List", "EM nodes", scene, "em_list", scene, "em_list_index")
            item = scene.em_list[scene.em_list_index]
 
                
            box = layout.box()
            row = box.row(align=True)
            split = row.split()
            col = split.column()
            row.prop(item, "name", text="")
            
            # type node
            split = row.split()
            col = split.column()
            row.label(text="  Type: "+item.node_type)

            # Aggiunta toggle visibilità
            if hasattr(item, "is_visible"):
                icon = 'HIDE_OFF' if item.is_visible else 'HIDE_ON'
                op = row.operator("em.strat_toggle_visibility", text="", icon=icon)
                if op:
                    op.index = scene.em_list_index

            # link proxy and US
            split = row.split()
            col = split.column()
            op = col.operator("listitem.toobj", icon="LINK_BLEND", text='')
            if op:
                op.list_type = "em_list"
            
            row = box.row()
            row.prop(item, "description", text="", slider=True, emboss=True)

            if scene.em_settings.em_proxy_sync is True:
                if obj is not None:
                    if check_if_current_obj_has_brother_inlist(obj.name, "em_list"):
                            select_list_element_from_obj_proxy(obj, "em_list")
                    
            if scene.em_settings.em_proxy_sync2 is True:
                if scene.em_list[scene.em_list_index].icon == 'RESTRICT_INSTANCED_OFF':
                    list_item = scene.em_list[scene.em_list_index]
                    if obj is not None:
                        if list_item.name != obj.name:
                            select_3D_obj(list_item.name)
                            if scene.em_settings.em_proxy_sync2_zoom is True:
                                for area in bpy.context.screen.areas:
                                    if area.type == 'VIEW_3D':
                                        ctx = bpy.context.copy()
                                        ctx['area'] = area
                                        ctx['region'] = area.regions[-1]
                                        bpy.ops.view3d.view_selected(ctx)
        else:
            row.label(text="No stratigraphic units here :-(")


class VIEW3D_PT_ToolsPanel(Panel, EM_ToolsPanel):
    bl_category = "EM"
    bl_idname = "VIEW3D_PT_ToolsPanel"
    bl_context = "objectmode"

# Custom list drawing with visibility icon - renamed to avoid conflicts

class EM_STRAT_UL_List(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        icons_style = 'OUTLINER'
        scene = context.scene
        is_in_scene = item.icon == 'RESTRICT_INSTANCED_OFF'
        
        # Layout with better spacing
        row = layout.row(align=True)
        
        # First column: Chain icon (active or inactive)
        first_split = row.split(factor=0.03)
        col1 = first_split.column(align=True)
        
        # Use the same column structure but control enablement at the column level
        sub_col = col1.column(align=True)
        sub_col.enabled = is_in_scene
        
        # Always use an operator, but the column enablement controls its functionality
        op = sub_col.operator("select.fromlistitem", text="", icon=item.icon, emboss=False)
        if op:
            op.list_type = "em_list"
            op.specific_item = item.name
        
        remaining = first_split.column(align=True)
        
        # Name column (25% of remaining space)
        name_split = remaining.split(factor=0.25)
        col2 = name_split.column(align=True)
        col2.label(text=item.name)
        
        # Description and visibility toggle
        desc_vis_split = name_split.column(align=True).split(factor=0.98)
        col3 = desc_vis_split.column(align=True)
        col3.label(text=item.description)
        
        # Visibility toggle
        col4 = desc_vis_split.column(align=True)
        col4.enabled = is_in_scene
        if hasattr(item, "is_visible"):
            vis_icon = 'HIDE_OFF' if item.is_visible else 'HIDE_ON'
            op = col4.operator("em.strat_toggle_visibility", text="", icon=vis_icon, emboss=False)
            if op:
                op.index = index


#### da qui si definiscono le funzioni e gli operatori
class EM_listitem_OT_to3D(bpy.types.Operator):
    bl_idname = "listitem.toobj"
    bl_label = "Use element's name from the list above to rename selected 3D object"
    bl_options = {"REGISTER", "UNDO"}

    list_type: StringProperty()

    @classmethod
    def poll(cls, context):
        obj = context.object
        if obj is None:
            pass
        else:
            return (obj.type in ['MESH'])

    def execute(self, context):
        scene = context.scene
        item_name_picker_cmd = "scene."+self.list_type+"[scene."+self.list_type+"_index]"
        item = eval(item_name_picker_cmd)
        context.active_object.name = item.name
        update_icons(context, self.list_type)
        if self.list_type == "em_list":
            if scene.proxy_display_mode == "EM":
                bpy.ops.emset.emmaterial()
            else:
                bpy.ops.emset.epochmaterial()
        return {'FINISHED'}

class EM_update_icon_list(bpy.types.Operator):
    bl_idname = "list_icon.update"
    bl_label = "Update only the icons"
    bl_options = {"REGISTER", "UNDO"}

    list_type: StringProperty()

    def execute(self, context):
        if self.list_type == "all":
            lists = ["em_list","epoch_list","em_sources_list","em_properties_list","em_extractors_list","em_combiners_list","em_v_sources_list","em_v_properties_list","em_v_extractors_list","em_v_combiners_list"]
            for single_list in lists:
                update_icons(context, single_list)
        else:
            update_icons(context, self.list_type)
        return {'FINISHED'}

class EM_select_list_item(bpy.types.Operator):
    bl_idname = "select.listitem"
    bl_label = "Select element in the list above from a 3D proxy"
    bl_description = "Select the row in the stratigraphy manager corresponding to the active proxy in the scene"
    bl_options = {"REGISTER", "UNDO"}

    list_type: StringProperty() # type: ignore

    def execute(self, context):
        scene = context.scene
        obj = context.object
        select_list_element_from_obj_proxy(obj, self.list_type)
        return {'FINISHED'}

class EM_select_from_list_item(bpy.types.Operator):
    bl_idname = "select.fromlistitem"
    bl_label = "Select 3D obj from the list above"
    bl_options = {"REGISTER", "UNDO"}

    list_type: StringProperty() # type: ignore
    specific_item: StringProperty(default="")  # type: ignore # Add this line

    def execute(self, context):
        scene = context.scene
        if self.specific_item:
            # Use the specific item name passed from the UI
            select_3D_obj(self.specific_item)
        else:
            # Fallback to the old behavior using the active index
            list_type_cmd = "scene."+self.list_type+"[scene."+self.list_type+"_index]"
            list_item = eval(list_type_cmd)
            select_3D_obj(list_item.name)
        return {'FINISHED'}

class EM_not_in_matrix(bpy.types.Operator):
    bl_idname = "notinthematrix.material"
    bl_label = "Helper for proxies visualization"
    bl_description = "Apply a custom material to proxies not yet present in the matrix"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        EM_mat_list = ['US', 'USVs', 'USVn', 'VSF', 'SF', 'USD']
        EM_mat_name = "mat_NotInTheMatrix"
        R = 1.0
        G = 0.0
        B = 1.0
        if not check_material_presence(EM_mat_name):
            newmat = bpy.data.materials.new(EM_mat_name)
            em_setup_mat_cycles(EM_mat_name,R,G,B)

        for ob in bpy.data.objects:
            if ob.type == 'MESH':
                if ob.data.materials:
                    if ob.material_slots[0].material.name in EM_mat_list or ob.material_slots[0].material.name.startswith('ep_'):
                        matrix_mat = True
                    else:
                        matrix_mat = False
                    not_in_matrix = True
                    for item in context.scene.em_list:
                        if item.name == ob.name:
                            not_in_matrix = False
                    if matrix_mat and not_in_matrix:
                        ob.data.materials.clear()
                        notinmatrix_mat = bpy.data.materials[EM_mat_name]
                        ob.data.materials.append(notinmatrix_mat)

        return {'FINISHED'}


def filter_list_update(self, context):
    """
    Update callback for filter toggle buttons.
    This function is called whenever a filter button is toggled.
    """
    scene = context.scene
    
    # PREVENT RECURSIVE CALLS: Check if we're already inside this function
    if hasattr(filter_list_update, "is_running") and filter_list_update.is_running:
        print("Preventing recursive filter_list_update call")
        return
    
    # Set flag to prevent recursion
    filter_list_update.is_running = True
    
    try:
        # Check which filter was toggled (self.name can be "filter_by_epoch" or "filter_by_activity")
        filter_name = getattr(self, "name", None)
        filter_value = getattr(scene, filter_name, False) if filter_name else False
        
        print(f"\n--- Filter toggle: {filter_name} = {filter_value} ---")
        
        # Check if there's a valid graph before proceeding
        from .functions import is_graph_available as check_graph
        graph_exists, _ = check_graph(context)
        
        if graph_exists:
            # Only apply filtering if at least one filter is active
            if scene.filter_by_epoch or scene.filter_by_activity:
                try:
                    bpy.ops.em.filter_lists()
                except Exception as e:
                    print(f"Error applying filters: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                # If all filters are off, use our reset operator
                # which is now fixed to not duplicate lists
                try:
                    bpy.ops.em.reset_filters()
                except Exception as e:
                    print(f"Error resetting filters: {e}")
                    import traceback
                    traceback.print_exc()
        else:
            # Show message to load a graph first
            bpy.context.window_manager.popup_menu(
                lambda self, context: self.layout.label(text="Please load a graph before filtering"),
                title="No Graph Available",
                icon='ERROR'
            )
            
            # Reset the filter that was just toggled
            if filter_name:
                # Disable temporary to prevent another callback
                old_is_running = getattr(filter_list_update, "is_running", False)
                filter_list_update.is_running = True
                
                setattr(scene, filter_name, False)
                print(f"Reset {filter_name} to False since no graph is available")
                
                # Restore previous state
                filter_list_update.is_running = old_is_running
    
    finally:
        # Reset the flag to allow future calls
        filter_list_update.is_running = False


def sync_visibility_update(self, context):
    if self.sync_list_visibility:
        try:
            bpy.ops.em.strat_sync_visibility()
        except Exception as e:
            print(f"Error syncing visibility: {e}")


# Add this new operator to EM_list.py
class EM_debug_filters(bpy.types.Operator):
    bl_idname = "em.debug_filters"
    bl_label = "Debug Filters"
    bl_description = "Print debug information about the current epoch and connected nodes"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        scene = context.scene
        
        # Get current graph
        from .functions import is_graph_available as check_graph
        graph_exists, graph = check_graph(context)
        
        if not graph_exists:
            self.report({'WARNING'}, "No active graph found. Please load a GraphML file first.")
            return {'CANCELLED'}
        
        print("\n=== FILTER DEBUG INFORMATION ===")
        
        # Print active epoch info
        print("\nActive Epoch Info:")
        if scene.epoch_list_index >= 0 and len(scene.epoch_list) > 0:
            active_epoch = scene.epoch_list[scene.epoch_list_index]
            print(f"  Name: {active_epoch.name}")
            print(f"  Start Time: {active_epoch.start_time}")
            print(f"  End Time: {active_epoch.end_time}")
            
            # Find the epoch node in the graph
            epoch_node = None
            for node in graph.nodes:
                if hasattr(node, 'node_type') and node.node_type == 'epoch' and node.name == active_epoch.name:
                    epoch_node = node
                    break
            
            if epoch_node:
                print(f"  Found epoch node in graph: {epoch_node.node_id}")
                
                # Count nodes connected to this epoch
                created_in_epoch = []
                surviving_in_epoch = []
                
                for edge in graph.edges:
                    if edge.edge_target == epoch_node.node_id:
                        source_node = graph.find_node_by_id(edge.edge_source)
                        if source_node and hasattr(source_node, 'node_type'):
                            if edge.edge_type == "has_first_epoch":
                                created_in_epoch.append(source_node)
                            elif edge.edge_type == "survive_in_epoch":
                                surviving_in_epoch.append(source_node)
                
                print(f"  Nodes created in this epoch: {len(created_in_epoch)}")
                for node in created_in_epoch:
                    print(f"    - {node.name} (Type: {node.node_type}, UUID: {node.node_id})")
                
                print(f"  Nodes surviving in this epoch: {len(surviving_in_epoch)}")
                for node in surviving_in_epoch:
                    print(f"    - {node.name} (Type: {node.node_type}, UUID: {node.node_id})")
                    
                # Check inclusion status
                include_surviving = scene.include_surviving_units
                print(f"  Include surviving units: {include_surviving}")
                
                # Total expected nodes
                expected_total = len(created_in_epoch) + (len(surviving_in_epoch) if include_surviving else 0)
                print(f"  Expected total nodes in filtered list: {expected_total}")
                
            else:
                print(f"  WARNING: Could not find epoch node in graph!")
        else:
            print("  No active epoch selected")
        
        # Print active activity info
        print("\nActive Activity Info:")
        if scene.filter_by_activity and scene.activity_manager.active_index >= 0 and len(scene.activity_manager.activities) > 0:
            active_activity = scene.activity_manager.activities[scene.activity_manager.active_index]
            print(f"  Name: {active_activity.name}")
            
            # Find the activity node in the graph
            activity_node = None
            for node in graph.nodes:
                if hasattr(node, 'node_type') and node.node_type == 'ActivityNodeGroup' and node.name == active_activity.name:
                    activity_node = node
                    break
            
            if activity_node:
                print(f"  Found activity node in graph: {activity_node.node_id}")
                
                # Count nodes in this activity
                nodes_in_activity = []
                
                for edge in graph.edges:
                    if edge.edge_target == activity_node.node_id and edge.edge_type == "is_in_activity":
                        source_node = graph.find_node_by_id(edge.edge_source)
                        if source_node and hasattr(source_node, 'node_type'):
                            nodes_in_activity.append(source_node)
                
                print(f"  Nodes in this activity: {len(nodes_in_activity)}")
                for node in nodes_in_activity:
                    print(f"    - {node.name} (Type: {node.node_type}, UUID: {node.node_id})")
            else:
                print(f"  WARNING: Could not find activity node in graph!")
        else:
            print("  No active activity selected")
        
        # Current filtered list info
        print("\nCurrent Filtered List Info:")
        print(f"  Items in em_list: {len(scene.em_list)}")
        print(f"  Filter by epoch: {scene.filter_by_epoch}")
        print(f"  Filter by activity: {scene.filter_by_activity}")
        
        # Compare with all stratigraphic nodes
        strat_nodes = [node for node in graph.nodes if hasattr(node, 'node_type') and 
                       node.node_type in ['US', 'USVs', 'USVn', 'VSF', 'SF', 'USD', 'serSU', 'serUSVn', 'serUSVs']]
        print(f"  Total stratigraphic nodes in graph: {len(strat_nodes)}")
        
        print("=== END FILTER DEBUG INFORMATION ===\n")
        
        self.report({'INFO'}, "Filter debug information printed to console")
        return {'FINISHED'}


class EM_toggle_include_surviving(bpy.types.Operator):
    bl_idname = "em.toggle_include_surviving"
    bl_label = "Toggle Include Surviving Units"
    bl_description = "Toggle whether to include units that survive in the current epoch"
    bl_options = {"REGISTER", "UNDO"}
    
    def execute(self, context):
        scene = context.scene
        # Invert the current value
        scene.include_surviving_units = not scene.include_surviving_units
        
        print(f"Toggled include_surviving_units to: {scene.include_surviving_units}")
        
        # Manually reapply the filter if epoch filtering is active
        if scene.filter_by_epoch:
            bpy.ops.em.filter_lists()
            
        return {'FINISHED'}


#SETUP MENU
#####################################################################

classes = [
    EM_STRAT_UL_List,
    EM_listitem_OT_to3D,
    VIEW3D_PT_ToolsPanel,
    EM_update_icon_list,
    EM_select_from_list_item,
    EM_select_list_item,
    EM_not_in_matrix,
    EM_filter_lists, 
    EM_reset_filters,
    EM_strat_toggle_visibility,
    EM_strat_sync_visibility,
    EM_strat_activate_collections,
    EM_debug_filters,
    EM_toggle_include_surviving
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    # Register new properties directly on Scene
    if not hasattr(bpy.types.Scene, "filter_by_epoch"):
        bpy.types.Scene.filter_by_epoch = BoolProperty(
            name="Filter by Epoch",
            description="Show only elements from the active epoch",
            default=False,
            update=filter_list_update
        )

    if not hasattr(bpy.types.Scene, "filter_by_activity"):
        bpy.types.Scene.filter_by_activity = BoolProperty(
            name="Filter by Activity",
            description="Show only elements from the active activity",
            default=False,
            update=filter_list_update
        )

    if not hasattr(bpy.types.Scene, "sync_list_visibility"):
        bpy.types.Scene.sync_list_visibility = BoolProperty(
            name="Sync Visibility",
            description="Synchronize proxy visibility with the current list (shows only proxies in the filtered list)",
            default=False,
            update=sync_visibility_update
        )

    if not hasattr(bpy.types.Scene, "sync_rm_visibility"):
        bpy.types.Scene.sync_rm_visibility = BoolProperty(
            name="Sync RM Visibility",
            description="Synchronize Representation Model visibility based on active epoch",
            default=False,
            update=sync_visibility_update  # Re-use the same update function
        )

    if not hasattr(bpy.types.Scene, "include_surviving_units"):
        print("Registering include_surviving_units property with update callback")
        bpy.types.Scene.include_surviving_units = bpy.props.BoolProperty(
            name="Include Surviving Units",
            description="Include units that survive in this epoch but were created in previous epochs",
            default=True
        )

def unregister():
    # Remove scene properties if they exist
    if hasattr(bpy.types.Scene, "filter_by_epoch"):
        del bpy.types.Scene.filter_by_epoch
    
    if hasattr(bpy.types.Scene, "filter_by_activity"):
        del bpy.types.Scene.filter_by_activity
    
    if hasattr(bpy.types.Scene, "sync_list_visibility"):
        del bpy.types.Scene.sync_list_visibility

    if hasattr(bpy.types.Scene, "sync_rm_visibility"):
        del bpy.types.Scene.sync_rm_visibility

    # Unregister classes in reverse order
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception as e:
            print(f"Error unregistering {cls.__name__}: {e}")