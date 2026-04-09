"""
Epoch Manager - Central module for managing archaeological epochs
This module provides functionality for viewing, filtering, and managing
time periods within the Extended Matrix framework.
"""

import bpy # type: ignore
from bpy.utils import register_class, unregister_class # type: ignore
from bpy.props import BoolProperty # type: ignore

# Import local modules
from .data import register_data, unregister_data
from .ui import register_ui, unregister_ui
from .operators import register_operators, unregister_operators
from .lighting import register_lighting, unregister_lighting

# Module info
__all__ = ['register', 'unregister']

def register():
    """Register all Epoch Manager classes and properties."""
    # Register in proper dependency order
    register_data()
    register_operators()
    register_lighting()
    register_ui()

    # Register properties that need to be on the Scene
    # These were previously in __init__.py but belong in this module
    bpy.types.Scene.show_epoch_details = BoolProperty(
        name="Show Epoch Details",
        description="Show/hide details of the selected epoch.",
        default=False
    )
    bpy.types.Scene.show_epoch_lighting = BoolProperty(
        name="Show Epoch Lighting",
        description="Show/hide epoch lighting settings.",
        default=False
    )

def unregister():
    """Unregister all Epoch Manager classes and properties."""
    # Remove properties
    if hasattr(bpy.types.Scene, "show_epoch_lighting"):
        del bpy.types.Scene.show_epoch_lighting
    if hasattr(bpy.types.Scene, "show_epoch_details"):
        del bpy.types.Scene.show_epoch_details

    # Unregister in reverse dependency order
    unregister_ui()
    unregister_lighting()
    unregister_operators()
    unregister_data()
