"""
Operators for the Stratigraphy Manager
This module contains all the operators needed for interacting with
stratigraphic units in the 3D viewport and in the UI lists.
"""

import bpy
import os
from bpy.props import StringProperty, IntProperty, BoolProperty
from bpy.types import Operator

from ..functions import check_material_presence, em_setup_mat_cycles, update_icons
from ..functions import select_3D_obj, select_list_element_from_obj_proxy

from s3dgraphy.utils.utils import manage_id_prefix, get_base_name, add_graph_prefix

def find_layer_collection(layer_collection, collection_name):
    """Trova ricorsivamente un layer_collection dato il nome della collection"""
    if layer_collection.name == collection_name:
        return layer_collection
    
    for child in layer_collection.children:
        found = find_layer_collection(child, collection_name)
        if found:
            return found
    return None

def activate_collection_fully(context, collection):
    """
    Attiva completamente una collezione sia a livello base che nel view layer
    E attiva ricorsivamente tutte le collezioni padre.
    
    Retrocompatibile con tutte le versioni di Blender (non usa layer_collection.parent)
    Returns: True se la collezione è stata attivata, False se era già attiva
    """
    was_activated = False
    
    # 1. Attiva collection base
    if collection.hide_viewport:
        collection.hide_viewport = False
        was_activated = True
    
    # 2. Attiva layer collection nel view layer
    layer_collection = find_layer_collection(context.view_layer.layer_collection, collection.name)
    if layer_collection and layer_collection.exclude:
        layer_collection.exclude = False
        was_activated = True
        
        # 3. ATTIVA RICORSIVAMENTE tutte le collezioni padre
        # Metodo retrocompatibile: costruisce il percorso dalla root
        def build_path_to_target(layer_col, target_name, path=None):
            """Costruisce il percorso dalla root alla collezione target"""
            if path is None:
                path = []
            
            if layer_col.name == target_name:
                path.append(layer_col)
                return True
            
            # Cerca ricorsivamente nei figli
            for child in layer_col.children:
                if build_path_to_target(child, target_name, path):
                    # Inserisci questo nodo all'inizio del path (prima del figlio)
                    path.insert(0, layer_col)
                    return True
            
            return False
        
        # Costruisci il path dalla root alla collezione target
        path = []
        if build_path_to_target(context.view_layer.layer_collection, collection.name, path):
            # Attiva tutte le collezioni nel percorso (esclusa la root del view layer)
            for layer_col in path:
                if layer_col != context.view_layer.layer_collection:
                    if layer_col.exclude:
                        layer_col.exclude = False
                        was_activated = True
    
    return was_activated

class EM_strat_toggle_visibility(Operator):
    bl_idname = "em.strat_toggle_visibility"
    bl_label = "Toggle Stratigraphy Visibility"
    bl_description = "Toggle visibility of the selected proxy in the scene"
    bl_options = {"REGISTER", "UNDO"}
    
    index: IntProperty(default=-1)  # -1 means use the active index
    
    def execute(self, context):
        """
        Toggle visibility for a single stratigraphic unit.

        ✅ CLEAN VERSION: Uses only scene.em_tools.stratigraphy paths
        """
        scene = context.scene
        strat = scene.em_tools.stratigraphy  # ✅ Nuovo

        index = self.index if self.index >= 0 else strat.units_index

        if index >= 0 and index < len(strat.units):
            item = strat.units[index]
            obj = bpy.data.objects.get(item.name)

            if obj:
                # Toggle visibility AND render synchronously
                new_visibility = not obj.hide_viewport
                obj.hide_viewport = not new_visibility
                obj.hide_render = not new_visibility
                item.is_visible = new_visibility

                # If the object is shown, activate its collections
                if new_visibility:
                    self.activate_object_collections(obj, context)

                return {'FINISHED'}
            else:
                self.report({'WARNING'}, f"Object '{item.name}' not found in scene")

        return {'CANCELLED'}
    
    def is_in_hidden_collection(self, obj, context):
        """Check if the object is in a hidden collection."""
        for collection in bpy.data.collections:
            if obj.name in collection.objects and collection.hide_viewport:
                return True
        return False
    
    def activate_object_collections(self, obj, context):
        """Activate all collections containing the object."""
        activated_collections = []
        
        for collection in bpy.data.collections:
            if obj.name in collection.objects:
                if activate_collection_fully(context, collection):
                    activated_collections.append(collection.name)
        
        if activated_collections:
            self.show_activation_message(", ".join(activated_collections))
    
    def show_activation_message(self, collection_names):
        def draw(self, context):
            self.layout.label(text="The following collections have been activated:")
            self.layout.label(text=collection_names)
        
        bpy.context.window_manager.popup_menu(draw, title="Collections Activated", icon='INFO')

