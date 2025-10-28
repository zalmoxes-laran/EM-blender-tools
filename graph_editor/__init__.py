"""
Graph Editor - Visual node editor for s3dgraphy graphs
Provides a dedicated node-based interface for viewing and editing
archaeological stratigraphy graphs with support for all s3dgraphy node types.
"""

import bpy
from bpy.utils import register_class, unregister_class
from bpy.props import BoolProperty

# Import local modules - USA IMPORT RELATIVI
from . import data
from . import nodes
from . import operators
from . import ui

# Module info
__all__ = ['register', 'unregister']

def register():
    """Register all Graph Editor classes and properties."""
    print("=== REGISTERING GRAPH EDITOR ===")
    
    # Register in proper dependency order
    data.register_data()      # Socket, NodeTree, PropertyGroups
    nodes.register_nodes()     # Tutti i tipi di nodi
    operators.register_operators() # Operatori per gestire il grafo
    ui.register_ui()        # Pannelli UI
    
    # Register scene properties
    if not hasattr(bpy.types.Scene, "show_graph_editor_tools"):
        bpy.types.Scene.show_graph_editor_tools = BoolProperty(
            name="Show Graph Editor Tools",
            description="Show/hide graph editor tools panel",
            default=True
        )
    
    if not hasattr(bpy.types.Scene, "graph_editor_auto_layout"):
        bpy.types.Scene.graph_editor_auto_layout = BoolProperty(
            name="Auto Layout",
            description="Automatically arrange nodes when loading graph",
            default=True
        )
    
    if not hasattr(bpy.types.Scene, "graph_editor_show_labels"):
        bpy.types.Scene.graph_editor_show_labels = BoolProperty(
            name="Show Node Labels",
            description="Show node labels in the graph editor",
            default=True
        )
    
    print("=== GRAPH EDITOR REGISTRATION COMPLETE ===")

def unregister():
    """Unregister all Graph Editor classes and properties."""
    print("=== UNREGISTERING GRAPH EDITOR ===")
    
    # Remove scene properties
    props_to_remove = [
        "show_graph_editor_tools",
        "graph_editor_auto_layout", 
        "graph_editor_show_labels"
    ]
    
    for prop_name in props_to_remove:
        if hasattr(bpy.types.Scene, prop_name):
            delattr(bpy.types.Scene, prop_name)
    
    # Unregister in reverse order
    ui.unregister_ui()
    operators.unregister_operators()
    nodes.unregister_nodes()
    data.unregister_data()
    
    print("=== GRAPH EDITOR UNREGISTRATION COMPLETE ===")