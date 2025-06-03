"""
Visual Manager - Central module for visualization, properties, and camera management
This module provides functionality for property-based coloring, camera management, 
label creation, and advanced visualization techniques within the Extended Matrix framework.
"""

import bpy

# Import local modules
from .data import register_data, unregister_data
from .ui import register_ui, unregister_ui
from .operators import register_operators, unregister_operators
from .label_tools import register_label_tools, unregister_label_tools

# Import visualization modules
from .visualization_modules import register as register_viz_modules, unregister as unregister_viz_modules
from .visualization_modules.utils import register_utils, unregister_utils

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
    
    print("Registering visualization modules...")
    register_viz_modules()
    
    print("Registering visualization utilities...")
    register_utils()
    
    print("Registering visual manager UI...")
    register_ui()
    
    print("=== VISUAL MANAGER REGISTRATION COMPLETE ===")

def unregister():
    """Unregister all Visual Manager classes and properties."""
    print("=== UNREGISTERING VISUAL MANAGER ===")
    
    # Unregister in reverse dependency order
    unregister_ui()
    unregister_utils()
    unregister_viz_modules()
    unregister_label_tools()
    unregister_operators()
    unregister_data()
    
    print("=== VISUAL MANAGER UNREGISTRATION COMPLETE ===")
