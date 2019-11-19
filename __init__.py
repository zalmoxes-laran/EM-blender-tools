'''
Copyright (C) 2018 Emanuel Demetrescu

Created by EMANUEL DEMETRESCU 2018-2019
emanuel.demetrescu@gmail.com

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
'''

bl_info = {
    "name": "EM tools",
    "description": "Blender tools for Extended Matrix",
    "author": "E. Demetrescu",
    "version": (1, 1, 7),
    "blender": (2, 80, 0),
#     "location": "3D View > Toolbox",
#    "warning": "This addon is still in development.",
    "wiki_url": "",
    "category": "Tools",
    }

# load and reload submodules
##################################

import math
import bpy
import bpy.props as prop
from bpy.props import (
        StringProperty,
        BoolProperty,
        FloatProperty,
        EnumProperty,
        IntProperty,
        PointerProperty,
        CollectionProperty,
        FloatVectorProperty,
        )
        
from bpy.types import (
        AddonPreferences,
        PropertyGroup,
        )

from . import (
        UI,
        EM_list,
        epoch_manager,
        functions,
        paradata_manager,
        )

from .functions import *
from bpy.utils import register_class, unregister_class

class EDGESListItem(bpy.types.PropertyGroup):
       """ Group of properties an item in the list """

       id_node: prop.StringProperty(
              name="id",
              description="A description for this item",
              default="Empty")

       source: prop.StringProperty(
              name="source",
              description="A description for this item",
              default="Empty")

       target: prop.StringProperty(
              name="target",
              description="A description for this item",
              default="Empty")

class EPOCHListItem(bpy.types.PropertyGroup):
       """ Group of properties representing an item in the list """
       name: prop.StringProperty(
              name="Name",
              description="A name for this item",
              default="Untitled")

       id: prop.StringProperty(
              name="id",
              description="A description for this item",
              default="Empty")

       min_y: prop.FloatProperty(
              name="code for icon",
              description="",
              default=0.0)

       max_y: prop.FloatProperty(
              name="code for icon",
              description="",
              default=0.0)

       height: prop.FloatProperty(
              name="height of epoch row",
              description="",
              default=0.0)
       
       epoch_color: prop.StringProperty(
              name="color of epoch row",
              description="",
              default="Empty")       

       use_toggle: BoolProperty(name="", default=True)
       is_locked: BoolProperty(name="", default=True)
       is_selected: BoolProperty(name="", default=False)
       epoch_soloing: BoolProperty(name="", default=False)

       unique_id: StringProperty(default="")

       epoch_RGB_color: FloatVectorProperty(
              name="epoch_color",
              subtype="COLOR",
              size=3,
              min=0.0,
              max=1.0,
              default=(0.5, 0.5, 0.5)
       )

       wire_color: FloatVectorProperty(
              name="wire",
              subtype='COLOR',
              default=(0.2, 0.2, 0.2),
              min=0.0, max=1.0,
              description="wire color of the group"
       )

class EM_Other_Settings(PropertyGroup):
       contex = bpy.context
       select_all_layers: BoolProperty(name="Select Visible Layers", default=True)
       unlock_obj: BoolProperty(name="Unlock Objects", default=False)
       unhide_obj: BoolProperty(name="Unhide Objects", default=True)
       em_proxy_sync: BoolProperty(name="Selecting a proxy you select the corresponding EM", default=False, update = functions.sync_Switch_em)
       em_proxy_sync2: BoolProperty(name="Selecting an EM you select the corresponding proxy", default=False, update = functions.sync_Switch_proxy)
       em_proxy_sync2_zoom: BoolProperty(name="Option to zoom to proxy", default=False, update = functions.sync_Switch_proxy)
       soloing_mode: BoolProperty(name="Soloing mode", default=False)

#######################################################################################################################

class EMListItem(bpy.types.PropertyGroup):
    """ Group of properties representing an item in the list """

    name: prop.StringProperty(
           name="Name",
           description="A name for this item",
           default="Untitled")

    description: prop.StringProperty(
           name="Description",
           description="A description for this item",
           default="Empty")

    icon: prop.StringProperty(
           name="code for icon",
           description="",
           default="RESTRICT_INSTANCED_ON")

    url: prop.StringProperty(
           name="url",
           description="An url behind this item",
           default="Empty")

    shape: prop.StringProperty(
           name="shape",
           description="The shape of this item",
           default="Empty")

    y_pos: prop.FloatProperty(
           name="y_pos",
           description="The y_pos of this item",
           default=0.0)

    epoch: prop.StringProperty(
           name="code for epoch",
           description="",
           default="Empty")

    id_node: prop.StringProperty(
           name="id node",
           description="",
           default="Empty")