class EM_strat_sync_visibility(Operator):
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
        """
        Synchronize proxy visibility with filtered list.

        ✅ CLEAN VERSION: Uses only scene.em_tools.stratigraphy paths
        """
        scene = context.scene
        strat = scene.em_tools.stratigraphy  # ✅ Nuovo

        # ✅ Usa SOLO nuovo path
        visible_proxy_names = {item.name for item in strat.units}
        
        # Find all proxy objects - need to include ALL mesh objects from proxy collections
        # plus any objects with matching names
        proxy_objects = []
        proxy_objects_set = set()  # To avoid duplicates
        activated_collections = []
        
        # Strategy: Look for collections that contain objects matching our em_list names
        # and treat those entire collections as "proxy collections"
        proxy_collections = set()
        
        # First pass: identify which collections contain objects from em_list
        all_em_list_names = {item.name for item in strat.units}
        for collection in bpy.data.collections:
            for obj in collection.objects:
                if get_base_name(obj.name) in all_em_list_names and obj.type == 'MESH':
                    proxy_collections.add(collection)
                    break
        
        # Add the original "Proxy" collection if it exists (for backward compatibility)
        proxy_collection = bpy.data.collections.get('Proxy')
        if proxy_collection:
            proxy_collections.add(proxy_collection)
        
        # Second pass: add ALL mesh objects from identified proxy collections
        for collection in proxy_collections:
            contains_visible_proxy = False
            
            for obj in collection.objects:
                if obj.type == 'MESH' and obj not in proxy_objects_set:
                    proxy_objects.append(obj)
                    proxy_objects_set.add(obj)
                    
                    # Check if this collection should be activated
                    if get_base_name(obj.name) in visible_proxy_names:
                        contains_visible_proxy = True
            
            # Activate collection COMPLETELY (base + view layer + parent) if it contains visible proxies
            if contains_visible_proxy:
                if activate_collection_fully(context, collection):
                    activated_collections.append(collection.name)
        
        # Also add any objects with matching names that might not be in proxy collections
        for obj_name in all_em_list_names:
            obj = bpy.data.objects.get(get_base_name(obj_name))
            if obj and obj.type == 'MESH' and obj not in proxy_objects_set:
                proxy_objects.append(obj)
                proxy_objects_set.add(obj)
        
        # Hide/Show proxy objects based on the list AND sync render state
        hidden_count = 0
        shown_count = 0
        
        for obj in proxy_objects:
            if get_base_name(obj.name) in visible_proxy_names:
                # Object should be visible AND renderable
                if obj.hide_viewport or obj.hide_render:
                    obj.hide_viewport = False
                    obj.hide_render = False
                    shown_count += 1
            else:
                # Object should be hidden AND non-renderable
                if not obj.hide_viewport or not obj.hide_render:
                    obj.hide_viewport = True
                    obj.hide_render = True
                    hidden_count += 1
        
        # ✅ Update icons SOLO nuova lista (no dual-sync!)
        for item in strat.units:
            obj = bpy.data.objects.get(get_base_name(item.name))
            if obj:
                item.is_visible = not obj.hide_viewport
        
        # Report results
        message = f"Proxy visibility and render synchronized: {shown_count} shown, {hidden_count} hidden"
        if activated_collections:
            message += f". Activated collections: {', '.join(activated_collections)}"
        
        self.report({'INFO'}, message)
        
    def sync_rm_visibility(self, context):
        """Synchronize RM object visibility based on active epoch"""
        scene = context.scene
        epochs = scene.em_tools.epochs
        
        # Check if we have an active epoch
        if epochs.list_index < 0 or epochs.list_index >= len(epochs.list):
            self.report({'WARNING'}, "No active epoch selected")
            return
            
        active_epoch = epochs.list[epochs.list_index]
        active_epoch_name = active_epoch.name
        
        # Get RM objects from the RM list
        rm_objects = []
        activated_collections = []
        
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
        
        # Find collections that contain RM objects that should be visible
        visible_rm_objects = []
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
            
            if belongs_to_active_epoch:
                visible_rm_objects.append(obj)
        
        # Activate collections that contain visible RM objects
        collections_to_check = set()
        
        # Add RM collection
        if rm_collection:
            collections_to_check.add(rm_collection)
        
        # Find all collections containing visible RM objects
        for obj in visible_rm_objects:
            for collection in bpy.data.collections:
                if obj.name in collection.objects:
                    collections_to_check.add(collection)
        
        # ATTIVA COMPLETAMENTE le collezioni (base + view layer + parent)
        for collection in collections_to_check:
            contains_visible_rm = any(obj.name in collection.objects for obj in visible_rm_objects)
            if contains_visible_rm:
                if activate_collection_fully(context, collection):
                    activated_collections.append(collection.name)
        
        # Hide/Show RM objects based on epoch association AND sync render state
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
            
            # Handle visibility AND render synchronously
            if belongs_to_active_epoch:
                # Object should be visible AND renderable
                if obj.hide_viewport or obj.hide_render:
                    obj.hide_viewport = False
                    obj.hide_render = False
                    shown_count += 1
            else:
                # Object should be hidden AND non-renderable
                if not obj.hide_viewport or not obj.hide_render:
                    obj.hide_viewport = True
                    obj.hide_render = True
                    hidden_count += 1
        
        # Report results
        message = f"RM visibility and render synchronized: {shown_count} shown, {hidden_count} hidden for epoch '{active_epoch_name}'"
        if activated_collections:
            message += f". Activated collections: {', '.join(activated_collections)}"
        
        self.report({'INFO'}, message)

