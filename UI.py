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
from . import addon_updater_ops

#####################################################################
#SETUP MENU
class Display_mode_menu(bpy.types.Menu):
    bl_label = "Custom Menu"
    bl_idname = "OBJECT_MT_Display_mode_menu"

    def draw(self, context):
        layout = self.layout

        layout.operator("emset.emmaterial", text="EM")
        layout.operator("emset.epochmaterial", text="Periods")

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

        if len(scene.em_list) > 0:
            is_em_list = True
        else:
            is_em_list = False
        #box = layout.box()

        row = layout.row(align=True)
        split = row.split()
        col = split.column()
        col.label(text="EM file")
        
        if scene.EM_file:
            col = split.column(align=True)
            if is_em_list:
                button_load_text = 'Reload'
                button_load_icon = 'FILE_REFRESH'
            else:
                button_load_text = 'Load'
                button_load_icon = 'IMPORT'
            col.operator("import.em_graphml", icon= button_load_icon, text=button_load_text)
        else:
            col.label(text="Select a GraphML file below", icon='SORT_ASC')
        #row = layout.row()
        if is_em_list:
            col = split.column(align=True)
            op = col.operator("list_icon.update", icon="PRESET", text='Refresh')
            op.list_type = "all"

        row = layout.row(align=True)
        row.prop(context.scene, 'EM_file', toggle = True, text ="")

        box = layout.box()
        row = box.row(align=True)
        #row = layout.row(align=True)
        split = row.split()
        col = split.column()
        col.label(text="US/USV")
        #col = split.column()
        col.prop(scene, "em_list", text='')
        col = split.column()
        col.label(text="Periods")
        #col = split.column()
        col.prop(scene, "epoch_list", text='')

        col = split.column()
        col.label(text="Properties")
        #col = split.column()
        col.prop(scene, "em_properties_list", text='')

        col = split.column()
        col.label(text="Sources")
        #col = split.column()
        col.prop(scene, "em_sources_list", text='')

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

        op = row.operator("label.onoff", text="", emboss=False, icon='RADIOBUT_ON')
        op.onoff = True

        op = row.operator("label.onoff", text="", emboss=False, icon='RADIOBUT_OFF')
        op.onoff = False

        op = row.operator("center.mass", text="", emboss=False, icon='CURSOR')
        op.center_to = "cursor"

        op = row.operator("center.mass", text="", emboss=False, icon='SNAP_FACE_CENTER')
        op.center_to = "mass"

class VIEW3D_PT_SetupPanel(Panel, EM_SetupPanel):
    bl_category = "EM"
    bl_idname = "VIEW3D_PT_SetupPanel"
    bl_context = "objectmode"
#SETUP MENU
#####################################################################

#####################################################################
#US/USV Manager
class EM_ToolsPanel:
    bl_label = "US/USV Manager"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'

    def draw(self, context):
        #addon_updater_ops.check_for_update_background(context)
        layout = self.layout
        scene = context.scene
        em_settings = scene.em_settings
        obj = context.object
        #layout.alignment = 'LEFT'
        row = layout.row()

        if scene.em_list_index >= 0 and len(scene.em_list) > 0:
            row.template_list("EM_UL_List", "EM nodes", scene, "em_list", scene, "em_list_index")
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
            op = col.operator("listitem.toobj", icon="PASTEDOWN", text='')
            op.list_type = "em_list"
            #row = layout.row()
            #row.label(text="Description:")
            row = box.row()
            #layout.alignment = 'LEFT'
            row.prop(item, "description", text="", slider=True, emboss=True)

            split = layout.split()
            if scene.em_list[scene.em_list_index].icon == 'RESTRICT_INSTANCED_OFF':
                col = split.column()
                op = col.operator("select.fromlistitem", text='', icon="MESH_CUBE")
                op.list_type = "em_list"
            else:
                col = split.column()
                col.label(text="", icon='MESH_CUBE') 
            if obj:
                if check_if_current_obj_has_brother_inlist(obj.name, "em_list"):
                    col = split.column(align=True)
                    op = col.operator("select.listitem", text='', icon="LONGDISPLAY")
                    op.list_type = "em_list"
                else:
                    col = split.column()
                    col.label(text="", icon='LONGDISPLAY')             

            #split = layout.split()
            col = split.column(align=True)
            col.label(text="Sync:")

            col = split.column(align=True)
            col.prop(em_settings, "em_proxy_sync2", text='', icon="MESH_CUBE")

            col = split.column(align=True)
            col.prop(em_settings, "em_proxy_sync2_zoom", text='', icon="ZOOM_SELECTED")

            col = split.column(align=True)
            col.prop(em_settings, "em_proxy_sync", text='', icon="LONGDISPLAY")

            col = split.column(align=True)
            col.prop(scene, "paradata_streaming_mode", text='', icon="SHORTDISPLAY")

            if scene.em_settings.em_proxy_sync is True:
                if obj is not None:
                    if check_if_current_obj_has_brother_inlist(obj.name, "em_list"):
                            select_list_element_from_obj_proxy(obj, "em_list")
                    
            if scene.em_settings.em_proxy_sync2 is True:
                if scene.em_list[scene.em_list_index].icon == 'RESTRICT_INSTANCED_OFF':
                    list_item = scene.em_list[scene.em_list_index]
                    if obj is not None:
                        if list_item.name != obj.name:
                            select_3D_obj(list_item.name)
                            if scene.em_settings.em_proxy_sync2_zoom is True:
                                for area in bpy.context.screen.areas:
                                    if area.type == 'VIEW_3D':
                                        ctx = bpy.context.copy()
                                        ctx['area'] = area
                                        ctx['region'] = area.regions[-1]
                                        bpy.ops.view3d.view_selected(ctx)

        else:
            row.label(text="No US/USV here :-(")

        #addon_updater_ops.update_notice_box_ui(self, context)

