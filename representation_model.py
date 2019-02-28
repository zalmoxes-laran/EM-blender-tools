# this library is a heavy modified version of the original code from: 
#    "name": "Super Grouper",
#    "author": "Paul Geraskin, Aleksey Juravlev, BA Community",

import bpy
import random
import string

from .functions import *
from bpy.props import *
from bpy.types import Operator
from bpy.types import Menu, Panel, UIList, PropertyGroup
from bpy.props import StringProperty, BoolProperty, IntProperty, CollectionProperty, BoolVectorProperty, PointerProperty
from bpy.app.handlers import persistent

SCENE_RM = '#RM'
UNIQUE_ID_NAME = 'rm_belong_id'

class RM_Add_Objects_Sub_Menu(bpy.types.Menu):
    bl_idname = "repmod_manager.add_objects_sub_menu"
    bl_label = "Add Selected Objects"
    bl_description = "Add Objects Menu"

    def draw(self, context):
        layout = self.layout
        for i, e_manager in enumerate(context.scene.repmod_managers):
            op = layout.operator(RM_add_to_group.bl_idname, text=e_manager.name)
            op.group_rm_idx = i

class RM_Remove_SGroup_Sub_Menu(bpy.types.Menu):
    bl_idname = "repmod_manager.remove_e_manager_sub_menu"
    bl_label = "Remove Super Group"
    bl_description = "Remove Super Group Menu"

    def draw(self, context):
        layout = self.layout
        for i, e_manager in enumerate(context.scene.repmod_managers):
            op = layout.operator(RM_repmod_manager_remove.bl_idname, text=e_manager.name)
            op.group_rm_idx = i

class RM_Select_SGroup_Sub_Menu(bpy.types.Menu):
    bl_idname = "repmod_manager.select_e_manager_sub_menu"
    bl_label = "Select SGroup"
    bl_description = "Select SGroup Menu"

    def draw(self, context):
        layout = self.layout
        for i, e_manager in enumerate(context.scene.repmod_managers):
            op = layout.operator(RM_toggle_select.bl_idname, text=e_manager.name)
            op.group_rm_idx = i
            op.is_select = True
            op.is_menu = True

class RM_Deselect_SGroup_Sub_Menu(bpy.types.Menu):
    bl_idname = "repmod_manager.deselect_e_manager_sub_menu"
    bl_label = "Deselect SGroup"
    bl_description = "Deselect SGroup Menu"

    def draw(self, context):
        layout = self.layout

        for i, e_manager in enumerate(context.scene.repmod_managers):
            op = layout.operator(RM_toggle_select.bl_idname, text=e_manager.name)
            op.group_rm_idx = i
            op.is_select = False
            op.is_menu = True


class RM_Toggle_Visible_SGroup_Sub_Menu(bpy.types.Menu):
    bl_idname = "repmod_manager.toggle_e_manager_sub_menu"
    bl_label = "Toggle SGroup"
    bl_description = "Toggle SGroup Menu"

    def draw(self, context):
        layout = self.layout

        for i, e_manager in enumerate(context.scene.repmod_managers):
            op = layout.operator(RM_toggle_visibility.bl_idname, text=e_manager.name)
            op.group_rm_idx = i


class RM_Toggle_Shading_Sub_Menu(bpy.types.Menu):
    bl_idname = "repmod_manager.toggle_shading_sub_menu"
    bl_label = "Toggle Shading"
    bl_description = "Toggle Shading Menu"

    def draw(self, context):
        layout = self.layout

        op = layout.operator(RM_change_selected_objects.bl_idname, text="Bound Shade")
        op.rm_objects_changer = 'BOUND_SHADE'

        op = layout.operator(RM_change_selected_objects.bl_idname, text="Wire Shade")
        op.rm_objects_changer = 'WIRE_SHADE'

        op = layout.operator(RM_change_selected_objects.bl_idname, text="Material Shade")
        op.rm_objects_changer = 'MATERIAL_SHADE'

        op = layout.operator(RM_change_selected_objects.bl_idname, text="Show Wire")
        op.rm_objects_changer = 'SHOW_WIRE'

        layout.separator()
        op = layout.operator(RM_change_selected_objects.bl_idname, text="One Side")
        op.rm_objects_changer = 'ONESIDE_SHADE'
        op = layout.operator(RM_change_selected_objects.bl_idname, text="Double Side")
        op.rm_objects_changer = 'TWOSIDE_SHADE'


