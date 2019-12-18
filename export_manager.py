import bpy
import string
import os
from bpy_extras.io_utils import ExportHelper
from bpy.types import Operator

from bpy.props import EnumProperty, StringProperty, BoolProperty, IntProperty, CollectionProperty, BoolVectorProperty, PointerProperty
import bpy.props as prop

from .functions import *

import random

class EM_export(bpy.types.Operator):
    """Export manager"""
    bl_idname = "export_manager.export"
    bl_label = "Export manager"
    bl_description = "Export manager"
    bl_options = {'REGISTER', 'UNDO'}

    em_export_type : StringProperty()

    def execute(self, context):
        scene = context.scene

        #selection = bpy.context.selected_objects
        bpy.ops.object.select_all(action='DESELECT')
        print(scene.EM_file)
        base_dir = os.path.dirname(scene.EM_file)
        print("la base_dir is:"+base_dir)
        foldername = self.em_export_type
        export_folder = createfolder(base_dir, foldername)
        if foldername == 'Proxies':
            for proxy in bpy.data.objects:
                for em in scene.em_list:
                    if proxy.name == em.name:
                        proxy.select_set(True)
                        name = bpy.path.clean_name(em.name)
                        export_file = os.path.join(export_folder, name)
                        bpy.ops.export_scene.obj(filepath=str(export_file + '.obj'), use_selection=True, axis_forward='Y', axis_up='Z', path_mode='RELATIVE')
                        proxy.select_set(False)
        elif foldername == 'RM':
            for ob in bpy.data.objects:
                if len(ob.EM_ep_belong_ob) >= 0:
                    for ob_tagged in ob.EM_ep_belong_ob:
                        for epoch in scene.epoch_list:
                            has_epoch = False
                            export_sub_folder = createfolder(export_folder, epoch.name)
                            if ob_tagged.epoch == epoch.name:
                                ob.select_set(True)
                                name = bpy.path.clean_name(ob.name)
                                export_file = os.path.join(export_sub_folder, name)
                                bpy.ops.export_scene.obj(filepath=str(export_file + '.obj'), use_selection=True, axis_forward='Y', axis_up='Z', path_mode='RELATIVE')
                                ob.select_set(False)
                                has_epoch = True
                            if not has_epoch:
                                os.rmdir(export_sub_folder)
        return {'FINISHED'}


class OBJECT_OT_ExportUUSS(bpy.types.Operator):
    bl_idname = "export.uuss_export"
    bl_label = "Export UUSS"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):

        bpy.ops.export.uuss_data('INVOKE_DEFAULT')
            
        return {'FINISHED'}

def convert_shape2type(shape):
    node_type = "None"
    if shape == "rectangle":
        node_type = "US"
    elif shape == "parallelogram":
        node_type = "USVs"
    elif shape == "ellipse":
        node_type = "Series of USVs"
    elif shape == "ellipse_white":
        node_type = "Series of US"
    elif shape == "hexagon":
        node_type = "USVn"
    elif shape == "octagon":
        node_type = "Special Find"
    return node_type

def write_UUSS_data(context, filepath, name, description, epoch, type_node):
    print("running write some data...")
    
    f = open(filepath, 'w', encoding='utf-8')

    f.write("Nome; Descrizione; Epoca; Tipo \n")

    for US in context.scene.em_list:
        
        #if name == True:
            
        f.write("%s; %s; %s; %s\n" % (US.name, US.description, US.epoch, convert_shape2type(US.shape)))
        
    f.close()    
    
#    f.write("Hello World %s" % use_some_setting)
#    f.close()

    return {'FINISHED'}

class ExportuussData(Operator, ExportHelper):
    """Export UUSS data into a csv file"""
    bl_idname = "export.uuss_data"  # important since its how bpy.ops.import_test.some_data is constructed
    bl_label = "Export UUSS Data"

    # ExportHelper mixin class uses this
    filename_ext = ".csv"

    filter_glob: StringProperty(
            default="*.csv",
            options={'HIDDEN'},
            maxlen=255,  # Max internal buffer length, longer would be clamped.
            )

    # List of operator properties, the attributes will be assigned
    # to the class instance from the operator settings before calling.

    name: BoolProperty(
            name="Add names of UUSS",
            description="This tool includes name",
            default=True,
            )

    description: BoolProperty(
            name="Add description",
            description="This tool includes description",
            default=True,
            )

    epoch: BoolProperty(
            name="Export epoch",
            description="This tool includes epoch",
            default=True,
            )

    type_node: BoolProperty(
            name="Node type",
            description="This includes node type",
            default=True,
            )

    def execute(self, context):
        return write_UUSS_data(context, self.filepath, self.name, self.description, self.epoch, self.type_node)

# Only needed if you want to add into a dynamic menu
#def menu_func_export(self, context):
#    self.layout.operator(ExportCoordinates.bl_idname, text="Text Export Operator")


def createfolder(base_dir, foldername):
    
    if not base_dir:
        raise Exception("Set again the GraphML file path in the first panel above before to export")

    export_folder = os.path.join(base_dir, foldername)
    if not os.path.exists(export_folder):
        os.mkdir(export_folder)
        print('There is no '+ foldername +' folder. Creating one...')
    else:
        print('Found previously created '+foldername+' folder. I will use it')

    return export_folder