class VIEW3D_PT_ToolsPanel(Panel, EM_ToolsPanel):
    bl_category = "EM"
    bl_idname = "VIEW3D_PT_ToolsPanel"
    bl_context = "objectmode"

#US/USV Manager
#####################################################################

#####################################################################
#Periods Manager
class EM_BasePanel:
    bl_label = "Periods Manager"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        row = layout.row()
        ob = context.object

        if len(scene.em_list) > 0:
            row.template_list(
                "EM_UL_named_epoch_managers", "", scene, "epoch_list", scene, "epoch_list_index")
            row = layout.row()
            row.label(text="Representation Models (RM):")
            op = row.operator("epoch_models.add_remove", text="", emboss=False, icon='ADD')
            op.rm_epoch = scene.epoch_list[scene.epoch_list_index].name
            op.rm_add = True
            op = row.operator("epoch_models.add_remove", text="", emboss=False, icon='REMOVE')
            op.rm_epoch = scene.epoch_list[scene.epoch_list_index].name
            op.rm_add = False
            op = row.operator("select_rm.given_epoch", text="", emboss=False, icon='SELECT_SET')
            op.rm_epoch = scene.epoch_list[scene.epoch_list_index].name
        else:
            row.label(text="No periods here :-(")
        
        row = layout.row()

        if ob is None:
            pass
        else:
            if ob.type in ['MESH']:
                row.label(text="Active object: "+ob.name)
                row = layout.row()

            if len(ob.EM_ep_belong_ob) > 0:
                row.template_list(
                    "EM_UL_belongob", "", ob, "EM_ep_belong_ob", ob, "EM_ep_belong_ob_index", rows=2)
            else:
                row.label(text="No periods for active object")

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
            icon = 'RESTRICT_SELECT_ON' if epoch_list.is_selected else 'RESTRICT_SELECT_OFF'
            if icons_style == 'OUTLINER':
                icon = 'VIEWZOOM' if epoch_list.use_toggle else 'VIEWZOOM'
            layout = layout.split(factor=0.1, align=True)
            layout.prop(epoch_list, "epoch_RGB_color", text="", emboss=True, icon_value=0)
            op = layout.operator(
                "epoch_manager.toggle_select", text="", emboss=False, icon=icon)

            #self.layout.prop(context.scene, "test_color", text='Detail Color')
            op.group_em_idx = index
            # op.is_menu = False
            # op.is_select = True

            # lock operator
            icon = 'LOCKED' if epoch_list.is_locked else 'UNLOCKED'
            if icons_style == 'OUTLINER':
                icon = 'RESTRICT_SELECT_OFF' if epoch_list.is_locked else 'RESTRICT_SELECT_ON'
            op = layout.operator("epoch_manager.toggle_selectable", text="", emboss=False, icon=icon)
            #op.em_group_changer = 'LOCKING'
            op.group_em_idx = index

            # view operator
            icon = 'RESTRICT_VIEW_OFF' if epoch_list.use_toggle else 'RESTRICT_VIEW_ON'
            op = layout.operator(
                "epoch_manager.toggle_visibility", text="", emboss=False, icon=icon)
            op.group_em_vis_idx = index

            # soloing operator
            icon = 'RADIOBUT_ON' if epoch_list.epoch_soloing else 'RADIOBUT_OFF'
            op = layout.operator(
                "epoch_manager.toggle_soloing", text="", emboss=False, icon=icon)
            op.group_em_idx = index

            #icon = 'KEYTYPE_KEYFRAME_VEC' if epoch_list.rm_models else 'HANDLETYPE_FREE_VEC'
            #layout.label(icon=icon)

        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'