def generate_id():
    # Generate unique id
    other_ids = []
    for scene in bpy.data.scenes:
        if scene != bpy.context.scene and scene.name.endswith(SCENE_RM) is False:
            for e_manager in scene.repmod_managers:
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

class RM_clean_object_ids(bpy.types.Operator):
    """Remove selected layer group"""
    bl_idname = "repmod_manager.clean_object_ids"
    bl_label = "Clean Objects IDs if the objects were imported from other blend files"
    bl_options = {'REGISTER', 'UNDO'}
    # group_rm_idx = bpy.props.IntProperty()
    @classmethod
    def poll(cls, context):
        return bool(context.scene)

    def execute(self, context):
        check_same_ids()  # check scene ids

        scenes_ids = []
        for scene in bpy.data.scenes:
            if scene.repmod_managers:
                for e_manager in scene.repmod_managers:
                    if e_manager.unique_id not in scenes_ids:
                        scenes_ids.append(e_manager.unique_id)

        for obj in bpy.data.objects:
            RM_del_properties_from_obj(UNIQUE_ID_NAME, scenes_ids, obj, False)

        scenes_ids = None  # clean

        return {'FINISHED'}


def RM_get_group_scene(context):
    group_scene_name = context.scene.name + SCENE_RM

    if group_scene_name in bpy.data.scenes:
        return bpy.data.scenes[group_scene_name]

    return None


def RM_create_group_scene(context):
    group_scene_name = context.scene.name + SCENE_RM

    if context.scene.name.endswith(SCENE_RM) is False:
        if group_scene_name in bpy.data.scenes:
            return bpy.data.scenes[group_scene_name]
        else:
            return bpy.data.scenes.new(group_scene_name)

    return None


def RM_select_objects(context, ids, do_select):
    if do_select:
        scene = context.scene
        temp_scene_layers = list(scene.layers[:])  # copy layers of the scene
        for obj in scene.objects:
            if obj.rm_belong_id:
                for prop in obj.rm_belong_id:
                    if prop.unique_id_object in ids:
                        for i in range(20):
                            if obj.layers[i] is True:
                                if scene.layers[i] is True or scene.rm_settings.select_all_layers:
                                    # unlock
                                    if scene.rm_settings.unlock_obj:
                                        obj.hide_select = False
                                    # unhide
                                    if scene.rm_settings.unhide_obj:
                                        obj.hide = False

                                    # select
                                    obj.select = True

                                    # break if we need to select only visible
                                    # layers
                                    if scene.rm_settings.select_all_layers is False:
                                        break
                                    else:
                                        temp_scene_layers[i] = obj.layers[i]

        # set layers switching to a scene
        if scene.rm_settings.select_all_layers:
            scene.layers = temp_scene_layers
    else:
        for obj in context.selected_objects:
            if obj.rm_belong_id:
                for prop in obj.rm_belong_id:
                    if prop.unique_id_object in ids:
                        obj.select = False


