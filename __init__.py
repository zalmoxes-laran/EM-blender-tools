'''
Created by EMANUEL DEMETRESCU 2018-2024
emanuel.demetrescu@cnr.it

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be us eful,
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
    "version": (1, 5, 0),
    "blender": (4, 2, 0),
    "devel_version": "v1.5.0 dev4",  # Aggiunto campo devel_version
    "location": "3D View > Toolbox",
    "warning": "This addon is in dev3 stage.",
    "wiki_url": "",
    "category": "Tools",
    }

def get_bl_info():
    return bl_info

# load and reload submodules
##################################

import math
import bpy  # type: ignore
import bpy.props as prop # type: ignore
from bpy.props import ( # type: ignore
        StringProperty,
        BoolProperty,
        FloatProperty,
        IntProperty,
        PointerProperty,
        CollectionProperty,
        FloatVectorProperty,
        )
        
from bpy.types import (  # type: ignore
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
        EMdb_excel,
        external_modules_install,
        em_statistics,
        server,
        graph2geometry,
        activity_manager,
        populate_lists
        #google_credentials
        )

from .functions import *
from bpy.utils import register_class, unregister_class  # type: ignore

from . import addon_updater_ops

from .external_modules_install import check_external_modules

from .populate_lists import *


# demo bare-bones preferences 
@addon_updater_ops.make_annotations
#@telegram_io.main()

class EMAddonSettings(bpy.types.PropertyGroup):
    preserve_web_url: bpy.props.BoolProperty(
        name="Preserve Web URL",
        description="Preserve web urls (if any) from the GraphML file",
        default=True
    ) # type: ignore

    overwrite_url_with_dosco_filepath: bpy.props.BoolProperty(
        name="Overwrite URL witPh DosCo Filepath",
        description="Retrieve the URL from real DosCo Filepath ignoring the url values stated in the GraphML file",
        default=False
    ) # type: ignore

    dosco_advanced_options: bpy.props.BoolProperty(
        name="Show advanced options ",
        description="Catch more information from DosCo folder loading the GraphML",
        default=False
    ) # type: ignore

class EmPreferences(bpy.types.AddonPreferences):
	bl_idname = __package__
       #bl_idname = __name__

	is_external_module : bpy.props.BoolProperty(
              name="Pandas module (to read xlsx files) is present",
              default=False
              ) # type: ignore

	# addon updater preferences
	auto_check_update : bpy.props.BoolProperty(
		name="Auto-check for Update",
		description="If enabled, auto-check for updates using an interval",
		default=False
		) # type: ignore
      
	updater_intrval_months : bpy.props.IntProperty(
		name='Months',
		description="Number of months between checking for updates",
		default=0,
		min=0
		) # type: ignore
      
	updater_intrval_days : bpy.props.IntProperty(
		name='Days',
		description="Number of days between checking for updates",
		default=7,
		min=0,
		max=31
		) # type: ignore
      
	updater_intrval_hours : bpy.props.IntProperty(
		name='Hours',
		description="Number of hours between checking for updates",
		default=0,
		min=0,
		max=23
		) # type: ignore
      
	updater_intrval_minutes : bpy.props.IntProperty(
		name='Minutes',
		description="Number of minutes between checking for updates",
		default=0,
		min=0,
		max=59
		) # type: ignore

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

              layout = self.layout
              layout.label(text="xlsx setup")
              #layout.prop(self, "filepath", text="Credentials path:")
              if self.is_external_module:
                     layout.label(text="Pandas module (to read xlsx files) is correctly installed")
              else:
                     layout.label(text="Pandas module is missing: install with the button below")
                     row = layout.row()
                     #row.label(text="")
              row = layout.row()              
              op = row.operator("install_em_missing.modules", icon="STICKY_UVS_DISABLE", text='Install pandas modules (waiting some minutes is normal)')
              op.is_install = True
              op.list_modules_to_install = "EMdb_xlsx"
              row = layout.row()
              op = row.operator("install_em_missing.modules", icon="STICKY_UVS_DISABLE", text='Uninstall pandas modules (waiting some minutes is normal)')
              op.is_install = False
              op.list_modules_to_install = "EMdb_xlsx"
              row = layout.row()              
              op = row.operator("install_em_missing.modules", icon="STICKY_UVS_DISABLE", text='Install NetworkX modules (waiting some minutes is normal)')
              op.is_install = True
              op.list_modules_to_install = "NetworkX"
              row = layout.row()
              op = row.operator("install_em_missing.modules", icon="STICKY_UVS_DISABLE", text='Uninstall NetworkX modules (waiting some minutes is normal)')
              op.is_install = False
              op.list_modules_to_install = "NetworkX"


class EDGESListItem(bpy.types.PropertyGroup):
       """ Group of properties an item in the list """

       id_node: prop.StringProperty(
              name="id",
              description="A description for this item",
              default="Empty") # type: ignore

       source: prop.StringProperty(
              name="source",
              description="A description for this item",
              default="Empty") # type: ignore

       target: prop.StringProperty(
              name="target",
              description="A description for this item",
              default="Empty") # type: ignore

       edge_type: prop.StringProperty(
              name="type",
              description="A description for this item",
              default="Empt") # type: ignore

class EPOCHListItem(bpy.types.PropertyGroup):
       """ Group of properties representing an item in the list """
       name: prop.StringProperty(
              name="Name",
              description="A name for this item",
              default="Untitled") # type: ignore

       id: prop.StringProperty(
              name="id",
              description="A description for this item",
              default="Empty") # type: ignore

       min_y: prop.FloatProperty(
              name="code for icon",
              description="",
              default=0.0) # type: ignore

       max_y: prop.FloatProperty(
              name="code for icon",
              description="",
              default=0.0) # type: ignore

       height: prop.FloatProperty(
              name="height of epoch row",
              description="",
              default=0.0) # type: ignore
       
       epoch_color: prop.StringProperty(
              name="color of epoch row",
              description="",
              default="Empty")  # type: ignore   

       start_time: prop.FloatProperty(
              name="Start time",
              description="",
              default=0.0) # type: ignore

       end_time:  prop.FloatProperty(
              name="End time",
              description="",
              default=0.0) # type: ignore 

       use_toggle: BoolProperty(name="", default=True) # type: ignore
       is_locked: BoolProperty(name="", default=True) # type: ignore
       is_selected: BoolProperty(name="", default=False) # type: ignore
       epoch_soloing: BoolProperty(name="", default=False) # type: ignore
       rm_models: BoolProperty(name="", default=False) # type: ignore
       reconstruction_on: BoolProperty(name="", default=False) # type: ignore
       #line_art: BoolProperty(name="", default=False) 
       
       unique_id: StringProperty(default="") # type: ignore

       epoch_RGB_color: FloatVectorProperty(
              name="epoch_color",
              subtype="COLOR",
              size=3,
              min=0.0,
              max=1.0,
              default=(0.5, 0.5, 0.5)
       ) # type: ignore

       wire_color: FloatVectorProperty(
              name="wire",
              subtype='COLOR',
              default=(0.2, 0.2, 0.2),
              min=0.0, max=1.0,
              description="wire color of the group"
       ) # type: ignore

class EM_Other_Settings(PropertyGroup):
       contex = bpy.context
       select_all_layers: BoolProperty(name="Select Visible Layers", default=True) # type: ignore
       unlock_obj: BoolProperty(name="Unlock Objects", default=False) # type: ignore
       unhide_obj: BoolProperty(name="Unhide Objects", default=True) # type: ignore
       em_proxy_sync: BoolProperty(name="Selecting a proxy you select the corresponding EM", default=False, update = functions.sync_Switch_em) # type: ignore
       em_proxy_sync2: BoolProperty(name="Selecting an EM you select the corresponding proxy", default=False, update = functions.sync_Switch_proxy) # type: ignore
       em_proxy_sync2_zoom: BoolProperty(name="Option to zoom to proxy", default=False, update = functions.sync_Switch_proxy) # type: ignore
       soloing_mode: BoolProperty(name="Soloing mode", default=False) # type: ignore

#######################################################################################################################

class EMListItem(bpy.types.PropertyGroup):
    """ Group of properties representing an item in the list """

    name: prop.StringProperty(
           name="Name",
           description="A name for this item",
           default="Untitled") # type: ignore

    description: prop.StringProperty(
           name="Description",
           description="A description for this item",
           default="Empty") # type: ignore

    icon: prop.StringProperty(
           name="code for icon",
           description="",
           default="RESTRICT_INSTANCED_ON") # type: ignore

    icon_db: prop.StringProperty(
           name="code for icon db",
           description="",
           default="DECORATE_ANIMATE") # nel caso di punto pieno sarà 'DECORATE_KEYFRAME'  # type: ignore

    url: prop.StringProperty(
           name="url",
           description="An url behind this item",
           default="Empty") # type: ignore

    shape: prop.StringProperty(
           name="shape",
           description="The shape of this item",
           default="Empty") # type: ignore

    y_pos: prop.FloatProperty(
           name="y_pos",
           description="The y_pos of this item",
           default=0.0) # type: ignore

    epoch: prop.StringProperty(
           name="code for epoch",
           description="",
           default="Empty") # type: ignore

    id_node: prop.StringProperty(
           name="id node",
           description="",
           default="Empty") # type: ignore

class EMreusedUS(bpy.types.PropertyGroup):
    """ Group of properties representing an item in the list """

    epoch: prop.StringProperty(
           name="epoch",
           description="Epoch",
           default="Untitled") # type: ignore

    em_element: prop.StringProperty(
           name="em_element",
           description="",
           default="Empty") # type: ignore

class EMviqListErrors(bpy.types.PropertyGroup):
    """ Group of properties representing list of errors in exporting the RM """

    name: prop.StringProperty( 
           name="Object",
           description="The object with an error",
           default="Empty") # type: ignore

    description: prop.StringProperty(
           name="Description",
           description="A description of the error",
           default="Empty") # type: ignore

    material: prop.StringProperty(
           name="material",
           description="",
           default="Empty") # type: ignore

    texture_type: prop.StringProperty(
           name="texture_type",
           description="",
           default="Empty") # type: ignore

class EMListParadata(bpy.types.PropertyGroup):
    """ Group of properties representing a paradata element in the list """

    name: prop.StringProperty(
           name="Name",
           description="A name for this item",
           default="Untitled") # type: ignore

    description: prop.StringProperty(
           name="Description",
           description="A description for this item",
           default="Empty") # type: ignore

    icon: prop.StringProperty(
           name="code for icon",
           description="",
           default="RESTRICT_INSTANCED_ON") # type: ignore

    icon_url: prop.StringProperty(
           name="code for icon url",
           description="",
           default="CHECKBOX_DEHLT") # type: ignore

    url: prop.StringProperty(
           name="url",
           description="An url behind this item",
           default="Empty") # type: ignore

    id_node: prop.StringProperty(
           name="id_node",
           description="The id node of this item",
           default="Empty") # type: ignore

class EM_epochs_belonging_ob(bpy.types.PropertyGroup):

    epoch: prop.StringProperty(
           name="epoch",
           description="Epoch",
           default="Untitled") # type: ignore

class ExportVars(bpy.types.PropertyGroup):
       format_file : bpy.props.EnumProperty(
              items=[
              ('gltf','gltf','gltf','', 0),
              ('obj','obj','obj','', 1),
              ('fbx','fbx','fbx','', 2),
              ],
              default='gltf'
       ) # type: ignore

class ExportTablesVars(bpy.types.PropertyGroup):
       table_type : bpy.props.EnumProperty(
              items=[
              ('US/USV','US/USV','US/USV','', 0),
              ('Sources','Sources','Sources','', 1),
              ('Extractors','Extractors','Extractors','', 2),
              ],
              default='US/USV'
    ) # type: ignore

class EMUSItem(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(name="Name", default="") # type: ignore
    description: bpy.props.StringProperty(name="Description", default="") # type: ignore
    status: bpy.props.StringProperty(name="Status", default="") # type: ignore
    y_pos: bpy.props.StringProperty(name="y_pos", default="") # type: ignore


def update_selected_epoch_us_list(self, context):
       #if context.scene.em_graph:
       bpy.ops.epoch_manager.update_us_list()

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
    UI.VIEW3D_PT_USListPanel,
    UI.EM_UL_US_List,
    paradata_manager.EM_files_opener,
    functions.OBJECT_OT_CenterMass,
    functions.OBJECT_OT_labelonoff,
    EMAddonSettings,
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
    EMUSItem
    )

def register():

       bpy.types.Scene.em_graph = None

       for cls in classes:
              bpy.utils.register_class(cls)

       em_setup.register()
       sqlite_io.register()
       visual_manager.register()

       external_modules_install.register()

       addon_updater_ops.register(bl_info)
       
       EMdb_excel.register()

       EM_list.register()

       export_manager.register()

       em_statistics.register()

       epoch_manager.register()

       server.register()

       graph2geometry.register()

       activity_manager.register()

       check_external_modules() 


       bpy.types.Scene.selected_epoch_us_list = bpy.props.CollectionProperty(type=EMUSItem)
       bpy.types.Scene.selected_epoch_us_list_index = bpy.props.IntProperty(name="Index for US list", default=0)

       bpy.types.WindowManager.export_vars = bpy.props.PointerProperty(type = ExportVars)
       bpy.types.WindowManager.export_tables_vars = bpy.props.PointerProperty(type = ExportTablesVars)

       bpy.types.Scene.emviq_error_list = prop.CollectionProperty(type = EMviqListErrors)
       bpy.types.Scene.emviq_error_list_index = prop.IntProperty(name = "Index for my_list", default = 0, update = functions.switch_paradata_lists)

       bpy.types.Scene.em_list = prop.CollectionProperty(type = EMListItem)
       bpy.types.Scene.em_list_index = prop.IntProperty(name = "Index for my_list", default = 0, update = functions.switch_paradata_lists)
       bpy.types.Scene.em_reused = prop.CollectionProperty(type = EMreusedUS)
       bpy.types.Scene.epoch_list = prop.CollectionProperty(type = EPOCHListItem)

       bpy.types.Scene.epoch_list_index = bpy.props.IntProperty(
       name="Index for epoch_list",
       default=0,
       update=update_selected_epoch_us_list
       )

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

       bpy.types.WindowManager.em_addon_settings = bpy.props.PointerProperty(type=EMAddonSettings)
       
######################################################################################################

def unregister():
       del bpy.types.Scene.em_graph 
       addon_updater_ops.unregister(bl_info)
       sqlite_io.unregister()
       visual_manager.unregister()
       em_setup.unregister()
       EMdb_excel.unregister()
       export_manager.unregister()
       em_statistics.unregister()
       EM_list.unregister()
       server.unregister()
       epoch_manager.unregister()
       graph2geometry.unregister()
       activity_manager.unregister()
       for cls in classes:
              try:
                     bpy.utils.unregister_class(cls)
              except RuntimeError:
                     pass

       ######################################################################################################
       #per epoch manager
       ##################
       del bpy.types.Scene.selected_epoch_us_list 
       del bpy.types.Scene.selected_epoch_us_list_index
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
       del bpy.types.WindowManager.em_addon_settings

       
       external_modules_install.unregister()
       #google_credentials.unregister()

######################################################################################################