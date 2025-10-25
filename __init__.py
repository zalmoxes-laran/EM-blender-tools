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
import bpy # type: ignore
import importlib
import logging
from bpy.props import ( # type: ignore
    StringProperty,
    BoolProperty,
    FloatProperty,
    IntProperty,
    PointerProperty,
    CollectionProperty,
    FloatVectorProperty,
    EnumProperty,
) # type: ignore
from bpy.types import PropertyGroup # type: ignore
from . import icons_manager

from .thumb_utils import cleanup_preview_collections

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("EMTools")

# Constants for reuse
VERSION = "1.5.0"
BL_INFO = {
    "name": "EM Tools",
    "author": "Emanuel Demetrescu",
    "version": VERSION,
    "blender": (4, 4, 0),
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
# KEYMAP INTEGRATION
# ============================

# Importa il keymap manager se i moduli sono caricati
if DEPENDENCIES_LOADED:
    try:
        from . import keymap_manager
        KEYMAP_MANAGER_LOADED = True
    except ImportError as e:
        logger.warning(f"Could not import keymap_manager: {e}")
        KEYMAP_MANAGER_LOADED = False
else:
    KEYMAP_MANAGER_LOADED = False

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
    ) # type: ignore

class EDGESListItem(PropertyGroup):
    """Edge information for graph edges"""
    id_node: StringProperty(
        name="id",
        description="Unique identifier for this edge",
        default=""
    ) # type: ignore
    source: StringProperty(
        name="source",
        description="Source node ID",
        default=""
    ) # type: ignore
    target: StringProperty(
        name="target",
        description="Target node ID",
        default=""
    ) # type: ignore
    edge_type: StringProperty(
        name="type",
        description="Type of edge connection",
        default=""
    ) # type: ignore

class EM_Other_Settings(PropertyGroup):
    """General settings for EM Tools"""
    select_all_layers: BoolProperty(name="Select Visible Layers", default=True) # type: ignore
    unlock_obj: BoolProperty(name="Unlock Objects", default=False) # type: ignore
    unhide_obj: BoolProperty(name="Unhide Objects", default=True) # type: ignore
    em_proxy_sync: BoolProperty(name="Selecting a proxy you select the corresponding EM", default=False) # type: ignore
    em_proxy_sync2: BoolProperty(name="Selecting an EM you select the corresponding proxy", default=False) # type: ignore
    em_proxy_sync2_zoom: BoolProperty(name="Option to zoom to proxy", default=False) # type: ignore
    soloing_mode: BoolProperty(name="Soloing mode", default=False) # type: ignore

class EMviqListErrors(PropertyGroup):
    """Error tracking for EMviq exports"""
    name: StringProperty(
        name="Object",
        description="The object with an error",
        default=""
    ) # type: ignore
    description: StringProperty(
        name="Description",
        description="Description of the error",
        default=""
    ) # type: ignore
    material: StringProperty(
        name="Material",
        description="Associated material",
        default=""
    ) # type: ignore
    texture_type: StringProperty(
        name="Texture Type",
        description="Type of texture with error",
        default=""
    ) # type: ignore

class EMListParadata(PropertyGroup):
    """ParaData node information"""
    name: StringProperty(
        name="Name",
        description="Name of this paradata item",
        default="Untitled"
    ) # type: ignore
    description: StringProperty(
        name="Description",
        description="Description of this paradata item",
        default=""
    ) # type: ignore
    icon: StringProperty(
        name="Icon",
        description="Icon code for UI display",
        default="RESTRICT_INSTANCED_ON"
    ) # type: ignore
    icon_url: StringProperty(
        name="URL Icon",
        description="Icon for URL status",
        default="CHECKBOX_DEHLT"
    ) # type: ignore
    url: StringProperty(
        name="URL",
        description="URL associated with this paradata",
        default=""
    ) # type: ignore
    id_node: StringProperty(
        name="Node ID",
        description="Unique node identifier",
        default=""
    ) # type: ignore

class EM_epochs_belonging_ob(PropertyGroup):
    """Association between objects and epochs"""
    epoch: StringProperty(
        name="Epoch",
        description="Associated epoch",
        default="Untitled"
    ) # type: ignore