class EM_strat_show_all_proxies(Operator):
    """Reset filters and show all proxy objects"""
    bl_idname = "em.strat_show_all_proxies"
    bl_label = "Show All Proxies"
    bl_description = "Reset all filters and show all proxy objects with render enabled"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene

        bpy.ops.epoch_manager.reset_visibility_ui()
        
        # 1. First reset all filters using the existing operator
        if scene.filter_by_epoch or scene.filter_by_activity:
            bpy.ops.em.reset_filters()
        
        # 2. Enable sync to ensure the system is active
        scene.sync_list_visibility = True
        
        # 3. Use the existing sync system but with all proxies visible
        shown_count = self.sync_all_proxies(scene, context)
        
        self.report({'INFO'}, f"All proxies shown and made renderable: {shown_count} objects")
        return {'FINISHED'}
    
    def sync_all_proxies(self, scene, context):
        """
        Show all proxy objects.

        ✅ CLEAN VERSION: Uses only scene.em_tools.stratigraphy paths
        """
        strat = scene.em_tools.stratigraphy  # ✅ Nuovo

        # Use the same logic as sync_proxy_visibility but without filtering
        proxy_objects = []
        proxy_objects_set = set()
        activated_collections = []

        # Strategy: Look for collections that contain objects matching our em_list names
        proxy_collections = set()

        # First pass: identify which collections contain objects from em_list
        # ✅ Usa SOLO nuovo path
        all_em_list_names = {item.name for item in strat.units}
        for collection in bpy.data.collections:
            for obj in collection.objects:
                if obj.name in all_em_list_names and obj.type == 'MESH':
                    proxy_collections.add(collection)
                    break
        
        # Add the original "Proxy" collection if it exists
        proxy_collection = bpy.data.collections.get('Proxy')
        if proxy_collection:
            proxy_collections.add(proxy_collection)
        
        # Second pass: add ALL mesh objects from identified proxy collections
        for collection in proxy_collections:
            for obj in collection.objects:
                if obj.type == 'MESH' and obj not in proxy_objects_set:
                    proxy_objects.append(obj)
                    proxy_objects_set.add(obj)
            
            # ATTIVA COMPLETAMENTE le collezioni proxy (base + view layer)
            if activate_collection_fully(context, collection):
                activated_collections.append(collection.name)
        
        # Also add any objects with matching names that might not be in proxy collections
        for obj_name in all_em_list_names:
            obj = bpy.data.objects.get(obj_name)
            if obj and obj.type == 'MESH' and obj not in proxy_objects_set:
                proxy_objects.append(obj)
                proxy_objects_set.add(obj)
                
                # ATTIVA anche le collezioni di questi oggetti singoli
                for collection in bpy.data.collections:
                    if obj.name in collection.objects:
                        if activate_collection_fully(context, collection):
                            if collection.name not in activated_collections:
                                activated_collections.append(collection.name)
        
        # Show ALL proxy objects and make them renderable
        shown_count = 0
        for obj in proxy_objects:
            if obj.hide_viewport or obj.hide_render:
                obj.hide_viewport = False
                obj.hide_render = False
                shown_count += 1
        
        # ✅ Update icons SOLO nuova lista (no dual-sync!)
        for item in strat.units:
            obj = bpy.data.objects.get(item.name)
            if obj:
                item.is_visible = not obj.hide_viewport
        
        # MOSTRA messaggio collezioni attivate (riusa la funzione esistente)
        if activated_collections:
            self.show_activation_message(", ".join(activated_collections))
            
        return shown_count
    
    def show_activation_message(self, collection_names):
        """Mostra il messaggio delle collezioni attivate"""
        def draw(self, context):
            self.layout.label(text="The following collections have been activated:")
            self.layout.label(text=collection_names)
        
        bpy.context.window_manager.popup_menu(draw, title="Collections Activated", icon='INFO')