class RM_toggle_select(bpy.types.Operator):
    bl_idname = "repmod_manager.toggle_select"
    bl_label = "Toggle Select"
    bl_description = "Toggle Select"
    bl_options = {'REGISTER', 'UNDO'}

    group_rm_idx : IntProperty()
    is_menu : BoolProperty(name="Is Menu?", default=True)
    is_select : BoolProperty(name="Is Select?", default=True)

    def invoke(self, context, event):
        scene = context.scene
        if self.group_rm_idx < len(scene.repmod_managers):
            # check_same_ids()  # check scene ids

            e_manager = scene.repmod_managers[self.group_rm_idx]

            if event.ctrl is True and self.is_menu is False:
                self.is_select = False

            if e_manager.use_toggle is True:
                if self.is_select is True:

                    # add active object if no selection
                    has_selection = False
                    if context.selected_objects:
                        has_selection = True

                    RM_select_objects(context, [e_manager.unique_id], True)
                    if scene.rm_settings.unlock_obj:
                        e_manager.is_locked = False

                    # set last active object if no selection was before
                    if has_selection is False and context.selected_objects:
                        scene.objects.active = context.selected_objects[-1]

                else:
                    RM_select_objects(context, [e_manager.unique_id], False)

        return {'FINISHED'}


class RM_toggle_visibility(bpy.types.Operator):

    """Draw a line with the mouse"""
    bl_idname = "repmod_manager.toggle_visibility"
    bl_label = "Toggle Visibility"
    bl_description = "Toggle Visibility"
    bl_options = {'REGISTER', 'UNDO'}

    group_rm_idx : IntProperty()

    def execute(self, context):
        scene = context.scene
        if self.group_rm_idx < len(scene.repmod_managers):
            # check_same_ids()  # check scene ids
            current_e_manager = scene.repmod_managers[self.group_rm_idx]

            # Try to get or create new GroupScene
            group_scene = RM_get_group_scene(context)
            if group_scene is None and current_e_manager.use_toggle is True:
                group_scene = RM_create_group_scene(context)

            # if GroupScene exists now we can switch objects
            if group_scene is not None:
                if current_e_manager.use_toggle is True:
                    for obj in scene.objects:
                        RM_switch_object(
                            obj, scene, group_scene, current_e_manager.unique_id)
                else:
                    for obj in group_scene.objects:
                        RM_switch_object(
                            obj, group_scene, scene, current_e_manager.unique_id)
                    if len(group_scene.objects) == 0:
                        bpy.data.scenes.remove(group_scene)

            current_e_manager.use_toggle = not current_e_manager.use_toggle  # switch visibility

            # set active object so that WMenu worked
            if current_e_manager.use_toggle is False and scene.objects.active is None:
                if scene.objects:
                    scene.objects.active = scene.objects[0]
        return {'FINISHED'}

def RM_switch_object(obj, scene_source, scene_terget, e_manager_id):
    do_switch = False
    if obj.rm_belong_id:
        for prop in obj.rm_belong_id:
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

def rm_is_object_in_e_managers(groups_prop_values, obj):
    is_in_group = False
    for prop in obj.rm_belong_id:
        if prop.unique_id_object in groups_prop_values:
            is_in_group = True
            break
    if is_in_group:
        return True
    else:
        return False

class RM_change_grouped_objects(bpy.types.Operator):
    bl_idname = "repmod_manager.rmchange_grouped_objects"
    bl_label = "Change Grouped"
    bl_description = "Change Grouped"
    bl_options = {'REGISTER', 'UNDO'}

    rm_group_changer : EnumProperty(
        items=(('COLOR_WIRE', 'COLOR_WIRE', ''),
               ('DEFAULT_COLOR_WIRE', 'DEFAULT_COLOR_WIRE', ''),
               ('LOCKING', 'LOCKING', '')
               ),
        default = 'DEFAULT_COLOR_WIRE'
    )

    list_objects = ['LOCKING']

    group_rm_idx : IntProperty()

    def execute(self, context):
        scene_parse = context.scene
        if scene_parse.repmod_managers:
            # check_same_ids()  # check scene ids

            e_manager = None
            if self.rm_group_changer not in self.list_objects:
                e_manager = scene_parse.repmod_managers[
                    scene_parse.repmod_managers_index]
            else:
                if self.group_rm_idx < len(scene_parse.repmod_managers):
                    e_manager = scene_parse.repmod_managers[self.group_rm_idx]

            if e_manager is not None and e_manager.use_toggle is True:
                for obj in scene_parse.objects:
                    if rm_is_object_in_e_managers([e_manager.unique_id], obj):
                        if self.rm_group_changer == 'COLOR_WIRE':
                            r = e_manager.wire_color[0]
                            g = e_manager.wire_color[1]
                            b = e_manager.wire_color[2]
                            obj.color = (r, g, b, 1)
                            obj.show_wire_color = True
                        elif self.rm_group_changer == 'DEFAULT_COLOR_WIRE':
                            obj.show_wire_color = False
                        elif self.rm_group_changer == 'LOCKING':
                            if e_manager.is_locked is False:
                                obj.hide_select = True
                                obj.select = False
                            else:
                                obj.hide_select = False

                # switch locking for the group
                if self.rm_group_changer == 'LOCKING':
                    if e_manager.is_locked is False:
                        e_manager.is_locked = True
                    else:
                        e_manager.is_locked = False

        return {'FINISHED'}

