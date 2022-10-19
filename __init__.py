'''
Copyright (C) 2022 Emanuel Demetrescu

Created by EMANUEL DEMETRESCU 2018-2022
emanuel.demetrescu@cnr.it

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
    "version": (1, 3, 0),
    "blender": (3, 3, 0),
#     "location": "3D View > Toolbox",
    "warning": "This addon is still in development.",
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
        IntProperty,
        PointerProperty,
        CollectionProperty,
        FloatVectorProperty,
        )
        
from bpy.types import (
        PropertyGroup,
        )


from . import (
        UI,
        EM_list,
        epoch_manager,
        functions,
        paradata_manager,
        export_manager,
        visual_tools,
        visual_manager,
        em_setup,
        sqlite_io,
        #external_modules_install,
        #google_credentials
        )

from .functions import *
from bpy.utils import register_class, unregister_class

from . import addon_updater_ops

# demo bare-bones preferences 
@addon_updater_ops.make_annotations
#@telegram_io.main()

class EmPreferences(bpy.types.AddonPreferences):
	bl_idname = __package__

	# addon updater preferences

	auto_check_update : bpy.props.BoolProperty(
		name="Auto-check for Update",
		description="If enabled, auto-check for updates using an interval",
		default=False
		)
	updater_intrval_months : bpy.props.IntProperty(
		name='Months',
		description="Number of months between checking for updates",
		default=0,
		min=0
		)
	updater_intrval_days : bpy.props.IntProperty(
		name='Days',
		description="Number of days between checking for updates",
		default=7,
		min=0,
		max=31
		)
	updater_intrval_hours : bpy.props.IntProperty(
		name='Hours',
		description="Number of hours between checking for updates",
		default=0,
		min=0,
		max=23
		)
	updater_intrval_minutes : bpy.props.IntProperty(
		name='Minutes',
		description="Number of minutes between checking for updates",
		default=0,
		min=0,
		max=59
		)

	def draw(self, context):
		layout = self.layout
		# col = layout.column() # works best if a column, or even just self.layout
		mainrow = layout.row()
		col = mainrow.column()

		# updater draw function
		# could also pass in col as third arg
		addon_updater_ops.update_settings_ui(self, context)

		# Alternate draw function, which is more condensed and can be
		# placed within an existing draw function. Only contains:
		#   1) check for update/update now buttons
		#   2) toggle for auto-check (interval will be equal to what is set above)
		# addon_updater_ops.update_settings_ui_condensed(self, context, col)

		# Adding another column to help show the above condensed ui as one column
		# col = mainrow.column()
		# col.scale_y = 2
		# col.operator("wm.url_open","Open webpage ").url=addon_updater_ops.updater.website

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
       rm_models: BoolProperty(name="", default=False)
       reconstruction_on: BoolProperty(name="", default=False)
       #line_art: BoolProperty(name="", default=False) 
       
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

    icon_db: prop.StringProperty(
           name="code for icon db",
           description="",
           default="DECORATE_ANIMATE") # nel caso di punto pieno sarà 'DECORATE_KEYFRAME'

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

class EMviqListErrors(bpy.types.PropertyGroup):
    """ Group of properties representing list of errors in exporting the RM """

    name: prop.StringProperty( 
           name="Object",
           description="The object with an error",
           default="Empty")

    description: prop.StringProperty(
           name="Description",
           description="A description of the error",
           default="Empty")

    material: prop.StringProperty(
           name="material",
           description="",
           default="Empty")

    texture_type: prop.StringProperty(
           name="texture_type",
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

class EM_epochs_belonging_ob(bpy.types.PropertyGroup):

    epoch: prop.StringProperty(
           name="epoch",
           description="Epoch",
           default="Untitled")

class ExportVars(bpy.types.PropertyGroup):
       format_file : bpy.props.EnumProperty(
              items=[
              ('gltf','gltf','gltf','', 0),
              ('obj','obj','obj','', 1),
              ('fbx','fbx','fbx','', 2),
              ],
              default='gltf'
    )

class ExportTablesVars(bpy.types.PropertyGroup):
       table_type : bpy.props.EnumProperty(
              items=[
              ('US/USV','US/USV','US/USV','', 0),
              ('Sources','Sources','Sources','', 1),
              ('Extractors','Extractors','Extractors','', 2),
              ],
              default='US/USV'
    )

# register
##################################

classes = (
    UI.VIEW3D_PT_ToolsPanel,
    UI.VIEW3D_PT_BasePanel,
    UI.VIEW3D_PT_EMdbPanel,
    UI.EM_UL_named_epoch_managers,
    UI.VIEW3D_PT_ParadataPanel,
    UI.EM_UL_properties_managers,
    UI.EM_UL_sources_managers,
    UI.EM_UL_extractors_managers,
    UI.EM_UL_combiners_managers,
    UI.EM_UL_belongob,
    UI.VIEW3D_PT_ExportPanel,
    UI.ER_UL_List,
    EM_list.EM_listitem_OT_to3D,
    EM_list.EM_update_icon_list,
    EM_list.EM_select_from_list_item,
    EM_list.EM_import_GraphML,
    EM_list.EM_select_list_item,
    EM_list.EM_not_in_matrix,
    epoch_manager.EM_UL_List,
    epoch_manager.EM_toggle_reconstruction,
    epoch_manager.EM_toggle_select,
    epoch_manager.EM_toggle_visibility,
    epoch_manager.EM_set_EM_materials,
    epoch_manager.EM_set_epoch_materials,
    epoch_manager.EM_change_selected_objects,
    epoch_manager.EM_toggle_selectable,
    epoch_manager.EM_toggle_soloing,
    epoch_manager.EM_add_remove_epoch_models,
    epoch_manager.EM_select_epoch_rm,
    export_manager.EM_export,
    export_manager.ExportuussData,
    export_manager.OBJECT_OT_ExportUUSS,
    paradata_manager.EM_files_opener,
    functions.OBJECT_OT_CenterMass,
    functions.OBJECT_OT_labelonoff,
    EMListItem,
    EM_Other_Settings,
    EPOCHListItem,
    EMreusedUS,
    EMListParadata,
    EDGESListItem,
    EM_epochs_belonging_ob,
    ExportVars,
    ExportTablesVars,
    EMviqListErrors,
    EmPreferences,
    visual_tools.EM_label_creation,
    em_create_collection,
    )

def register():

       sqlite_io.register()

       em_setup.register()

       visual_manager.register()

       #external_modules_install.register()

       addon_updater_ops.register(bl_info)

       #google_credentials.register()

       for cls in classes:
              bpy.utils.register_class(cls)
       
       bpy.types.WindowManager.export_vars = bpy.props.PointerProperty(type = ExportVars)
       bpy.types.WindowManager.export_tables_vars = bpy.props.PointerProperty(type = ExportTablesVars)

       bpy.types.Scene.emviq_error_list = prop.CollectionProperty(type = EMviqListErrors)
       bpy.types.Scene.emviq_error_list_index = prop.IntProperty(name = "Index for my_list", default = 0, update = functions.switch_paradata_lists)

       bpy.types.Scene.em_list = prop.CollectionProperty(type = EMListItem)
       bpy.types.Scene.em_list_index = prop.IntProperty(name = "Index for my_list", default = 0, update = functions.switch_paradata_lists)
       bpy.types.Scene.em_reused = prop.CollectionProperty(type = EMreusedUS)
       bpy.types.Scene.epoch_list = prop.CollectionProperty(type = EPOCHListItem)
       bpy.types.Scene.epoch_list_index = prop.IntProperty(name = "Index for epoch_list", default = 0)

       bpy.types.Scene.edges_list = prop.CollectionProperty(type = EDGESListItem)

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

       bpy.types.Scene.enable_image_compression = BoolProperty(name="Tex compression", description = "Use compression settings for textures. If disabled, original images (size and compression) will be used.",default=True)

       bpy.types.Scene.paradata_streaming_mode = BoolProperty(name="Paradata streaming mode", description = "Enable/disable tables streaming mode",default=True, update = functions.switch_paradata_lists)
       bpy.types.Scene.prop_paradata_streaming_mode = BoolProperty(name="Properties Paradata streaming mode", description = "Enable/disable property table streaming mode",default=True, update = functions.stream_properties)
       bpy.types.Scene.comb_paradata_streaming_mode = BoolProperty(name="Combiners Paradata streaming mode", description = "Enable/disable combiner table streaming mode",default=True, update = functions.stream_combiners)
       bpy.types.Scene.extr_paradata_streaming_mode = BoolProperty(name="Extractors Paradata streaming mode", description = "Enable/disable extractor table streaming mode",default=True, update = functions.stream_extractors)

       bpy.types.Scene.proxy_shader_mode = BoolProperty(name="Proxy shader mode", description = "Enable additive shader for proxies",default=True, update = functions.proxy_shader_mode_function)
       bpy.types.Scene.EM_file = StringProperty(
              name = "EM GraphML file",
              default = "",
              description = "Define the path to the EM GraphML file",
              subtype = 'FILE_PATH'
       )

       bpy.types.Scene.EMviq_folder = StringProperty(
           name="EMviq collection export folder",
           default="",
           description="Define the path to export the EMviq collection",
           subtype='DIR_PATH'
       )

       bpy.types.Scene.EMviq_scene_folder = StringProperty(
           name="EMviq scene export folder",
           default="",
           description="Define the path to export the EMviq scene",
           subtype='DIR_PATH'
       )

       bpy.types.Scene.EMviq_project_name = StringProperty(
           name="EMviq project name",
           default="",
           description="Define the name of the EMviq project"#,
           #subtype='DIR_PATH'
       )

       bpy.types.Scene.EMviq_user_name = StringProperty(
           name="EMviq user name",
           default="",
           description="Define the name of the EMviq user"#,
           #subtype='DIR_PATH'
       )

       bpy.types.Scene.EMviq_user_password = StringProperty(
           name="EMviq user name",
           default="",
           description="Define the name of the EMviq user",
           subtype='PASSWORD'
       )

       bpy.types.Scene.ATON_path = StringProperty(
           name="ATON path",
           default="",
           description="Define the path to the ATON framework (root folder)",
           subtype='DIR_PATH'
       )

       bpy.types.Scene.EMviq_model_author_name = StringProperty(
           name="Name of the author(s) of the models",
           default="",
           description="Define the nameof the author(s) of the models"#,
           #subtype='DIR_PATH'
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

       bpy.types.Object.EM_ep_belong_ob = CollectionProperty(type=EM_epochs_belonging_ob)
       bpy.types.Object.EM_ep_belong_ob_index = IntProperty()

       bpy.types.Scene.EM_gltf_export_quality = IntProperty(
       name="export quality",
       default=100,
       description="Define the quality of the output images. 100 is maximum quality but at a cost of bigger weight (no optimization); 80 is compressed with near lossless quality but still hight in weight; 60 is a good middle way; 40 is hardly optimized with some evident loss in quality (sometimes it can work).",
       )

       bpy.types.Scene.EM_gltf_export_maxres = IntProperty(
       name="export max resolution",
       default=4096,
       description="Define the maximum resolution of the bigger side (it depends if it is a squared landscape or portrait image) of the output images",
       )


       

######################################################################################################

def unregister():

       addon_updater_ops.unregister(bl_info)
       sqlite_io.unregister()
       visual_manager.unregister()
       em_setup.unregister()

       for cls in classes:
              try:
                     bpy.utils.unregister_class(cls)
              except RuntimeError:
                     pass

       ######################################################################################################
       #per epoch manager
       ##################
       del bpy.types.WindowManager.export_vars
       del bpy.types.Scene.emviq_error_list
       del bpy.types.Scene.emviq_error_list_index
       del bpy.types.Scene.em_settings
       del bpy.types.Scene.em_list
       del bpy.types.Scene.em_list_index
       del bpy.types.Scene.em_reused
       del bpy.types.Scene.epoch_list
       del bpy.types.Scene.epoch_list_index
       del bpy.types.Scene.proxy_shader_mode
       del bpy.types.Scene.EM_file
       del bpy.types.Scene.EMviq_folder
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
       del bpy.types.Object.EM_ep_belong_ob
       del bpy.types.Object.EM_ep_belong_ob_index

       del bpy.types.Scene.EMviq_user_name
       del bpy.types.Scene.EMviq_project_name
       del bpy.types.Scene.EMviq_scene_folder
       del bpy.types.Scene.EMviq_model_author_name
       del bpy.types.Scene.ATON_path
       del bpy.types.Scene.EM_gltf_export_maxres
       del bpy.types.Scene.EM_gltf_export_quality
       del bpy.types.Scene.enable_image_compression
       

       
       #external_modules_install.unregister()
       #google_credentials.unregister()

######################################################################################################