class ExportVars(PropertyGroup):
    """Export settings for various formats"""
    format_file: EnumProperty(
        items=[
            ('gltf', 'gltf', 'gltf', '', 0),
            ('obj', 'obj', 'obj', '', 1),
            ('fbx', 'fbx', 'fbx', '', 2),
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
    heriverse_use_gpu_instancing: BoolProperty(
        name="Use GPU Instancing",
        description="Enable GPU instancing for models with shared meshes (improved performance)",
        default=True
    ) # type: ignore
    heriverse_skip_extracted_tilesets: BoolProperty(
        name="Skip Previously Extracted Tilesets",
        description="Skip tileset extraction if already extracted in the destination folder",
        default=True
    ) # type: ignore
    heriverse_export_rmdoc: BoolProperty(
        name="Export ParaData Objects",
        description="Export 3D objects associated with ParaData nodes (Documents, Extractors, Combiners)",
        default=True
    ) # type: ignore
    heriverse_export_rmsf: BoolProperty(
        name="Export Special Finds Models",
        description="Export 3D models associated with Special Finds (SF) nodes",
        default=True
    ) # type: ignore

    heriverse_export_animations: BoolProperty(
        name="Export Animations",
        description="Export animations and armatures in glTF files",
        default=False
    ) # type: ignore
    heriverse_export_all_animations: BoolProperty(
        name="Export All Animations",
        description="Export all animations instead of just the active one",
        default=False
    ) # type: ignore
    heriverse_animation_frame_range: BoolProperty(
        name="Limit to Frame Range",
        description="Export only the current frame range instead of all frames",
        default=True
    ) # type: ignore

class ExportTablesVars(PropertyGroup):
    """Table export settings"""
    table_type: EnumProperty(
        items=[
            ('US/USV', 'US/USV', 'US/USV', '', 0),
            ('Sources', 'Sources', 'Sources', '', 1),
            ('Extractors', 'Extractors', 'Extractors', '', 2),
        ],
        default='US/USV'
    ) # type: ignore

# ============================
# MODULE IMPORTS
# ============================

# Only import submodules if dependencies are satisfied
if DEPENDENCIES_LOADED:
    try:
        # Import addon modules - these will be imported during registration
        from . import (
            operators,
            mapping_preferences,
            em_setup,
            visual_manager,  # <-- Solo UI e operatori base
            stratigraphy_manager,
            epoch_manager,
            functions,
            paradata_manager,
            export_manager,
            EMdb_excel,
            em_statistics,
            graph2geometry,
            activity_manager,
            rm_manager,
            proxy_inflate_manager,
            anastylosis_manager,
            proxy_to_rm_projection,
            cronofilter,
            landscape_system,
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
    """Register all addon modules in correct dependency order"""
    if not MODULE_IMPORT_SUCCESS:
        logger.warning("Skipping module registration due to missing dependencies")
        return
    
    # Import statements
    from .import_operators import importer_graphml
    from .export_operators import exporter_heriverse
    from .import_operators import import_EMdb
    from .operators import graphml_converter
    from . import thumb_operators
    
    # FASE 0: Preferenze (devono essere registrate per prime)
    try:
        mapping_preferences.register()
        logger.debug("Registered mapping preferences")
    except Exception as e:
        logger.warning(f"Error registering mapping preferences: {e}")

    # FASE 1: Moduli core indipendenti (nessuna dipendenza UI)
    core_independent_modules = [
        icons_manager,
        em_setup,
        EMdb_excel,
        visual_manager,
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
        operators,
        cronofilter,
        thumb_operators
    ]
    
    for module in core_independent_modules:
        try:
            module.register()
            logger.debug(f"Registered core independent module: {module.__name__}")
        except Exception as e:
            logger.error(f"Error registering core module {module.__name__}: {e}")
    '''
    # FASE 2: Visual Manager (crea i pannelli parent) 
    try:
        #visual_manager.register()
        logger.debug(f"Registered visual manager (creates parent panels)")
    except Exception as e:
        logger.error(f"Error registering visual manager: {e}")
    '''
    # FASE 3: Moduli che dipendono dai pannelli del Visual Manager
    ui_dependent_modules = [
        proxy_inflate_manager,  # Dipende da VIEW3D_PT_visual_panel
        proxy_to_rm_projection, # Potrebbe dipendere dai pannelli visual
    ]
    
    for module in ui_dependent_modules:
        try:
            module.register()
            logger.debug(f"Registered UI dependent module: {module.__name__}")
        except Exception as e:
            logger.error(f"Error registering UI dependent module {module.__name__}: {e}")
    
    # FASE 4: Landscape System (modalità semplice e pulita)
    try:
        landscape_system.register()
        logger.debug(f"Registered landscape system")
    except Exception as e:
        logger.error(f"Error registering landscape system: {e}")

    # Registra il keymap manager per ultimo
    if KEYMAP_MANAGER_LOADED:
        try:
            keymap_manager.register()
            logger.info("Keymap manager registered successfully")
        except Exception as e:
            logger.error(f"Error registering keymap manager: {e}")

    # Inizializza i percorsi personalizzati
    try:
        mapping_preferences.initialize_custom_mappings()
        logger.info("Scheduled custom mapping paths initialization")
    except Exception as e:
        logger.warning(f"Error scheduling custom mappings initialization: {e}")




def unregister_modules():
    """Unregister all modules in reverse dependency order"""
    if not MODULE_IMPORT_SUCCESS:
        logger.warning("Skipping module unregistration - modules not loaded")
        return
    
    from .export_operators import exporter_heriverse
    from .import_operators import importer_graphml, import_EMdb
    from .operators import graphml_converter
    from . import thumb_operators
    
    # Rimuovi il keymap manager per primo
    if KEYMAP_MANAGER_LOADED:
        try:
            keymap_manager.unregister()
            logger.info("Keymap manager unregistered successfully")
        except Exception as e:
            logger.error(f"Error unregistering keymap manager: {e}")


    # FASE 1: Landscape system (va rimosso per primo)
    try:
        landscape_system.unregister()
        logger.debug(f"Unregistered landscape system")
    except Exception as e:
        logger.warning(f"Error unregistering landscape system: {e}")
    
    # FASE 2: Moduli dipendenti da pannelli UI
    ui_dependent_modules = [
        proxy_to_rm_projection,
        proxy_inflate_manager,
    ]
    
    for module in ui_dependent_modules:
        try:
            module.unregister()
            logger.debug(f"Unregistered UI dependent module: {module.__name__}")
        except Exception as e:
            logger.warning(f"Error unregistering UI dependent module {module.__name__}: {e}")
    
    # FASE 3: Visual Manager (rimuove i pannelli parent)
    try:
        visual_manager.unregister()
        logger.debug(f"Unregistered visual manager")
    except Exception as e:
        logger.warning(f"Error unregistering visual manager: {e}")
    
    # FASE 4: Moduli core in ordine inverso
    core_modules = [
        thumb_operators,
        cronofilter,
        operators,
        graphml_converter,
        import_EMdb,
        exporter_heriverse,
        importer_graphml,
        graph2geometry,
        em_statistics,
        export_manager,
        rm_manager,
        anastylosis_manager,
        paradata_manager,
        epoch_manager,
        stratigraphy_manager,
        activity_manager,
        EMdb_excel,
        em_setup,
        icons_manager,
    ]
    
    for module in core_modules:
        try:
            module.unregister()
            logger.debug(f"Unregistered core module: {module.__name__}")
        except Exception as e:
            logger.warning(f"Error unregistering core module {module.__name__}: {e}")

    # Rimuovi preferenze per ultime
    try:
        mapping_preferences.unregister()
        logger.debug("Unregistered mapping preferences")
    except Exception as e:
        logger.warning(f"Error unregistering mapping preferences: {e}")


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
    
    # 4. Register all modules in the correct order
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
    
    # 2. Unregister modules using the new organized function
    if MODULE_IMPORT_SUCCESS:
        unregister_modules()  # Usa la nuova funzione organizzata
    
    # 3. Remove properties (utilizza il codice che hai già implementato)
    # Remove graph reference
    if hasattr(bpy.types.Scene, 'em_graph'):
        bpy.types.Scene.em_graph = None
    
    # Remove collection properties
    collection_props = [
        'emviq_error_list',
        'edges_list', 
        'em_sources_list',
        'em_properties_list',
        'em_extractors_list',
        'em_combiners_list',
        'em_v_sources_list',
        'em_v_properties_list',
        'em_v_extractors_list',
        'em_v_combiners_list',
    ]
    
    for prop_name in collection_props:
        if hasattr(bpy.types.Scene, prop_name):
            delattr(bpy.types.Scene, prop_name)
            logger.debug(f"Removed collection property: {prop_name}")
    
    # Remove index properties
    index_props = [
        'selected_epoch_us_list_index',
        'emviq_error_list_index',
        'em_list_index',
        'epoch_list_index',
        'edges_list_index',
        'em_sources_list_index',
        'em_properties_list_index',
        'em_extractors_list_index',
        'em_combiners_list_index',
        'em_v_sources_list_index',
        'em_v_properties_list_index',
        'em_v_extractors_list_index',
        'em_v_combiners_list_index',
    ]
    
    for prop_name in index_props:
        if hasattr(bpy.types.Scene, prop_name):
            delattr(bpy.types.Scene, prop_name)
            logger.debug(f"Removed index property: {prop_name}")
    
    # Remove boolean properties
    bool_props = [
        'paradata_streaming_mode',
        'prop_paradata_streaming_mode',
        'comb_paradata_streaming_mode',
        'extr_paradata_streaming_mode',
    ]
    
    for prop_name in bool_props:
        if hasattr(bpy.types.Scene, prop_name):
            delattr(bpy.types.Scene, prop_name)
            logger.debug(f"Removed boolean property: {prop_name}")
    
    # Remove string properties (based on setup_scene_properties)
    string_props = [
        'EM_file_name',
        'EM_file_path',
        'EM_file_name_source',
        'EM_file_path_source',
        'EM_unit_text',
        'EM_unit_description',
        'EM_unit_name',
        'data_path',
        'image_path',
        'file_path',
        'my_file',
    ]
    
    for prop_name in string_props:
        if hasattr(bpy.types.Scene, prop_name):
            delattr(bpy.types.Scene, prop_name)
            logger.debug(f"Removed string property: {prop_name}")
    
    # Remove float properties
    if hasattr(bpy.types.Scene, 'proxy_display_alpha'):
        delattr(bpy.types.Scene, 'proxy_display_alpha')
        logger.debug("Removed float property: proxy_display_alpha")
    
    # Remove integer properties
    int_props = [
        'EM_gltf_export_quality',
        'EM_gltf_export_maxres',
    ]
    
    for prop_name in int_props:
        if hasattr(bpy.types.Scene, prop_name):
            delattr(bpy.types.Scene, prop_name)
            logger.debug(f"Removed integer property: {prop_name}")
    
    # Remove pointer properties from Scene
    scene_pointer_props = [
        'em_settings',
    ]
    
    for prop_name in scene_pointer_props:
        if hasattr(bpy.types.Scene, prop_name):
            delattr(bpy.types.Scene, prop_name)
            logger.debug(f"Removed Scene pointer property: {prop_name}")
    
    # Remove pointer properties from WindowManager
    wm_pointer_props = [
        'em_addon_settings',
        'export_vars',
        'export_tables_vars',
    ]
    
    for prop_name in wm_pointer_props:
        if hasattr(bpy.types.WindowManager, prop_name):
            delattr(bpy.types.WindowManager, prop_name)
            logger.debug(f"Removed WindowManager pointer property: {prop_name}")
    
    # Remove Object properties
    object_props = [
        'EM_ep_belong_ob',
        'EM_ep_belong_ob_index',
    ]
    
    for prop_name in object_props:
        if hasattr(bpy.types.Object, prop_name):
            delattr(bpy.types.Object, prop_name)
            logger.debug(f"Removed Object property: {prop_name}")
    
    # Unregister base classes in reverse order
    for cls in reversed(BASE_CLASSES):
        try:
            bpy.utils.unregister_class(cls)
            logger.debug(f"Unregistered base class: {cls.__name__}")
        except Exception as e:
            logger.warning(f"Could not unregister {cls.__name__}: {e}")
    
    logger.info("EM Tools unregistration complete")

if __name__ == "__main__":
    register()