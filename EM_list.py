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

    def execute(self, context):
        scene = context.scene
        obj = context.object
        select_list_element_from_obj_proxy(obj)
        return {'FINISHED'}

class EM_select_from_list_item(bpy.types.Operator):
    bl_idname = "select.fromlistitem"
    bl_label = "Select 3D proxy from the list above"
    bl_options = {"REGISTER", "UNDO"}

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
        em_list_index_ema = 0
#        tree = ET.parse('/Users/emanueldemetrescu/Desktop/EM_test.graphml')
        allnodes = tree.findall('.//{http://graphml.graphdrawing.org/xmlns}node')
        for node_element in allnodes:
#            print(node_element.text)
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
                    em_list_index_ema += 1
                else:
                    pass
            if EM_check_node_type(node_element) == 'node_swimlane':
#                print("swimlane node is: " + str(node_element.attrib))
                extract_epochs(node_element)
#                my_epoch, my_y_max_epoch, my_y_min_epoch = extract_epochs(node_element)
#                print(my_epoch)
        for em_i in range(len(scene.em_list)):
            #print(scene.em_list[em_i].name)
            for epoch_in in range(len(scene.epoch_list)):
                if scene.epoch_list[epoch_in].min_y < scene.em_list[em_i].y_pos < scene.epoch_list[epoch_in].max_y:
                    scene.em_list[em_i].epoch = scene.epoch_list[epoch_in].name
#                    print(scene.epoch_list[epoch_in].name)
        bpy.ops.epoch_manager.epoch_manager_remove()
        bpy.ops.epoch_manager.epoch_manager_add()
        add_sceneobj_to_epochs()

        return {'FINISHED'}