class EM_strat_show_all_rms(Operator):
    """Reset filters and show all RM objects"""
    bl_idname = "em.strat_show_all_rms"
    bl_label = "Show All RMs"  
    bl_description = "Reset all filters and show all RM objects with render enabled"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        
        # 1. First reset all filters using the existing operator
        if scene.filter_by_epoch or scene.filter_by_activity:
            bpy.ops.em.reset_filters()
        
        # 2. Enable RM sync if available
        if hasattr(scene, 'sync_rm_visibility'):
            scene.sync_rm_visibility = True
        
        # 3. Use the existing RM system but show all RMs
        shown_count = self.sync_all_rms(scene, context)
        
        self.report({'INFO'}, f"All RM objects shown and made renderable: {shown_count} objects")
        return {'FINISHED'}
    
    def sync_all_rms(self, scene, context):
        """Show all RM objects using the existing system logic"""
        shown_count = 0
        activated_collections = []
        
        # Use the SAME logic as sync_rm_visibility but without epoch filtering
        rm_objects = []
        
        # Find objects in the scene that are registered as RM in the rm_list
        for item in scene.rm_list:
            obj = bpy.data.objects.get(item.name)
            if obj and obj.type == 'MESH':
                rm_objects.append(obj)
        
        # Also check for objects in the RM collection
        rm_collection = bpy.data.collections.get('RM')
        if rm_collection:
            for obj in rm_collection.objects:
                if obj.type == 'MESH' and obj not in rm_objects:
                    rm_objects.append(obj)
            
            # ATTIVA COMPLETAMENTE la collezione RM (base + view layer)
            if activate_collection_fully(context, rm_collection):
                activated_collections.append('RM')
        
        # ATTIVA anche eventuali altre collezioni che contengono RM
        for obj in rm_objects:
            for collection in bpy.data.collections:
                if obj.name in collection.objects:
                    if activate_collection_fully(context, collection):
                        if collection.name not in activated_collections:
                            activated_collections.append(collection.name)
        
        # Show and make renderable ALL RM objects
        for obj in rm_objects:
            if obj.hide_viewport or obj.hide_render:
                obj.hide_viewport = False
                obj.hide_render = False
                shown_count += 1
        
        # MOSTRA messaggio collezioni attivate
        if activated_collections:
            self.show_activation_message(", ".join(activated_collections))
        
        return shown_count
    
    def show_activation_message(self, collection_names):
        """Mostra il messaggio delle collezioni attivate"""
        def draw(self, context):
            self.layout.label(text="The following collections have been activated:")
            self.layout.label(text=collection_names)
        
        bpy.context.window_manager.popup_menu(draw, title="Collections Activated", icon='INFO')



class EM_strat_activate_collections(Operator):
    bl_idname = "em.strat_activate_collections"
    bl_label = "Activate Stratigraphy Collections"
    bl_description = "Activate all collections containing proxies in the current list"
    bl_options = {"REGISTER", "UNDO"}
    
    def execute(self, context):
        scene = context.scene
        strat = scene.em_tools.stratigraphy  # ✅ Nuovo

        # Create a set of names that are in the list
        proxy_names = {item.name for item in strat.units}
        activated_collections = []
        
        # Process all collections
        for collection in bpy.data.collections:
            contains_proxy = False
            
            for obj in collection.objects:
                if obj.name in proxy_names:
                    contains_proxy = True
                    break
            
            if contains_proxy:
                if activate_collection_fully(context, collection):
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

class EM_listitem_OT_to3D(Operator):
    bl_idname = "listitem.toobj"
    bl_label = "Use element's name from the list above to rename selected 3D object"
    bl_options = {"REGISTER", "UNDO"}

    list_type: StringProperty() # type: ignore

    @classmethod
    def poll(cls, context):
        obj = context.object
        if obj is None:
            pass
        else:
            return (obj.type in ['MESH'])

    def execute(self, context):

        from ..functions import is_graph_available as check_graph
        from ..operators.addon_prefix_helpers import node_name_to_proxy_name

        scene = context.scene
        item_name_picker_cmd = "scene."+self.list_type+"[scene."+self.list_type+"_index]"
        item = eval(item_name_picker_cmd)

        # ✅ Ottieni il grafo attivo
        graph_exists, graph = check_graph(context)
        active_graph = graph if graph_exists else None
        
        # ✅ Converti il nome con prefisso
        proxy_name = node_name_to_proxy_name(item.name, context=context, graph=active_graph)
        context.active_object.name = proxy_name

        update_icons(context, self.list_type)
        if self.list_type == "em_list":
            current_mode = scene.em_tools.proxy_display_mode
            
            if current_mode == "EM":
                bpy.ops.emset.emmaterial()
            elif current_mode == "Epochs":
                bpy.ops.emset.epochmaterial()
            elif current_mode == "Properties":
                # Mantieni Properties attivo - non cambiarlo!
                pass
            # Future modalità qui
        return {'FINISHED'}

class EM_update_icon_list(Operator):
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

class EM_select_list_item(Operator):
    bl_idname = "select.listitem"
    bl_label = "Select element in the list above from a 3D proxy"
    bl_description = "(ALT+F WIN/Linux; OPTION+F on MAC) to select the 3D object from the list above"
    bl_options = {"REGISTER", "UNDO"}

    list_type: StringProperty() # type: ignore

    def execute(self, context):
        """
        Seleziona un elemento nella lista dal proxy 3D.
        
        ✅ MODIFICATO: Ora ottiene il graph attivo e lo passa
        """
        from ..functions import is_graph_available as check_graph
        
        scene = context.scene
        obj = context.object
        
        # ✅ Ottieni il grafo attivo
        graph_exists, graph = check_graph(context)
        active_graph = graph if graph_exists else None
        
        select_list_element_from_obj_proxy(
            obj, 
            self.list_type,
            context=context,
            graph=active_graph  # ✅ Passa il graph
        )
        
        return {'FINISHED'}