class EM_UL_belongob(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        split = layout.split()
        #split.label(text=str(item.epoch))
        split.prop(item, "epoch", text="", emboss=False, translate=False, icon='SORTTIME')

#Periods Manager
#####################################################################

#####################################################################
#Paradata Section

class EM_ParadataPanel:
    bl_label = "Paradata Manager"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        obj = context.object
        row = layout.row()

        # define variables 
        if scene.paradata_streaming_mode:
            property_list_var = "em_v_properties_list"
            property_list_index_var = "em_v_properties_list_index"
            property_list_cmd = "scene.em_v_properties_list"
            property_list_index_cmd = "scene.em_v_properties_list_index"

            combiner_list_var = "em_v_combiners_list"
            combiner_list_index_var = "em_v_combiners_list_index"
            combiner_list_cmd = "scene.em_v_combiners_list"
            combiner_list_index_cmd = "scene.em_v_combiners_list_index"

            extractor_list_var = "em_v_extractors_list"
            extractor_list_index_var = "em_v_extractors_list_index"
            extractor_list_cmd = "scene.em_v_extractors_list"
            extractor_list_index_cmd = "scene.em_v_extractors_list_index"

            source_list_var = "em_v_sources_list"
            source_list_index_var = "em_v_sources_list_index"
            source_list_cmd = "scene.em_v_sources_list"
            source_list_index_cmd = "scene.em_v_sources_list_index"

        else:
            property_list_var = "em_properties_list"
            property_list_index_var = "em_properties_list_index"
            property_list_cmd = "scene.em_properties_list"
            property_list_index_cmd = "scene.em_properties_list_index"

            combiner_list_var = "em_combiners_list"
            combiner_list_index_var = "em_combiners_list_index"
            combiner_list_cmd = "scene.em_combiners_list"
            combiner_list_index_cmd = "scene.em_combiners_list_index"

            extractor_list_var = "em_extractors_list"
            extractor_list_index_var = "em_extractors_list_index"
            extractor_list_cmd = "scene.em_extractors_list"
            extractor_list_index_cmd = "scene.em_extractors_list_index"  

            source_list_var = "em_sources_list"
            source_list_index_var = "em_sources_list_index"
            source_list_cmd = "scene.em_sources_list"
            source_list_index_cmd = "scene.em_sources_list_index"           

    ###############################################################################
    ##          Properties
    ###############################################################################

        len_property_var = "len("+property_list_cmd+")"
        if eval(property_list_index_cmd) >= 0 and eval(len_property_var) > 0:

            # layout.row().separator()

            row.label(text="Properties: ("+str(eval(len_property_var))+")")
            row.prop(scene, "prop_paradata_streaming_mode", text='', icon="SHORTDISPLAY")
            row = layout.row()
            row.template_list("EM_UL_properties_managers", "", scene, property_list_var, scene, property_list_index_var, rows=2)

            #item_source = scene.em_properties_list[scene.em_properties_list_index]
            item_property = eval(property_list_cmd)[eval(property_list_index_cmd)]
            box = layout.box()
            row = box.row(align=True)
            row = box.row()
            row.prop(item_property, "name", text="", icon='FILE_TEXT')
            row = box.row()
            row.prop(item_property, "description", text="", slider=True, emboss=True, icon='TEXT')
        else:
            row.label(text="No paradata here :-(")
    ###############################################################################
    ##          Combiners
    ###############################################################################

        len_combiner_var = "len("+combiner_list_cmd+")"
        if eval(combiner_list_index_cmd) >= 0 and eval(len_combiner_var) > 0:

            # layout.row().separator()

            row = layout.row()
            row.label(text="Reasoning - Combiners: ("+str(eval(len_combiner_var))+")")
            row.prop(scene, "comb_paradata_streaming_mode", text='', icon="SHORTDISPLAY")
            row = layout.row()
            row.template_list("EM_UL_combiners_managers", "", scene, combiner_list_var, scene, combiner_list_index_var, rows=1)
        
            item_property = eval(combiner_list_cmd)[eval(combiner_list_index_cmd)]
            box = layout.box()
            row = box.row(align=True)
            row = box.row()
            row.prop(item_property, "name", text="", icon='FILE_TEXT')
            row = box.row()
            row.prop(item_property, "description", text="", slider=True, emboss=True, icon='TEXT')
            row = box.row()
            row.prop(item_property, "url", text="", slider=True, emboss=True, icon='URL')
            op = row.operator("open.file", icon="EMPTY_SINGLE_ARROW", text='')
            op.node_type = combiner_list_var
            
    ###############################################################################
    ##          Extractors
    ###############################################################################

        len_source_var = "len("+extractor_list_cmd+")"
        if eval(extractor_list_index_cmd) >= 0 and eval(len_source_var) > 0:

            # layout.row().separator()

            row = layout.row()
            row.label(text="Interpretation - Extractors: ("+str(eval(len_source_var))+")")
            row.prop(scene, "extr_paradata_streaming_mode", text='', icon="SHORTDISPLAY")
            row = layout.row()
            row.template_list("EM_UL_extractors_managers", "", scene, extractor_list_var, scene, extractor_list_index_var, rows=2)

            item_source = eval(extractor_list_cmd)[eval(extractor_list_index_cmd)]
            box = layout.box()
            row = box.row(align=True)
            row = box.row()
            row.prop(item_source, "name", text="", icon='FILE_TEXT')
            op = row.operator("listitem.toobj", icon="PASTEDOWN", text='')
            op.list_type = extractor_list_var
            
            if scene.em_list[scene.em_list_index].icon == 'RESTRICT_INSTANCED_OFF':
                op = row.operator("select.fromlistitem", text='', icon="MESH_CUBE")
                op.list_type = extractor_list_var
            else:
                row.label(text="", icon='MESH_CUBE')
            if obj:
                if check_if_current_obj_has_brother_inlist(obj.name, extractor_list_var):
                    op = row.operator("select.listitem", text='', icon="LONGDISPLAY")
                    op.list_type = extractor_list_var
                else:
                    row.label(text="", icon='LONGDISPLAY')   
            
            row = box.row()
            row.prop(item_source, "description", text="", slider=True, emboss=True, icon='TEXT')
            row = box.row()
            row.prop(item_source, "url", text="", slider=True, emboss=True, icon='URL')
            op = row.operator("open.file", icon="EMPTY_SINGLE_ARROW", text='')
            op.node_type = extractor_list_var

    ###############################################################################
    ##          Sources
    ###############################################################################

        len_source_var = "len("+source_list_cmd+")"
        if eval(source_list_index_cmd) >= 0 and eval(len_source_var) > 0:

            # layout.row().separator()

            row = layout.row()
            row.label(text="Sources: ("+str(eval(len_source_var))+")")
            row = layout.row()
            row.template_list("EM_UL_sources_managers", "", scene, source_list_var, scene, source_list_index_var, rows=2)

            item_source = eval(source_list_cmd)[eval(source_list_index_cmd)]
            box = layout.box()
            row = box.row()
            row.prop(item_source, "name", text="", icon='FILE_TEXT')
            split = row.split()
            op = row.operator("listitem.toobj", icon="PASTEDOWN", text='')
            op.list_type = source_list_var
            
            #split = layout.split()
            if scene.em_list[scene.em_list_index].icon == 'RESTRICT_INSTANCED_OFF':
                #col = split.column()
                op = row.operator("select.fromlistitem", text='', icon="MESH_CUBE")
                op.list_type = source_list_var
            else:
                #col = split.column()
                row.label(text="", icon='MESH_CUBE')
            if obj:
                if check_if_current_obj_has_brother_inlist(obj.name, source_list_var):
                    #col = split.column(align=True)
                    op = row.operator("select.listitem", text='', icon="LONGDISPLAY")
                    op.list_type = source_list_var
                else:
                    #col = split.column()
                    row.label(text="", icon='LONGDISPLAY')              
            
            row = box.row()
            row.prop(item_source, "description", text="", slider=True, emboss=True, icon='TEXT')
            row = box.row()
            row.prop(item_source, "url", text="", slider=True, emboss=True, icon='URL')
            op = row.operator("open.file", icon="EMPTY_SINGLE_ARROW", text='')
            op.node_type = source_list_var
            row = box.row()

            #split = row.split(110 / (context.region.width - 45))
            #row.template_preview(bpy.data.textures['mao'], show_buttons=True)

class VIEW3D_PT_ParadataPanel(Panel, EM_ParadataPanel):
    bl_category = "EM"
    bl_idname = "VIEW3D_PT_ParadataPanel"
    bl_context = "objectmode"

class EM_UL_sources_managers(UIList):

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        icons_style = 'OUTLINER'
        scene = context.scene
        layout = layout.split(factor =0.22, align = True)
        layout.label(text = item.name, icon = item.icon)
        layout.label(text = item.description, icon=item.icon_url)

class EM_UL_properties_managers(UIList):

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        icons_style = 'OUTLINER'
        scene = context.scene
        layout = layout.split(factor =0.4, align = True)
        layout.label(text = item.name)
        layout.label(text = item.description)

class EM_UL_combiners_managers(UIList):

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        icons_style = 'OUTLINER'
        scene = context.scene
        layout = layout.split(factor =0.25, align = True)
        layout.label(text = item.name)
        layout.label(text = item.description)

class EM_UL_extractors_managers(UIList):

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        icons_style = 'OUTLINER'
        scene = context.scene
        layout = layout.split(factor =0.25, align = True)
        layout.label(text = item.name, icon = item.icon)
        layout.label(text = item.description, icon=item.icon_url)

# Paradata section 
#####################################################################

#####################################################################
#Export Section

class EM_ExportPanel:
    bl_label = "Export Manager"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        row = layout.row()

        row.label(text="Export Models:")
        row = layout.row()
        op = row.operator("export_manager.export", text="Proxies", emboss=True, icon='SHADING_SOLID')
        op.em_export_type = 'Proxies'
        op = row.operator("export_manager.export", text="RM", emboss=True, icon='SHADING_TEXTURE')
        op.em_export_type = 'RM'
        row = layout.row()

        row.label(text="Export Tables:")
        row = layout.row()
        op = row.operator("export.uuss_export", text="EM (csv)", emboss=True, icon='LONGDISPLAY')
        row = layout.row()
        row.prop(context.window_manager.export_tables_vars, 'table_type', expand=True)
        row = layout.row()

        row.label(text="EMviq:")
        row = layout.row()#(align=True)
        row.prop(context.scene, 'EMviq_folder', toggle=True, text="")
        row.label(text="<-- folder export path")
        row = layout.row()
        op = row.operator("export_manager.export", text="Generate EMviq Folder", emboss=True, icon='LONGDISPLAY')
        op.em_export_type = 'EMviq'
        op.em_export_format = context.window_manager.export_vars.format_file
        row = layout.row()
        row.prop(context.window_manager.export_vars, 'format_file', expand=True)
        row = layout.row()
        if scene.emviq_error_list_index >= 0 and len(scene.emviq_error_list) > 0:
            row.template_list("ER_UL_List", "EM nodes", scene, "emviq_error_list", scene, "emviq_error_list_index")
            item = scene.emviq_error_list[scene.emviq_error_list_index]
            box = layout.box()
            row = box.row(align=True)

            split = row.split()
            col = split.column()
            row.prop(item, "name", text="")
            split = row.split()
            col = split.column()
            op = col.operator("select.fromlistitem", text='', icon="MESH_CUBE")
            op.list_type = "emviq_error_list"
            #op = col.operator("listitem.toobj", icon="PASTEDOWN", text='')
            #op.list_type = "emviq_error_list"
            #row = layout.row()
            #row.label(text="Description:")
            row = box.row()
            #layout.alignment = 'LEFT'
            row.prop(item, "description", text="", slider=True, emboss=True)

        #op.em_export_format = 'gltf'
        #op.em_export_type = 'RM'
        

class VIEW3D_PT_ExportPanel(Panel, EM_ExportPanel):
    bl_category = "EM"
    bl_idname = "VIEW3D_PT_ExportPanel"
    bl_context = "objectmode"


class ER_UL_List(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        icons_style = 'OUTLINER'
        scene = context.scene
        layout = layout.split(factor =0.30, align = True)
        layout.label(text = item.texture_type, icon = 'ERROR')
        layout.label(text = item.material, icon='NONE', icon_value=0)

#Export Section
#####################################################################