class EMreusedUS(bpy.types.PropertyGroup):
    """ Group of properties representing an item in the list """

    epoch: prop.StringProperty(
           name="epoch",
           description="Epoch",
           default="Untitled")

    em_element: prop.StringProperty(
           name="em_element",
           description="",
           default="Empty")

class EMListParadata(bpy.types.PropertyGroup):
    """ Group of properties representing a paradata element in the list """

    name: prop.StringProperty(
           name="Name",
           description="A name for this item",
           default="Untitled")

    description: prop.StringProperty(
           name="Description",
           description="A description for this item",
           default="Empty")

    icon: prop.StringProperty(
           name="code for icon",
           description="",
           default="RESTRICT_INSTANCED_ON")

    icon_url: prop.StringProperty(
           name="code for icon url",
           description="",
           default="CHECKBOX_DEHLT")

    url: prop.StringProperty(
           name="url",
           description="An url behind this item",
           default="Empty")

    id_node: prop.StringProperty(
           name="id_node",
           description="The id node of this item",
           default="Empty")

# register
##################################

classes = (
    UI.VIEW3D_PT_SetupPanel,
    UI.VIEW3D_PT_ToolsPanel,
    UI.VIEW3D_PT_BasePanel,
    UI.EM_UL_named_epoch_managers,
    UI.RM_UL_named_repmod_managers,
    UI.Display_mode_menu,
    UI.VIEW3D_PT_ParadataPanel,
    UI.EM_UL_properties_managers,
    UI.EM_UL_sources_managers,
    UI.EM_UL_extractors_managers,
    UI.EM_UL_combiners_managers,
    EM_list.EM_listitem_OT_to3D,
    EM_list.EM_update_icon_list,
    EM_list.EM_select_from_list_item,
    EM_list.EM_import_GraphML,
    EM_list.EM_select_list_item,
    epoch_manager.EM_UL_List,
    epoch_manager.EM_toggle_select,
    epoch_manager.EM_toggle_visibility,
    epoch_manager.EM_set_EM_materials,
    epoch_manager.EM_set_epoch_materials,
    epoch_manager.EM_change_selected_objects,
    epoch_manager.EM_toggle_selectable,
    epoch_manager.EM_toggle_soloing,
    paradata_manager.EM_files_opener,
    EMListItem,
    EM_Other_Settings,
    EPOCHListItem,
    EMreusedUS,
    EMListParadata,
    EDGESListItem
    )