class EM_select_from_list_item(Operator):
    bl_idname = "select.fromlistitem"
    bl_label = "Select 3D obj from the list above"
    bl_options = {"REGISTER", "UNDO"}

    list_type: StringProperty() # type: ignore
    specific_item: StringProperty(default="") # type: ignore

    def execute(self, context):
        """
        Seleziona un oggetto 3D dalla lista.
        
        ✅ MODIFICATO: Ora ottiene il graph attivo e lo passa a select_3D_obj
        """
        from ..functions import is_graph_available as check_graph
        
        scene = context.scene
        
        # ✅ Ottieni il grafo attivo
        graph_exists, graph = check_graph(context)
        active_graph = graph if graph_exists else None
        
        if self.specific_item:
            # Use the specific item name passed from the UI
            select_3D_obj(
                self.specific_item, 
                context=context,
                graph=active_graph  # ✅ Passa il graph
            )
        else:
            # Fallback to the old behavior using the active index
            list_type_cmd = "scene." + self.list_type + "[scene." + self.list_type + "_index]"
            list_item = eval(list_type_cmd)
            select_3D_obj(
                list_item.name,
                context=context, 
                graph=active_graph  # ✅ Passa il graph
            )
        
        return {'FINISHED'}

class EM_not_in_matrix(Operator):
    bl_idname = "notinthematrix.material"
    bl_label = "Helper for proxies visualization"
    bl_description = "Apply a custom material to proxies not yet present in the matrix"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        EM_mat_list = ['US', 'USVs', 'USVn', 'VSF', 'SF', 'USD', 'serSU', 'serUSVn', 'serUSVs']
        EM_mat_name = "mat_NotInTheMatrix"
        R = 1.0
        G = 0.0
        B = 1.0
        
        # Crea il materiale se non esiste
        if not check_material_presence(EM_mat_name):
            newmat = bpy.data.materials.new(EM_mat_name)
            em_setup_mat_cycles(EM_mat_name, R, G, B)

        # ✅ MODIFICATO: Aggiungi import e graph
        from ..functions import is_graph_available as check_graph
        from ..operators.addon_prefix_helpers import node_name_to_proxy_name
        
        graph_exists, graph = check_graph(context)
        active_graph = graph if graph_exists else None
        
        applied_count = 0  # Counter per statistiche
        
        for ob in bpy.data.objects:
            if ob.type == 'MESH':
                # ✅ CORREZIONE PRINCIPALE: Controlla che material_slots non sia vuoto
                # e che il primo slot abbia un materiale assegnato
                if ob.data.materials and len(ob.material_slots) > 0:
                    # ✅ Verifica che il materiale non sia None
                    if ob.material_slots[0].material is not None:
                        mat_name = ob.material_slots[0].material.name
                        
                        # Verifica se è un materiale EM o epoch
                        if mat_name in EM_mat_list or mat_name.startswith('ep_'):
                            matrix_mat = True
                        else:
                            matrix_mat = False
                        
                        # Verifica se l'oggetto è nella em_list
                        not_in_matrix = True
                        strat = context.scene.em_tools.stratigraphy  # ✅ Nuovo
                        for item in strat.units:
                            # ✅ AGGIUNTO: Converti il nome del nodo in proxy name
                            proxy_name = node_name_to_proxy_name(
                                item.name, 
                                context=context, 
                                graph=active_graph
                            )
                            if proxy_name == ob.name:
                                not_in_matrix = False
                                break
                        
                        # Applica il materiale "NotInTheMatrix" se necessario
                        if matrix_mat and not_in_matrix:
                            ob.data.materials.clear()
                            notinmatrix_mat = bpy.data.materials[EM_mat_name]
                            ob.data.materials.append(notinmatrix_mat)
                            applied_count += 1
                            print(f"✅ Applied 'NotInTheMatrix' material to {ob.name}")

        self.report({'INFO'}, f"Applied 'NotInTheMatrix' material to {applied_count} objects")
        print(f"{'='*50}")
        print(f"✅ Total objects marked as 'NotInTheMatrix': {applied_count}")
        print(f"{'='*50}")
        
        return {'FINISHED'}

class EM_set_EM_materials(Operator):
    bl_idname = "emset.emmaterial"
    bl_label = "Change proxy materials EM"
    bl_description = "Change proxy materials using EM standard palette"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        context.scene.em_tools.proxy_display_mode = "EM"
        update_icons(context, "em_list")
        bpy.ops.set_materials.using_em_list()
        return {'FINISHED'}

class EM_set_epoch_materials(Operator):
    bl_idname = "emset.epochmaterial"
    bl_label = "Change proxy Epochs"
    bl_description = "Change proxy materials using Epochs"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        context.scene.em_tools.proxy_display_mode = "Epochs"
        update_icons(context, "em_list")
        bpy.ops.set_materials.using_epoch_list()
        return {'FINISHED'}

