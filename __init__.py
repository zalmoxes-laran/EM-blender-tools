'''
Created by EMANUEL DEMETRESCU 2018-2025
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
    "version": (1, 5, 0),  # This is fine as a tuple
    "blender": (4, 0, 0),  # Make sure this matches the minimum Blender version you support
    "location": "3D View > Toolbox",
    "warning": "dev18",
    "wiki_url": "",
    "category": "Tools",
}

def get_bl_info():
    return bl_info

# load basic modules required for all operations
##################################
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


# Funzione per configurare il percorso corretto per l'importazione dei moduli
def setup_module_paths():
    """
    Configura i percorsi per l'importazione corretta dei moduli
    Questo permette di importare da:
    1. La directory lib dell'addon (se esiste)
    2. I site-packages di Blender
    3. I percorsi standard di Python
    """
    import os
    import sys
    import site
    
    # Determina la directory dell'addon
    addon_dir = os.path.dirname(os.path.realpath(__file__))
    
    # Aggiungi la directory lib dell'addon al path se esiste
    lib_dir = os.path.join(addon_dir, 'lib')
    if os.path.exists(lib_dir) and lib_dir not in sys.path:
        sys.path.insert(0, lib_dir)
        print(f"Added addon lib directory to path: {lib_dir}")
        return True
    return False

# Esegui setup_module_paths all'avvio
module_paths_setup = setup_module_paths()

# Inizializza la variabile globale per tracciare lo stato delle dipendenze
DEPENDENCIES_INSTALLED = False

def check_dependencies():
    """Verifica se le dipendenze esterne sono disponibili"""
    try:
        import pandas
        import networkx 
        return True
    except ImportError as e:
        print(f"Missing dependencies: {e}")
        return False

# Verifica le dipendenze durante il caricamento
DEPENDENCIES_INSTALLED = check_dependencies()

from . import dependecy_panel, us_list_per_epoch

class EmPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__
       #bl_idname = __name__

    is_external_module : bpy.props.BoolProperty(
              name="Pandas module (to read xlsx files) is present",
              default=False
              ) # type: ignore

    def draw(self, context):
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

# These class definitions need to be available even when dependencies are missing
# to prevent errors when dependencies are installed and Blender is restarted
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
    em_proxy_sync: BoolProperty(name="Selecting a proxy you select the corresponding EM", default=False) # type: ignore
    em_proxy_sync2: BoolProperty(name="Selecting an EM you select the corresponding proxy", default=False) # type: ignore
    em_proxy_sync2_zoom: BoolProperty(name="Option to zoom to proxy", default=False) # type: ignore
    soloing_mode: BoolProperty(name="Soloing mode", default=False) # type: ignore


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
    
    border_style: prop.StringProperty(
           name="border style",
           description="",
           default="Empty") # type: ignore    

    fill_color: prop.StringProperty(
           name="fill color",
           description="",
           default="Empty") # type: ignore
           
    is_visible: prop.BoolProperty(
           name="Visible",
           description="Whether this item is visible in the viewport",
           default=True) # type: ignore

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

       heriverse_expanded: BoolProperty(
              name="Show Heriverse export options",
              description="Expand/Collapse Heriverse export options",
              default=False
       ) # type: ignore


       emviq_expanded: BoolProperty(
              name="Show Emviq export options",
              description="Expand/Collapse Emviq export options",
              default=False
       ) # type: ignore

       heriverse_project_name: StringProperty(
              name="Project Name", 
              description="Name of the Heriverse project",
              default=""
       ) # type: ignore

       heriverse_export_path: StringProperty(
              name="Export Path",
              description="Path where to export Heriverse project",
              subtype='DIR_PATH'
       ) # type: ignore

       heriverse_export_all_graphs: BoolProperty(
              name="Export all graphs",
              description="Export all loaded graphs instead of just the selected one",
              default=False
       ) # type: ignore

       heriverse_overwrite_json: BoolProperty(
              name="Overwrite JSON",
              description="Overwrite existing JSON file",
              default=True
       ) # type: ignore

       heriverse_export_dosco: BoolProperty(
              name="Export DosCo files",
              description="Copy DosCo files to output",
              default=True
       ) # type: ignore

       heriverse_export_proxies: BoolProperty(
              name="Export proxies",
              description="Export proxy models",
              default=True
       ) # type: ignore

       heriverse_export_rm: BoolProperty(
              name="Export RM",
              description="Export representation models",
              default=True
       ) # type: ignore

       heriverse_create_zip: BoolProperty(
              name="Create ZIP archive",
              description="Create a ZIP archive of the exported project",
              default=True
       ) # type: ignore

       heriverse_advanced_options: BoolProperty(
       name="Show advanced options",
       description="Show advanced export options like compression settings",
       default=False
       ) # type: ignore

       heriverse_use_draco: BoolProperty(
       name="Use Draco compression",
       description="Enable Draco mesh compression for smaller file size",
       default=True
       ) # type: ignore

       heriverse_draco_level: IntProperty(
       name="Compression Level",
       description="Draco compression level (higher = smaller files but slower)",
       min=1,
       max=10,
       default=6
       ) # type: ignore

       heriverse_separate_textures: BoolProperty(
       name="Export textures separately",
       description="Export textures as separate files instead of embedding",
       default=True
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

class em_create_collection(bpy.types.Operator):
    bl_idname = "create.collection"
    bl_label = "Create Collection"
    bl_description = "Create Collection"
    bl_options = {'REGISTER', 'UNDO'}

    def create_collection(target_collection):
        context = bpy.context
        if bpy.data.collections.get(target_collection) is None:
            currentCol = bpy.context.blend_data.collections.new(name= target_collection)
            bpy.context.scene.collection.children.link(currentCol)
        else:
            currentCol = bpy.data.collections.get(target_collection)
        return currentCol

# Basic classes that need to be registered regardless of dependencies
base_classes = [
    EmPreferences,
    EMAddonSettings,
    EDGESListItem,
    EPOCHListItem,
    EM_Other_Settings,
    EMListItem,
    EMreusedUS,
    EMviqListErrors,
    EMListParadata,
    EM_epochs_belonging_ob,
    ExportVars,
    ExportTablesVars,
    EMUSItem,
    em_create_collection
]

def register_full_addon():
    """Register full addon functionality when dependencies are available"""
    print("EM Tools: Registering full addon functionality")
    
    try:
        # Import required modules
        from . import (
            EM_list,
            epoch_manager,
            functions,
            paradata_manager,
            export_manager,
            visual_tools,
            visual_manager,
            em_setup,
            EMdb_excel,
            external_modules_install,
            em_statistics,
            server,
            graph2geometry,
            activity_manager,
            rm_manager,
            us_list_per_epoch
        )

        from .import_operators import importer_graphml
        from .export_operators import exporter_heriverse
        from .import_operators import import_EMdb
        # Import modules without wildcard imports
        from . import populate_lists
        from .s3Dgraphy.utils.utils import get_material_color
        from .operators import graphml_converter

        # Create a set to keep track of registered classes to prevent duplicates
        registered_classes = set()

        # Full classes list for addon
        classes = (
            functions.OBJECT_OT_CenterMass,
            functions.OBJECT_OT_labelonoff,
            visual_tools.EM_label_creation,
        )

        # Register remaining classes - with duplicate prevention
        for cls in classes:
            cls_name = cls.__name__
            if cls_name not in registered_classes:
                try:
                    bpy.utils.register_class(cls)
                    registered_classes.add(cls_name)
                except ValueError as e:
                    print(f"Warning: Class '{cls_name}' already registered: {e}")



        # Initialize graph property
        bpy.types.Scene.em_graph = None

        # Register properties
        bpy.types.Scene.selected_epoch_us_list = bpy.props.CollectionProperty(type=EMUSItem)
        bpy.types.Scene.selected_epoch_us_list_index = bpy.props.IntProperty(
            name="Index for US list", 
            default=0,
            update=lambda self, context: bpy.ops.epoch_manager.update_us_list()
        )

        bpy.types.WindowManager.export_vars = bpy.props.PointerProperty(type=ExportVars)
        bpy.types.WindowManager.export_tables_vars = bpy.props.PointerProperty(type=ExportTablesVars)

        bpy.types.Scene.emviq_error_list = prop.CollectionProperty(type=EMviqListErrors)
        bpy.types.Scene.emviq_error_list_index = prop.IntProperty(
            name="Index for my_list", 
            default=0, 
            update=functions.switch_paradata_lists
        )

        bpy.types.Scene.em_list = prop.CollectionProperty(type=EMListItem)
        bpy.types.Scene.em_list_index = prop.IntProperty(
            name="Index for my_list", 
            default=0, 
            update=functions.switch_paradata_lists
        )
        bpy.types.Scene.em_reused = prop.CollectionProperty(type=EMreusedUS)
        bpy.types.Scene.epoch_list = prop.CollectionProperty(type=EPOCHListItem)

        bpy.types.Scene.epoch_list_index = bpy.props.IntProperty(
            name="Index for epoch_list",
            default=0,
            update=lambda self, context: bpy.ops.epoch_manager.update_us_list()
        )

        bpy.types.Scene.edges_list = prop.CollectionProperty(type=EDGESListItem)

        bpy.types.Scene.em_sources_list = prop.CollectionProperty(type=EMListParadata)
        bpy.types.Scene.em_sources_list_index = prop.IntProperty(name="Index for sources list", default=0)
        bpy.types.Scene.em_properties_list = prop.CollectionProperty(type=EMListParadata)
        bpy.types.Scene.em_properties_list_index = prop.IntProperty(name="Index for properties list", default=0)
        bpy.types.Scene.em_extractors_list = prop.CollectionProperty(type=EMListParadata)
        bpy.types.Scene.em_extractors_list_index = prop.IntProperty(name="Index for extractors list", default=0)
        bpy.types.Scene.em_combiners_list = prop.CollectionProperty(type=EMListParadata)
        bpy.types.Scene.em_combiners_list_index = prop.IntProperty(name="Index for combiners list", default=0)

        bpy.types.Scene.em_v_sources_list = prop.CollectionProperty(type=EMListParadata)
        bpy.types.Scene.em_v_sources_list_index = prop.IntProperty(name="Index for sources list", default=0)
        bpy.types.Scene.em_v_properties_list = prop.CollectionProperty(type=EMListParadata)
        bpy.types.Scene.em_v_properties_list_index = prop.IntProperty(
            name="Index for properties list", 
            default=0, 
            update=functions.stream_properties
        )
        bpy.types.Scene.em_v_extractors_list = prop.CollectionProperty(type=EMListParadata)
        bpy.types.Scene.em_v_extractors_list_index = prop.IntProperty(
            name="Index for extractors list", 
            default=0, 
            update=functions.stream_extractors
        )
        bpy.types.Scene.em_v_combiners_list = prop.CollectionProperty(type=EMListParadata)
        bpy.types.Scene.em_v_combiners_list_index = prop.IntProperty(
            name="Index for combiners list", 
            default=0, 
            update=functions.stream_combiners
        )

        bpy.types.Scene.paradata_streaming_mode = BoolProperty(
            name="Paradata streaming mode", 
            description="Enable/disable tables streaming mode",
            default=True, 
            update=functions.switch_paradata_lists
        )
        bpy.types.Scene.prop_paradata_streaming_mode = BoolProperty(
            name="Properties Paradata streaming mode",
            description="Enable/disable property table streaming mode",
            default=True, 
            update=functions.stream_properties
        )
        bpy.types.Scene.comb_paradata_streaming_mode = BoolProperty(
            name="Combiners Paradata streaming mode",
            description="Enable/disable combiner table streaming mode",
            default=True, 
            update=functions.stream_combiners
        )
        bpy.types.Scene.extr_paradata_streaming_mode = BoolProperty(
            name="Extractors Paradata streaming mode",
            description="Enable/disable extractor table streaming mode",
            default=True, 
            update=functions.stream_extractors
        )

        bpy.types.Scene.proxy_shader_mode = BoolProperty(
            name="Proxy shader mode",
            description="Enable additive shader for proxies",
            default=True, 
            update=functions.proxy_shader_mode_function
        )
        bpy.types.Scene.EM_file = StringProperty(
            name="EM GraphML file",
            default="",
            description="Define the path to the EM GraphML file",
            subtype='FILE_PATH'
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
            description="Define the name of the EMviq project"
        )

        bpy.types.Scene.EMviq_user_name = StringProperty(
            name="EMviq user name",
            default="",
            description="Define the name of the EMviq user"
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
            description="Define the nameof the author(s) of the models"
        )

        bpy.types.Scene.em_settings = PointerProperty(type=EM_Other_Settings)
        #bpy.types.Scene.rm_settings = PointerProperty(type=EM_Other_Settings)
        bpy.types.Scene.proxy_display_mode = StringProperty(
            name="Proxy display mode",
            default="select",
            description="Proxy current display mode"
        )
        bpy.types.Scene.proxy_blend_mode = StringProperty(
            name="Proxy blend mode",
            default="BLEND",
            description="EM proxy blend mode for current display mode"
        )
        bpy.types.Scene.proxy_display_alpha = FloatProperty(
            name="alpha",
            description="The alphavalue for proxies",
            min=0,
            max=1,
            default=0.5,
            update=functions.update_display_mode
        )

        bpy.types.VIEW3D_MT_mesh_add.append(functions.menu_func)

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

        if not hasattr(bpy.types.WindowManager, 'em_addon_settings'):
            bpy.types.WindowManager.em_addon_settings = bpy.props.PointerProperty(type=EMAddonSettings)


        # Register modules
        em_setup.register()
        visual_manager.register()
        external_modules_install.register()
        EMdb_excel.register()
        activity_manager.register()
        EM_list.register()
        
        epoch_manager.register()
        us_list_per_epoch.register()
        paradata_manager.register()
        rm_manager.register()
        export_manager.register()
        em_statistics.register()
        server.register()
        graph2geometry.register()
        importer_graphml.register()
        exporter_heriverse.register()
        import_EMdb.register()
        graphml_converter.register()

        # Execute external modules check
        from .external_modules_install import check_external_modules
        check_external_modules()

        print("EM Tools: Full addon registration complete")
        return True
        
    except Exception as e:
        import traceback
        print(f"EM Tools: Error during full addon registration: {e}")
        traceback.print_exc()
        return False

def register():
    """Main registration function"""
    
    # Register base classes
    for cls in base_classes:
        bpy.utils.register_class(cls)

    # Check for dependencies
    global DEPENDENCIES_INSTALLED
    DEPENDENCIES_INSTALLED = check_dependencies()
    
    if DEPENDENCIES_INSTALLED:
        # Register full addon functionality
        register_full_addon()
    else:
        # Register only dependency panel
        print("EM Tools: Missing dependencies. Registering only dependency panel.")
        dependecy_panel.register()

def unregister():
    """Main unregistration function"""
    global DEPENDENCIES_INSTALLED
    
    if DEPENDENCIES_INSTALLED:
        try:
            # Import functions module here to ensure it's available during unregistration
            from . import functions
            
            # Unregister all components in reverse order
            if hasattr(bpy.types.WindowManager, 'em_addon_settings'):
                del bpy.types.WindowManager.em_addon_settings
            del bpy.types.Scene.EM_gltf_export_maxres
            del bpy.types.Scene.EM_gltf_export_quality
            del bpy.types.Object.EM_ep_belong_ob_index
            del bpy.types.Object.EM_ep_belong_ob
            
            bpy.types.VIEW3D_MT_mesh_add.remove(functions.menu_func)
            
            del bpy.types.Scene.proxy_display_alpha
            del bpy.types.Scene.proxy_blend_mode
            del bpy.types.Scene.proxy_display_mode
            #del bpy.types.Scene.rm_settings
            del bpy.types.Scene.em_settings
            
            del bpy.types.Scene.EMviq_model_author_name
            del bpy.types.Scene.ATON_path
            del bpy.types.Scene.EMviq_user_password
            del bpy.types.Scene.EMviq_user_name
            del bpy.types.Scene.EMviq_project_name
            del bpy.types.Scene.EMviq_scene_folder
            del bpy.types.Scene.EMviq_folder
            del bpy.types.Scene.EM_file
            del bpy.types.Scene.proxy_shader_mode
            
            del bpy.types.Scene.extr_paradata_streaming_mode
            del bpy.types.Scene.comb_paradata_streaming_mode
            del bpy.types.Scene.prop_paradata_streaming_mode
            del bpy.types.Scene.paradata_streaming_mode
            
            del bpy.types.Scene.em_v_combiners_list_index
            del bpy.types.Scene.em_v_combiners_list
            del bpy.types.Scene.em_v_extractors_list_index
            del bpy.types.Scene.em_v_extractors_list
            del bpy.types.Scene.em_v_properties_list_index
            del bpy.types.Scene.em_v_properties_list
            del bpy.types.Scene.em_v_sources_list_index
            del bpy.types.Scene.em_v_sources_list
            
            del bpy.types.Scene.em_combiners_list_index
            del bpy.types.Scene.em_combiners_list
            del bpy.types.Scene.em_extractors_list_index
            del bpy.types.Scene.em_extractors_list
            del bpy.types.Scene.em_properties_list_index
            del bpy.types.Scene.em_properties_list
            del bpy.types.Scene.em_sources_list_index
            del bpy.types.Scene.em_sources_list
            
            del bpy.types.Scene.edges_list
            del bpy.types.Scene.epoch_list_index
            del bpy.types.Scene.epoch_list
            del bpy.types.Scene.em_reused
            del bpy.types.Scene.em_list_index
            del bpy.types.Scene.em_list
            del bpy.types.Scene.emviq_error_list_index
            del bpy.types.Scene.emviq_error_list
            
            del bpy.types.WindowManager.export_tables_vars
            del bpy.types.WindowManager.export_vars
            
            del bpy.types.Scene.selected_epoch_us_list_index
            del bpy.types.Scene.selected_epoch_us_list
            
            # Unregister modules
            from . import (
                activity_manager,
                graph2geometry,
                server,
                epoch_manager,
                em_statistics,
                export_manager,
                EM_list,
                EMdb_excel,
                external_modules_install,
                visual_manager,
                em_setup,
                rm_manager,
                paradata_manager
            )
            
            from .export_operators import exporter_heriverse
            from .import_operators import importer_graphml, import_EMdb 
            from .operators import graphml_converter

            graphml_converter.unregister()
            import_EMdb.unregister()
            exporter_heriverse.unregister()
            importer_graphml.unregister()
            activity_manager.unregister()
            graph2geometry.unregister()
            server.unregister()
            rm_manager.unregister()
            us_list_per_epoch.unregister()
            paradata_manager.unregister()
            epoch_manager.unregister()
            em_statistics.unregister()
            export_manager.unregister()
            EM_list.unregister()
            EMdb_excel.unregister()
            external_modules_install.unregister()
            visual_manager.unregister()
            em_setup.unregister()
            
            # Unregister UI classes
            from . import paradata_manager, visual_tools
            
            classes = (
                visual_tools.EM_label_creation,
                functions.OBJECT_OT_labelonoff,
                functions.OBJECT_OT_CenterMass,
                paradata_manager.EM_files_opener,
            )
            
            for cls in reversed(classes):
                try:
                    bpy.utils.unregister_class(cls)
                except Exception:
                    pass
            
            del bpy.types.Scene.em_graph
            
        except Exception as e:
            import traceback
            print(f"EM Tools: Error during full addon unregistration: {e}")
            traceback.print_exc()
    else:
        # Unregister only dependency panel
        dependecy_panel.unregister()
    
    # Unregister base classes
    for cls in reversed(base_classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
    