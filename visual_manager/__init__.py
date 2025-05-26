"""
Visual Manager - Central module for visualization, properties, and camera management
This module provides functionality for property-based coloring, camera management, 
and label creation within the Extended Matrix framework.
"""

import bpy

# Import local modules
from .data import register_data, unregister_data
from .ui import register_ui, unregister_ui
from .operators import register_operators, unregister_operators
from .label_tools import register_label_tools, unregister_label_tools

# Module info
__all__ = ['register', 'unregister']

def register():
    """Register all Visual Manager classes and properties."""
    # Register in proper dependency order
    register_data()
    register_operators()
    register_label_tools()
    register_ui()

def unregister():
    """Unregister all Visual Manager classes and properties."""
    # Unregister in reverse dependency order
    unregister_ui()
    unregister_label_tools()
    unregister_operators()
    unregister_data()