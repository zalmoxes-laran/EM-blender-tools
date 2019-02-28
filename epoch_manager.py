#    part of this library is a heavy modified version of the original code from: 
#    "name": "Super Grouper",
#    "author": "Paul Geraskin, Aleksey Juravlev, BA Community",

import bpy
import string

from bpy.props import EnumProperty, StringProperty, BoolProperty, IntProperty, CollectionProperty, BoolVectorProperty, PointerProperty
import bpy.props as prop

from .functions import *

import random


SCENE_EM = '#EM'
UNIQUE_ID_NAME = 'em_belong_id'
########################

class EM_UL_List(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        icons_style = 'OUTLINER'
        scene = context.scene
        layout.label(text = item.name, icon = item.icon)
        layout.label(text = item.description, icon='NONE', icon_value=0)

########################

def generate_id():
    # Generate unique id
    other_ids = []
    for scene in bpy.data.scenes:
        if scene != bpy.context.scene and scene.name.endswith(SCENE_EM) is False:
            for e_manager in scene.epoch_managers:
                other_ids.append(e_manager.unique_id)

    while True:
        uni_numb = None
        uniq_id_temp = ''.join(random.choice(string.ascii_uppercase + string.digits)
                               for _ in range(10))
        if uniq_id_temp not in other_ids:
            uni_numb = uniq_id_temp
            break
    other_ids = None  # clean
    return uni_numb

class EM_clean_object_ids(bpy.types.Operator):
    """Remove selected layer group"""
    bl_idname = "epoch_manager.clean_object_ids"
    bl_label = "Clean Objects IDs if the objects were imported from other blend files"
    bl_options = {'REGISTER', 'UNDO'}
    # group_em_idx = bpy.props.IntProperty()
    @classmethod
    def poll(cls, context):
        return bool(context.scene)

    def execute(self, context):
        check_same_ids()  # check scene ids

        scenes_ids = []
        for scene in bpy.data.scenes:
            if scene.epoch_managers:
                for e_manager in scene.epoch_managers:
                    if e_manager.unique_id not in scenes_ids:
                        scenes_ids.append(e_manager.unique_id)

        for obj in bpy.data.objects:
            EM_del_properties_from_obj(UNIQUE_ID_NAME, scenes_ids, obj, False)

        scenes_ids = None  # clean

        return {'FINISHED'}

def EM_get_group_scene(context):
    group_scene_name = context.scene.name + SCENE_EM

    if group_scene_name in bpy.data.scenes:
        return bpy.data.scenes[group_scene_name]

    return None

def EM_create_group_scene(context):
    group_scene_name = context.scene.name + SCENE_EM

    if context.scene.name.endswith(SCENE_EM) is False:
        if group_scene_name in bpy.data.scenes:
            return bpy.data.scenes[group_scene_name]
        else:
            return bpy.data.scenes.new(group_scene_name)

    return None

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
                        obj.select = False

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
        if self.group_em_idx < len(scene.epoch_managers):
            # check_same_ids()  # check scene ids
            current_e_manager = scene.epoch_managers[self.group_em_idx]

            # Try to get or create new GroupScene
            group_scene = EM_get_group_scene(context)
            if group_scene is None and current_e_manager.use_toggle is True:
                group_scene = EM_create_group_scene(context)

            # if GroupScene exists now we can switch objects
            if group_scene is not None:
                if current_e_manager.use_toggle is True:
                    for obj in scene.objects:
                        EM_switch_object(
                            obj, scene, group_scene, current_e_manager.unique_id)
                else:
                    for obj in group_scene.objects:
                        EM_switch_object(
                            obj, group_scene, scene, current_e_manager.unique_id)
                    if len(group_scene.objects) == 0:
                        bpy.data.scenes.remove(group_scene)

            current_e_manager.use_toggle = not current_e_manager.use_toggle  # switch visibility

            # set active object so that WMenu worked
            if current_e_manager.use_toggle is False and context.active_object is None:
                if scene.objects:
                    #scene.objects.active = scene.objects[0]
                    context.view_layer.objects.active = scene.objects[0]
        return {'FINISHED'}

def EM_switch_object(obj, scene_source, scene_terget, e_manager_id):
    do_switch = False
    if obj.em_belong_id:
        for prop in obj.em_belong_id:
            if prop.unique_id_object == e_manager_id:
                do_switch = True
                break

        if do_switch is True:
            layers = obj.layers[:]  # copy layers
            obj.select = False

            # if object is not already linked
            if obj.name not in scene_terget.objects:
                obj2 = scene_terget.objects.link(obj)
                obj2.layers = layers  # paste layers

            scene_source.objects.unlink(obj)
            layers = None  # clean

def sg_is_object_in_e_managers(groups_prop_values, obj):
    is_in_group = False
    for prop in obj.em_belong_id:
        if prop.unique_id_object in groups_prop_values:
            is_in_group = True
            break
    if is_in_group:
        return True
    else:
        return False

class EM_change_grouped_objects(bpy.types.Operator):
    bl_idname = "epoch_manager.change_grouped_objects"
    bl_label = "Change Grouped"
    bl_description = "Change Grouped"
    bl_options = {'REGISTER', 'UNDO'}

    em_group_changer : EnumProperty(
        items=(('COLOR_WIRE', 'COLOR_WIRE', ''),
               ('DEFAULT_COLOR_WIRE', 'DEFAULT_COLOR_WIRE', ''),
               ('LOCKING', 'LOCKING', '')
               ),
        default = 'DEFAULT_COLOR_WIRE'
    )

    list_objects = ['LOCKING']

    group_em_idx : IntProperty()

    def execute(self, context):
        scene_parse = context.scene
        if scene_parse.epoch_managers:
            # check_same_ids()  # check scene ids

            e_manager = None
            if self.em_group_changer not in self.list_objects:
                e_manager = scene_parse.epoch_managers[
                    scene_parse.epoch_managers_index]
            else:
                if self.group_em_idx < len(scene_parse.epoch_managers):
                    e_manager = scene_parse.epoch_managers[self.group_em_idx]

            if e_manager is not None and e_manager.use_toggle is True:
                for obj in scene_parse.objects:
                    if sg_is_object_in_e_managers([e_manager.unique_id], obj):
                        if self.em_group_changer == 'COLOR_WIRE':
                            r = e_manager.wire_color[0]
                            g = e_manager.wire_color[1]
                            b = e_manager.wire_color[2]
                            obj.color = (r, g, b, 1)
                            obj.show_wire_color = True
                        elif self.em_group_changer == 'DEFAULT_COLOR_WIRE':
                            obj.show_wire_color = False
                        elif self.em_group_changer == 'LOCKING':
                            if e_manager.is_locked is False:
                                obj.hide_select = True
                                obj.select = False
                            else:
                                obj.hide_select = False

                # switch locking for the group
                if self.em_group_changer == 'LOCKING':
                    if e_manager.is_locked is False:
                        e_manager.is_locked = True
                    else:
                        e_manager.is_locked = False

        return {'FINISHED'}

class EM_set_EM_materials(bpy.types.Operator):
    bl_idname = "emset.emmaterial"
    bl_label = "Change proxy materials"
    bl_description = "Change proxy materials"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        update_icons(context)
        set_EM_materials_using_EM_list(context)
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
                obj.draw_type = 'BOUNDS'
                obj.show_wire = False
            elif self.sg_objects_changer == 'WIRE_SHADE':
                obj.draw_type = 'WIRE'
                obj.show_wire = False
            elif self.sg_objects_changer == 'MATERIAL_SHADE':
                obj.draw_type = 'TEXTURED'
                obj.show_wire = False
            elif self.sg_objects_changer == 'SHOW_WIRE':
                obj.draw_type = 'TEXTURED'
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

class EM_epoch_manager_add(bpy.types.Operator):

    """Add and select a new layer group"""
    bl_idname = "epoch_manager.epoch_manager_add"
    bl_label = "Add Epoch group"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return bool(context.scene)

    def execute(self, context):
        
        bpy.ops.epoch_manager.epoch_manager_remove()        
        scene = context.scene
        epoch_number = len(scene.epoch_list)
        for epoch in range(epoch_number):
            epochname = scene.epoch_list[epoch].name

            check_same_ids()  # check scene ids

            epoch_managers = scene.epoch_managers

            # get all ids
            all_ids = []
            for e_manager in epoch_managers:
                if e_manager.unique_id not in all_ids:
                    all_ids.append(e_manager.unique_id)

             # generate new id
            uni_numb = generate_id()
            all_ids = None

            group_em_idx = len(epoch_managers)
            new_e_manager = epoch_managers.add()
            new_e_manager.name = epochname
            new_e_manager.unique_id = uni_numb
            scene.epoch_managers_index = group_em_idx

        return {'FINISHED'}

class EM_epoch_manager_remove(bpy.types.Operator):

    """Remove selected layer group"""
    bl_idname = "epoch_manager.epoch_manager_remove"
    bl_label = "Clear all epochs"
    bl_options = {'REGISTER', 'UNDO'}

    group_em_idx : IntProperty()

    @classmethod
    def poll(cls, context):
        return bool(context.scene)

    def execute(self, context):
        scene_parse = context.scene
        epoch_num = len(scene_parse.epoch_managers)
        for i in range(epoch_num):
            self.group_em_idx = scene_parse.epoch_managers_index
            # if a scene contains goups
            if scene_parse.epoch_managers:
                check_same_ids()  # check scene ids
                get_e_manager = scene_parse.epoch_managers[self.group_em_idx]
                if get_e_manager is not None and self.group_em_idx < len(scene_parse.epoch_managers):
                    e_manager_id = get_e_manager.unique_id

                    # get all ids
                    e_managers = []
                    for e_manager in scene_parse.epoch_managers:
                        e_managers.append(e_manager.unique_id)

                    # clear context scene
                    for obj in scene_parse.objects:
                        EM_del_properties_from_obj(
                            UNIQUE_ID_NAME, [e_manager_id], obj, True)

                    # clear SGR scene
                    sgr_scene_name = scene_parse.name + SCENE_EM
                    if sgr_scene_name in bpy.data.scenes:
                        sgr_scene = bpy.data.scenes[scene_parse.name + SCENE_EM]
                        for obj in sgr_scene.objects:
                            SGR_switch_object(obj, sgr_scene, scene_parse, e_manager_id)
                            EM_del_properties_from_obj(
                                UNIQUE_ID_NAME, [e_manager_id], obj, True)

                        # remove group_scene if it's empty
                        if len(sgr_scene.objects) == 0:
                            bpy.data.scenes.remove(sgr_scene)

                    # finally remove e_manager
                    scene_parse.epoch_managers.remove(self.group_em_idx)
                    if len(scene_parse.epoch_managers) > 0:
                        scene_parse.epoch_managers_index = len(scene_parse.epoch_managers) - 1
                    else:
                        scene_parse.epoch_managers_index = -1
                    #self.group_em_idx = scene_parse.epoch_managers_index
        
        return {'FINISHED'}

class EM_add_to_group(bpy.types.Operator):
    bl_idname = "epoch_manager.add_to_group"
    bl_label = "Add Selected Objects"
    bl_description = "Add To Super Group"
    bl_options = {'REGISTER', 'UNDO'}

    group_em_idx : IntProperty()


    def execute(self, context):
        scene_parse = context.scene

        if scene_parse.epoch_managers:
            check_same_ids()  # check ids

            # remove e_managers
            ids = []
            for e_manager in scene_parse.epoch_managers:
                ids.append(e_manager.unique_id)
            for obj in context.selected_objects:
                for e_manager in scene_parse.epoch_managers:
                    EM_del_properties_from_obj(UNIQUE_ID_NAME, ids, obj, True)
            ids = None

            e_manager = scene_parse.epoch_managers[self.group_em_idx]
            if e_manager is not None and self.group_em_idx < len(scene_parse.epoch_managers):
                for obj in context.selected_objects:
                    # add the unique id of selected group
                    EM_add_property_to_obj(e_manager.unique_id, obj)

                    # switch locking for obj
                    if e_manager.is_locked is True:
                        obj.hide_select = True
                        obj.select = False
                    else:
                        obj.hide_select = False

                    # check if the group is hidden
                    if e_manager.use_toggle is False:
                        # Try to get or create new GroupScene
                        group_scene = EM_get_group_scene(context)
                        if group_scene is None:
                            group_scene = EM_create_group_scene(context)

                        # Unlink object
                        if group_scene is not None:
                            group_scene.objects.link(obj)
                            context.scene.objects.unlink(obj)

        return {'FINISHED'}

class EM_remove_from_group(bpy.types.Operator):
    bl_idname = "epoch_manager.super_remove_from_group"
    bl_label = "Remove Selected Objects"
    bl_description = "Remove from Super Group"
    bl_options = {'REGISTER', 'UNDO'}

    # group_em_idx = bpy.props.IntProperty()

    def execute(self, context):
        scene = context.scene

        if scene.epoch_managers:
            check_same_ids()  # check ids

            # get all ids
            e_managers = []
            for e_manager in scene.epoch_managers:
                e_managers.append(e_manager.unique_id)

            # remove e_managers
            for obj in context.selected_objects:
                EM_del_properties_from_obj(UNIQUE_ID_NAME, e_managers, obj, True)
            e_managers = None  # clear

        return {'FINISHED'}

def EM_add_property_to_obj(prop_name, obj):
    props = obj.em_belong_id

    has_value = False
    if props:
        for prop in props:
            if prop.unique_id_object == prop_name:
                has_value = True
                break

    # add the value if it does not exist
    if has_value == False:
        added_prop = props.add()
        added_prop.unique_id_object = prop_name

def EM_del_properties_from_obj(prop_name, e_managers_ids, obj, delete_in_e_managers=True):
    props = obj.em_belong_id

    if len(props.values()) > 0:

        # remove item
        prop_len = len(props)
        index_prop = 0
        for i in range(prop_len):
            prop_obj = props[index_prop]
            is_removed = False
            if prop_obj.unique_id_object in e_managers_ids and delete_in_e_managers == True:
                props.remove(index_prop)
                is_removed = True
            elif prop_obj.unique_id_object not in e_managers_ids and delete_in_e_managers == False:
                props.remove(index_prop)
                is_removed = True

            if is_removed is False:
                index_prop += 1

        if len(props.values()) == 0:
            del bpy.data.objects[obj.name][prop_name]

def check_same_ids():
    scenes = bpy.data.scenes
    current_scene = bpy.context.scene

    check_scenes = []
    for scene in scenes:
        if scene.name.endswith(SCENE_EM) is False and scene != current_scene:
            check_scenes.append(scene)

    if check_scenes:
        other_ids = []
        for scene in check_scenes:
            for e_manager in scene.epoch_managers:
                if e_manager.unique_id not in other_ids:
                    other_ids.append(e_manager.unique_id)

        all_obj_list = None

        if other_ids:
            for i in range(len(current_scene.epoch_managers)):
                current_e_manager = current_scene.epoch_managers[i]
                current_id = current_e_manager.unique_id
                if current_id in other_ids:
                    new_id = generate_id()

                    if all_obj_list is None:
                        all_obj_list = []
                        all_obj_list += current_scene.objects
                        group_scene = EM_get_group_scene(bpy.context)
                        if group_scene is not None:
                            all_obj_list += group_scene.objects

                    for obj in all_obj_list:
                        has_id = False
                        for prop in obj.em_belong_id:
                            if prop.unique_id_object == current_e_manager.unique_id:
                                has_id = True
                                break
                        if has_id == True:
                            EM_add_property_to_obj(new_id, obj)

                    # set new id
                    current_e_manager.unique_id = new_id

    # clean
    check_scenes = None
    all_obj_list = None
    other_ids = None