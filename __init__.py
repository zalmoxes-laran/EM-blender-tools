'''
Extended Matrix 3D Tools (EMTools)
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

import os
import bpy
import importlib
import logging
from bpy.props import (
    StringProperty,
    BoolProperty,
    FloatProperty,
    IntProperty,
    PointerProperty,
    CollectionProperty,
    FloatVectorProperty,
    EnumProperty,
)
from bpy.types import PropertyGroup

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("EMTools")

# Constants for reuse
VERSION = "1.5.0"
BL_INFO = {
    "name": "EM Tools",
    "author": "Emanuel Demetrescu",
    "version": VERSION,
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > EM",
    "description": "Extended Matrix 3D Tools",
    "warning": "",
    "doc_url": "https://docs.extendedmatrix.org",
    "category": "3D View",
}

# ============================
# DEPENDENCY MANAGEMENT
# ============================
DEPENDENCIES = {
    "required": ["pandas", "networkx", "PIL.Image"], 
    "optional": []
}

def check_dependencies():
    """Check if all required dependencies are available"""
    missing = []
        
    for module_name in DEPENDENCIES["required"]:
        parts = module_name.split('.')
        base_module = parts[0]
        try:
            if base_module == "PIL":
                try:
                    from PIL import Image
                except ImportError:
                    missing.append("pillow")
            else:
                importlib.import_module(base_module)
        except ImportError:
            missing.append(base_module)
    
    if missing:
        logger.warning(f"Missing required dependencies: {', '.join(missing)}")
        logger.warning("Tip: Run 'em.bat setup force' to reinstall dependencies")
        return False
    return True

DEPENDENCIES_LOADED = check_dependencies()

# ============================
# PROPERTY GROUP CLASSES
# ============================

class EMAddonSettings(PropertyGroup):
    """General settings for the EM Tools addon"""
    preserve_web_url: BoolProperty(
        name="Preserve Web URL",
        description="Preserve web urls (if any) from the GraphML file",
        default=True
    ) # type: ignore
    overwrite_url_with_dosco_filepath: BoolProperty(
        name="Overwrite URL with DosCo Filepath",
        description="Retrieve the URL from real DosCo Filepath ignoring the url values stated in the GraphML file",
        default=True
    ) # type: ignore
    dosco_options: BoolProperty(
        name="Show Dosco Section",
        description="Info about DosCo folder loading the GraphML",
        default=False
    ) # type: ignore
    dosco_advanced_options: BoolProperty(
        name="Show advanced options",
        description="Catch more information from DosCo folder loading the GraphML",
        default=False
    )

class EDGESListItem(PropertyGroup):
    """Edge information for graph edges"""
    id_node: StringProperty(
        name="id",
        description="Unique identifier for this edge",
        default=""
    )
    source: StringProperty(
        name="source",
        description="Source node ID",
        default=""
    )
    target: StringProperty(
        name="target",
        description="Target node ID",
        default=""
    )
    edge_type: StringProperty(
        name="type",
        description="Type of edge connection",
        default=""
    )

class EM_Other_Settings(PropertyGroup):
    """General settings for EM Tools"""
    select_all_layers: BoolProperty(name="Select Visible Layers", default=True)
    unlock_obj: BoolProperty(name="Unlock Objects", default=False)
    unhide_obj: BoolProperty(name="Unhide Objects", default=True)
    em_proxy_sync: BoolProperty(name="Selecting a proxy you select the corresponding EM", default=False)
    em_proxy_sync2: BoolProperty(name="Selecting an EM you select the corresponding proxy", default=False)
    em_proxy_sync2_zoom: BoolProperty(name="Option to zoom to proxy", default=False)
    soloing_mode: BoolProperty(name="Soloing mode", default=False)

class EMviqListErrors(PropertyGroup):
    """Error tracking for EMviq exports"""
    name: StringProperty(
        name="Object",
        description="The object with an error",
        default=""
    )
    description: StringProperty(
        name="Description",
        description="Description of the error",
        default=""
    )
    material: StringProperty(
        name="Material",
        description="Associated material",
        default=""
    )
    texture_type: StringProperty(
        name="Texture Type",
        description="Type of texture with error",
        default=""
    )

class EMListParadata(PropertyGroup):
    """ParaData node information"""
    name: StringProperty(
        name="Name",
        description="Name of this paradata item",
        default="Untitled"
    )
    description: StringProperty(
        name="Description",
        description="Description of this paradata item",
        default=""
    )
    icon: StringProperty(
        name="Icon",
        description="Icon code for UI display",
        default="RESTRICT_INSTANCED_ON"
    )
    icon_url: StringProperty(
        name="URL Icon",
        description="Icon for URL status",
        default="CHECKBOX_DEHLT"
    )
    url: StringProperty(
        name="URL",
        description="URL associated with this paradata",
        default=""
    )
    id_node: StringProperty(
        name="Node ID",
        description="Unique node identifier",
        default=""
    )

class EM_epochs_belonging_ob(PropertyGroup):
    """Association between objects and epochs"""
    epoch: StringProperty(
        name="Epoch",
        description="Associated epoch",
        default="Untitled"
    )

class ExportVars(PropertyGroup):
    """Export settings for various formats"""
    format_file: EnumProperty(
        items=[
            ('gltf', 'gltf', 'gltf', '', 0),
            ('obj', 'obj', 'obj', '', 1),
            ('fbx', 'fbx', 'fbx', '', 2),
        ],
        default='gltf'
    )
    heriverse_expanded: BoolProperty(
        name="Show Heriverse export options",
        description="Expand/Collapse Heriverse export options",
        default=False
    )
    emviq_expanded: BoolProperty(
        name="Show Emviq export options",
        description="Expand/Collapse Emviq export options",
        default=False
    )
    heriverse_project_name: StringProperty(
        name="Project Name",
        description="Name of the Heriverse project",
        default=""
    )
    heriverse_export_path: StringProperty(
        name="Export Path",
        description="Path where to export Heriverse project",
        subtype='DIR_PATH'
    )
    heriverse_export_all_graphs: BoolProperty(
        name="Export all graphs",
        description="Export all loaded graphs instead of just the selected one",
        default=False
    )
    heriverse_overwrite_json: BoolProperty(
        name="Overwrite JSON",
        description="Overwrite existing JSON file",
        default=True
    )
    heriverse_export_dosco: BoolProperty(
        name="Export DosCo files",
        description="Copy DosCo files to output",
        default=True
    )
    heriverse_export_proxies: BoolProperty(
        name="Export proxies",
        description="Export proxy models",
        default=True
    )
    heriverse_export_rm: BoolProperty(
        name="Export RM",
        description="Export representation models",
        default=True
    )
    heriverse_create_zip: BoolProperty(
        name="Create ZIP archive",
        description="Create a ZIP archive of the exported project",
        default=True
    )
    heriverse_advanced_options: BoolProperty(
        name="Show advanced options",
        description="Show advanced export options like compression settings",
        default=False
    )
    heriverse_use_draco: BoolProperty(
        name="Use Draco compression",
        description="Enable Draco mesh compression for smaller file size",
        default=True
    )
    heriverse_draco_level: IntProperty(
        name="Compression Level",
        description="Draco compression level (higher = smaller files but slower)",
        min=1,
        max=10,
        default=6
    )
    heriverse_separate_textures: BoolProperty(
        name="Export textures separately",
        description="Export textures as separate files instead of embedding",
        default=True
    )
    heriverse_use_gpu_instancing: BoolProperty(
        name="Use GPU Instancing",
        description="Enable GPU instancing for models with shared meshes (improved performance)",
        default=True
    )
    heriverse_skip_extracted_tilesets: BoolProperty(
        name="Skip Previously Extracted Tilesets",
        description="Skip tileset extraction if already extracted in the destination folder",
        default=True
    )
    heriverse_export_rmdoc: BoolProperty(
        name="Export ParaData Objects",
        description="Export 3D objects associated with ParaData nodes (Documents, Extractors, Combiners)",
        default=True
    )
    heriverse_export_rmsf: BoolProperty(
        name="Export Special Finds Models",
        description="Export 3D models associated with Special Finds (SF) nodes",
        default=True
    )

class ExportTablesVars(PropertyGroup):
    """Table export settings"""
    table_type: EnumProperty(
        items=[
            ('US/USV', 'US/USV', 'US/USV', '', 0),
            ('Sources', 'Sources', 'Sources', '', 1),
            ('Extractors', 'Extractors', 'Extractors', '', 2),
        ],
        default='US/USV'
    )



# ============================
# MODULE IMPORTS
# ============================

# Only import submodules if dependencies are satisfied
if DEPENDENCIES_LOADED:
    try:
        # Import addon modules - these will be imported during registration
        from . import (
            operators,
            em_setup,
            stratigraphy_manager,
            epoch_manager,
            functions,
            paradata_manager,
            export_manager,
            visual_manager,
            EMdb_excel,
            em_statistics,
            graph2geometry,
            activity_manager,
            rm_manager,
            proxy_inflate_manager,
            anastylosis_manager
        )
        MODULE_IMPORT_SUCCESS = True
    except ImportError as e:
        logger.error(f"Error importing addon modules: {e}")
        MODULE_IMPORT_SUCCESS = False
else:
    logger.warning("Skipping module imports due to missing dependencies")
    MODULE_IMPORT_SUCCESS = False

# ============================
# REGISTRATION FUNCTIONS
# ============================

# Base class list for registration
BASE_CLASSES = [
    EMAddonSettings,
    EDGESListItem,
    EM_Other_Settings,
    EMviqListErrors,
    EMListParadata,
    EM_epochs_belonging_ob,
    ExportVars,
    ExportTablesVars
]

def register_base_classes():
    """Register the PropertyGroup and Operator classes"""
    for cls in BASE_CLASSES:
        try:
            bpy.utils.register_class(cls)
            logger.debug(f"Registered class: {cls.__name__}")
        except Exception as e:
            logger.warning(f"Could not register {cls.__name__}: {e}")

def setup_scene_collections():
    """Setup all collection properties on Scene"""
    collection_types = {
        'emviq_error_list': EMviqListErrors,
        'edges_list': EDGESListItem,
        'em_sources_list': EMListParadata,
        'em_properties_list': EMListParadata,
        'em_extractors_list': EMListParadata,
        'em_combiners_list': EMListParadata,
        'em_v_sources_list': EMListParadata,
        'em_v_properties_list': EMListParadata,
        'em_v_extractors_list': EMListParadata,
        'em_v_combiners_list': EMListParadata,
    }
    
    for prop_name, prop_type in collection_types.items():
        if hasattr(bpy.types.Scene, prop_name):
            # Force re-creation for development reloads
            delattr(bpy.types.Scene, prop_name)
        setattr(bpy.types.Scene, prop_name, CollectionProperty(type=prop_type))
        logger.debug(f"Setup collection: {prop_name}")

def setup_scene_indices():
    """Setup index properties for collections"""
    indices_with_updates = [
        ('selected_epoch_us_list_index', 0, lambda self, context: getattr(bpy.ops, 'epoch_manager.update_us_list', lambda: None)()),
        ('emviq_error_list_index', 0, functions.switch_paradata_lists if MODULE_IMPORT_SUCCESS else None),
        ('em_list_index', 0, functions.switch_paradata_lists if MODULE_IMPORT_SUCCESS else None),
        ('epoch_list_index', 0, None),
        ('edges_list_index', 0, None),
        ('em_sources_list_index', 0, None),
        ('em_properties_list_index', 0, None),
        ('em_extractors_list_index', 0, None),
        ('em_combiners_list_index', 0, None),
        ('em_v_sources_list_index', 0, None),
        ('em_v_properties_list_index', 0, functions.stream_properties if MODULE_IMPORT_SUCCESS else None),
        ('em_v_extractors_list_index', 0, functions.stream_extractors if MODULE_IMPORT_SUCCESS else None),
        ('em_v_combiners_list_index', 0, functions.stream_combiners if MODULE_IMPORT_SUCCESS else None),
    ]
    
    for prop_name, default, update_func in indices_with_updates:
        if hasattr(bpy.types.Scene, prop_name):
            delattr(bpy.types.Scene, prop_name)
            
        props = {
            'name': f"Index for {prop_name}", 
            'default': default
        }
        if update_func:
            props['update'] = update_func
            
        setattr(bpy.types.Scene, prop_name, IntProperty(**props))
        logger.debug(f"Setup index: {prop_name}")

def setup_scene_properties():
    """Setup other properties on Scene"""
    # Boolean properties with update functions
    bool_props = [
        ('paradata_streaming_mode', {
            "name": "Paradata streaming mode", 
            "description": "Enable/disable tables streaming mode", 
            "default": True, 
            "update": functions.switch_paradata_lists if MODULE_IMPORT_SUCCESS else None
        }),
        ('prop_paradata_streaming_mode', {
            "name": "Properties Paradata streaming mode", 
            "description": "Enable/disable property table streaming mode",
            "default": True, 
            "update": functions.stream_properties if MODULE_IMPORT_SUCCESS else None
        }),
        ('comb_paradata_streaming_mode', {
            "name": "Combiners Paradata streaming mode", 
            "description": "Enable/disable combiner table streaming mode",
            "default": True, 
            "update": functions.stream_combiners if MODULE_IMPORT_SUCCESS else None
        }),
        ('extr_paradata_streaming_mode', {
            "name": "Extractors Paradata streaming mode", 
            "description": "Enable/disable extractor table streaming mode",
            "default": True, 
            "update": functions.stream_extractors if MODULE_IMPORT_SUCCESS else None
        }),
        ('proxy_shader_mode', {
            "name": "Proxy shader mode", 
            "description": "Enable additive shader for proxies",
            "default": True, 
            "update": functions.proxy_shader_mode_function if MODULE_IMPORT_SUCCESS else None
        }),
    ]
    
    for prop_name, prop_kwargs in bool_props:
        if hasattr(bpy.types.Scene, prop_name):
            delattr(bpy.types.Scene, prop_name)
        setattr(bpy.types.Scene, prop_name, BoolProperty(**prop_kwargs))
        logger.debug(f"Setup boolean property: {prop_name}")
    
    # String properties
    string_props = [
        ('EM_file', "Define the path to the EM GraphML file", ''),
        ('EMviq_folder', "Define the path to export the EMviq collection", ''),
        ('EMviq_scene_folder', "Define the path to export the EMviq scene", ''),
        ('EMviq_project_name', "Define the name of the EMviq project", ''),
        ('EMviq_user_name', "Define the name of the EMviq user", ''),
        ('EMviq_user_password', "Define the name of the EMviq user", 'PASSWORD'),
        ('ATON_path', "Define the path to the ATON framework (root folder)", ''),
        ('EMviq_model_author_name', "Define the name of the author(s) of the models", ''),
        ('proxy_display_mode', "Proxy display mode", "select"),
        ('proxy_blend_mode', "Proxy blend mode", "BLEND"),
    ]
    
    for prop_name, description, subtype in string_props:
        if hasattr(bpy.types.Scene, prop_name):
            delattr(bpy.types.Scene, prop_name)
            
        props = {
            'name': prop_name, 
            'default': "", 
            'description': description
        }
        if prop_name == 'proxy_blend_mode':
            props['default'] = 'BLEND'
            
        if subtype:
            if subtype not in ["", "PASSWORD", "select", "BLEND"]:
                props['subtype'] = subtype
                
        setattr(bpy.types.Scene, prop_name, StringProperty(**props))
        logger.debug(f"Setup string property: {prop_name}")
    
    # Float properties
    if hasattr(bpy.types.Scene, 'proxy_display_alpha'):
        delattr(bpy.types.Scene, 'proxy_display_alpha')
        
    bpy.types.Scene.proxy_display_alpha = FloatProperty(
        name="alpha", description="The alpha value for proxies",
        min=0, max=1, default=0.5, 
        update=functions.update_display_mode if MODULE_IMPORT_SUCCESS else None
    )
    
    # Integer properties
    int_props = [
        ('EM_gltf_export_quality', "export quality", 
            "Define the quality of the output images", 100),
        ('EM_gltf_export_maxres', "export max resolution", 
            "Define the maximum resolution of the output images", 4096),
    ]
    
    for prop_name, name, description, default in int_props:
        if hasattr(bpy.types.Scene, prop_name):
            delattr(bpy.types.Scene, prop_name)
            
        setattr(bpy.types.Scene, prop_name, IntProperty(
            name=name, description=description, default=default))
        logger.debug(f"Setup integer property: {prop_name}")

def setup_pointer_properties():
    """Setup pointer properties on various types"""
    # Scene properties
    if hasattr(bpy.types.Scene, 'em_settings'):
        delattr(bpy.types.Scene, 'em_settings')
    bpy.types.Scene.em_settings = PointerProperty(type=EM_Other_Settings)
    
    # WindowManager properties
    if hasattr(bpy.types.WindowManager, 'em_addon_settings'):
        delattr(bpy.types.WindowManager, 'em_addon_settings')
    bpy.types.WindowManager.em_addon_settings = PointerProperty(type=EMAddonSettings)
    
    if hasattr(bpy.types.WindowManager, 'export_vars'):
        delattr(bpy.types.WindowManager, 'export_vars')
    bpy.types.WindowManager.export_vars = PointerProperty(type=ExportVars)
    
    if hasattr(bpy.types.WindowManager, 'export_tables_vars'):
        delattr(bpy.types.WindowManager, 'export_tables_vars')
    bpy.types.WindowManager.export_tables_vars = PointerProperty(type=ExportTablesVars)
    
    # Object properties
    if hasattr(bpy.types.Object, 'EM_ep_belong_ob'):
        delattr(bpy.types.Object, 'EM_ep_belong_ob')
    bpy.types.Object.EM_ep_belong_ob = CollectionProperty(type=EM_epochs_belonging_ob)
    
    if hasattr(bpy.types.Object, 'EM_ep_belong_ob_index'):
        delattr(bpy.types.Object, 'EM_ep_belong_ob_index')
    bpy.types.Object.EM_ep_belong_ob_index = IntProperty()

def register_modules():
    """Register all addon modules"""
    if not MODULE_IMPORT_SUCCESS:
        logger.warning("Skipping module registration due to missing dependencies")
        return
    
    # We need to import these here to access the registration functions
    from .import_operators import importer_graphml
    from .export_operators import exporter_heriverse
    from .import_operators import import_EMdb
    from .operators import graphml_converter
    
    modules_to_register = [
        em_setup,
        visual_manager,
        EMdb_excel,
        activity_manager,
        stratigraphy_manager,
        epoch_manager,
        paradata_manager,
        anastylosis_manager,
        rm_manager,
        export_manager,
        em_statistics,
        graph2geometry,
        importer_graphml,
        exporter_heriverse,
        import_EMdb,
        graphml_converter,
        proxy_inflate_manager,
        operators
    ]
    
    for module in modules_to_register:
        try:
            module.register()
            logger.debug(f"Registered module: {module.__name__}")
        except Exception as e:
            logger.error(f"Error registering {module.__name__}: {e}")

def register():
    """Main registration function"""
    logger.info(f"Registering EM Tools {VERSION}")
    
    # 1. Register base property classes first
    register_base_classes()
    
    # 2. Setup all properties
    setup_scene_collections()
    setup_scene_indices()
    setup_scene_properties()
    setup_pointer_properties()
    
    # 3. Set graph reference
    bpy.types.Scene.em_graph = None
    
    # 4. Register all modules
    register_modules()
    
    # 5. Add menu items
    if MODULE_IMPORT_SUCCESS:
        bpy.types.VIEW3D_MT_mesh_add.append(functions.menu_func)
    
    logger.info("EM Tools registration complete")

def unregister():
    """Main unregistration function"""
    logger.info("Unregistering EM Tools")
    
    # 1. Remove menu items
    if MODULE_IMPORT_SUCCESS:
        try:
            bpy.types.VIEW3D_MT_mesh_add.remove(functions.menu_func)
        except Exception as e:
            logger.warning(f"Error removing menu function: {e}")
    
    # 2. Unregister modules in reverse order
    if MODULE_IMPORT_SUCCESS:
        from .export_operators import exporter_heriverse
        from .import_operators import importer_graphml, import_EMdb
        from .operators import graphml_converter
        
        modules_to_unregister = [
            operators,
            graphml_converter,
            import_EMdb,
            exporter_heriverse,
            importer_graphml,
            proxy_inflate_manager,
            activity_manager,
            graph2geometry,
            rm_manager,
            anastylosis_manager,
            paradata_manager,
            epoch_manager,
            em_statistics,
            export_manager,
            EMdb_excel,
            visual_manager,
            em_setup
        ] 
        
        for module in modules_to_unregister:
            try:
                module.unregister()
                logger.debug(f"Unregistered module: {module.__name__}")
            except Exception as e:
                logger.warning(f"Error unregistering {module.__name__}: {e}")
    
    # 3. Remove properties
    property_owners = [
        (bpy.types.WindowManager, ['export_vars', 'export_tables_vars', 'em_addon_settings']),
        (bpy.types.Scene, [
            'EM_gltf_export_maxres', 'EM_gltf_export_quality', 'proxy_display_alpha',
            'proxy_blend_mode', 'proxy_display_mode', 'em_settings', 'EMviq_model_author_name',
            'ATON_path', 'EMviq_user_password', 'EMviq_user_name', 'EMviq_project_name',
            'EMviq_scene_folder', 'EMviq_folder', 'EM_file', 'paradata_streaming_mode',
            'prop_paradata_streaming_mode', 'comb_paradata_streaming_mode', 'extr_paradata_streaming_mode',
            'proxy_shader_mode', 'em_graph', 'filter_by_epoch', 'filter_by_activity',
            'include_surviving_units', 'sync_list_visibility', 'sync_rm_visibility'
        ]),
        (bpy.types.Object, ['EM_ep_belong_ob_index', 'EM_ep_belong_ob'])
    ]
    
    # Remove collection properties
    collection_names = [
        'selected_epoch_us_list', 'emviq_error_list', 'em_list', 'em_reused',
        'epoch_list', 'edges_list', 'em_sources_list', 'em_properties_list',
        'em_extractors_list', 'em_combiners_list', 'em_v_sources_list',
        'em_v_properties_list', 'em_v_extractors_list', 'em_v_combiners_list'
    ]
    
    # Add index properties to remove
    index_names = [f"{name}_index" for name in collection_names]
    property_owners[1][1].extend(index_names)
    property_owners[1][1].extend(collection_names)
    
    # Remove all properties
    for prop_owner, prop_names in property_owners:
        for prop_name in prop_names:
            if hasattr(prop_owner, prop_name):
                try:
                    delattr(prop_owner, prop_name)
                    logger.debug(f"Removed property: {prop_owner.__name__}.{prop_name}")
                except Exception as e:
                    logger.warning(f"Error removing {prop_owner.__name__}.{prop_name}: {e}")
    
    # 4. Unregister base classes in reverse order
    for cls in reversed(BASE_CLASSES):
        try:
            bpy.utils.unregister_class(cls)
            logger.debug(f"Unregistered class: {cls.__name__}")
        except Exception as e:
            logger.warning(f"Error unregistering {cls.__name__}: {e}")
    
    logger.info("EM Tools unregistration complete")

if __name__ == "__main__":
    register()