class SET_materials_using_em_list(Operator):
    bl_idname = "set_materials.using_em_list"
    bl_label = "Set Materials Using EM List"
    bl_description = "Set materials based on EM node types"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        # ✅ AGGIUNTO: Import delle funzioni necessarie
        from ..functions import consolidate_EM_material_presence, em_setup_mat_cycles
        from ..functions import is_graph_available
        from ..operators.addon_prefix_helpers import node_name_to_proxy_name
        
        # ✅ AGGIUNTO: Ottieni il grafo attivo una sola volta
        graph_exists, graph = is_graph_available(context)
        active_graph = graph if graph_exists else None
        
        # Prepare EM materials
        overwrite_mats = True
        consolidate_EM_material_presence(overwrite_mats)
        
        # Apply materials based on node types
        strat = context.scene.em_tools.stratigraphy  # ✅ Nuovo
        em_list_lenght = len(strat.units)
        applied_count = 0  # ✅ AGGIUNTO: Counter per il report

        counter = 0
        while counter < em_list_lenght:
            current_ob_em_list = strat.units[counter]
            if current_ob_em_list.icon == 'LINKED':
                # ✅ MODIFICATO: Converti il nome con prefisso
                proxy_name = node_name_to_proxy_name(
                    current_ob_em_list.name, 
                    context=context, 
                    graph=active_graph
                )
                
                # ✅ MODIFICATO: Usa get() invece di [] per evitare KeyError
                current_ob_scene = context.scene.objects.get(proxy_name)
                
                if not current_ob_scene:
                    print(f"⚠️ Warning: Object '{proxy_name}' not found in scene (node: {current_ob_em_list.name})")
                    counter += 1
                    continue
                
                ob_material_name = 'US'  # Default
                
                # Check the node_type first (most reliable method)
                if hasattr(current_ob_em_list, 'node_type') and current_ob_em_list.node_type:
                    if current_ob_em_list.node_type in ['US', 'USVs', 'USVn', 'VSF', 'SF', 'USD', 'serSU', 'serUSVn', 'serUSVs']:
                        ob_material_name = current_ob_em_list.node_type
                else:
                    # Fallback to shape + border style
                    if current_ob_em_list.shape == 'rectangle':
                        ob_material_name = 'US'
                    elif current_ob_em_list.shape == 'ellipse_white':
                        ob_material_name = 'US'
                    elif current_ob_em_list.shape == 'ellipse':
                        ob_material_name = 'USVn'
                    elif current_ob_em_list.shape == 'parallelogram':
                        ob_material_name = 'USVs'
                    elif current_ob_em_list.shape == 'hexagon':
                        ob_material_name = 'USVn'
                    elif current_ob_em_list.shape == 'octagon':
                        # Check border style for octagon shapes
                        if current_ob_em_list.border_style == '#D8BD30':
                            ob_material_name = 'SF'
                        elif current_ob_em_list.border_style == '#B19F61':
                            ob_material_name = 'VSF'
                        else:
                            # Default for octagon without recognized border
                            ob_material_name = 'VSF'
                    elif current_ob_em_list.shape == 'roundrectangle':
                        ob_material_name = 'USD'
                
                # ✅ AGGIUNTO: Controllo se il materiale esiste
                if ob_material_name in bpy.data.materials:
                    mat = bpy.data.materials[ob_material_name]
                    current_ob_scene.data.materials.clear()
                    current_ob_scene.data.materials.append(mat)
                    applied_count += 1
                    print(f"✅ Applied {ob_material_name} material to {proxy_name}")
                else:
                    print(f"⚠️ Warning: Material '{ob_material_name}' not found")
                    
            counter += 1
        
        # ✅ AGGIUNTO: Report finale
        print(f"\n{'='*50}")
        print(f"✅ Applied EM materials to {applied_count} of {em_list_lenght} objects")
        print(f"{'='*50}")
        self.report({'INFO'}, f"Applied EM materials to {applied_count} objects")
        
        return {'FINISHED'}

