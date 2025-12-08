"""
EM-Tools Centralized Property Management - CLEAN VERSION
=========================================================

✅ CLEAN: No legacy properties, single source of truth
All properties for the entire add-on are defined here under scene.em_tools

This module includes:
- StratigraphyManagerProps - Stratigraphy manager properties
- EpochManagerProps - Epoch manager properties  
- VisualManagerProps - Visual manager properties
- AnastylosisManagerProps - Anastylosis manager properties
- RMManagerProps - RM (Representation Model) manager properties
- EM_Tools - Main container PropertyGroup
"""

import bpy
from bpy.props import (
    PointerProperty, CollectionProperty, IntProperty, BoolProperty, 
    StringProperty, EnumProperty, FloatProperty, FloatVectorProperty
)
from bpy.types import PropertyGroup

# Import from submodules
from .proxy_box_creator.data import ProxyBoxSettings, ProxyBoxPointSettings
from .anastylosis_manager import AnastylisisItem, AnastylisisSettings, AnastylosisSFNodeItem
from .stratigraphy_manager.data import EMListItem, EMreusedUS
from .epoch_manager.data import EPOCHListItem, EMUSItem
from .visual_manager.data import ColorRampProperties, PropertyValueItem, CameraItem, LabelSettings

# Import from em_setup
from .em_setup import GraphMLFileItem, AuxiliaryFileProperties
from .em_setup.properties import get_emdb_mappings, get_pyarchinit_mappings

# Import base PropertyGroup classes
from .em_base_props import EMviqListErrors, EDGESListItem, EMListParadata, EM_Other_Settings


# =====================================================
# UPDATE CALLBACKS
# =====================================================

def update_stratigraphic_selection(self, context):
    """
    Called when the user changes the selection in the stratigraphic list.
    Updates paradata lists if streaming mode is enabled.
    Pre-loads thumbnails for the selected US to avoid UI lag.
    """
    try:
        # Pre-load thumbnails for the selected US (only if needed)
        scene = context.scene
        strat = scene.em_tools.stratigraphy

        if strat.units and strat.units_index >= 0:
            selected_us = strat.units[strat.units_index]
            if selected_us.id_node:
                # Import here to avoid circular imports
                from .thumb_utils import reload_doc_previews_for_us
                # This will use cache if available, otherwise load once
                reload_doc_previews_for_us(selected_us.id_node)

        # Import here to avoid circular imports
        from .functions import switch_paradata_lists

        # Create dummy self object for compatibility with switch_paradata_lists signature
        class DummySelf:
            pass
        dummy = DummySelf()

        switch_paradata_lists(dummy, context)
    except Exception as e:
        print(f"Warning: Could not update paradata lists: {e}")


def update_paradata_streaming(self, context):
    """Called when paradata streaming mode changes"""
    try:
        from .functions import switch_paradata_lists
        class DummySelf:
            pass
        switch_paradata_lists(DummySelf(), context)
    except Exception as e:
        print(f"Warning: Could not update paradata lists: {e}")


def update_stream_properties(self, context):
    """Called when property streaming settings change"""
    try:
        from .functions import stream_properties
        class DummySelf:
            pass
        stream_properties(DummySelf(), context)
    except Exception as e:
        print(f"Warning: Could not stream properties: {e}")


def update_stream_extractors(self, context):
    """Called when extractor streaming settings change"""
    try:
        from .functions import stream_extractors
        class DummySelf:
            pass
        stream_extractors(DummySelf(), context)
    except Exception as e:
        print(f"Warning: Could not stream extractors: {e}")


def update_stream_combiners(self, context):
    """Called when combiner streaming settings change"""
    try:
        from .functions import stream_combiners
        class DummySelf:
            pass
        stream_combiners(DummySelf(), context)
    except Exception as e:
        print(f"Warning: Could not stream combiners: {e}")


def update_proxy_shader_mode(self, context):
    """Called when proxy shader mode changes"""
    try:
        from .functions import proxy_shader_mode_function
        class DummySelf:
            pass
        proxy_shader_mode_function(DummySelf(), context)
    except Exception as e:
        print(f"Warning: Could not update proxy shader mode: {e}")


