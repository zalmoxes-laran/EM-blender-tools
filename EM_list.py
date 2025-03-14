import bpy # type: ignore
import xml.etree.ElementTree as ET
import os
import bpy.props as prop # type: ignore
from bpy.types import Panel # type: ignore


#from bpy.props import StringProperty, BoolProperty, IntProperty, CollectionProperty, BoolVectorProperty, PointerProperty

from bpy.props import (BoolProperty, # type: ignore
                       FloatProperty,
                       StringProperty,
                       EnumProperty,
                       CollectionProperty,
                       IntProperty,
                       PointerProperty,
                       FloatVectorProperty,
                       )

from bpy.types import ( # type: ignore
        AddonPreferences,
        PropertyGroup,
        )

from .functions import *



class EM_filter_lists(bpy.types.Operator):
    bl_idname = "em.filter_lists"
    bl_label = "Filter Lists"
    bl_description = "Apply filters to US/USV list"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        scene = context.scene
        em_tools = scene.em_tools
        
        # Verifica se c'è un grafo attivo
        is_graph_available, graph = is_graph_available(context)
        if not is_graph_available:
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
                active_epoch = scene.epoch_list[scene.epoch_list_index].name if scene.epoch_list_index >= 0 and len(scene.epoch_list) > 0 else None
                if active_epoch:
                    epoch_node = graph.get_connected_epoch_node_by_edge_type(node, "has_first_epoch")
                    if not epoch_node or epoch_node.name != active_epoch:
                        # Verifica anche i nodi "survive_in_epoch"
                        survived_epochs = graph.get_connected_nodes_by_edge_type(node.node_id, "survive_in_epoch")
                        survived_in_active_epoch = any(epoch.name == active_epoch for epoch in survived_epochs)
                        if not survived_in_active_epoch:
                            include_node = False
            
            # Applica filtro per attività se attivo
            if scene.filter_by_activity and include_node:
                active_activity = scene.activity_manager.activities[scene.activity_manager.active_index].name if scene.activity_manager.active_index >= 0 and len(scene.activity_manager.activities) > 0 else None
                if active_activity:
                    activity_nodes = graph.get_connected_nodes_by_edge_type(node.node_id, "has_activity")
                    if not any(activity.name == active_activity for activity in activity_nodes):
                        include_node = False
            
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


#####################################################################
#US/USV Manager

class EM_ToolsPanel:
    bl_label = "US/USV Manager"
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
        row.label(text="Filters:")
        row.prop(scene, "filter_by_epoch", text="Epoch", toggle=True, icon='SORTTIME')
        row.prop(scene, "filter_by_activity", text="Activity", toggle=True, icon='GROUP')

        # Reset filtri
        if scene.filter_by_epoch or scene.filter_by_activity:
            row.operator("em.reset_filters", text="", icon='X')
        
        row = layout.row()

        if scene.em_list_index >= 0 and len(scene.em_list) > 0:
            row.template_list("EM_UL_List", "EM nodes", scene, "em_list", scene, "em_list_index")
            item = scene.em_list[scene.em_list_index]
            box = layout.box()
            row = box.row(align=True)
            split = row.split()
            col = split.column()
            row.prop(item, "name", text="")
            split = row.split()
            col = split.column()
            op = col.operator("listitem.toobj", icon="PASTEDOWN", text='')
            op.list_type = "em_list"
            row = box.row()
            row.prop(item, "description", text="", slider=True, emboss=True)

            split = layout.split()
            if scene.em_list[scene.em_list_index].icon == 'RESTRICT_INSTANCED_OFF':
                col = split.column()
                op = col.operator("select.fromlistitem", text='Proxy3D from List item', icon="MESH_CUBE")
                op.list_type = "em_list"
            else:
                col = split.column()
                col.label(text="", icon='MESH_CUBE') 
            if obj:
                if check_if_current_obj_has_brother_inlist(obj.name, "em_list"):
                    col = split.column(align=True)
                    op = col.operator("select.listitem", text='List item from 3DProxy', icon="LONGDISPLAY")
                    op.list_type = "em_list"
                else:
                    col = split.column()
                    col.label(text="", icon='LONGDISPLAY')             
                    
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
            row.label(text="No US/USV here :-(")


class VIEW3D_PT_ToolsPanel(Panel, EM_ToolsPanel):
    bl_category = "EM"
    bl_idname = "VIEW3D_PT_ToolsPanel"
    bl_context = "objectmode"

#US/USV Manager

#### da qui si definiscono le funzioni e gli operatori
class EM_listitem_OT_to3D(bpy.types.Operator):
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

    list_type: StringProperty() # type: ignore

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

    def execute(self, context):
        scene = context.scene
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


#SETUP MENU
#####################################################################

classes = [
    EM_listitem_OT_to3D,
    VIEW3D_PT_ToolsPanel,
    EM_update_icon_list,
    EM_select_from_list_item,
    EM_select_list_item,
    EM_not_in_matrix,
    EM_filter_lists, 
    EM_reset_filters 
    ]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.filter_by_epoch = BoolProperty(
        name="Filter by Epoch",
        description="Show only elements from the active epoch",
        default=False,
        update=lambda self, context: bpy.ops.em.filter_lists()
    )

    bpy.types.Scene.filter_by_activity = BoolProperty(
        name="Filter by Activity",
        description="Show only elements from the active activity",
        default=False,
        update=lambda self, context: bpy.ops.em.filter_lists()
    )


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    
    # Rimuovi le proprietà dei filtri
    del bpy.types.Scene.filter_by_epoch
    del bpy.types.Scene.filter_by_activity



