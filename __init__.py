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
    "version": (1, 1, 1),
    "blender": (2, 80, 0),
    "location": "3D View > Toolbox",
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
        )

from .functions import *
from bpy.utils import register_class, unregister_class


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


class EM_Group(PropertyGroup):
    use_toggle: BoolProperty(name="", default=True)
    #is_wire = BoolProperty(name="", default=False)
    is_locked: BoolProperty(name="", default=False)
    is_selected: BoolProperty(name="", default=False)
                               # this is just a temporary value as a user can
                               # select/deselect
    unique_id: StringProperty(default="")

    wire_color: FloatVectorProperty(
        name="wire",
        subtype='COLOR',
        default=(0.2, 0.2, 0.2),
        min=0.0, max=1.0,
        description="wire color of the group"
    )

class EM_Object_Id(PropertyGroup):
    unique_id_object: StringProperty(default="")

class EM_Other_Settings(PropertyGroup):
    select_all_layers: BoolProperty(name="Select Visible Layers", default=True)
    unlock_obj: BoolProperty(name="Unlock Objects", default=False)
    unhide_obj: BoolProperty(name="Unhide Objects", default=True)
    em_proxy_sync: BoolProperty(name="Sync EM Proxy selection", default=False, update = settingsSwitch)
    em_proxy_sync2: BoolProperty(name="Sync EM Proxy selection2", default=False, update = settingsSwitch)
    em_proxy_sync2_zoom: BoolProperty(name="Sync EM Proxy selection2 zoom", default=False, update = settingsSwitch)

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
           default="QUESTION")

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



# register
##################################

classes = (
    UI.VIEW3D_EM_ToolsPanel,
    UI.VIEW3D_EM_BasePanel,
    UI.EM_named_epoch_managers,
    # UI.EM_Add_Objects_Sub_Menu,
    # UI.EM_Remove_SGroup_Sub_Menu,
    # UI.EM_Select_SGroup_Sub_Menu,
    # UI.EM_Deselect_SGroup_Sub_Menu,
    # UI.EM_Toggle_Shading_Sub_Menu,
    # UI.EM_Toggle_Visible_SGroup_Sub_Menu,
    EM_list.EM_usname_OT_toproxy,
    EM_list.EM_update_icon_list,
    EM_list.EM_select_from_list_item,
    EM_list.EM_import_GraphML,
    EM_list.EM_select_list_item,
    epoch_manager.EM_UL_List,
#     epoch_manager.EM_clean_object_ids,
    epoch_manager.EM_toggle_select,
    epoch_manager.EM_toggle_visibility,
#     epoch_manager.EM_switch_object,
    epoch_manager.EM_change_grouped_objects,
    epoch_manager.EM_set_EM_materials,
    epoch_manager.EM_change_selected_objects,
    epoch_manager.EM_epoch_manager_add,
    epoch_manager.EM_epoch_manager_remove,
    epoch_manager.EM_add_to_group,
#     epoch_manager.EM_remove_from_group,
    EMListItem,
    EM_Other_Settings,
    EPOCHListItem,
    EM_Group,
    EM_Object_Id
    )


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    #bpy.types.WindowManager.interface_vars = bpy.props.PointerProperty(type=InterfaceVars)
    bpy.types.Scene.em_list = prop.CollectionProperty(type = EMListItem)
    bpy.types.Scene.em_list_index = prop.IntProperty(name = "Index for my_list", default = 0)
    bpy.types.Scene.epoch_list = prop.CollectionProperty(type = EPOCHListItem)
    bpy.types.Scene.epoch_list_index = prop.IntProperty(name = "Index for epoch_list", default = 0)
    bpy.types.Scene.EM_file = StringProperty(
      name = "EM GraphML file",
      default = "",
      description = "Define the path to the EM GraphML file",
      subtype = 'FILE_PATH'
      )

######################################################################################################
#per epoch manager
##################

    bpy.types.Scene.epoch_managers = CollectionProperty(type=EM_Group)
    bpy.types.Object.em_belong_id = CollectionProperty(type=EM_Object_Id)
    bpy.types.Scene.em_settings = PointerProperty(type=EM_Other_Settings)

    bpy.types.Scene.epoch_managers_index = IntProperty(default=-1)

    bpy.types.VIEW3D_MT_object_specials.append(menu_func)

######################################################################################################


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)

######################################################################################################
#per epoch manager
##################
    del bpy.types.Scene.epoch_managers
    del bpy.types.Object.em_belong_id
    del bpy.types.Scene.em_settings
    del bpy.types.Scene.epoch_managers_index
######################################################################################################