def update_proxy_display(self, context):
    """Called when proxy display alpha changes"""
    try:
        from .functions import update_display_mode
        class DummySelf:
            pass
        update_display_mode(DummySelf(), context)
    except Exception as e:
        print(f"Warning: Could not update proxy display: {e}")


def update_epoch_index(self, context):
    """Called when epoch list index changes"""
    scene = context.scene
    # Usa il toggle di filtro presente sulla scena
    if getattr(scene, "filter_by_epoch", False):
        try:
            if hasattr(bpy.ops, 'em') and hasattr(bpy.ops.em, 'filter_lists'):
                bpy.ops.em.filter_lists()
        except Exception as e:
            print(f"Warning: Could not re-filter after epoch change: {e}")


# =====================================================
# ENUM CALLBACKS FOR DYNAMIC PROPERTIES
# =====================================================

def get_doc_previews_enum_items(self, context):
    """
    Callback for EnumProperty that returns document previews for selected US.
    Used by template_icon_view() in Gallery mode.

    Returns:
        List of tuples: (identifier, name, description, icon_id, index)
    """
    try:
        # Import here to avoid circular dependency
        from .thumb_utils import reload_doc_previews_for_us

        scene = context.scene
        strat = scene.em_tools.stratigraphy

        # If no US selected, return empty list
        if not strat.units or strat.units_index < 0:
            return []

        selected_us = strat.units[strat.units_index]

        # Get thumbnails using existing function
        enum_items = reload_doc_previews_for_us(selected_us.id_node)

        return enum_items if enum_items else []

    except Exception as e:
        print(f"Error in get_doc_previews_enum_items: {e}")
        import traceback
        traceback.print_exc()
        return []


# =====================================================
# MANAGER AGGREGATOR CLASSES
# =====================================================

class StratigraphyManagerProps(PropertyGroup):
    """
    Aggregates all stratigraphy-related properties.
    
    ✅ CLEAN VERSION: This is the ONLY place for stratigraphy properties.
    No more scene.em_list, scene.em_list_index, etc.
    """
    
    units: CollectionProperty(
        type=EMListItem,
        name="Stratigraphic Units",
        description="List of stratigraphic units from the active graph"
    )  # type: ignore
    
    units_index: IntProperty(
        name="Selected Unit Index",
        description="Index of the currently selected stratigraphic unit",
        default=0,
        update=update_stratigraphic_selection  # ✅ Callback for paradata updates
    )  # type: ignore
    
    reused: CollectionProperty(
        type=EMreusedUS,
        name="Reused Units",
        description="List of stratigraphic units that are reused across epochs"
    )  # type: ignore
    
    show_filter_system: BoolProperty(
        name="Show Filter System",
        description="Show/hide the filter system UI",
        default=False
    )  # type: ignore
    
    show_documents: BoolProperty(
        name="Show Documents",
        description="Show/hide the documents section",
        default=False
    )  # type: ignore

    documents_view_mode: EnumProperty(
        name="Documents View Mode",
        description="How to display document thumbnails",
        items=[
            ('OFF', "Preview OFF", "Don't show document previews", 'CANCEL', 0),
            ('LIST', "List", "Show documents as a list with small thumbnails", 'LINENUMBERS_ON', 1),
            ('GALLERY', "Gallery", "Show documents as a large gallery grid", 'IMAGE_DATA', 2),
        ],
        default='LIST'
    )  # type: ignore

    selected_document: EnumProperty(
        name="Selected Document",
        description="Currently selected document in gallery view",
        items=get_doc_previews_enum_items
    )  # type: ignore

    preview_image: PointerProperty(
        type=bpy.types.Image,
        name="Preview Image",
        description="Image used for document thumbnail preview"
    )  # type: ignore