# class RM_set_RM_materials(bpy.types.Operator):
#     bl_idname = "emset.emmaterial"
#     bl_label = "Change proxy materials"
#     bl_description = "Change proxy materials"
#     bl_options = {'REGISTER', 'UNDO'}
    
#     def execute(self, context):
#         update_icons(context)
#         set_RM_materials_using_RM_list(context)
#         return {'FINISHED'}

class RM_change_selected_objects(bpy.types.Operator):
    bl_idname = "repmod_manager.change_selected_objects"
    bl_label = "Change Selected"
    bl_description = "Change Selected"
    bl_options = {'REGISTER', 'UNDO'}

    rm_objects_changer = EnumProperty(
        items=(('BOUND_SHADE', 'BOUND_SHADE', ''),
               ('WIRE_SHADE', 'WIRE_SHADE', ''),
               ('MATERIAL_SHADE', 'MATERIAL_SHADE', ''),
               ('SHOW_WIRE', 'SHOW_WIRE', ''),
               ('RM_COLOURS', 'RM_COLOURS', ''),
               ('ONESIDE_SHADE', 'ONESIDE_SHADE', ''),
               ('TWOSIDE_SHADE', 'TWOSIDE_SHADE', '')
               ),
        default = 'MATERIAL_SHADE'
    )
    rm_do_with_groups = [
        'COLOR_WIRE', 'DEFAULT_COLOR_WIRE', 'LOCKED', 'UNLOCKED']

    def execute(self, context):
        for obj in context.selected_objects:
            if self.rm_objects_changer == 'BOUND_SHADE':
                obj.draw_type = 'BOUNDS'
                obj.show_wire = False
            elif self.rm_objects_changer == 'WIRE_SHADE':
                obj.draw_type = 'WIRE'
                obj.show_wire = False
            elif self.rm_objects_changer == 'MATERIAL_SHADE':
                obj.draw_type = 'TEXTURED'
                obj.show_wire = False
            elif self.rm_objects_changer == 'SHOW_WIRE':
                obj.draw_type = 'TEXTURED'
                obj.show_wire = True
            elif self.rm_objects_changer == 'ONESIDE_SHADE':
                if obj.type == 'MESH':
                    obj.data.show_double_sided = False
            elif self.rm_objects_changer == 'TWOSIDE_SHADE':
                if obj.type == 'MESH':
                    obj.data.show_double_sided = True
#            elif self.rm_objects_changer == 'RM_COLOURS':
#                if obj.type == 'MESH':
#                    set_RM_materials_using_RM_list(context)

        return {'FINISHED'}

class RM_repmod_manager_add(bpy.types.Operator):

    """Add and select a new layer group"""
    bl_idname = "repmod_manager.repmod_manager_add"
    bl_label = "Add Epoch group"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return bool(context.scene)

    def execute(self, context):
        
        bpy.ops.repmod_manager.repmod_manager_remove()        
        scene = context.scene
        epoch_number = len(scene.epoch_list)
        for epoch in range(epoch_number):
            epochname = scene.epoch_list[epoch].name

            check_same_ids()  # check scene ids

            repmod_managers = scene.repmod_managers

            # get all ids
            all_ids = []
            for e_manager in repmod_managers:
                if e_manager.unique_id not in all_ids:
                    all_ids.append(e_manager.unique_id)

             # generate new id
            uni_numb = generate_id()
            all_ids = None

            group_rm_idx = len(repmod_managers)
            new_e_manager = repmod_managers.add()
            new_e_manager.name = epochname
            new_e_manager.unique_id = uni_numb
            scene.repmod_managers_index = group_rm_idx

        return {'FINISHED'}
    

