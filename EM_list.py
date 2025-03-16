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
        strat_nodes = [node for node in graph.nodes if isinstance(node, StratigraphicNode)]
        
        for node in strat_nodes:
            include_node = True
            
            # Applica filtro per epoca se attivo
            if scene.filter_by_epoch:
                if scene.epoch_list_index >= 0 and len(scene.epoch_list) > 0:
                    active_epoch = scene.epoch_list[scene.epoch_list_index].name
                    if active_epoch:
                        epoch_node = graph.get_connected_epoch_node_by_edge_type(node, "has_first_epoch")
                        if not epoch_node or epoch_node.name != active_epoch:
                            # Verifica anche i nodi "survive_in_epoch"
                            survived_epochs = graph.get_connected_nodes_by_edge_type(node.node_id, "survive_in_epoch")
                            survived_in_active_epoch = any(epoch.name == active_epoch for epoch in survived_epochs)
                            if not survived_in_active_epoch:
                                include_node = False
                else:
                    # Se non ci sono epoche nella lista, disattiva il filtro
                    scene.filter_by_epoch = False
                    self.report({'INFO'}, "No epochs available, filter disabled")
            
            # Applica filtro per attività se attivo
            if scene.filter_by_activity and include_node:
                if scene.activity_manager.active_index >= 0 and len(scene.activity_manager.activities) > 0:
                    active_activity = scene.activity_manager.activities[scene.activity_manager.active_index].name
                    if active_activity:
                        activity_nodes = graph.get_connected_nodes_by_edge_type(node.node_id, "has_activity")
                        if not any(activity.name == active_activity for activity in activity_nodes):
                            include_node = False
                else:
                    # Se non ci sono attività nella lista, disattiva il filtro
                    scene.filter_by_activity = False
                    self.report({'INFO'}, "No activities available, filter disabled")
            
            # Se il nodo passa tutti i filtri, aggiungilo alla lista
            if include_node:
                filtered_items.append(node)
        
        # Aggiorna la lista em_list con gli elementi filtrati
        # Salva l'elemento attualmente selezionato (se presente)
        current_selected = scene.em_list[scene.em_list_index].name if scene.em_list_index >= 0 and len(scene.em_list) > 0 else None
        
        # Pulisci la lista attuale
        EM_list_clear(context, "em_list")
        
        # Ricostruisci la lista con gli elementi filtrati
        for node in filtered_items:
            em_item = scene.em_list.add()
            em_item.name = node.name
            em_item.description = node.description
            em_item.id_node = node.node_id
            em_item.icon = check_objs_in_scene_and_provide_icon_for_list_element(node.name)
            
            # Verifica se l'oggetto è visibile o nascosto in scena
            obj = bpy.data.objects.get(node.name)
            if obj:
                em_item.is_visible = not obj.hide_viewport
            else:
                em_item.is_visible = True  # Default per oggetti non in scena
            
            # Aggiungi altre proprietà come fatto in populate_stratigraphic_node
            if hasattr(node, 'attributes'):
                em_item.shape = node.attributes.get('shape', "")
                em_item.y_pos = node.attributes.get('y_pos', 0.0)
                em_item.fill_color = node.attributes.get('fill_color', "")
                em_item.border_style = node.attributes.get('border_style', "")
            
            # Imposta l'epoca
            first_epoch = graph.get_connected_epoch_node_by_edge_type(node, "has_first_epoch")
            em_item.epoch = first_epoch.name if first_epoch else ""
        
        # Ripristina la selezione se possibile
        if current_selected:
            for i, item in enumerate(scene.em_list):
                if item.name == current_selected:
                    scene.em_list_index = i
                    break
        
        # Reimposta l'indice a 0 se la lista non è vuota, altrimenti a -1
        if len(scene.em_list) > 0:
            scene.em_list_index = 0
        else:
            scene.em_list_index = -1
            self.report({'INFO'}, "No items match the current filters")
        
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
        
        # Disattiva i filtri
        scene.filter_by_epoch = False
        scene.filter_by_activity = False
        
        # Ricarica la lista completa
        em_tools = scene.em_tools
        if em_tools.active_file_index >= 0:
            graphml = em_tools.graphml_files[em_tools.active_file_index]
            graph = get_graph(graphml.name)
            
            if graph:
                # Pulisci le liste Blender
                EM_list_clear(context, "em_list")
                
                # Ripopola usando la funzione esistente
                populate_blender_lists_from_graph(context, graph)
                
                self.report({'INFO'}, "Filters reset, showing all items")
            else:
                self.report({'WARNING'}, "No active graph found")
        
        return {'FINISHED'}

