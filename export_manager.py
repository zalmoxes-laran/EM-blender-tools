import bpy
import string
import os

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

class EM_export_csv(bpy.types.Operator):
    """Export UUSS"""
    bl_idname = "export_UUSS.export"
    bl_label = "Export UUSS"
    bl_description = "Export UUSS"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        

        return {'FINISHED'}


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