class EpochManagerProps(PropertyGroup):
    """Aggregates all epoch-related properties"""

    list: CollectionProperty(
        type=EPOCHListItem,
        name="Epochs"
    )  # type: ignore

    list_index: IntProperty(
        name="Selected Epoch Index",
        default=0,
        update=update_epoch_index
    )  # type: ignore

    selected_us_list: CollectionProperty(
        type=EMUSItem,
        name="Selected Epoch Units"
    )  # type: ignore

    selected_us_index: IntProperty(
        name="Selected US Index",
        default=0
    )  # type: ignore

    show_details: BoolProperty(
        name="Show Details",
        default=False
    )  # type: ignore

    # Filtering options
    filter_by_epoch: BoolProperty(
        name="Filter by Epoch",
        description="Filter lists by selected epoch",
        default=False
    )  # type: ignore

    filter_by_activity: BoolProperty(
        name="Filter by Activity",
        description="Filter lists by activity type",
        default=False
    )  # type: ignore


class VisualManagerProps(PropertyGroup):
    """Aggregates all visual manager properties"""
    
    # Property list for visual representation
    properties_list: CollectionProperty(
        type=PropertyValueItem,
        name="Properties"
    )  # type: ignore
    
    properties_index: IntProperty(
        name="Selected Property Index",
        default=0
    )  # type: ignore
    
    # Color ramp settings
    color_ramp: PointerProperty(
        type=ColorRampProperties,
        name="Color Ramp"
    )  # type: ignore
    
    # Camera settings
    cameras: CollectionProperty(
        type=CameraItem,
        name="Cameras"
    )  # type: ignore
    
    cameras_index: IntProperty(
        name="Selected Camera Index",
        default=0
    )  # type: ignore
    
    # Label settings
    labels: PointerProperty(
        type=LabelSettings,
        name="Label Settings"
    )  # type: ignore
    
    # UI state
    show_color_options: BoolProperty(
        name="Show Color Options",
        default=False
    )  # type: ignore
    
    show_camera_options: BoolProperty(
        name="Show Camera Options",
        default=False
    )  # type: ignore


class AnastylosisManagerProps(PropertyGroup):
    """Aggregates all anastylosis-related properties"""
    
    show_options: BoolProperty(
        name="Show Anastylosis Options",
        default=False
    )  # type: ignore

    list: CollectionProperty(
        type=AnastylisisItem,
        name="Anastylosis List",
        description="All RMSF objects tracked for anastylosis"
    )  # type: ignore

    list_index: IntProperty(
        name="Anastylosis Index",
        description="Active index for the anastylosis list",
        default=0
    )  # type: ignore

    settings: PointerProperty(
        type=AnastylisisSettings,
        name="Anastylosis Settings",
        description="Display and interaction settings for anastylosis"
    )  # type: ignore

    sf_nodes: CollectionProperty(
        type=AnastylosisSFNodeItem,
        name="Available SpecialFind Nodes",
        description="Temporary list of SpecialFind/VirtualSpecialFind nodes used during linking"
    )  # type: ignore

    temp_obj_name: StringProperty(
        name="Temp Object Name",
        description="Temporary object name used during SpecialFind linking",
        default=""
    )  # type: ignore

    temp_rmsf_id: StringProperty(
        name="Temp RMSF ID",
        description="Temporary RMSF node id used during SpecialFind linking",
        default=""
    )  # type: ignore


class RMManagerProps(PropertyGroup):
    """Aggregates all RM (Representation Model) properties"""
    
    # Placeholder for RM properties
    # Will be expanded as needed
    show_options: BoolProperty(
        name="Show RM Options",
        default=False
    )  # type: ignore


# =====================================================
# MAIN CONTAINER CLASS
# =====================================================

