"""
EM-Tools Centralized Property Management - FINAL COMPLETE VERSION
==================================================================

This version includes ALL properties from EMToolsSettings needed by the entire add-on.
"""

import bpy
from bpy.props import (
    PointerProperty, CollectionProperty, IntProperty, BoolProperty, 
    StringProperty, EnumProperty
)
from bpy.types import PropertyGroup

# Import from submodules
from .proxy_box_creator.data import ProxyBoxSettings, ProxyBoxPointSettings
from .stratigraphy_manager.data import EMListItem, EMreusedUS
from .epoch_manager.data import EPOCHListItem, EMUSItem
from .visual_manager.data import ColorRampProperties, PropertyValueItem, CameraItem, LabelSettings

# Import from em_setup
from .em_setup import GraphMLFileItem, AuxiliaryFileProperties


# =====================================================
# MANAGER AGGREGATOR CLASSES
# =====================================================

class StratigraphyManagerProps(PropertyGroup):
    """Aggregates all stratigraphy-related properties"""
    
    units: CollectionProperty(
        type=EMListItem,
        name="Stratigraphic Units"
    )  # type: ignore
    
    units_index: IntProperty(
        name="Selected Unit Index",
        default=0
    )  # type: ignore
    
    reused: CollectionProperty(
        type=EMreusedUS,
        name="Reused Units"
    )  # type: ignore
    
    show_filter_system: BoolProperty(
        name="Show Filter System",
        default=False
    )  # type: ignore
    
    show_documents: BoolProperty(
        name="Show Documents",
        default=False
    )  # type: ignore
    
    preview_image: PointerProperty(
        type=bpy.types.Image,
        name="Preview Image"
    )  # type: ignore


class EpochManagerProps(PropertyGroup):
    """Aggregates all epoch-related properties"""
    
    list: CollectionProperty(
        type=EPOCHListItem,
        name="Epochs"
    )  # type: ignore
    
    list_index: IntProperty(
        name="Selected Epoch Index",
        default=0
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
        name="Show Epoch Details",
        default=False
    )  # type: ignore


class VisualManagerProps(PropertyGroup):
    """Aggregates all visual manager properties"""
    
    property_enum: StringProperty(
        name="Property Enum",
        default=""
    )  # type: ignore
    
    selected_property: StringProperty(
        name="Selected Property",
        default=""
    )  # type: ignore
    
    color_ramps: PointerProperty(
        type=ColorRampProperties,
        name="Color Ramps"
    )  # type: ignore


class AnastylosisManagerProps(PropertyGroup):
    """Aggregates all anastylosis manager properties"""
    pass  # Placeholder for future properties


class RMManagerProps(PropertyGroup):
    """Aggregates all RM manager properties"""
    pass  # Placeholder for future properties


# =====================================================
# MAIN CONTAINER CLASS
# =====================================================

class EM_Tools(PropertyGroup):
    """Central container for all EM Tools properties"""
    
    # ===== MODE FLAGS =====
    
    mode_em_advanced: BoolProperty(
        name="Advanced EM Mode",
        description="Enable Advanced Extended Matrix mode",
        default=True
    )  # type: ignore
    
    mode_landscape: BoolProperty(
        name="Landscape Mode",
        description="Enable Landscape visualization mode",
        default=False
    )  # type: ignore
    
    experimental_features: BoolProperty(
        name="Experimental Features",
        description="Enable experimental/development features",
        default=False
    )  # type: ignore
    
    show_advanced_tools: BoolProperty(
        name="Show Advanced Tools",
        description="Display advanced tools for managing GraphML files and objects",
        default=False
    )  # type: ignore
    
    # ===== 3D GIS MODE SETTINGS =====
    
    mode_3dgis_import_type: EnumProperty(
        name="3D GIS Import Type",
        items=[
            ('GENERIC_XLSX', "Generic XLSX", "Import from generic Excel file"),
            ('PYARCHINIT_DB', "pyArchInit DB", "Import from pyArchInit SQLite database")
        ],
        default='GENERIC_XLSX'
    )  # type: ignore
    
    generic_xlsx_file: StringProperty(
        name="XLSX File",
        description="Path to generic XLSX file for import",
        subtype='FILE_PATH',
        default=""
    )  # type: ignore
    
    pyarchinit_db_path: StringProperty(
        name="pyArchInit DB",
        description="Path to pyArchInit SQLite database",
        subtype='FILE_PATH',
        default=""
    )  # type: ignore
    
    # ===== GRAPHML FILES MANAGEMENT =====
    
    graphml_files: CollectionProperty(
        type=GraphMLFileItem,
        name="GraphML Files"
    )  # type: ignore
    
    active_file_index: IntProperty(
        name="Active GraphML File",
        description="Index of the currently active GraphML file",
        default=-1
    )  # type: ignore
    
    # ===== XLSX IMPORT SETTINGS =====
    
    xlsx_sheet_name: StringProperty(
        name="Sheet Name",
        description="Name of the Excel sheet to import",
        default=""
    )  # type: ignore
    
    xlsx_id_column: StringProperty(
        name="ID Column",
        description="Column name containing unique identifiers",
        default=""
    )  # type: ignore
    
    # ===== FEATURE MODULES =====
    
    stratigraphy: PointerProperty(
        type=StratigraphyManagerProps,
        name="Stratigraphy Manager"
    )  # type: ignore
    
    epochs: PointerProperty(
        type=EpochManagerProps,
        name="Epoch Manager"
    )  # type: ignore
    
    proxy_box: PointerProperty(
        type=ProxyBoxSettings,
        name="Proxy Box Creator"
    )  # type: ignore
    
    visual: PointerProperty(
        type=VisualManagerProps,
        name="Visual Manager"
    )  # type: ignore
    
    anastylosis: PointerProperty(
        type=AnastylosisManagerProps,
        name="Anastylosis Manager"
    )  # type: ignore
    
    rm: PointerProperty(
        type=RMManagerProps,
        name="RM Manager"
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
    AuxiliaryFileProperties,  # ← MUST be BEFORE GraphMLFileItem
    GraphMLFileItem,
    ProxyBoxSettings,
    
    # Manager aggregators SECOND
    # These use the Sub-PropertyGroups above
    StratigraphyManagerProps,
    EpochManagerProps,
    VisualManagerProps,
    AnastylosisManagerProps,
    RMManagerProps,
    
    # Main container LAST
    # This uses ALL the classes above
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