class SET_materials_using_epoch_list(Operator):
    bl_idname = "set_materials.using_epoch_list"
    bl_label = "Set Materials Using Epoch List"
    bl_description = "Set materials based on epoch assignments"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        # ✅ AGGIUNTO: Import delle funzioni necessarie
        from ..functions import (
            check_material_presence, 
            em_setup_mat_cycles, 
            consolidate_epoch_material_presence
        )
        from ..functions import is_graph_available as check_graph
        from ..operators.addon_prefix_helpers import node_name_to_proxy_name
        
        # ✅ AGGIUNTO: Ottieni il grafo attivo una sola volta
        graph_exists, graph = check_graph(context)
        active_graph = graph if graph_exists else None
        
        scene = context.scene 
        epochs = scene.em_tools.epochs.list
        mat_prefix = "ep_"
        applied_count = 0  # ✅ AGGIUNTO: Counter per il report
        
        # Create/update epoch materials
        for epoch in epochs:
            matname = mat_prefix + epoch.name
            mat = consolidate_epoch_material_presence(matname)
            R = epoch.epoch_RGB_color[0]
            G = epoch.epoch_RGB_color[1]
            B = epoch.epoch_RGB_color[2]
            em_setup_mat_cycles(matname, R, G, B)
            
            # Apply materials to objects in this epoch
            strat = scene.em_tools.stratigraphy  # ✅ Nuovo
            for em_element in strat.units:
                if em_element.icon == "LINKED":
                    if em_element.epoch == epoch.name:
                        # ✅ MODIFICATO: Converti il nome con prefisso
                        proxy_name = node_name_to_proxy_name(
                            em_element.name, 
                            context=context, 
                            graph=active_graph
                        )
                        
                        # ✅ MODIFICATO: Usa get() invece di [] per evitare KeyError
                        obj = bpy.data.objects.get(proxy_name)
                        
                        if obj:
                            obj.data.materials.clear()
                            obj.data.materials.append(mat)
                            applied_count += 1
                            print(f"✅ Applied epoch material '{matname}' to {proxy_name}")
                        else:
                            print(f"⚠️ Warning: Object '{proxy_name}' not found in scene (node: {em_element.name})")
        
        # ✅ AGGIUNTO: Report finale
        print(f"\n{'='*50}")
        print(f"✅ Applied Epoch materials to {applied_count} objects")
        print(f"{'='*50}")
        self.report({'INFO'}, f"Applied Epoch materials to {applied_count} objects")
        
        return {'FINISHED'}


class EM_debug_filters(Operator):
    bl_idname = "em.debug_filters"
    bl_label = "Debug Filters"
    bl_description = "Print debug information about the current graph and connections"
    bl_options = {"REGISTER", "UNDO"}
    
    debug_mode: bpy.props.EnumProperty(
        items=[
            ('FULL', "Full Graph", "Debug the entire graph structure"),
            ('CURRENT', "Current Node", "Debug only the currently selected node")
        ],
        default='CURRENT',
        name="Debug Mode"
    )
    
    max_depth: bpy.props.IntProperty(
        name="Max Recursion Depth",
        description="Maximum recursion depth for graph traversal",
        default=5,
        min=1,
        max=20
    )
    
    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)
    
    def draw(self, context):
        layout = self.layout
        layout.prop(self, "debug_mode")
        layout.prop(self, "max_depth")
    
    def execute(self, context):
        scene = context.scene
        
        # Get current graph
        from ..functions import is_graph_available as check_graph
        graph_exists, graph = check_graph(context)
        
        if not graph_exists:
            self.report({'WARNING'}, "No active graph found. Please load a GraphML file first.")
            return {'CANCELLED'}
        
        try:
            # Import debug_graph_structure
            from s3dgraphy.utils.utils import debug_graph_structure
            
            if self.debug_mode == 'FULL':
                # Debug full graph
                debug_graph_structure(graph, max_depth=self.max_depth)
                self.report({'INFO'}, "Full graph debug information printed to console")
            else:
                # Debug current node
                strat = scene.em_tools.stratigraphy  # ✅ Nuovo
                if strat.units_index >= 0 and len(strat.units) > 0:
                    node_id = strat.units[strat.units_index].id_node
                    debug_graph_structure(graph, node_id, max_depth=self.max_depth)
                    self.report({'INFO'}, f"Node debug information printed to console for {strat.units[strat.units_index].name}")
                else:
                    # Fallback to full graph if no node is selected
                    self.report({'WARNING'}, "No node selected, showing full graph information")
                    debug_graph_structure(graph, max_depth=self.max_depth)
            
            return {'FINISHED'}
            
        except RecursionError as e:
            self.report({'ERROR'}, f"Recursion error in debug function. Try reducing the max depth: {str(e)}")
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}
        except Exception as e:
            self.report({'ERROR'}, f"Error during debug: {str(e)}")
            import traceback
            traceback.print_exc()  
            return {'CANCELLED'}

class STRAT_OT_preview_document(bpy.types.Operator):
    """Preview document image"""
    bl_idname = "strat.preview_document"
    bl_label = "Preview Document"
    bl_description = "Preview document image"
    
    document_url: bpy.props.StringProperty()
    document_name: bpy.props.StringProperty()
        
    def execute(self, context):
        if not self.document_url:
            return {'CANCELLED'}
        
        # Build full path and load image
        full_path = self._build_file_path(context, self.document_url)
        
        if full_path and os.path.exists(full_path):
            try:
                # Check if already loaded
                preview_name = f"StratPreview_{self.document_name}"
                existing_img = None
                
                for img in bpy.data.images:
                    if img.name == preview_name:
                        existing_img = img
                        break
                
                if existing_img:
                    # Reload existing
                    existing_img.reload()
                    img = existing_img
                else:
                    # Load new
                    img = bpy.data.images.load(full_path)
                    img.name = preview_name
                
                img.use_fake_user = True  # ✅ Keep in memory
                
                self.report({'INFO'}, f"Loaded preview: {self.document_name}")
            except Exception as e:
                self.report({'ERROR'}, f"Error loading image: {str(e)}")
                return {'CANCELLED'}
        else:
            self.report({'WARNING'}, f"Image not found: {self.document_url}")
            return {'CANCELLED'}
        
        return {'FINISHED'}
    
    def _build_file_path(self, context, relative_path):
        """Build full file path from relative path"""
        scene = context.scene
        
        # Get resource folder from auxiliary file settings
        try:
            em_tools = scene.em_tools
            if em_tools.active_file_index >= 0:
                graphml = em_tools.graphml_files[em_tools.active_file_index]
                if graphml.auxiliary_files:
                    aux_file = graphml.auxiliary_files[graphml.active_auxiliary_index]
                    if aux_file.resource_folder:
                        return os.path.join(aux_file.resource_folder, relative_path)
        except:
            pass
        
        # Fallback: try as absolute path
        if os.path.isabs(relative_path):
            return relative_path
            
        return None

