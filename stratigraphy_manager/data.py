"""
Data structures for the Stratigraphy Manager
This module contains all PropertyGroup definitions and data structures
needed for the Stratigraphy Manager.
"""

import bpy
from bpy.props import (
    StringProperty,
    BoolProperty,
    FloatProperty,
    IntProperty,
    CollectionProperty,
    PointerProperty
)
from bpy.types import PropertyGroup

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
            import bpy
            bpy.context.window_manager.popup_menu(
                lambda self, ctx: self.layout.label(text=f"Reset {index_property_name} to valid value"),
                title="Index Out of Range",
                icon='INFO'
            )
            
    return True


class EMListItem(PropertyGroup):
    """Stratigraphic unit information"""
    name: StringProperty(
        name="Name",
        description="Name of this stratigraphic unit",
        default="Untitled"
    )
    description: StringProperty(
        name="Description",
        description="Description of this stratigraphic unit",
        default=""
    )
    icon: StringProperty(
        name="Icon",
        description="Icon code for UI display",
        default="RESTRICT_INSTANCED_ON"
    )
    icon_db: StringProperty(
        name="Database Icon",
        description="Database icon code",
        default="DECORATE_ANIMATE"
    )
    url: StringProperty(
        name="URL",
        description="URL associated with this unit",
        default=""
    )
    shape: StringProperty(
        name="Shape",
        description="Shape of this unit",
        default=""
    )
    y_pos: FloatProperty(
        name="Y Position",
        description="Y-axis position value",
        default=0.0
    )
    epoch: StringProperty(
        name="Epoch",
        description="Associated epoch",
        default=""
    )
    id_node: StringProperty(
        name="Node ID",
        description="Unique node identifier",
        default=""
    )
    border_style: StringProperty(
        name="Border Style",
        description="Style of the border",
        default=""
    )
    fill_color: StringProperty(
        name="Fill Color",
        description="Fill color code",
        default=""
    )
    is_visible: BoolProperty(
        name="Visible",
        description="Whether this item is visible in the viewport",
        default=True
    )
    node_type: StringProperty(
        name="Node Type",
        description="The type of this node",
        default=""
    )

class EMreusedUS(PropertyGroup):
    """Information about reused stratigraphic units"""
    epoch: StringProperty(
        name="Epoch",
        description="Associated epoch",
        default="Untitled"
    )
    em_element: StringProperty(
        name="EM Element",
        description="Associated EM element",
        default=""
    )

def register_data():
    """Register all data classes."""
    classes = [
        EMListItem,
        EMreusedUS,
    ]
    
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except ValueError:
            # Class might already be registered
            pass
            
    # Setup collection properties if not yet existing
    if not hasattr(bpy.types.Scene, "em_list"):
        bpy.types.Scene.em_list = CollectionProperty(type=EMListItem)
    
    if not hasattr(bpy.types.Scene, "em_list_index"):
        bpy.types.Scene.em_list_index = IntProperty(
            name="Index for em_list",
            default=0,
            update=lambda self, context: None  # Will be updated to call filters
        )
    
    if not hasattr(bpy.types.Scene, "em_reused"):
        bpy.types.Scene.em_reused = CollectionProperty(type=EMreusedUS)

def unregister_data():
    """Unregister all data classes."""
    # Remove collection properties
    if hasattr(bpy.types.Scene, "em_list"):
        del bpy.types.Scene.em_list
    
    if hasattr(bpy.types.Scene, "em_list_index"):
        del bpy.types.Scene.em_list_index
    
    if hasattr(bpy.types.Scene, "em_reused"):
        del bpy.types.Scene.em_reused
    
    # Unregister classes in reverse order
    classes = [
        EMreusedUS,
        EMListItem,
    ]
    
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except ValueError:
            # Class might already be unregistered
            pass
