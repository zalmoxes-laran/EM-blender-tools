import bpy
import xml.etree.ElementTree as ET
import os
import bpy.props as prop


#from bpy.props import StringProperty, BoolProperty, IntProperty, CollectionProperty, BoolVectorProperty, PointerProperty

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
from .epoch_manager import *

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
        #item = scene.em_list[scene.em_list_index]
        item = eval(item_name_picker_cmd)
        context.active_object.name = item.name
        update_icons(context, self.list_type)
        if self.list_type == "em_list":
            if context.scene.proxy_display_mode == "EM":
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
    bl_options = {"REGISTER", "UNDO"}

    list_type: StringProperty()

    # questa via mi sembrava più pulita ma non è praticabile perché non si può passare una variabile alla funzione di pool (novembre 2019)
    # @classmethod
    # def poll(cls, context):
    #     global list_type
    #     scene = context.scene
    #     obj = context.object 
    #     list_cmd = ("scene."+ list_type)
    #     if obj is None:
    #         pass
    #     else:
    #         return (check_if_current_obj_has_brother_inlist(obj.name, eval(list_cmd)))

    def execute(self, context):
        scene = context.scene
        obj = context.object
        select_list_element_from_obj_proxy(obj, self.list_type)
        return {'FINISHED'}

class EM_select_from_list_item(bpy.types.Operator):
    bl_idname = "select.fromlistitem"
    bl_label = "Select 3D obj from the list above"
    bl_options = {"REGISTER", "UNDO"}

    list_type: StringProperty()

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

def togli_a_capo(stringa):
    stringa_pulita = stringa.replace("/n","")
    return stringa_pulita