class STRAT_OT_open_document_file(bpy.types.Operator):
    """Open document file in system default application"""
    bl_idname = "strat.open_document_file"
    bl_label = "Open File"
    bl_description = "Open document file in system default application"
    
    document_url: bpy.props.StringProperty()
    
    def execute(self, context):
        if not self.document_url:
            return {'CANCELLED'}
            
        full_path = STRAT_OT_preview_document._build_file_path(None, context, self.document_url)
        
        if full_path and os.path.exists(full_path):
            import subprocess
            import platform
            
            try:
                if platform.system() == "Windows":
                    os.startfile(full_path)
                elif platform.system() == "Darwin":  # macOS
                    subprocess.run(["open", full_path])
                else:  # Linux
                    subprocess.run(["xdg-open", full_path])
                    
                self.report({'INFO'}, f"Opened: {os.path.basename(full_path)}")
            except Exception as e:
                self.report({'ERROR'}, f"Error opening file: {str(e)}")
                return {'CANCELLED'}
        else:
            self.report({'ERROR'}, f"File not found: {self.document_url}")
            return {'CANCELLED'}
        
        return {'FINISHED'}

class STRAT_OT_open_document_folder(bpy.types.Operator):
    """Open document folder in system file manager"""
    bl_idname = "strat.open_document_folder"
    bl_label = "Open Folder"
    bl_description = "Open document folder in system file manager"
    
    document_url: bpy.props.StringProperty()
    
    def execute(self, context):
        if not self.document_url:
            return {'CANCELLED'}
            
        full_path = STRAT_OT_preview_document._build_file_path(None, context, self.document_url)
        
        if full_path and os.path.exists(full_path):
            folder_path = os.path.dirname(full_path)
            
            import subprocess
            import platform
            
            try:
                if platform.system() == "Windows":
                    subprocess.run(["explorer", folder_path])
                elif platform.system() == "Darwin":  # macOS
                    subprocess.run(["open", folder_path])
                else:  # Linux
                    subprocess.run(["xdg-open", folder_path])
                    
                self.report({'INFO'}, f"Opened folder: {folder_path}")
            except Exception as e:
                self.report({'ERROR'}, f"Error opening folder: {str(e)}")
                return {'CANCELLED'}
        else:
            self.report({'ERROR'}, f"File not found: {self.document_url}")
            return {'CANCELLED'}
        
        return {'FINISHED'}


def register_operators():
    """Register all operator classes."""
    operators = [
        EM_strat_toggle_visibility,
        EM_strat_sync_visibility,
        EM_strat_show_all_proxies,
        EM_strat_show_all_rms,
        EM_strat_activate_collections,
        EM_listitem_OT_to3D,
        EM_update_icon_list,
        EM_select_list_item,
        EM_select_from_list_item,
        EM_not_in_matrix,
        EM_set_EM_materials,
        EM_set_epoch_materials,
        SET_materials_using_em_list,
        SET_materials_using_epoch_list,
        EM_debug_filters,
        STRAT_OT_preview_document,
        STRAT_OT_open_document_file,
        STRAT_OT_open_document_folder,
    ]
    
    for cls in operators:
        try:
            bpy.utils.register_class(cls)
        except ValueError:
            # Class might already be registered
            pass

def unregister_operators():
    """Unregister all operator classes."""
    operators = [
        STRAT_OT_open_document_folder,
        STRAT_OT_open_document_file,
        STRAT_OT_preview_document,
        EM_debug_filters,
        SET_materials_using_epoch_list,
        SET_materials_using_em_list,
        EM_set_epoch_materials,
        EM_set_EM_materials,
        EM_not_in_matrix,
        EM_select_from_list_item,
        EM_select_list_item,
        EM_update_icon_list,
        EM_listitem_OT_to3D,
        EM_strat_activate_collections,
        EM_strat_show_all_rms,
        EM_strat_show_all_proxies,
        EM_strat_sync_visibility,
        EM_strat_toggle_visibility,
    ]
    
    for cls in reversed(operators):
        try:
            bpy.utils.unregister_class(cls)
        except ValueError:
            # Class might already be unregistered
            pass
