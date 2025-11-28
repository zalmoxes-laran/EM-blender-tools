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
from .stratigraphy_manager.data import EMListItem, EMreusedUS
from .epoch_manager.data import EPOCHListItem, EMUSItem
from .visual_manager.data import ColorRampProperties, PropertyValueItem, CameraItem, LabelSettings

# Import from em_setup
from .em_setup import GraphMLFileItem, AuxiliaryFileProperties


# =====================================================
# UPDATE CALLBACKS
# =====================================================

def update_stratigraphic_selection(self, context):
    """
    Called when the user changes the selection in the stratigraphic list.
    Updates paradata lists if streaming mode is enabled.
    """
    try:
        # Import here to avoid circular imports
        from .functions import switch_paradata_lists
        
        # Create dummy self object for compatibility with switch_paradata_lists signature
        class DummySelf:
            pass
        dummy = DummySelf()
        
        switch_paradata_lists(dummy, context)
    except Exception as e:
        print(f"Warning: Could not update paradata lists: {e}")


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
        name="Show Details",
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
    
    # Placeholder for anastylosis properties
    # Will be expanded as needed
    show_options: BoolProperty(
        name="Show Anastylosis Options",
        default=False
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
    
    experimental_features: BoolProperty(
        name="Experimental Features",
        description="Enable experimental and debug features",
        default=False
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