class RM_repmod_manager_remove(bpy.types.Operator):

    """Remove selected layer group"""
    bl_idname = "repmod_manager.repmod_manager_remove"
    bl_label = "Clear all epochs"
    bl_options = {'REGISTER', 'UNDO'}

    group_rm_idx : IntProperty()

    @classmethod
    def poll(cls, context):
        return bool(context.scene)

    def execute(self, context):
        scene_parse = context.scene
        epoch_num = len(scene_parse.repmod_managers)
        for i in range(epoch_num):
            self.group_rm_idx = scene_parse.repmod_managers_index
            # if a scene contains goups
            if scene_parse.repmod_managers:
                check_same_ids()  # check scene ids
                get_e_manager = scene_parse.repmod_managers[self.group_rm_idx]
                if get_e_manager is not None and self.group_rm_idx < len(scene_parse.repmod_managers):
                    e_manager_id = get_e_manager.unique_id

                    # get all ids
                    e_managers = []
                    for e_manager in scene_parse.repmod_managers:
                        e_managers.append(e_manager.unique_id)

                    # clear context scene
                    for obj in scene_parse.objects:
                        RM_del_properties_from_obj(
                            UNIQUE_ID_NAME, [e_manager_id], obj, True)

                    # clear SGR scene
                    sgr_scene_name = scene_parse.name + SCENE_RM
                    if sgr_scene_name in bpy.data.scenes:
                        sgr_scene = bpy.data.scenes[scene_parse.name + SCENE_RM]
                        for obj in sgr_scene.objects:
                            SGR_switch_object(obj, sgr_scene, scene_parse, e_manager_id)
                            RM_del_properties_from_obj(
                                UNIQUE_ID_NAME, [e_manager_id], obj, True)

                        # remove group_scene if it's empty
                        if len(sgr_scene.objects) == 0:
                            bpy.data.scenes.remove(sgr_scene)

                    # finally remove e_manager
                    scene_parse.repmod_managers.remove(self.group_rm_idx)
                    if len(scene_parse.repmod_managers) > 0:
                        scene_parse.repmod_managers_index = len(scene_parse.repmod_managers) - 1
                    else:
                        scene_parse.repmod_managers_index = -1
#                    self.group_rm_idx = scene_parse.repmod_managers_index
        
        return {'FINISHED'}


class RM_repmod_move(bpy.types.Operator):

    """Remove selected layer group"""
    bl_idname = "repmod_manager.repmod_manager_move"
    bl_label = "Move RepMod epoch"
    bl_options = {'REGISTER', 'UNDO'}

    do_move : EnumProperty(
        items=(('UP', 'UP', ''),
               ('DOWN', 'DOWN', '')
               ),
        default = 'UP'
    )

    @classmethod
    def poll(cls, context):
        return bool(context.scene)

    def execute(self, context):
        scene = context.scene

        # if a scene contains goups
        if scene.super_groups and len(scene.super_groups) > 1:
            s_group_id = scene.super_groups[scene.super_groups_index].unique_id
            if scene.super_groups:
                move_id = None
                if self.do_move == 'UP' and scene.super_groups_index > 0:
                    move_id = scene.super_groups_index - 1
                    scene.super_groups.move(scene.super_groups_index, move_id)
                elif self.do_move == 'DOWN' and scene.super_groups_index < len(scene.super_groups) - 1:
                    move_id = scene.super_groups_index + 1
                    scene.super_groups.move(scene.super_groups_index, move_id)

                if move_id is not None:
                    scene.super_groups_index = move_id

        return {'FINISHED'}


