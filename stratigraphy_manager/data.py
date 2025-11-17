"""
Data structures for the Stratigraphy Manager
This module contains all PropertyGroup definitions and data structures
needed for the Stratigraphy Manager.

REFACTORED: PropertyGroup classes are registered ONLY by em_props.py
This file now handles ONLY Scene property attachment/removal.
"""

import bpy # type: ignore
from bpy.props import ( # type: ignore
    StringProperty,
    BoolProperty,
    FloatProperty,
    IntProperty,
    CollectionProperty,
    PointerProperty
)
from bpy.types import PropertyGroup # type: ignore


# =====================================================
# UTILITY FUNCTIONS
# =====================================================

def ensure_valid_index(collection_property, index_property_name, context=None, show_popup=True):
    """
    Ensures that the index for a collection property is valid.
    
    Args:
        collection_property: The collection property
        index_property_name: The name of the index property
        context: Blender context (optional)
        show_popup: Whether to show a popup when correcting the index
    """
    # Get the owner object that contains both properties
    owner = collection_property.id_data
    
    # Get current index value
    current_index = getattr(owner, index_property_name)
    
    # Check if collection is empty
    if len(collection_property) == 0:
        # Set index to -1 for empty collections
        setattr(owner, index_property_name, -1)
        print(f"Collection is empty, reset {index_property_name} to -1")
        return False
    
    # Check if index is out of range
    if current_index < 0 or current_index >= len(collection_property):
        # Reset to a valid index (first item)
        setattr(owner, index_property_name, 0)
        print(f"Index {current_index} out of range for collection (size {len(collection_property)}), reset to 0")
        
        # Report if context is provided AND show_popup is True
        if context and show_popup:
            bpy.context.window_manager.popup_menu(
                lambda self, ctx: self.layout.label(text=f"Reset {index_property_name} to valid value"),
                title="Index Out of Range",
                icon='INFO'
            )
            
    return True


# =====================================================
# PROPERTY GROUP CLASSES
# =====================================================
# NOTE: These classes are registered by em_props.py
# We only define them here for import by other modules

class EMListItem(PropertyGroup):
    """Information about a stratigraphic unit"""
    name: StringProperty(
        name="Name",
        description="Name of the stratigraphic unit",
        default="Untitled"
    ) # type: ignore
    id: StringProperty(
        name="id",
        description="Unique identifier",
        default=""
    ) # type: ignore
    node_id: StringProperty(
        name="Node ID",
        description="Node identifier in graph",
        default=""
    ) # type: ignore
    description: StringProperty(
        name="Description",
        description="Description of this unit",
        default=""
    ) # type: ignore
    icon: StringProperty(
        name="Icon",
        description="Icon code for UI display",
        default="RESTRICT_INSTANCED_ON"
    ) # type: ignore
    icon_db: StringProperty(
        name="Database Icon",
        description="Database icon code",
        default="DECORATE_ANIMATE"
    ) # type: ignore
    url: StringProperty(
        name="URL",
        description="URL associated with this unit",
        default=""
    ) # type: ignore
    shape: StringProperty(
        name="Shape",
        description="Shape of this unit",
        default=""
    ) # type: ignore
    y_pos: FloatProperty(
        name="Y Position",
        description="Y-axis position value",
        default=0.0
    ) # type: ignore
    epoch: StringProperty(
        name="Epoch",
        description="Associated epoch",
        default=""
    ) # type: ignore
    id_node: StringProperty(
        name="Node ID",
        description="Unique node identifier",
        default=""
    ) # type: ignore
    border_style: StringProperty(
        name="Border Style",
        description="Style of the border",
        default=""
    ) # type: ignore
    fill_color: StringProperty(
        name="Fill Color",
        description="Fill color code",
        default=""
    ) # type: ignore
    is_visible: BoolProperty(
        name="Visible",
        description="Whether this item is visible in the viewport",
        default=True
    ) # type: ignore
    node_type: StringProperty(
        name="Node Type",
        description="The type of this node",
        default=""
    ) # type: ignore


class EMreusedUS(PropertyGroup):
    """Information about reused stratigraphic units"""
    epoch: StringProperty(
        name="Epoch",
        description="Associated epoch",
        default="Untitled"
    ) # type: ignore
    em_element: StringProperty(
        name="EM Element",
        description="Associated EM element",
        default=""
    ) # type: ignore


def update_stratigraphic_selection(self, context):
    """
    Called when the user changes the selection in the stratigraphic list.
    Updates UI elements and can trigger filtering if needed.
    """
    scene = context.scene
    print(f"Stratigraphic selection changed to index {scene.em_list_index}")


# =====================================================
# REGISTRATION FUNCTIONS
# =====================================================

def register_data():
    """
    Register Stratigraphy Manager data structures.
    
    REFACTORED: PropertyGroup classes are registered by em_props.py
    This function now ONLY handles Scene property attachment.
    """
    # ❌ PropertyGroup registration rimosso (gestito da em_props.py)
    
    # ✅ SOLO Scene properties NON gestite da em_props
    # Setup collection properties if not yet existing
    if not hasattr(bpy.types.Scene, "em_list"):
        bpy.types.Scene.em_list = CollectionProperty(type=EMListItem)
    
    if not hasattr(bpy.types.Scene, "em_list_index"):
        bpy.types.Scene.em_list_index = IntProperty(
            name="Index for em_list",
            default=0,
            update=update_stratigraphic_selection
        )
    
    if not hasattr(bpy.types.Scene, "em_reused"):
        bpy.types.Scene.em_reused = CollectionProperty(type=EMreusedUS)

    bpy.types.Scene.show_filter_system = BoolProperty(
        name="Filter system", 
        description="Show/hide filter options",
        default=False
    )

    bpy.types.Scene.show_strat_documents = BoolProperty(
        name="Show documents", 
        description="Show/hide documents section",
        default=False
    )
    
    bpy.types.Scene.strat_preview_image = PointerProperty(type=bpy.types.Image)


def unregister_data():
    """
    Unregister Stratigraphy Manager data structures.
    
    REFACTORED: PropertyGroup classes are unregistered by em_props.py
    This function now ONLY handles Scene property removal.
    """
    # ✅ SOLO rimozione Scene properties
    if hasattr(bpy.types.Scene, "em_list"):
        del bpy.types.Scene.em_list
    
    if hasattr(bpy.types.Scene, "em_list_index"):
        del bpy.types.Scene.em_list_index
    
    if hasattr(bpy.types.Scene, "em_reused"):
        del bpy.types.Scene.em_reused

    if hasattr(bpy.types.Scene, "show_filter_system"):
        del bpy.types.Scene.show_filter_system

    if hasattr(bpy.types.Scene, "show_strat_documents"):
        del bpy.types.Scene.show_strat_documents
        
    if hasattr(bpy.types.Scene, "strat_preview_image"):
        del bpy.types.Scene.strat_preview_image
    
    # ❌ PropertyGroup unregistration rimosso (gestito da em_props.py)