class EM_Tools(PropertyGroup):
    """
    Main container for ALL EM-Tools properties.
    
    ✅ SINGLE SOURCE OF TRUTH: Everything is under scene.em_tools
    
    This PropertyGroup is attached to bpy.types.Scene as 'em_tools'
    and provides centralized access to all add-on properties.
    
    Usage:
        scene = context.scene
        em_tools = scene.em_tools
        
        # Access stratigraphy
        strat = em_tools.stratigraphy
        units = strat.units
        selected_index = strat.units_index
        
        # Access epochs
        epochs = em_tools.epochs.list
        
        # Access visual manager
        visual = em_tools.visual
        
        # etc.
    """
    
    # ============================================
    # MANAGER CONTAINERS
    # ============================================
    
    stratigraphy: PointerProperty(
        type=StratigraphyManagerProps,
        name="Stratigraphy Manager",
        description="All stratigraphy-related properties"
    )  # type: ignore
    
    epochs: PointerProperty(
        type=EpochManagerProps,
        name="Epoch Manager",
        description="All epoch-related properties"
    )  # type: ignore
    
    visual: PointerProperty(
        type=VisualManagerProps,
        name="Visual Manager",
        description="All visual representation properties"
    )  # type: ignore
    
    anastylosis: PointerProperty(
        type=AnastylosisManagerProps,
        name="Anastylosis Manager",
        description="All anastylosis-related properties"
    )  # type: ignore
    
    rm: PointerProperty(
        type=RMManagerProps,
        name="RM Manager",
        description="All representation model properties"
    )  # type: ignore
    
    proxy_box: PointerProperty(
        type=ProxyBoxSettings,
        name="Proxy Box Creator",
        description="Proxy box creation settings"
    )  # type: ignore
    
    # ============================================
    # GRAPHML FILE MANAGEMENT
    # ============================================
    
    graphml_files: CollectionProperty(
        type=GraphMLFileItem,
        name="GraphML Files",
        description="List of GraphML files in this project"
    )  # type: ignore
    
    active_file_index: IntProperty(
        name="Active File Index",
        description="Index of the currently active GraphML file",
        default=-1
    )  # type: ignore
    
    # ============================================
    # GLOBAL SETTINGS
    # ============================================

    mode_em_advanced: BoolProperty(
        name="EM Advanced Mode",
        description="Switch between 3D GIS mode and EM advanced mode",
        default=True
    )  # type: ignore

    show_advanced_tools: BoolProperty(
        name="Show Advanced Tools",
        description="Display advanced tools for managing GraphML files and objects",
        default=False
    )  # type: ignore

    show_collection_manager: BoolProperty(
        name="Show Collection Manager",
        description="Toggle the Collection Manager section in the setup panel",
        default=False,
    )  # type: ignore

    experimental_features: BoolProperty(
        name="Experimental Features",
        description="Enable experimental and debug features",
        default=False
    )  # type: ignore

    mode_3dgis_import_type: EnumProperty(
        name="Import Type",
        description="Select the 3D GIS import format",
        items=[
            ("generic_xlsx", "Generic Excel", "Import from a generic Excel file"),
            ("pyarchinit", "pyArchInit", "Import from a pyArchInit SQLite database"),
            ("emdb_xlsx", "EMdb Excel", "Import from EMdb Excel format"),
        ],
        default="generic_xlsx",
    )  # type: ignore

    landscape_mode: BoolProperty(
        name="Landscape Mode",
        description="Enable landscape mode for viewing multiple graphs",
        default=False
    )  # type: ignore

    multigraph_mode: BoolProperty(
        name="Multigraph Mode",
        description="Enable multigraph mode for handling multiple graphs simultaneously",
        default=False
    )  # type: ignore

    # ✅ XLSX/EMdb import properties
    generic_xlsx_file: StringProperty(
        name="Excel File",
        description="Path to generic Excel file",
        subtype='FILE_PATH',
        options={'PATH_SUPPORTS_BLEND_RELATIVE'} if bpy.app.version >= (4, 5, 0) else set()
    )  # type: ignore

    xlsx_sheet_name: StringProperty(
        name="Sheet Name",
        description="Name of the Excel sheet containing the data",
        default="Sheet1"
    )  # type: ignore

    xlsx_id_column: StringProperty(
        name="ID Column",
        description="Name of the column containing unique IDs",
        default="ID"
    )  # type: ignore

    emdb_xlsx_file: StringProperty(
        name="EMdb Excel File",
        description="Path to EMdb Excel file",
        subtype='FILE_PATH',
        options={'PATH_SUPPORTS_BLEND_RELATIVE'} if bpy.app.version >= (4, 5, 0) else set()
    )  # type: ignore

    emdb_mapping: EnumProperty(
        name="EMdb Format",
        description="Select EMdb format",
        items=lambda self, context: get_emdb_mappings(),
    )  # type: ignore

    pyarchinit_db_path: StringProperty(
        name="pyArchInit DB",
        description="Path to pyArchInit SQLite database",
        subtype='FILE_PATH',
        options={'PATH_SUPPORTS_BLEND_RELATIVE'} if bpy.app.version >= (4, 5, 0) else set(),
    )  # type: ignore

    pyarchinit_table: EnumProperty(
        name="Table",
        items=[
            ('US', 'US', 'Unità Stratigrafiche'),
            ('SITE', 'Site', 'Siti'),
            ('PERIODIZATION', 'Periodization', 'Periodizzazione'),
        ],
        default='US',
    )  # type: ignore

    pyarchinit_mapping: EnumProperty(
        name="pyArchInit Mapping",
        description="Select pyArchInit table mapping",
        items=get_pyarchinit_mappings,
    )  # type: ignore

    # ============================================
    # PARADATA COLLECTIONS & INDICES
    # ============================================

    # Error list
    emviq_error_list: CollectionProperty(
        type=EMviqListErrors,
        name="EMviq Errors",
        description="List of errors during EMviq export"
    )  # type: ignore

    emviq_error_list_index: IntProperty(
        name="Error List Index",
        default=0,
        update=update_paradata_streaming
    )  # type: ignore

    # Edges list
    edges_list: CollectionProperty(
        type=EDGESListItem,
        name="Edges",
        description="List of graph edges"
    )  # type: ignore

    edges_list_index: IntProperty(
        name="Edges List Index",
        default=0
    )  # type: ignore

    # Sources paradata (non-streaming)
    em_sources_list: CollectionProperty(
        type=EMListParadata,
        name="Sources",
        description="List of source paradata nodes"
    )  # type: ignore

    em_sources_list_index: IntProperty(
        name="Sources Index",
        default=0
    )  # type: ignore

    # Properties paradata (non-streaming)
    em_properties_list: CollectionProperty(
        type=EMListParadata,
        name="Properties",
        description="List of property paradata nodes"
    )  # type: ignore

    em_properties_list_index: IntProperty(
        name="Properties Index",
        default=0
    )  # type: ignore

    # Extractors paradata (non-streaming)
    em_extractors_list: CollectionProperty(
        type=EMListParadata,
        name="Extractors",
        description="List of extractor paradata nodes"
    )  # type: ignore

    em_extractors_list_index: IntProperty(
        name="Extractors Index",
        default=0
    )  # type: ignore

    # Combiners paradata (non-streaming)
    em_combiners_list: CollectionProperty(
        type=EMListParadata,
        name="Combiners",
        description="List of combiner paradata nodes"
    )  # type: ignore

    em_combiners_list_index: IntProperty(
        name="Combiners Index",
        default=0
    )  # type: ignore

    # Versioned/streaming sources
    em_v_sources_list: CollectionProperty(
        type=EMListParadata,
        name="Versioned Sources",
        description="List of source paradata for selected unit (streaming mode)"
    )  # type: ignore

    em_v_sources_list_index: IntProperty(
        name="Versioned Sources Index",
        default=0
    )  # type: ignore

    # Versioned/streaming properties
    em_v_properties_list: CollectionProperty(
        type=EMListParadata,
        name="Versioned Properties",
        description="List of property paradata for selected unit (streaming mode)"
    )  # type: ignore

    em_v_properties_list_index: IntProperty(
        name="Versioned Properties Index",
        default=0,
        update=update_stream_properties
    )  # type: ignore

    # Versioned/streaming extractors
    em_v_extractors_list: CollectionProperty(
        type=EMListParadata,
        name="Versioned Extractors",
        description="List of extractor paradata for selected unit (streaming mode)"
    )  # type: ignore

    em_v_extractors_list_index: IntProperty(
        name="Versioned Extractors Index",
        default=0,
        update=update_stream_extractors
    )  # type: ignore

    # Versioned/streaming combiners
    em_v_combiners_list: CollectionProperty(
        type=EMListParadata,
        name="Versioned Combiners",
        description="List of combiner paradata for selected unit (streaming mode)"
    )  # type: ignore

    em_v_combiners_list_index: IntProperty(
        name="Versioned Combiners Index",
        default=0,
        update=update_stream_combiners
    )  # type: ignore

    # Legacy index (already migrated but kept for reference)
    em_list_index: IntProperty(
        name="Legacy EM List Index",
        description="Legacy index property - should not be used",
        default=0
    )  # type: ignore

    # Epoch US list for selection
    selected_epoch_us_list_index: IntProperty(
        name="Selected Epoch US Index",
        default=0
    )  # type: ignore

    # ============================================
    # PARADATA STREAMING MODE SETTINGS
    # ============================================

    paradata_streaming_mode: BoolProperty(
        name="Paradata Streaming Mode",
        description="Enable/disable tables streaming mode",
        default=True,
        update=update_paradata_streaming
    )  # type: ignore

    prop_paradata_streaming_mode: BoolProperty(
        name="Properties Paradata Streaming Mode",
        description="Enable/disable property table streaming mode",
        default=True,
        update=update_stream_properties
    )  # type: ignore

    comb_paradata_streaming_mode: BoolProperty(
        name="Combiners Paradata Streaming Mode",
        description="Enable/disable combiner table streaming mode",
        default=True,
        update=update_stream_combiners
    )  # type: ignore

    extr_paradata_streaming_mode: BoolProperty(
        name="Extractors Paradata Streaming Mode",
        description="Enable/disable extractor table streaming mode",
        default=True,
        update=update_stream_extractors
    )  # type: ignore

    # ============================================
    # PROXY DISPLAY SETTINGS
    # ============================================

    proxy_shader_mode: BoolProperty(
        name="Proxy Shader Mode",
        description="Enable additive shader for proxies",
        default=True,
        update=update_proxy_shader_mode
    )  # type: ignore

    proxy_display_mode: StringProperty(
        name="Proxy Display Mode",
        description="Proxy display mode",
        default="select"
    )  # type: ignore

    proxy_blend_mode: StringProperty(
        name="Proxy Blend Mode",
        description="Proxy blend mode",
        default="BLEND"
    )  # type: ignore

    proxy_display_alpha: FloatProperty(
        name="Proxy Alpha",
        description="The alpha value for proxies",
        min=0.0,
        max=1.0,
        default=0.5,
        update=update_proxy_display
    )  # type: ignore

    # Proxy inflate settings
    proxy_inflate_thickness: FloatProperty(
        name="Thickness",
        description="Thickness value for the Solidify modifier",
        default=0.01,
        min=0.0001,
        soft_max=0.1,
        unit='LENGTH'
    )  # type: ignore

    proxy_inflate_offset: FloatProperty(
        name="Offset",
        description="Offset value for the Solidify modifier",
        default=0.0,
        min=-1.0,
        max=1.0
    )  # type: ignore

    proxy_auto_inflate_on_export: BoolProperty(
        name="Auto-Inflate on Export",
        description="Automatically add inflation to proxies without it during export",
        default=False
    )  # type: ignore

    # ============================================
    # PARADATA AUTO-UPDATE SETTING
    # ============================================

    paradata_auto_update: BoolProperty(
        name="Auto Update Paradata",
        description="Automatically update paradata lists when selection changes",
        default=True
    )  # type: ignore

    # ============================================
    # GRAPHML FILE & PROJECT SETTINGS
    # ============================================

    EM_file: StringProperty(
        name="GraphML File",
        description="Path to the EM GraphML file",
        default=""
    )  # type: ignore

    # ============================================
    # EMVIQ EXPORT SETTINGS
    # ============================================

    EMviq_folder: StringProperty(
        name="EMviq Export Folder",
        description="Path to export the EMviq collection",
        default=""
    )  # type: ignore

    EMviq_scene_folder: StringProperty(
        name="EMviq Scene Folder",
        description="Path to export the EMviq scene",
        default=""
    )  # type: ignore

    EMviq_project_name: StringProperty(
        name="EMviq Project Name",
        description="Name of the EMviq project",
        default=""
    )  # type: ignore

    EMviq_user_name: StringProperty(
        name="EMviq User Name",
        description="Name of the EMviq user",
        default=""
    )  # type: ignore

    EMviq_user_password: StringProperty(
        name="EMviq User Password",
        description="Password of the EMviq user",
        default=""
    )  # type: ignore

    EMviq_model_author_name: StringProperty(
        name="Model Author Name",
        description="Name of the author(s) of the models",
        default=""
    )  # type: ignore

    # ============================================
    # ATON FRAMEWORK SETTINGS
    # ============================================

    ATON_path: StringProperty(
        name="ATON Path",
        description="Path to the ATON framework (root folder)",
        default=""
    )  # type: ignore

    # ============================================
    # EXPORT QUALITY SETTINGS
    # ============================================

    EM_gltf_export_quality: IntProperty(
        name="Export Quality",
        description="Quality of the output images",
        default=100
    )  # type: ignore

    EM_gltf_export_maxres: IntProperty(
        name="Export Max Resolution",
        description="Maximum resolution of the output images",
        default=4096
    )  # type: ignore

    # ============================================
    # OTHER SETTINGS POINTER
    # ============================================

    # Other general settings
    settings: PointerProperty(
        type=EM_Other_Settings,
        name="Other Settings",
        description="General EM Tools settings"
    )  # type: ignore