class RM_add_to_group(bpy.types.Operator):
    bl_idname = "repmod_manager.add_to_group"
    bl_label = "Add Selected Objects"
    bl_description = "Add To Super Group"
    bl_options = {'REGISTER', 'UNDO'}

    group_rm_idx = IntProperty()


    def execute(self, context):
        scene_parse = context.scene

        if scene_parse.repmod_managers:
            check_same_ids()  # check ids

            # remove e_managers
            ids = []
            for e_manager in scene_parse.repmod_managers:
                ids.append(e_manager.unique_id)
            for obj in context.selected_objects:
                for e_manager in scene_parse.repmod_managers:
                    RM_del_properties_from_obj(UNIQUE_ID_NAME, ids, obj, True)
            ids = None

            e_manager = scene_parse.repmod_managers[self.group_rm_idx]
            if e_manager is not None and self.group_rm_idx < len(scene_parse.repmod_managers):
                for obj in context.selected_objects:
                    # add the unique id of selected group
                    RM_add_property_to_obj(e_manager.unique_id, obj)

                    # switch locking for obj
                    if e_manager.is_locked is True:
                        obj.hide_select = True
                        obj.select = False
                    else:
                        obj.hide_select = False

                    # check if the group is hidden
                    if e_manager.use_toggle is False:
                        # Try to get or create new GroupScene
                        group_scene = RM_get_group_scene(context)
                        if group_scene is None:
                            group_scene = RM_create_group_scene(context)

                        # Unlink object
                        if group_scene is not None:
                            group_scene.objects.link(obj)
                            context.scene.objects.unlink(obj)

        return {'FINISHED'}


class RM_remove_from_group(bpy.types.Operator):
    bl_idname = "repmod_manager.super_remove_from_group"
    bl_label = "Remove Selected Objects"
    bl_description = "Remove from Super Group"
    bl_options = {'REGISTER', 'UNDO'}

    # group_rm_idx = bpy.props.IntProperty()

    def execute(self, context):
        scene = context.scene

        if scene.repmod_managers:
            check_same_ids()  # check ids

            # get all ids
            e_managers = []
            for e_manager in scene.repmod_managers:
                e_managers.append(e_manager.unique_id)

            # remove e_managers
            for obj in context.selected_objects:
                RM_del_properties_from_obj(UNIQUE_ID_NAME, e_managers, obj, True)
            e_managers = None  # clear

        return {'FINISHED'}


def RM_add_property_to_obj(prop_name, obj):
    props = obj.rm_belong_id

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


def RM_del_properties_from_obj(prop_name, e_managers_ids, obj, delete_in_e_managers=True):
    props = obj.rm_belong_id

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
        if scene.name.endswith(SCENE_RM) is False and scene != current_scene:
            check_scenes.append(scene)

    if check_scenes:
        other_ids = []
        for scene in check_scenes:
            for e_manager in scene.repmod_managers:
                if e_manager.unique_id not in other_ids:
                    other_ids.append(e_manager.unique_id)

        all_obj_list = None

        if other_ids:
            for i in range(len(current_scene.repmod_managers)):
                current_e_manager = current_scene.repmod_managers[i]
                current_id = current_e_manager.unique_id
                if current_id in other_ids:
                    new_id = generate_id()

                    if all_obj_list is None:
                        all_obj_list = []
                        all_obj_list += current_scene.objects
                        group_scene = RM_get_group_scene(bpy.context)
                        if group_scene is not None:
                            all_obj_list += group_scene.objects

                    for obj in all_obj_list:
                        has_id = False
                        for prop in obj.rm_belong_id:
                            if prop.unique_id_object == current_e_manager.unique_id:
                                has_id = True
                                break
                        if has_id == True:
                            RM_add_property_to_obj(new_id, obj)

                    # set new id
                    current_e_manager.unique_id = new_id

    # clean
    check_scenes = None
    all_obj_list = None
    other_ids = None