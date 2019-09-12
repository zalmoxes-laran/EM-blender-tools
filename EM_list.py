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
class EM_usname_OT_toproxy(bpy.types.Operator):
    bl_idname = "usname.toproxy"
    bl_label = "Use US name for selected proxy"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        obj = context.object
        return (obj.type in ['MESH'])

    def execute(self, context):
        scene = context.scene
        item = scene.em_list[scene.em_list_index]
        context.active_object.name = item.name
        update_icons(context)
        set_EM_materials_using_EM_list(context)
        return {'FINISHED'}

class EM_update_icon_list(bpy.types.Operator):
    bl_idname = "uslist_icon.update"
    bl_label = "Update only the icons"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        update_icons(context)
        
        return {'FINISHED'}

class EM_select_list_item(bpy.types.Operator):
    bl_idname = "select.listitem"
    bl_label = "Select element in the list above from a 3D proxy"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        obj = context.object
        return (check_if_current_obj_has_brother_inlist(obj.name))

    def execute(self, context):
        scene = context.scene
        obj = context.object
        select_list_element_from_obj_proxy(obj)
        return {'FINISHED'}

class EM_select_from_list_item(bpy.types.Operator):
    bl_idname = "select.fromlistitem"
    bl_label = "Select 3D proxy from the list above"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        scene = context.scene
        return (scene.em_list[scene.em_list_index].icon == 'RESTRICT_INSTANCED_OFF')

    def execute(self, context):
        scene = context.scene
        list_item = scene.em_list[scene.em_list_index]
        select_3D_obj(list_item.name)
        return {'FINISHED'}

class EM_import_GraphML(bpy.types.Operator):
    bl_idname = "import.em_graphml"
    bl_label = "Import the EM GraphML"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        scene = context.scene
        graphml_file = scene.EM_file
        tree = ET.parse(graphml_file)
        EM_list_clear(context)
        EM_reused_list_clear(context)
        em_list_index_ema = 0
        em_reused_index = 0

        allnodes = tree.findall('.//{http://graphml.graphdrawing.org/xmlns}node')
        
        for node_element in allnodes:
            if EM_check_node_type(node_element) == 'node_simple': # The node is not a group or a swimlane
                if EM_check_node_us(node_element): # Check if the node is an US, SU, USV, USM or USR node
                    my_nodename, my_node_description, my_node_url, my_node_shape, my_node_y_pos = EM_extract_node_name(node_element)
                    scene.em_list.add()
                    scene.em_list[em_list_index_ema].name = my_nodename
                    scene.em_list[em_list_index_ema].icon = EM_check_GraphML_Blender(my_nodename)
                    scene.em_list[em_list_index_ema].y_pos = float(my_node_y_pos)
#                    print('-' + my_nodename + '-' + ' has an icon: ' + EM_check_GraphML_Blender(my_nodename))
                    scene.em_list[em_list_index_ema].description = my_node_description
                    scene.em_list[em_list_index_ema].shape = my_node_shape
                    scene.em_list[em_list_index_ema].id_node = getnode_id(node_element)
                    #print(scene.em_list[em_list_index_ema].id_node)
                    em_list_index_ema += 1
                else:
                    pass
            if EM_check_node_type(node_element) == 'node_swimlane':
                extract_epochs(node_element)

        for em_i in range(len(scene.em_list)):
            #print(scene.em_list[em_i].name)
            for epoch_in in range(len(scene.epoch_list)):
                if scene.epoch_list[epoch_in].min_y < scene.em_list[em_i].y_pos < scene.epoch_list[epoch_in].max_y:
                    scene.em_list[em_i].epoch = scene.epoch_list[epoch_in].name

        #porzione di codice per estrarre le continuità
        
        for node_element in allnodes:
            if EM_check_node_type(node_element) == 'node_simple': # The node is not a group or a swimlane
                if EM_check_node_continuity(node_element):
                    EM_us_target, continuity_y = get_edge_target(tree, node_element)
                    #print(EM_us_target+" has y value: "+str(continuity_y))
                    for EM_item in bpy.context.scene.em_list:
                        if EM_item.name == EM_us_target:
                            
                            for ep_i in range(len(scene.epoch_list)):
                                #print("epoca "+epoch.name+" : min"+str(epoch.min_y)+" max: "+str(epoch.max_y)+" minore di "+str(continuity_y)+" e "+ str(epoch.min_y) +" minore di "+str(EM_item.y_pos))
                                if scene.epoch_list[ep_i].max_y > continuity_y and scene.epoch_list[ep_i].max_y < EM_item.y_pos:
                                    #print("found")
                                    scene.em_reused.add()
                                    scene.em_reused[em_reused_index].epoch = scene.epoch_list[ep_i].name
                                    scene.em_reused[em_reused_index].em_element = EM_item.name
                                    print("All'epoca "+scene.em_reused[em_reused_index].epoch+ " appartiene : "+ scene.em_reused[em_reused_index].em_element)
                                    em_reused_index += 1
                else:
                    pass

        return {'FINISHED'}