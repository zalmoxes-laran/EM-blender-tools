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
    "blender": (4, 3, 2),
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

    def get_verbose_logging(self):
        """Getter for verbose logging - reads from addon preferences"""
        try:
            prefs = bpy.context.preferences.addons.get(__package__)
            if prefs and hasattr(prefs.preferences, 'verbose_logging'):
                return prefs.preferences.verbose_logging
        except:
            pass
        return False

    def set_verbose_logging(self, value):
        """Setter for verbose logging - writes to addon preferences"""
        try:
            prefs = bpy.context.preferences.addons.get(__package__)
            if prefs and hasattr(prefs.preferences, 'verbose_logging'):
                prefs.preferences.verbose_logging = value
        except:
            pass

    verbose_logging: BoolProperty(
        name="Verbose Logging",
        description="Enable detailed console logging (mirrors the setting in addon preferences)",
        get=get_verbose_logging,
        set=set_verbose_logging
    ) # type: ignore

# Note: EDGESListItem, EM_Other_Settings, EMviqListErrors, EMListParadata, EM_epochs_belonging_ob
# are now defined in em_base_props.py and imported above (lines 394-400)

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

    tabular_expanded: BoolProperty(
        name="Show tabular export options",
        description="Expand/Collapse tabular export options",
        default=True
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
        subtype='DIR_PATH',
        options={'PATH_SUPPORTS_BLEND_RELATIVE'} if bpy.app.version >= (4, 5, 0) else set()
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
            graph_editor,
            epoch_manager,
            functions,
            paradata_manager,
            document_manager,
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
            proxy_box_creator,
            viewport_overlay,
            em_base_props,  # ← Base PropertyGroup classes
            em_props,
            debug_graph_connections,  # Debug operator
            tapestry_integration,  # Tapestry AI reconstruction
            surface_areale  # Surface Areale proxy creation
        )

        # Import base PropertyGroup classes into this namespace
        from .em_base_props import (
            EDGESListItem,
            EMviqListErrors,
            EMListParadata,
            EM_epochs_belonging_ob,
            EM_Other_Settings
        )

        MODULE_IMPORT_SUCCESS = True
    except ImportError as e:
        logger.error(f"Error importing addon modules: {e}")
        MODULE_IMPORT_SUCCESS = False
else:
    logger.warning("Skipping module imports due to missing dependencies")
    MODULE_IMPORT_SUCCESS = False

# ============================
@bpy.app.handlers.persistent
def validate_mappings_on_load(dummy):
    """Valida i mapping e migra DosCo legacy quando si carica un file .blend"""
    try:
        # Usa un timer per essere sicuri che tutto sia caricato
        def do_validation():
            try:
                from . import em_setup
                em_setup.validate_all_mapping_enums(bpy.context)

                # Migrate legacy DosCo to Auxiliary Resources
                from .em_setup.utils import migrate_legacy_dosco_to_auxiliary
                migrate_legacy_dosco_to_auxiliary(bpy.context)
            except Exception as e:
                print(f"Error validating mappings on load: {e}")
            return None  # Stop timer

        bpy.app.timers.register(do_validation, first_interval=0.5)
    except Exception as e:
        print(f"Error scheduling mapping validation: {e}")


# ============================
# REGISTRATION FUNCTIONS
# ============================

