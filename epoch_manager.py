#    part of this library is a (very) heavily modified version of the original code from: 
#    "name": "Super Grouper",
#    "author": "Paul Geraskin, Aleksey Juravlev, BA Community",

import bpy
import string

from bpy.props import EnumProperty, StringProperty, BoolProperty, IntProperty, CollectionProperty, BoolVectorProperty, PointerProperty
import bpy.props as prop

from .functions import *

import random

########################

class EM_UL_List(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        icons_style = 'OUTLINER'
        scene = context.scene
        layout.label(text = item.name, icon = item.icon)
        layout.label(text = item.description, icon='NONE', icon_value=0)

########################

def EM_select_objects(context, ids, do_select):
    if do_select:
        scene = context.scene
        for obj in scene.objects:
            if obj.em_belong_id:
                for prop in obj.em_belong_id:
                    if prop.unique_id_object in ids:
                        if scene.em_settings.unlock_obj:
                            obj.hide_select = False
                        # unhide
                        if scene.em_settings.unhide_obj:
                            obj.hide_viewport = False
                        # select
                        obj.select_set(True)
       
    else:
        for obj in context.selected_objects:
            if obj.em_belong_id:
                for prop in obj.em_belong_id:
                    if prop.unique_id_object in ids:
                        obj.select_set(False)

class EM_toggle_select(bpy.types.Operator):
    bl_idname = "epoch_manager.toggle_select"
    bl_label = "Toggle Select"
    bl_description = "Toggle Select"
    bl_options = {'REGISTER', 'UNDO'}

    group_em_idx : IntProperty()
    is_menu : BoolProperty(name="Is Menu?", default=True)
    is_select : BoolProperty(name="Is Select?", default=True)

    def invoke(self, context, event):
        scene = context.scene
        if self.group_em_idx < len(scene.epoch_managers):
            # check_same_ids()  # check scene ids

            e_manager = scene.epoch_managers[self.group_em_idx]

            if event.ctrl is True and self.is_menu is False:
                self.is_select = False

            if e_manager.use_toggle is True:
                if self.is_select is True:

                    # add active object if no selection
                    has_selection = False
                    if context.selected_objects:
                        has_selection = True

                    EM_select_objects(context, [e_manager.unique_id], True)
                    if scene.em_settings.unlock_obj:
                        e_manager.is_locked = False

                    # set last active object if no selection was before
                    if has_selection is False and context.selected_objects:
                        context.view_layer.objects.active = context.selected_objects[-1]

                else:
                    EM_select_objects(context, [e_manager.unique_id], False)

        return {'FINISHED'}

class EM_toggle_visibility(bpy.types.Operator):

    """Draw a line with the mouse"""
    bl_idname = "epoch_manager.toggle_visibility"
    bl_label = "Toggle Visibility"
    bl_description = "Toggle Visibility"
    bl_options = {'REGISTER', 'UNDO'}

    group_em_idx : IntProperty()

    def execute(self, context):
        scene = context.scene
        if self.group_em_idx < len(scene.epoch_list):
            # check_same_ids()  # check scene ids
            current_e_manager = scene.epoch_list[self.group_em_idx]
            for us in scene.em_list:
                if us.icon == "RESTRICT_INSTANCED_OFF":
                    print(us.epoch)
                    if current_e_manager.name == us.epoch:
                        object_to_set_visibility = bpy.data.objects[us.name]
                        object_to_set_visibility.hide_viewport = current_e_manager.use_toggle
        current_e_manager.use_toggle = not current_e_manager.use_toggle
        return {'FINISHED'}

class EM_set_EM_materials(bpy.types.Operator):
    bl_idname = "emset.emmaterial"
    bl_label = "Change proxy materials EM"
    bl_description = "Change proxy materials using EM standard palette"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        context.scene.proxy_display_mode = "EM"
        update_icons(context)
        set_EM_materials_using_EM_list(context)
        return {'FINISHED'}

class EM_set_epoch_materials(bpy.types.Operator):
    bl_idname = "emset.epochmaterial"
    bl_label = "Change proxy epochs"
    bl_description = "Change proxy materials using epochs"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        context.scene.proxy_display_mode = "Epochs"
        #update_icons(context)
        set_epoch_materials(context)
        return {'FINISHED'}

class EM_change_selected_objects(bpy.types.Operator):
    bl_idname = "epoch_manager.change_selected_objects"
    bl_label = "Change Selected"
    bl_description = "Change Selected"
    bl_options = {'REGISTER', 'UNDO'}

    sg_objects_changer : EnumProperty(
        items=(('BOUND_SHADE', 'BOUND_SHADE', ''),
               ('WIRE_SHADE', 'WIRE_SHADE', ''),
               ('MATERIAL_SHADE', 'MATERIAL_SHADE', ''),
               ('SHOW_WIRE', 'SHOW_WIRE', ''),
               ('EM_COLOURS', 'EM_COLOURS', ''),
               ('ONESIDE_SHADE', 'ONESIDE_SHADE', ''),
               ('TWOSIDE_SHADE', 'TWOSIDE_SHADE', '')
               ),
        default = 'MATERIAL_SHADE'
    )
    sg_do_with_groups = [
        'COLOR_WIRE', 'DEFAULT_COLOR_WIRE', 'LOCKED', 'UNLOCKED']

    def execute(self, context):
        for obj in context.selected_objects:
            if self.sg_objects_changer == 'BOUND_SHADE':
                obj.display_type = 'BOUNDS'
                obj.show_wire = False
            elif self.sg_objects_changer == 'WIRE_SHADE':
                obj.display_type = 'WIRE'
                obj.show_wire = False
            elif self.sg_objects_changer == 'MATERIAL_SHADE':
                obj.display_type = 'TEXTURED'
                obj.show_wire = False
            elif self.sg_objects_changer == 'SHOW_WIRE':
                obj.display_type = 'TEXTURED'
                obj.show_wire = True
            elif self.sg_objects_changer == 'ONESIDE_SHADE':
                if obj.type == 'MESH':
                    obj.data.show_double_sided = False
            elif self.sg_objects_changer == 'TWOSIDE_SHADE':
                if obj.type == 'MESH':
                    obj.data.show_double_sided = True
            #elif self.sg_objects_changer == 'EM_COLOURS':
                #if obj.type == 'MESH':
                   #set_EM_materials_using_EM_list(context)

        return {'FINISHED'}
