"""
Epoch Manager - Central module for managing archaeological epochs
This module provides functionality for viewing, filtering, and managing
time periods within the Extended Matrix framework.
"""

import bpy
from bpy.utils import register_class, unregister_class
from bpy.props import BoolProperty

# Import local modules
from .data import register_data, unregister_data
from .ui import register_ui, unregister_ui
from .operators import register_operators, unregister_operators

# Module info
__all__ = ['register', 'unregister']

def register():
    """Register all Epoch Manager classes and properties."""
    # Register in proper dependency order
    register_data()
    register_operators()
    register_ui()
    
    # Register properties that need to be on the Scene
    # These were previously in __init__.py but belong in this module
    bpy.types.Scene.show_epoch_details = BoolProperty(
        name="Show Epoch Details",
        description="Show/hide details of the selected epoch.",
        default=False
    )

def unregister():
    """Unregister all Epoch Manager classes and properties."""
    # Remove properties
    if hasattr(bpy.types.Scene, "show_epoch_details"):
        del bpy.types.Scene.show_epoch_details
    
    # Unregister in reverse dependency order
    unregister_ui()
    unregister_operators()
    unregister_data()