def register():
       for cls in classes:
              bpy.utils.register_class(cls)
       bpy.types.Scene.em_list = prop.CollectionProperty(type = EMListItem)
       bpy.types.Scene.em_list_index = prop.IntProperty(name = "Index for my_list", default = 0, update = functions.switch_paradata_lists)
       bpy.types.Scene.em_reused = prop.CollectionProperty(type = EMreusedUS)
       bpy.types.Scene.epoch_list = prop.CollectionProperty(type = EPOCHListItem)
       bpy.types.Scene.epoch_list_index = prop.IntProperty(name = "Index for epoch_list", default = 0)

       bpy.types.Scene.edges_list = prop.CollectionProperty(type = EDGESListItem)
       #bpy.types.Scene.em_sources_list_index = prop.IntProperty(name = "Index for sources list", default = 0)

       bpy.types.Scene.em_sources_list = prop.CollectionProperty(type = EMListParadata)
       bpy.types.Scene.em_sources_list_index = prop.IntProperty(name = "Index for sources list", default = 0)
       bpy.types.Scene.em_properties_list = prop.CollectionProperty(type = EMListParadata)
       bpy.types.Scene.em_properties_list_index = prop.IntProperty(name = "Index for properties list", default = 0)
       bpy.types.Scene.em_extractors_list = prop.CollectionProperty(type = EMListParadata)
       bpy.types.Scene.em_extractors_list_index = prop.IntProperty(name = "Index for extractors list", default = 0)
       bpy.types.Scene.em_combiners_list = prop.CollectionProperty(type = EMListParadata)
       bpy.types.Scene.em_combiners_list_index = prop.IntProperty(name = "Index for combiners list", default = 0)

       bpy.types.Scene.em_v_sources_list = prop.CollectionProperty(type = EMListParadata)
       bpy.types.Scene.em_v_sources_list_index = prop.IntProperty(name = "Index for sources list", default = 0)
       bpy.types.Scene.em_v_properties_list = prop.CollectionProperty(type = EMListParadata)
       bpy.types.Scene.em_v_properties_list_index = prop.IntProperty(name = "Index for properties list", default = 0, update = functions.stream_properties)
       bpy.types.Scene.em_v_extractors_list = prop.CollectionProperty(type = EMListParadata)
       bpy.types.Scene.em_v_extractors_list_index = prop.IntProperty(name = "Index for extractors list", default = 0, update = functions.stream_extractors)
       bpy.types.Scene.em_v_combiners_list = prop.CollectionProperty(type = EMListParadata)
       bpy.types.Scene.em_v_combiners_list_index = prop.IntProperty(name = "Index for combiners list", default = 0, update = functions.stream_combiners)

       bpy.types.Scene.paradata_streaming_mode = BoolProperty(name="Paradata streaming mode", description = "Enable/disable tables streaming mode",default=True, update = functions.switch_paradata_lists)
       bpy.types.Scene.prop_paradata_streaming_mode = BoolProperty(name="Properties Paradata streaming mode", description = "Enable/disable property table streaming mode",default=True, update = functions.stream_properties)
       bpy.types.Scene.comb_paradata_streaming_mode = BoolProperty(name="Combiners Paradata streaming mode", description = "Enable/disable combiner table streaming mode",default=True, update = functions.stream_combiners)
       bpy.types.Scene.extr_paradata_streaming_mode = BoolProperty(name="Extractors Paradata streaming mode", description = "Enable/disable extractor table streaming mode",default=True, update = functions.stream_extractors)

       bpy.types.Scene.proxy_shader_mode = BoolProperty(name="Proxy shader mode", description = "Enable additive shader for proxies",default=False, update = functions.proxy_shader_mode_function)
       bpy.types.Scene.EM_file = StringProperty(
              name = "EM GraphML file",
              default = "",
              description = "Define the path to the EM GraphML file",
              subtype = 'FILE_PATH'
       )

       ######################################################################################################
       #per epoch manager
       ##################

       bpy.types.Scene.em_settings = PointerProperty(type=EM_Other_Settings)
       bpy.types.Scene.rm_settings = PointerProperty(type=EM_Other_Settings)
       bpy.types.Scene.proxy_display_mode = StringProperty(
              name = "Proxy display mode",
              default = "EM",
              description = "EM proxy current display mode"
       )
       bpy.types.Scene.proxy_blend_mode = StringProperty(
              name = "Proxy blend mode",
              default = "BLEND",
              description = "EM proxy blend mode for current display mode"
       )
       bpy.types.Scene.proxy_display_alpha = FloatProperty(
              name="alpha",
              description="The alphavalue for proxies",
              min=0,
              max=1,
              default=0.5,
              update = functions.update_display_mode
       )

       bpy.types.VIEW3D_MT_mesh_add.append(menu_func)

######################################################################################################

def unregister():
       for cls in classes:
              bpy.utils.unregister_class(cls)

       ######################################################################################################
       #per epoch manager
       ##################
       del bpy.types.Scene.em_settings
       del bpy.types.Scene.em_list
       del bpy.types.Scene.em_list_index
       del bpy.types.Scene.em_reused
       del bpy.types.Scene.epoch_list
       del bpy.types.Scene.epoch_list_index
       del bpy.types.Scene.proxy_shader_mode
       del bpy.types.Scene.EM_file
       del bpy.types.Scene.rm_settings
       del bpy.types.Scene.proxy_display_mode
       del bpy.types.Scene.proxy_blend_mode
       del bpy.types.Scene.proxy_display_alpha
       del bpy.types.Scene.em_sources_list_index
       del bpy.types.Scene.em_sources_list
       del bpy.types.Scene.em_properties_list
       del bpy.types.Scene.em_properties_list_index
       del bpy.types.Scene.em_extractors_list
       del bpy.types.Scene.em_extractors_list_index
       del bpy.types.Scene.em_combiners_list
       del bpy.types.Scene.em_combiners_list_index

       del bpy.types.Scene.em_v_sources_list_index
       del bpy.types.Scene.em_v_sources_list
       del bpy.types.Scene.em_v_properties_list
       del bpy.types.Scene.em_v_properties_list_index
       del bpy.types.Scene.em_v_extractors_list
       del bpy.types.Scene.em_v_extractors_list_index
       del bpy.types.Scene.em_v_combiners_list
       del bpy.types.Scene.em_v_combiners_list_index

       del bpy.types.Scene.edges_list

       del bpy.types.Scene.paradata_streaming_mode

       del bpy.types.Scene.prop_paradata_streaming_mode
       del bpy.types.Scene.comb_paradata_streaming_mode
       del bpy.types.Scene.extr_paradata_streaming_mode

######################################################################################################

