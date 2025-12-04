"""
Graph Editor - Visual node editor for s3dgraphy graphs
"""

import bpy

# Import local modules
from . import data
from . import nodes
from . import properties
from . import operators
from . import ui
from . import keymap
from . import socket_generator

__all__ = ['register', 'unregister']

def register():
    """Register all Graph Editor classes and properties"""
    print("=== REGISTERING GRAPH EDITOR ===")

    # ✅ Initialize dynamic socket system FIRST
    socket_generator.initialize_socket_system()

    # Register in proper order
    data.register_data()           # Socket, NodeTree
    nodes.register_nodes()          # Node types
    properties.register_properties() # Scene properties
    operators.register_operators()   # Operators
    ui.register_ui()                # UI panels
    keymap.register_keymaps()       # Keyboard shortcuts

    # Initialize edge filters on startup
    try:
        from .properties import initialize_edge_filters
        # Will be called when first accessed
    except:
        pass

    print("=== GRAPH EDITOR REGISTRATION COMPLETE ===")

def unregister():
    """Unregister all Graph Editor classes and properties"""
    print("=== UNREGISTERING GRAPH EDITOR ===")
    
    # Unregister in reverse order
    keymap.unregister_keymaps()
    ui.unregister_ui()
    operators.unregister_operators()
    properties.unregister_properties() # ✅ NUOVO
    nodes.unregister_nodes()
    data.unregister_data()
    
    print("=== GRAPH EDITOR UNREGISTRATION COMPLETE ===")