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
        layout = layout.split(factor =0.03, align = True)
        layout.label(text = "", icon = item.icon_db)
        layout = layout.split(factor =0.30, align = True)
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
                    if current_e_manager.name == us.epoch:
                        object_to_select = bpy.data.objects[us.name]
                        object_to_select.select_set(True)
        return {'FINISHED'}
#["rectangle", "ellipse_white", "roundrectangle", "octagon_white"]
#["parallelogram", "ellipse", "hexagon", "octagon"]

class EM_toggle_reconstruction(bpy.types.Operator):
    """Draw a line with the mouse"""
    bl_idname = "epoch_manager.toggle_reconstruction"
    bl_label = "Toggle Reconstruction"
    bl_description = "Toggle Reconstruction"
    bl_options = {'REGISTER', 'UNDO'}

    group_em_vis_idx : IntProperty()
    soloing_epoch: StringProperty()


    def execute(self, context):
        scene = context.scene
        if self.group_em_vis_idx < len(scene.epoch_list):
            # check_same_ids()  # check scene ids
            current_e_manager = scene.epoch_list[self.group_em_vis_idx]
            #parsing the em list
            for us in scene.em_list:
                #selecting only in-scene em elements
                if us.icon == "RESTRICT_INSTANCED_OFF":
                    # check if the us is in epoch
                    if current_e_manager.name == us.epoch:
                        if is_reconstruction_us(us):

                            # identify object to be turned on/off
                            object_to_set_visibility = bpy.data.objects[us.name]
                            # before to turn on/off elements in scene, check if we are in soloing mode
                            if scene.em_settings.soloing_mode == True:
                                found_reused = False
                                # parsing the re_used element list
                                for em_reused in scene.em_reused:
                                    if found_reused is False:
                                        if em_reused.em_element == us.name and em_reused.epoch == self.soloing_epoch:
                                            object_to_set_visibility.hide_viewport = False
                                            found_reused = True
                                        else:
                                            object_to_set_visibility.hide_viewport = current_e_manager.reconstruction_on
                            else:
                                object_to_set_visibility.hide_viewport = current_e_manager.reconstruction_on
        current_e_manager.reconstruction_on = not current_e_manager.reconstruction_on
        return {'FINISHED'}

class EM_toggle_visibility(bpy.types.Operator):
    """Draw a line with the mouse"""
    bl_idname = "epoch_manager.toggle_visibility"
    bl_label = "Toggle Visibility"
    bl_description = "Toggle Visibility"
    bl_options = {'REGISTER', 'UNDO'}

    group_em_vis_idx : IntProperty()
    soloing_epoch: StringProperty()
    

    def execute(self, context):
        scene = context.scene
        if self.group_em_vis_idx < len(scene.epoch_list):
            # check_same_ids()  # check scene ids
            current_e_manager = scene.epoch_list[self.group_em_vis_idx]
            #parsing the em list
            for us in scene.em_list:
                #selecting only in-scene em elements
                if us.icon == "RESTRICT_INSTANCED_OFF":
                    # check if the us is in epoch
                    if current_e_manager.name == us.epoch:
                        # identify object to be turned on/off
                        object_to_set_visibility = bpy.data.objects[us.name]
                        # before to turn on/off elements in scene, check if we are in soloing mode
                        if scene.em_settings.soloing_mode == True:
                            found_reused = False
                            # parsing the re_used element list
                            for em_reused in scene.em_reused:
                                if found_reused is False:
                                    if em_reused.em_element == us.name and em_reused.epoch == self.soloing_epoch:
                                        object_to_set_visibility.hide_viewport = False
                                        found_reused = True
                                    else:
                                        object_to_set_visibility.hide_viewport = current_e_manager.use_toggle
                        else:
                            object_to_set_visibility.hide_viewport = current_e_manager.use_toggle
        current_e_manager.use_toggle = not current_e_manager.use_toggle
        return {'FINISHED'}


class EM_toggle_selectable(bpy.types.Operator):
    """Toggle select"""
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
                    if current_e_manager.name == us.epoch:
                        object_to_set_visibility = bpy.data.objects[us.name]
                        object_to_set_visibility.hide_select = current_e_manager.is_locked
        current_e_manager.is_locked = not current_e_manager.is_locked
        return {'FINISHED'}

