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

class EM_toggle_select(bpy.types.Operator):

    """Draw a line with the mouse"""
    bl_idname = "epoch_manager.toggle_select"
    bl_label = "Toggle Select"
    bl_description = "Toggle Select"
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
                        object_to_select = bpy.data.objects[us.name]
                        object_to_select.select_set(True)
                        #object_to_select.select_set(current_e_manager.is_selected)
        #current_e_manager.is_selected = not current_e_manager.is_selected

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


class EM_toggle_selectable(bpy.types.Operator):

    """Draw a line with the mouse"""
    bl_idname = "epoch_manager.toggle_selectable"
    bl_label = "Toggle Selectable"
    bl_description = "Toggle Selectable"
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
                        object_to_set_visibility.hide_select = current_e_manager.is_locked
        current_e_manager.is_locked = not current_e_manager.is_locked
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
