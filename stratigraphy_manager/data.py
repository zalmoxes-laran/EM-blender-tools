"""
Stratigraphy Manager Data Structures
====================================

✅ CLEAN VERSION - No legacy Scene properties
All properties are now in em_props.py under scene.em_tools.stratigraphy

This module contains:
- PropertyGroup class definitions (EMListItem, EMreusedUS)
- Empty registration functions (for module compatibility)
- Utility functions for data validation
"""

import bpy # type: ignore
from bpy.props import StringProperty, FloatProperty, BoolProperty # type: ignore
from bpy.types import PropertyGroup # type: ignore


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
    parent_node_id: StringProperty(
        name="Parent Node ID",
        description="Node ID of the container US (if this node is contained via is_part_of)",
        default=""
    ) # type: ignore
    is_container: BoolProperty(
        name="Is Container",
        description="True if this US contains other elements (has has_part edges)",
        default=False
    ) # type: ignore
    contained_in_name: StringProperty(
        name="Contained In",
        description="Name of the container US",
        default=""
    ) # type: ignore
    is_in_instance_chain: BoolProperty(
        name="In Instance Chain",
        description="True if this node has changed_from/changed_to edges",
        default=False
    ) # type: ignore
    instance_chain_node_ids: StringProperty(
        name="Instance Chain Node IDs",
        description="Comma-separated node IDs of all members in this instance chain",
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


# =====================================================
# UTILITY FUNCTIONS
# =====================================================

def ensure_valid_index(collection, index, show_popup=True):
    """
    Ensures that an index is valid for a given collection.
    Returns True if valid, False otherwise.
    
    Args:
        collection: Blender CollectionProperty
        index: Integer index to validate
        show_popup: Whether to show warning popup (default True)
    
    Returns:
        bool: True if index is valid, False otherwise
    """
    if not collection or len(collection) == 0:
        return False
        
    if index < 0 or index >= len(collection):
        if show_popup:
            # Note: popup would need context, so just print for now
            print(f"Warning: Index {index} out of range for collection with {len(collection)} items")
        return False
        
    return True


# =====================================================
# REGISTRATION FUNCTIONS
# =====================================================

def register_data():
    """
    Register Stratigraphy Manager data structures.
    
    ✅ CLEAN VERSION: All PropertyGroup classes and Scene properties 
    are now registered centrally in em_props.py.
    
    This function is kept for compatibility with the module registration
    system but does nothing.
    """
    pass  # Everything handled by em_props.py


def unregister_data():
    """
    Unregister Stratigraphy Manager data structures.
    
    ✅ CLEAN VERSION: All PropertyGroup classes and Scene properties
    are now unregistered centrally in em_props.py.
    
    This function is kept for compatibility with the module registration
    system but does nothing.
    """
    pass  # Everything handled by em_props.py