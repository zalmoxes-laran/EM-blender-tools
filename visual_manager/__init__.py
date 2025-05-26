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
    print("=== REGISTERING VISUAL MANAGER ===")
    
    # Register in proper dependency order
    print("Registering visual manager data...")
    register_data()
    
    print("Registering visual manager operators...")
    register_operators()
    
    print("Registering visual manager label tools...")
    register_label_tools()
    
    print("Registering visual manager UI...")
    register_ui()
    
    print("=== VISUAL MANAGER REGISTRATION COMPLETE ===")

def unregister():
    """Unregister all Visual Manager classes and properties."""
    print("=== UNREGISTERING VISUAL MANAGER ===")
    
    # Unregister in reverse dependency order
    unregister_ui()
    unregister_label_tools()
    unregister_operators()
    unregister_data()
    
    print("=== VISUAL MANAGER UNREGISTRATION COMPLETE ===")