class EM_toggle_soloing(bpy.types.Operator):
    """Toggle soloing"""
    bl_idname = "epoch_manager.toggle_soloing"
    bl_label = "Toggle Soloing"
    bl_description = "Toggle epoch Soloing"
    bl_options = {'REGISTER', 'UNDO'}

    group_em_idx : IntProperty()

    def execute(self, context):
        scene = context.scene
        ep_idx = 0
        # check if selected row is consistent
        if self.group_em_idx < len(scene.epoch_list):
            #get current row in epoch list
            current_e_manager = scene.epoch_list[self.group_em_idx]
            # invert soloing icon for clicked row
            current_e_manager.epoch_soloing = not current_e_manager.epoch_soloing
            # set general soloing mode from current row
            scene.em_settings.soloing_mode = current_e_manager.epoch_soloing
            # parsing epoch list to update icons and run routines
            for ep_idx in range(len(scene.epoch_list)):
                # in case of the row to be "soloed"
                if ep_idx == self.group_em_idx:
                    # force toggle visibility to soloing row
                    scene.epoch_list[ep_idx].use_toggle = False
                    bpy.ops.epoch_manager.toggle_visibility("INVOKE_DEFAULT", group_em_vis_idx = ep_idx, soloing_epoch = current_e_manager.name)
                # in case of other rows..
                else:
                    # .. force turn off soloing
                    scene.epoch_list[ep_idx].epoch_soloing = False
                    # .. check if they are turned off
                    if scene.epoch_list[ep_idx].use_toggle == False:
                        # .. and in that case check if we are no more in soloing mode..
                        if scene.em_settings.soloing_mode is False:
                            # .. and turn them all back visible
                            bpy.ops.epoch_manager.toggle_visibility("INVOKE_DEFAULT", group_em_vis_idx = ep_idx, soloing_epoch = current_e_manager.name)
                    else:
                        bpy.ops.epoch_manager.toggle_visibility("INVOKE_DEFAULT", group_em_vis_idx = ep_idx, soloing_epoch = current_e_manager.name)
                            
        return {'FINISHED'}


class EM_select_epoch_rm(bpy.types.Operator):
    """Select RM for a given epoch"""
    bl_idname = "select_rm.given_epoch"
    bl_label = "Select RM for a given epoch"
    bl_description = "Select RM for a given epoch"
    bl_options = {'REGISTER', 'UNDO'}

    rm_epoch : StringProperty()

    def execute(self, context):
        #scene = context.scene
        for ob in bpy.data.objects:
            if len(ob.EM_ep_belong_ob) >= 0:
                for ob_tagged in ob.EM_ep_belong_ob:
                    if ob_tagged.epoch == self.rm_epoch:
                        ob.select_set(True)
        return {'FINISHED'}

class EM_add_remove_epoch_models(bpy.types.Operator):
    """Add and remove models from epochs"""
    bl_idname = "epoch_models.add_remove"
    bl_label = "Add and remove models from epochs"
    bl_description = "Add and remove models from epochs"
    bl_options = {'REGISTER', 'UNDO'}

    rm_epoch : StringProperty()
    rm_add : BoolProperty()

    def execute(self, context):
        scene = context.scene
        selected_objects = context.selected_objects

        for ob in selected_objects:
            if len(ob.EM_ep_belong_ob) >= 0:
                if self.rm_add:
                    if not self.rm_epoch in ob.EM_ep_belong_ob:
                        local_counter = len(ob.EM_ep_belong_ob)
                        ob.EM_ep_belong_ob.add()
                        ob.EM_ep_belong_ob[local_counter].epoch = self.rm_epoch
                else:
                    counter = 0
                    for ob_list in ob.EM_ep_belong_ob:
                        if ob_list.epoch == self.rm_epoch:
                            ob.EM_ep_belong_ob.remove(counter)  
                        counter +=1
            else:
                ob.EM_ep_belong_ob.add()
                ob.EM_ep_belong_ob[0].epoch = self.rm_epoch                   
        return {'FINISHED'}

class EM_set_EM_materials(bpy.types.Operator):
    bl_idname = "emset.emmaterial"
    bl_label = "Change proxy materials EM"
    bl_description = "Change proxy materials using EM standard palette"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        context.scene.proxy_display_mode = "EM"
        update_icons(context,"em_list")
        set_materials_using_EM_list(context)
        return {'FINISHED'}

class EM_set_epoch_materials(bpy.types.Operator):
    bl_idname = "emset.epochmaterial"
    bl_label = "Change proxy periods"
    bl_description = "Change proxy materials using periods"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        context.scene.proxy_display_mode = "Periods"
        update_icons(context,"em_list")
        set_materials_using_epoch_list(context)
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

        return {'FINISHED'}