# =====================================================
# REGISTRATION
# =====================================================

classes = (
    # ⚠️ CRITICAL ORDER: Sub-PropertyGroups FIRST
    # These are used by Manager aggregators and EM_Tools
    ProxyBoxPointSettings,
    EMListItem,
    EMreusedUS,
    EPOCHListItem,
    EMUSItem,
    ColorRampProperties,
    PropertyValueItem,
    CameraItem,
    LabelSettings,
    AnastylisisItem,
    AnastylisisSettings,
    AnastylosisSFNodeItem,
    # NOTE: AuxiliaryFileProperties and GraphMLFileItem are registered by em_setup module
    # to avoid circular imports (em_setup needs them, EM_Tools uses them)
    ProxyBoxSettings,

    # Manager aggregators SECOND
    # These use the Sub-PropertyGroups above
    StratigraphyManagerProps,
    EpochManagerProps,
    VisualManagerProps,
    AnastylosisManagerProps,
    RMManagerProps,

    # Main container LAST
    # This uses ALL the classes above (including AuxiliaryFileProperties and GraphMLFileItem from em_setup)
    EM_Tools,
)


def register():
    """Register all PropertyGroup classes and attach EM_Tools to Scene"""
    print("[em_props] Starting registration...")

    for cls in classes:
        try:
            bpy.utils.register_class(cls)
            print(f"[em_props] ✓ Registered {cls.__name__}")
        except ValueError as e:
            print(f"[em_props] ⚠ Warning: Could not register {cls.__name__}: {e}")

    # Attach to Scene
    bpy.types.Scene.em_tools = PointerProperty(
        type=EM_Tools,
        name="EM Tools",
        description="Extended Matrix Tools - Central property container"
    )

    print("[em_props] ✓ Attached Scene.em_tools")
    print("[em_props] ✓ Registration complete")


def unregister():
    """Unregister all PropertyGroup classes and remove Scene.em_tools"""
    print("[em_props] Starting unregistration...")
    
    # Remove from Scene first
    if hasattr(bpy.types.Scene, "em_tools"):
        del bpy.types.Scene.em_tools
        print("[em_props] ✓ Removed Scene.em_tools")
    
    # Unregister classes in reverse order
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
            print(f"[em_props] ✓ Unregistered {cls.__name__}")
        except RuntimeError as e:
            print(f"[em_props] ⚠ Warning: Could not unregister {cls.__name__}: {e}")
    
    print("[em_props] ✓ Unregistration complete")
