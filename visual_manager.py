import bpy

from bpy.types import Panel
from bpy.types import Operator
from bpy.types import PropertyGroup
from bpy.types import UIList

from .functions import *

import os
from bpy_extras.io_utils import ImportHelper

from bpy.props import (BoolProperty,
                       StringProperty,
                       EnumProperty,
                       CollectionProperty
                       )

import json
import os
import shutil

import logging
log = logging.getLogger(__name__)

class Display_mode_menu(bpy.types.Menu):
    bl_label = "Custom Menu"
    bl_idname = "OBJECT_MT_Display_mode_menu"

    def draw(self, context):
        layout = self.layout

        layout.operator("emset.emmaterial", text="EM")
        layout.operator("emset.epochmaterial", text="Periods")



class VISUALToolsPanel:
    bl_label = "Visual manager"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_options = {'DEFAULT_CLOSED'}


    def draw(self, context):
        layout = self.layout
        scene = context.scene
        current_proxy_display_mode = context.scene.proxy_display_mode
        layout.alignment = 'LEFT'
        #row_epoch = layout.row()
        #row_epoch.label(text="List of visualisation tools:")
        row = layout.row(align=True)
        split = row.split()
        col = split.column()
        col.label(text="Display mode")
        col = split.column(align=True)
        
        col.menu(Display_mode_menu.bl_idname, text=current_proxy_display_mode, icon='COLOR')
 
        row = layout.row()
        #split = row.split()
        
        #col = split.column(align=True)
        row.prop(scene, "proxy_display_alpha")

        #col = split.column(align=True)

        # function sadly disabled because of the lack of support of 'ADD' Blend Mode in Blender 2.81
        #row.prop(scene, "proxy_shader_mode", text='', icon="NODE_MATERIAL")

        #row = layout.row(align=True)
        #col = split.column(align=True)

        #col.label(text="On selected:")

        op = row.operator(
            "epoch_manager.change_selected_objects", text="", emboss=False, icon='SHADING_BBOX')
        op.sg_objects_changer = 'BOUND_SHADE'

        op = row.operator(
            "epoch_manager.change_selected_objects", text="", emboss=False, icon='SHADING_WIRE')
        op.sg_objects_changer = 'WIRE_SHADE'

        op = row.operator(
            "epoch_manager.change_selected_objects", text="", emboss=False, icon='SHADING_SOLID')
        op.sg_objects_changer = 'MATERIAL_SHADE'

        op = row.operator(
            "epoch_manager.change_selected_objects", text="", emboss=False, icon='SPHERE')
        op.sg_objects_changer = 'SHOW_WIRE'

        #op = row.operator(
        #    "emset.emmaterial", text="", emboss=False, icon='SHADING_TEXTURE')
        row = layout.row()

        row.operator("notinthematrix.material", icon="MOD_MASK", text='')

        row.label(text="Labels:")

        op = row.operator("create.collection", text="", emboss=False, icon='OUTLINER_COLLECTION')

        """ 
        op = row.operator("label.onoff", text="", emboss=False, icon='RADIOBUT_OFF')
        op.onoff = False
        """

        op = row.operator("label.creation", text="",
                          emboss=False, icon='SYNTAX_OFF')
        #op.onoff = False

        op = row.operator("center.mass", text="", emboss=False, icon='CURSOR')
        op.center_to = "cursor"

        op = row.operator("center.mass", text="", emboss=False, icon='SNAP_FACE_CENTER')
        op.center_to = "mass"
        
        """ op = row.operator("center.mass", text="", emboss=False, icon='SNAP_FACE_CENTER')
        op.center_to = "mass" """

class VIEW3D_PT_VisualPanel(Panel, VISUALToolsPanel):
    bl_category = "EM"
    bl_idname = "VIEW3D_PT_VisualPanel"
    #bl_context = "objectmode"


classes = [
    VIEW3D_PT_VisualPanel,
    Display_mode_menu]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

"""  bpy.types.Scene.epoch_list_un = CollectionProperty(type = EPOCHListItemUN)
    bpy.types.Scene.epoch_list_un_index = IntProperty(name = "Index for my_list", default = 0)
    bpy.types.Scene.un_inepoch_list_index = IntProperty(name="Index for my_list", default=0)
 """
def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
    """ del bpy.types.Scene.epoch_list_un
    del bpy.types.Scene.epoch_list_un_index
    del bpy.types.Scene.un_inepoch_list_index
 """