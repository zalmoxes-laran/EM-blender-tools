#    part of this library is a heavy modified version of the original code from: 
#    "name": "Super Grouper",
#    "author": "Paul Geraskin, Aleksey Juravlev, BA Community",

import bpy

from .functions import *
from bpy.props import *
from bpy.types import Operator
from bpy.types import Menu, Panel, UIList, PropertyGroup
from bpy.props import StringProperty, BoolProperty, IntProperty, CollectionProperty, BoolVectorProperty, PointerProperty
from bpy.app.handlers import persistent

from .epoch_manager import *
from .EM_list import *


class Display_mode_menu(bpy.types.Menu):
    bl_label = "Custom Menu"
    bl_idname = "OBJECT_MT_Display_mode_menu"

    def draw(self, context):
        layout = self.layout

        layout.operator("emset.emmaterial", text="EM")
        layout.operator("emset.epochmaterial", text="Epochs")

        #layout.label(text="Hello world!", icon='WORLD_DATA')

        # use an operator enum property to populate a sub-menu
        # layout.operator_menu_enum("object.select_by_type",
        #                           property="type",
        #                           text="Select All by Type...",
        #                           )

        # call another menu
        #layout.operator("wm.call_menu", text="Unwrap").name = "VIEW3D_MT_uv_map"

class EM_SetupPanel:
    bl_label = "EM setup"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        em_settings = scene.em_settings
        obj = context.object
        current_proxy_display_mode = context.scene.proxy_display_mode
        #box = layout.box()

        row = layout.row(align=True)
        split = row.split()
        col = split.column()
        col.label(text="EM file")
        col = split.column(align=True)
        col.operator("import.em_graphml", icon="FILE_REFRESH", text='(Re)Load')
        #row = layout.row()
        #col = split.column(align=True)
        #col.operator("uslist_icon.update", icon="PRESET", text='Refresh')

        row = layout.row(align=True)
        row.prop(context.scene, 'EM_file', toggle = True, text ="")

        row = layout.row(align=True)
        split = row.split()
        col = split.column()
        col.label(text="US/USV")
        #col = split.column()
        col.prop(scene, "em_list", text='')
        col = split.column()
        col.label(text="Epochs")
        #col = split.column()
        col.prop(scene, "epoch_list", text='')

        row = layout.row(align=True)
        split = row.split()
        col = split.column()
        col.label(text="Display mode")
        col = split.column(align=True)
        
        col.menu(Display_mode_menu.bl_idname, text=current_proxy_display_mode, icon='COLOR')
 
        row = layout.row()
        split = row.split()
        
        col = split.column(align=True)
        col.prop(scene, "proxy_display_alpha")
        
        col = split.column(align=True)
        col.prop(scene, "proxy_shader_mode")

        col = split.column()
        col.operator("import.em_graphml", icon="FILE_REFRESH", text='')

        row = layout.row(align=True)

        row.label(text="On selected:")
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
        
class VIEW3D_PT_SetupPanel(Panel, EM_SetupPanel):
    bl_category = "EM"
    bl_idname = "VIEW3D_PT_SetupPanel"
    bl_context = "objectmode"

class EM_ToolsPanel:
    bl_label = "US/USV Manager"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        em_settings = scene.em_settings
        obj = context.object
        #layout.alignment = 'LEFT'
        row = layout.row()
        row.template_list("EM_UL_List", "EM nodes", scene, "em_list", scene, "em_list_index")
        if scene.em_list_index >= 0 and len(scene.em_list) > 0:
            item = scene.em_list[scene.em_list_index]
            box = layout.box()
            row = box.row(align=True)
            #row.label(text="US/USV name, description:")
            #row = box.row()
            split = row.split()
            col = split.column()
            row.prop(item, "name", text="")
            split = row.split()
            col = split.column()
            col.operator("usname.toproxy", icon="PASTEDOWN", text='')
            #row = layout.row()
            #row.label(text="Description:")
            row = box.row()
            #layout.alignment = 'LEFT'
            row.prop(item, "description", text="", slider=True, emboss=True)

        split = layout.split()
        col = split.column()

        col.operator("select.fromlistitem", text='Proxy', icon="MESH_CUBE")
        col = split.column(align=True)
        col.operator("select.listitem", text='EM', icon="LONGDISPLAY")

        split = layout.split()
        col = split.column(align=True)
        col.label(text="Sync:")

        col = split.column(align=True)
        col.prop(em_settings, "em_proxy_sync2", text='', icon="MESH_CUBE")

        col = split.column(align=True)
        col.prop(em_settings, "em_proxy_sync2_zoom", text='', icon="ZOOM_SELECTED")

        col = split.column(align=True)
        col.prop(em_settings, "em_proxy_sync", text='', icon="LONGDISPLAY")

        if scene.em_settings.em_proxy_sync is True:
            if check_if_current_obj_has_brother_inlist(obj.name):
                    select_list_element_from_obj_proxy(obj)
                
        if scene.em_settings.em_proxy_sync2 is True:
            if scene.em_list[scene.em_list_index].icon == 'RESTRICT_INSTANCED_OFF':
                list_item = scene.em_list[scene.em_list_index]
                if list_item.name != obj.name:
                    select_3D_obj(list_item.name)
                    if scene.em_settings.em_proxy_sync2_zoom is True:
                        for area in bpy.context.screen.areas:
                            if area.type == 'VIEW_3D':
                                ctx = bpy.context.copy()
                                ctx['area'] = area
                                ctx['region'] = area.regions[-1]
                                bpy.ops.view3d.view_selected(ctx)
            