class EM_import_GraphML(bpy.types.Operator):
    bl_idname = "import.em_graphml"
    bl_label = "Import the EM GraphML"
    bl_description = "Import the EM GraphML"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        scene = context.scene
        graphml_file = bpy.path.abspath(scene.EM_file)
        tree = ET.parse(graphml_file)
        EM_list_clear(context, "em_list")
        EM_list_clear(context, "em_reused")
        EM_list_clear(context, "em_sources_list")
        EM_list_clear(context, "em_properties_list")
        EM_list_clear(context, "em_extractors_list")
        EM_list_clear(context, "em_combiners_list")
        em_list_index_ema = 0
        em_reused_index = 0
        em_sources_index_ema = 0
        em_properties_index_ema = 0
        em_extractors_index_ema = 0
        em_combiners_index_ema = 0

        allnodes = tree.findall('.//{http://graphml.graphdrawing.org/xmlns}node')

        for node_element in allnodes:
            if EM_check_node_type(node_element) == 'node_simple': # The node is not a group or a swimlane
                if EM_check_node_us(node_element): # Check if the node is an US, SU, USV, USM or USR node
                    my_nodename, my_node_description, my_node_url, my_node_shape, my_node_y_pos, my_node_fill_color = EM_extract_node_name(node_element)
                    scene.em_list.add()
                    scene.em_list[em_list_index_ema].name = my_nodename
                    scene.em_list[em_list_index_ema].icon = check_objs_in_scene_and_provide_icon_for_list_element(my_nodename)
                    scene.em_list[em_list_index_ema].y_pos = float(my_node_y_pos)
                    scene.em_list[em_list_index_ema].description = my_node_description
                        #print(my_node_shape)
                    if my_node_fill_color == '#FFFFFF':
                        if my_node_shape == "ellipse" or my_node_shape == "octagon":
                            scene.em_list[em_list_index_ema].shape = my_node_shape+"_white"
                        else:
                            scene.em_list[em_list_index_ema].shape = my_node_shape
                    else:
                        scene.em_list[em_list_index_ema].shape = my_node_shape
                    scene.em_list[em_list_index_ema].id_node = getnode_id(node_element)
                    em_list_index_ema += 1
                elif EM_check_node_document(node_element):
                    source_already_in_list = False
                    source_number = 2
                    src_nodename, src_node_id, src_node_description, src_nodeurl, subnode_is_document = EM_extract_document_node(node_element)
                    src_nodename_safe = src_nodename
                    if em_sources_index_ema > 0: 
                        for source_item in scene.em_sources_list:
                            if source_item.name == src_nodename:
                                source_already_in_list = True
                    if source_already_in_list:
                        src_nodename = src_nodename+"_"+str(source_number)
                        source_number +=1
                    scene.em_sources_list.add()
                    scene.em_sources_list[em_sources_index_ema].name = src_nodename
                    scene.em_sources_list[em_sources_index_ema].icon = check_objs_in_scene_and_provide_icon_for_list_element(src_nodename_safe)
                    scene.em_sources_list[em_sources_index_ema].id_node = src_node_id
                    scene.em_sources_list[em_sources_index_ema].url = src_nodeurl
                    if src_nodeurl == "--None--":
                        scene.em_sources_list[em_sources_index_ema].icon_url = "CHECKBOX_DEHLT"
                    else:
                        scene.em_sources_list[em_sources_index_ema].icon_url = "CHECKBOX_HLT"
                    scene.em_sources_list[em_sources_index_ema].description = src_node_description
                    em_sources_index_ema += 1
                elif EM_check_node_property(node_element):
                    pro_nodename, pro_node_id, pro_node_description, pro_nodeurl, subnode_is_property = EM_extract_property_node(node_element)
                    scene.em_properties_list.add()
                    scene.em_properties_list[em_properties_index_ema].name = pro_nodename
                    scene.em_properties_list[em_properties_index_ema].icon = check_objs_in_scene_and_provide_icon_for_list_element(pro_nodename)
                    scene.em_properties_list[em_properties_index_ema].id_node = pro_node_id
                    scene.em_properties_list[em_properties_index_ema].url = pro_nodeurl
                    if pro_nodeurl == "--None--":
                        scene.em_properties_list[em_properties_index_ema].icon_url = "CHECKBOX_DEHLT"
                    else:
                        scene.em_properties_list[em_properties_index_ema].icon_url = "CHECKBOX_HLT"
                    scene.em_properties_list[em_properties_index_ema].description = pro_node_description
                    em_properties_index_ema += 1
                elif EM_check_node_extractor(node_element):
                    ext_nodename, ext_node_id, ext_node_description, ext_nodeurl, subnode_is_extractor = EM_extract_extractor_node(node_element)
                    scene.em_extractors_list.add()
                    scene.em_extractors_list[em_extractors_index_ema].name = ext_nodename
                    scene.em_extractors_list[em_extractors_index_ema].id_node = ext_node_id                   
                    scene.em_extractors_list[em_extractors_index_ema].icon = check_objs_in_scene_and_provide_icon_for_list_element(ext_nodename)
                    scene.em_extractors_list[em_extractors_index_ema].url = ext_nodeurl
                   #print(ext_nodeurl)
                    if ext_nodeurl == "--None--":
                        scene.em_extractors_list[em_extractors_index_ema].icon_url = "CHECKBOX_DEHLT"
                    else:
                        scene.em_extractors_list[em_extractors_index_ema].icon_url = "CHECKBOX_HLT"
                    scene.em_extractors_list[em_extractors_index_ema].description = ext_node_description
                    em_extractors_index_ema += 1
                elif EM_check_node_combiner(node_element):
                    ext_nodename, ext_node_id, ext_node_description, ext_nodeurl, subnode_is_combiner = EM_extract_combiner_node(node_element)
                    scene.em_combiners_list.add()
                    scene.em_combiners_list[em_combiners_index_ema].name = ext_nodename
                    scene.em_combiners_list[em_combiners_index_ema].id_node = ext_node_id                   
                    scene.em_combiners_list[em_combiners_index_ema].icon = check_objs_in_scene_and_provide_icon_for_list_element(ext_nodename)
                    scene.em_combiners_list[em_combiners_index_ema].url = ext_nodeurl
                   #print(ext_nodeurl)
                    if ext_nodeurl == "--None--":
                        scene.em_combiners_list[em_combiners_index_ema].icon_url = "CHECKBOX_DEHLT"
                    else:
                        scene.em_combiners_list[em_combiners_index_ema].icon_url = "CHECKBOX_HLT"
                    scene.em_combiners_list[em_combiners_index_ema].description = ext_node_description
                    em_combiners_index_ema += 1
                else:
                    pass

            if EM_check_node_type(node_element) == 'node_swimlane':
                extract_epochs(node_element)

        for em_i in range(len(scene.em_list)):
            for epoch_in in range(len(scene.epoch_list)):
                if scene.epoch_list[epoch_in].min_y < scene.em_list[em_i].y_pos < scene.epoch_list[epoch_in].max_y:
                    scene.em_list[em_i].epoch = scene.epoch_list[epoch_in].name

        #porzione di codice per estrarre le continuità
        for node_element in allnodes:
            if EM_check_node_type(node_element) == 'node_simple': # The node is not a group or a swimlane
                if EM_check_node_continuity(node_element):
                    #print("found continuity node")
                    EM_us_target, continuity_y = get_edge_target(tree, node_element)
                    #print(EM_us_target+" has y value: "+str(continuity_y))
                    for EM_item in bpy.context.scene.em_list:
                        if EM_item.icon == "RESTRICT_INSTANCED_OFF":
                            if EM_item.name == EM_us_target:
                                for ep_i in range(len(scene.epoch_list)):
                                    #print("epoca "+epoch.name+" : min"+str(epoch.min_y)+" max: "+str(epoch.max_y)+" minore di "+str(continuity_y)+" e "+ str(epoch.min_y) +" minore di "+str(EM_item.y_pos))
                                    if scene.epoch_list[ep_i].max_y > continuity_y and scene.epoch_list[ep_i].max_y < EM_item.y_pos:
                                        #print("found")
                                        scene.em_reused.add()
                                        scene.em_reused[em_reused_index].epoch = scene.epoch_list[ep_i].name
                                        scene.em_reused[em_reused_index].em_element = EM_item.name
                                       #print("All'epoca "+scene.em_reused[em_reused_index].epoch+ " appartiene : "+ scene.em_reused[em_reused_index].em_element)
                                        em_reused_index += 1
        read_edge_db(context,tree)
        try:
            node_send = scene.em_list[scene.em_list_index]
        except IndexError as error:
            scene.em_list_index = 0
            node_send = scene.em_list[scene.em_list_index]
        create_derived_lists(node_send)
        if context.scene.proxy_display_mode == "EM":
            bpy.ops.emset.emmaterial()
        else:
            bpy.ops.emset.epochmaterial()
        return {'FINISHED'}