# Base class list for registration
# Note: EDGESListItem, EM_Other_Settings, EMviqListErrors, EMListParadata, EM_epochs_belonging_ob
# are registered by em_base_props.register() instead
BASE_CLASSES = [
    EMAddonSettings,
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

def update_epoch_index(self, context):
    """Re-filter when epoch changes (if filter active)"""
    scene = context.scene
    if scene.filter_by_epoch and hasattr(bpy.ops, 'em') and hasattr(bpy.ops.em, 'filter_lists'):
        epochs = scene.em_tools.epochs
        print(f"Epoch changed to index {epochs.list_index}, re-filtering...")
        bpy.ops.em.filter_lists()

def setup_scene_indices():
    """Setup index properties for collections"""
    indices_with_updates = [
        ('emviq_error_list_index', 0, functions.switch_paradata_lists if MODULE_IMPORT_SUCCESS else None),
        ('em_list_index', 0, functions.switch_paradata_lists if MODULE_IMPORT_SUCCESS else None),
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
    # NOTE: proxy_display_alpha is now in scene.em_tools (em_props.py)
    # if hasattr(bpy.types.Scene, 'proxy_display_alpha'):
    #     delattr(bpy.types.Scene, 'proxy_display_alpha')
    #
    # bpy.types.Scene.proxy_display_alpha = FloatProperty(
    #     name="alpha", description="The alpha value for proxies",
    #     min=0, max=1, default=0.5,
    #     update=functions.update_display_mode if MODULE_IMPORT_SUCCESS else None
    # )
    
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
    if not MODULE_IMPORT_SUCCESS:
        logger.warning("Cannot setup pointer properties: modules not loaded")
        return

    # Scene properties
    # ⚠️ MIGRATION NOTE: em_settings is now scene.em_tools.settings
    # if hasattr(bpy.types.Scene, 'em_settings'):
    #     delattr(bpy.types.Scene, 'em_settings')
    # bpy.types.Scene.em_settings = PointerProperty(type=EM_Other_Settings)

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

    # Object properties (need EM_epochs_belonging_ob from em_base_props)
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
    from .export_operators import exporter_graphml
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
    # NOTE: em_setup is registered separately BEFORE em_props in main register()
    core_independent_modules = [
        icons_manager,
        EMdb_excel,
        visual_manager,
        activity_manager,
        stratigraphy_manager,
        graph_editor,
        epoch_manager,
        paradata_manager,
        document_manager,
        anastylosis_manager,
        rm_manager,
        export_manager,
        em_statistics,
        graph2geometry,
        importer_graphml,
        exporter_heriverse,
        exporter_graphml,
        import_EMdb,
        graphml_converter,
        operators,
        cronofilter,
        thumb_operators,
        viewport_overlay,  # Viewport overlay for epoch/US display
        debug_graph_connections  # Debug operator
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

    # FASE 5: Tapestry Integration (experimental feature)
    try:
        tapestry_integration.register()
        logger.debug(f"Registered tapestry integration")
    except Exception as e:
        logger.error(f"Error registering tapestry integration: {e}")

    # FASE 6: Surface Areale system
    try:
        surface_areale.register()
        logger.debug(f"Registered surface areale system")
    except Exception as e:
        logger.error(f"Error registering surface areale: {e}")

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

    # Registra handler per validazione mapping
    if validate_mappings_on_load not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(validate_mappings_on_load)
        logger.info("Registered mapping validation handler")


def unregister_modules():
    """Unregister all modules in reverse dependency order"""
    if not MODULE_IMPORT_SUCCESS:
        logger.warning("Skipping module unregistration - modules not loaded")
        return
    
    from .export_operators import exporter_heriverse
    from .export_operators import exporter_graphml
    from .import_operators import importer_graphml, import_EMdb
    from .operators import graphml_converter
    from . import thumb_operators

    # Rimuovi handler per validazione mapping
    if validate_mappings_on_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(validate_mappings_on_load)
        logger.info("Removed mapping validation handler")

    # Rimuovi il keymap manager per primo
    if KEYMAP_MANAGER_LOADED:
        try:
            keymap_manager.unregister()
            logger.info("Keymap manager unregistered successfully")
        except Exception as e:
            logger.error(f"Error unregistering keymap manager: {e}")


    # FASE 0: Surface Areale (va rimosso per primo)
    try:
        surface_areale.unregister()
        logger.debug(f"Unregistered surface areale")
    except Exception as e:
        logger.warning(f"Error unregistering surface areale: {e}")

    # FASE 1: Tapestry Integration (va rimosso per primo - experimental feature)
    try:
        tapestry_integration.unregister()
        logger.debug(f"Unregistered tapestry integration")
    except Exception as e:
        logger.warning(f"Error unregistering tapestry integration: {e}")

    # FASE 2: Landscape system
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

    # Overlay in 3D View
    try:
        viewport_overlay.unregister()
        logger.debug(f"Unregistered viewport overlay")
    except Exception as e:
        logger.warning(f"Error unregistering viewport overlay: {e}")
    
    # FASE 4: Moduli core in ordine inverso
    core_modules = [
        debug_graph_connections,  # Debug operator
        thumb_operators,
        cronofilter,
        operators,
        graphml_converter,
        import_EMdb,
        exporter_graphml,
        exporter_heriverse,
        importer_graphml,
        graph2geometry,
        em_statistics,
        export_manager,
        rm_manager,
        anastylosis_manager,
        document_manager,
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

    # 0. Register base PropertyGroup classes FIRST (needed by em_props)
    if MODULE_IMPORT_SUCCESS:
        try:
            em_base_props.register()
            logger.info("✓ Registered em_base_props (base PropertyGroup classes)")
        except Exception as e:
            logger.error(f"✗ Error registering em_base_props: {e}")
            import traceback
            traceback.print_exc()

    # 1. Register remaining base property classes
    register_base_classes()

    # 2. Setup all properties
    # ⚠️ MIGRATION NOTE: Collections, indices, and most properties are now in em_tools
    # setup_scene_collections()  # ← Migrated to em_tools
    # setup_scene_indices()      # ← Migrated to em_tools
    # setup_scene_properties()   # ← Migrated to em_tools
    setup_pointer_properties()   # ← Still needed for Object and WindowManager properties

    # 3. Set graph reference
    bpy.types.Scene.em_graph = None

    # 4. Register em_setup FIRST (contains GraphMLFileItem needed by EM_Tools)
    if MODULE_IMPORT_SUCCESS:
        try:
            em_setup.register()
            logger.info("✓ Registered em_setup (AuxiliaryFileProperties, GraphMLFileItem, etc.)")
        except Exception as e:
            logger.error(f"✗ Error registering em_setup: {e}")
            import traceback
            traceback.print_exc()

    # 5. Register em_props AFTER em_setup (EM_Tools depends on GraphMLFileItem)
    if MODULE_IMPORT_SUCCESS:
        try:
            em_props.register()
            logger.info("✓ Registered em_props (PropertyGroup classes + Scene.em_tools)")
        except Exception as e:
            logger.error(f"✗ Error registering em_props: {e}")
            import traceback
            traceback.print_exc()

    # 6. Register all other modules in the correct order
    if MODULE_IMPORT_SUCCESS:
        register_modules()

    # 5. Register proxy_box_creator AFTER all other modules
    #    (needs Scene.em_tools to exist)
    if MODULE_IMPORT_SUCCESS:
        try:
            proxy_box_creator.register()
            logger.info("Registered proxy_box_creator")
        except Exception as e:
            logger.error(f"Error registering proxy_box_creator: {e}")
    
    # 7. Add menu items
    if MODULE_IMPORT_SUCCESS:
        bpy.types.VIEW3D_MT_mesh_add.append(functions.menu_func)

    # 8. ✅ OPTIMIZATION: Start performance optimization services
    if MODULE_IMPORT_SUCCESS:
        try:
            from . import thumb_async
            thumb_async.start_thumbnail_loader()
            logger.info("✓ Started async thumbnail loader")
        except Exception as e:
            logger.warning(f"✗ Could not start thumbnail loader: {e}")

        try:
            # Pre-warm caches for faster first access
            from . import graph_index, material_cache, object_cache
            logger.info("✓ Loaded optimization modules (graph_index, material_cache, object_cache)")
        except Exception as e:
            logger.warning(f"✗ Could not load optimization modules: {e}")

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

    # 2. Unregister proxy_box_creator FIRST (before other modules)
    if MODULE_IMPORT_SUCCESS:
        try:
            proxy_box_creator.unregister()
            logger.info("Unregistered proxy_box_creator")
        except Exception as e:
            logger.warning(f"Error unregistering proxy_box_creator: {e}")

    # 3. Unregister other modules
    if MODULE_IMPORT_SUCCESS:
        unregister_modules()

    # 4. Unregister em_props (removes Scene.em_tools)
    if MODULE_IMPORT_SUCCESS:
        try:
            em_props.unregister()
            logger.info("✓ Unregistered em_props")
        except Exception as e:
            logger.warning(f"✗ Error unregistering em_props: {e}")

    # 5. ✅ OPTIMIZATION: Stop performance optimization services
    if MODULE_IMPORT_SUCCESS:
        try:
            from . import thumb_async
            thumb_async.stop_thumbnail_loader()
            logger.info("✓ Stopped async thumbnail loader")
        except Exception as e:
            logger.warning(f"✗ Could not stop thumbnail loader: {e}")

        try:
            # Clear all caches
            from . import graph_index, material_cache, object_cache, debounce
            graph_index.clear_all_graph_indices()
            material_cache.clear_material_cache()
            object_cache.clear_object_cache()
            debounce.clear_debouncers()
            logger.info("✓ Cleared all optimization caches")
        except Exception as e:
            logger.warning(f"✗ Could not clear optimization caches: {e}")

    # 6. Unregister em_setup LAST (after em_props since EM_Tools depends on GraphMLFileItem)
    if MODULE_IMPORT_SUCCESS:
        try:
            em_setup.unregister()
            logger.info("✓ Unregistered em_setup")
        except Exception as e:
            logger.warning(f"✗ Error unregistering em_setup: {e}")
    
    # 5. Remove properties (utilizza il codice che hai già implementato)
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
    # ⚠️ MIGRATION NOTE: em_settings is now scene.em_tools.settings (removed with em_tools)
    # scene_pointer_props = [
    #     'em_settings',
    # ]
    #
    # for prop_name in scene_pointer_props:
    #     if hasattr(bpy.types.Scene, prop_name):
    #         delattr(bpy.types.Scene, prop_name)
    #         logger.debug(f"Removed Scene pointer property: {prop_name}")
    
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

    # Unregister em_base_props LAST (after everything else)
    if MODULE_IMPORT_SUCCESS:
        try:
            em_base_props.unregister()
            logger.info("✓ Unregistered em_base_props")
        except Exception as e:
            logger.warning(f"✗ Error unregistering em_base_props: {e}")

    logger.info("EM Tools unregistration complete")

if __name__ == "__main__":
    register()