class VIEW3D_PT_ToolsPanel(Panel, EM_ToolsPanel):
    bl_category = "EM"
    bl_idname = "VIEW3D_PT_ToolsPanel"
    bl_context = "objectmode"

class EM_BasePanel:
    bl_label = "Epochs Manager"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        em_settings = scene.em_settings
        row = layout.row()
        row.template_list(
            "EM_UL_named_epoch_managers", "", scene, "epoch_list", scene, "epoch_list_index")
        #layout.label(text="Selection Settings:")
        #row = layout.row(align=True)
        #row.prop(em_settings, "unlock_obj", text='UnLock')
        #row.prop(em_settings, "unhide_obj", text='Unhide')
        #row = layout.row(align=True)

class VIEW3D_PT_BasePanel(Panel, EM_BasePanel):
    bl_category = "EM"
    bl_idname = "VIEW3D_PT_BasePanel"
    bl_context = "objectmode"

class EM_UL_named_epoch_managers(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        epoch_list = item
        #user_preferences = context.user_preferences
        #self.layout.prop(context.scene, "test_color", text='Detail Color')
        icons_style = 'OUTLINER'
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            layout = layout.split(factor=0.6, align=True)
            layout.prop(epoch_list, "name", text="", emboss=False)

            # select operator
            icon = 'RESTRICT_SELECT_OFF' if epoch_list.use_toggle else 'RESTRICT_SELECT_ON'

            #if icons_style == 'OUTLINER':
            # icon = 'VIEWZOOM' if epoch_list.use_toggle else 'VIEWZOOM'
            # layout = layout.split(factor=0.1, align=True)
            # layout.prop(epoch_list, "epoch_color", text="", emboss=True, icon_value=0)
            # op = layout.operator(
            #     "epoch_manager.toggle_select", text="", emboss=False, icon=icon)

            #self.layout.prop(context.scene, "test_color", text='Detail Color')
            # op.group_em_idx = index
            # op.is_menu = False
            # op.is_select = True

            # lock operator
            # icon = 'LOCKED' if epoch_list.is_locked else 'UNLOCKED'

            #if icons_style == 'OUTLINER':
            # icon = 'RESTRICT_SELECT_ON' if epoch_list.is_locked else 'RESTRICT_SELECT_OFF'
            # op = layout.operator(
            #     "epoch_manager.toggle_select.change_grouped_objects", text="", emboss=False, icon=icon)
            # op.em_group_changer = 'LOCKING'
            # op.group_em_idx = index

            # view operator
            icon = 'RESTRICT_VIEW_OFF' if epoch_list.use_toggle else 'RESTRICT_VIEW_ON'
            op = layout.operator(
                "epoch_manager.toggle_visibility", text="", emboss=False, icon=icon)
            op.group_em_idx = index

        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'

class EM_Add_Objects_Sub_Menu(bpy.types.Menu):
    bl_idname = "epoch_manager.add_objects_sub_menu"
    bl_label = "Add Selected Objects"
    bl_description = "Add Objects Menu"

    def draw(self, context):
        layout = self.layout

        for i, e_manager in enumerate(context.scene.epoch_managers):
            op = layout.operator(EM_add_to_group.bl_idname, text=e_manager.name)
            op.group_em_idx = i


class EM_Remove_SGroup_Sub_Menu(bpy.types.Menu):
    bl_idname = "epoch_manager.remove_e_manager_sub_menu"
    bl_label = "Remove Super Group"
    bl_description = "Remove Super Group Menu"

    def draw(self, context):
        layout = self.layout

        for i, e_manager in enumerate(context.scene.epoch_managers):
            op = layout.operator(EM_epoch_manager_remove.bl_idname, text=e_manager.name)
            op.group_em_idx = i


class EM_Select_SGroup_Sub_Menu(bpy.types.Menu):
    bl_idname = "epoch_manager.select_e_manager_sub_menu"
    bl_label = "Select SGroup"
    bl_description = "Select SGroup Menu"

    def draw(self, context):
        layout = self.layout

        for i, e_manager in enumerate(context.scene.epoch_managers):
            op = layout.operator(EM_toggle_select.bl_idname, text=e_manager.name)
            op.group_em_idx = i
            op.is_select = True
            op.is_menu = True


class EM_Deselect_SGroup_Sub_Menu(bpy.types.Menu):
    bl_idname = "epoch_manager.deselect_e_manager_sub_menu"
    bl_label = "Deselect SGroup"
    bl_description = "Deselect SGroup Menu"

    def draw(self, context):
        layout = self.layout

        for i, e_manager in enumerate(context.scene.epoch_managers):
            op = layout.operator(EM_toggle_select.bl_idname, text=e_manager.name)
            op.group_em_idx = i
            op.is_select = False
            op.is_menu = True


class EM_Toggle_Visible_SGroup_Sub_Menu(bpy.types.Menu):
    bl_idname = "epoch_manager.toggle_e_manager_sub_menu"
    bl_label = "Toggle SGroup"
    bl_description = "Toggle SGroup Menu"

    def draw(self, context):
        layout = self.layout

        for i, e_manager in enumerate(context.scene.epoch_managers):
            op = layout.operator(EM_toggle_visibility.bl_idname, text=e_manager.name)
            op.group_em_idx = i


class EM_Toggle_Shading_Sub_Menu(bpy.types.Menu):
    bl_idname = "epoch_manager.toggle_shading_sub_menu"
    bl_label = "Toggle Shading"
    bl_description = "Toggle Shading Menu"

    def draw(self, context):
        layout = self.layout

        op = layout.operator(EM_change_selected_objects.bl_idname, text="Bound Shade")
        op.sg_objects_changer = 'BOUND_SHADE'

        op = layout.operator(EM_change_selected_objects.bl_idname, text="Wire Shade")
        op.sg_objects_changer = 'WIRE_SHADE'

        op = layout.operator(EM_change_selected_objects.bl_idname, text="Material Shade")
        op.sg_objects_changer = 'MATERIAL_SHADE'

        op = layout.operator(EM_change_selected_objects.bl_idname, text="Show Wire")
        op.sg_objects_changer = 'SHOW_WIRE'

        layout.separator()
        op = layout.operator(EM_change_selected_objects.bl_idname, text="One Side")
        op.sg_objects_changer = 'ONESIDE_SHADE'
        op = layout.operator(EM_change_selected_objects.bl_idname, text="Double Side")
        op.sg_objects_changer = 'TWOSIDE_SHADE'

#########################################################################################################

class RM_BasePanel:
    bl_label = "Representation models"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        rm_settings = scene.rm_settings

        row = layout.row(align=True)
        row.operator(
            "repmod_manager.repmod_manager_add", icon='ADD', text="")
        op = row.operator(
            "repmod_manager.repmod_manager_remove", icon='REMOVE', text="")
        op.group_rm_idx = scene.repmod_managers_index

        op = row.operator(
            "repmod_manager.repmod_manager_move", icon='TRIA_UP', text="")
        op.do_move = 'UP'

        op = row.operator(
            "repmod_manager.repmod_manager_move", icon='TRIA_DOWN', text="")
        op.do_move = 'DOWN'

        row = layout.row()
        row.template_list(
            "RM_UL_named_repmod_managers", "", scene, "repmod_managers", scene, "repmod_managers_index")

        row = layout.row()
        op = row.operator("repmod_manager.repmod_add_to_group", text="Add")
        op.group_rm_idx = scene.repmod_managers_index

        row.operator(
            "repmod_manager.repmod_remove_from_group", text="Remove")
        row.operator("repmod_manager.clean_object_ids", text="Clean")



        layout.label(text="Selection Settings:")
        row = layout.row(align=True)
        #row.prop(rm_settings, "select_all_layers", text='Layers')
        row.prop(rm_settings, "unlock_obj", text='UnLock')
        row.prop(rm_settings, "unhide_obj", text='Unhide')
        row = layout.row(align=True)


class VIEW3D_RM_BasePanel(Panel, RM_BasePanel):
    bl_category = "EM"
    bl_idname = "VIEW3D_RM_BasePanel"
    bl_context = "objectmode"


class RM_UL_named_repmod_managers(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        repmod_manager = item
        #user_preferences = context.user_preferences
        icons_style = 'OUTLINER'
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            layout.prop(repmod_manager, "name", text="", emboss=False)
            # select operator
            icon = 'RESTRICT_SELECT_OFF' if repmod_manager.use_toggle else 'RESTRICT_SELECT_ON'
            #if icons_style == 'OUTLINER':
            icon = 'VIEWZOOM' if repmod_manager.use_toggle else 'VIEWZOOM'
            op = layout.operator(
                "repmod_manager.toggle_select", text="", emboss=False, icon=icon)
            op.group_rm_idx = index
            op.is_menu = False
            op.is_select = True
            # lock operator
            icon = 'LOCKED' if repmod_manager.is_locked else 'UNLOCKED'
            #if icons_style == 'OUTLINER':
            icon = 'RESTRICT_SELECT_ON' if repmod_manager.is_locked else 'RESTRICT_SELECT_OFF'
            op = layout.operator(
                "repmod_manager.rmchange_grouped_objects", text="", emboss=False, icon=icon)
            op.rm_group_changer = 'LOCKING'
            op.group_rm_idx = index
            # view operator
            icon = 'RESTRICT_VIEW_OFF' if repmod_manager.use_toggle else 'RESTRICT_VIEW_ON'
            op = layout.operator(
                "repmod_manager.toggle_visibility", text="", emboss=False, icon=icon)
            op.group_rm_idx = index

        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'