class EM_strat_toggle_visibility(bpy.types.Operator):
    bl_idname = "em.strat_toggle_visibility"
    bl_label = "Toggle Stratigraphy Visibility"
    bl_description = "Toggle visibility of the selected proxy in the scene"
    bl_options = {"REGISTER", "UNDO"}
    
    index: IntProperty(default=-1)  # -1 means use the active index
    
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
    bl_description = "Synchronize proxy visibility with the current list (shows only proxies in the filtered list)"
    bl_options = {"REGISTER", "UNDO"}
    
    def execute(self, context):
        scene = context.scene
        
        if not scene.sync_list_visibility:
            return {'CANCELLED'}
        
        # Create a set of names that should be visible
        visible_names = {item.name for item in scene.em_list}
        
        # Process all mesh objects
        hidden_count = 0
        shown_count = 0
        
        for obj in bpy.data.objects:
            if obj.type == 'MESH':
                if obj.name in visible_names:
                    if obj.hide_viewport:
                        obj.hide_viewport = False
                        shown_count += 1
                else:
                    if not obj.hide_viewport:
                        obj.hide_viewport = True
                        hidden_count += 1
        
        # Update visibility icons in the list
        for item in scene.em_list:
            obj = bpy.data.objects.get(item.name)
            if obj:
                item.is_visible = not obj.hide_viewport
        
        self.report({'INFO'}, f"Visibility synchronized: {shown_count} shown, {hidden_count} hidden")
        return {'FINISHED'}

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
        row = layout.row(align=True)
        row.label(text=" Rows: " + str(len(scene.em_list)))

        #row.label(text="Filters:")
        
        # Verifichiamo che le proprietà esistano prima di usarle
        if hasattr(scene, "filter_by_epoch"):
            row.prop(scene, "filter_by_epoch", text="", toggle=True, icon='SORTTIME')
        
        if hasattr(scene, "filter_by_activity"):
            row.prop(scene, "filter_by_activity", text="", toggle=True, icon='GROUP')
        
        # Reset filtri
        if hasattr(scene, "filter_by_epoch") and hasattr(scene, "filter_by_activity"):
            if scene.filter_by_epoch or scene.filter_by_activity:
                row.operator("em.reset_filters", text="", icon='X')

        if hasattr(scene, "sync_list_visibility"):
            row.prop(scene, "sync_list_visibility", text="Sync", 
                    icon='HIDE_OFF' if scene.sync_list_visibility else 'HIDE_ON')

        # Tasto per attivare tutte le collezioni con proxy
        row.operator("em.strat_activate_collections", text="", icon='OUTLINER_COLLECTION')

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


        row = layout.row()

        if scene.em_list_index >= 0 and len(scene.em_list) > 0:
            row.template_list("EM_STRAT_UL_List", "EM nodes", scene, "em_list", scene, "em_list_index")
            item = scene.em_list[scene.em_list_index]
            box = layout.box()
            row = box.row(align=True)
            split = row.split()
            col = split.column()
            row.prop(item, "name", text="")
            
            # Aggiunta toggle visibilità
            if hasattr(item, "is_visible"):
                icon = 'HIDE_OFF' if item.is_visible else 'HIDE_ON'
                op = row.operator("em.strat_toggle_visibility", text="", icon=icon)
                if op:
                    op.index = scene.em_list_index
            
            split = row.split()
            col = split.column()
            op = col.operator("listitem.toobj", icon="PASTEDOWN", text='')
            if op:
                op.list_type = "em_list"
            
            row = box.row()
            row.prop(item, "description", text="", slider=True, emboss=True)

            split = layout.split()

            col = split.column(align=True)
            col.prop(scene, "paradata_streaming_mode", text='Paradata', icon="SHORTDISPLAY")

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
    # Check if there's a valid graph before calling the operator
    from .functions import is_graph_available as check_graph
    graph_exists, _ = check_graph(context)
    
    if graph_exists:
        # Controlla se l'operatore è disponibile prima di chiamarlo
        if hasattr(bpy.ops.em, "filter_lists"):
            try:
                bpy.ops.em.filter_lists()
            except Exception as e:
                print(f"Error updating filtered list: {e}")
    else:
        # Show message to load a graph first
        bpy.context.window_manager.popup_menu(
            lambda self, context: self.layout.label(text="Please load a graph before filtering"),
            title="No Graph Available",
            icon='ERROR'
        )
        # Reset the filter that was just toggled
        if hasattr(self, "name"):
            if self.name == "filter_by_epoch":
                context.scene.filter_by_epoch = False
            elif self.name == "filter_by_activity":
                context.scene.filter_by_activity = False


def sync_visibility_update(self, context):
    if self.sync_list_visibility:
        try:
            bpy.ops.em.strat_sync_visibility()
        except Exception as e:
            print(f"Error syncing visibility: {e}")

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
    EM_strat_activate_collections
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


def unregister():
    # Remove scene properties if they exist
    if hasattr(bpy.types.Scene, "filter_by_epoch"):
        del bpy.types.Scene.filter_by_epoch
    
    if hasattr(bpy.types.Scene, "filter_by_activity"):
        del bpy.types.Scene.filter_by_activity
    
    if hasattr(bpy.types.Scene, "sync_list_visibility"):
        del bpy.types.Scene.sync_list_visibility
    
    # Unregister classes in reverse order
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception as e:
            print(f"Error unregistering {cls.__name__}: {e}")