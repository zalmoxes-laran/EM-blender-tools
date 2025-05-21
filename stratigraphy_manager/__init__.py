"""
Stratigraphy Manager - Central module for managing stratigraphic units
This module provides functionality for viewing, filtering, and managing
stratigraphic units within the Extended Matrix framework.
"""

import bpy
from bpy.utils import register_class, unregister_class
from bpy.props import BoolProperty

# Import local modules
from .data import register_data, unregister_data
from .ui import register_ui, unregister_ui
from .operators import register_operators, unregister_operators
from .filters import register_filters, unregister_filters

# Module info
__all__ = ['register', 'unregister']

def register():
    """Register all Stratigraphy Manager classes and properties."""
    # Register in proper dependency order
    register_data()
    register_filters()
    register_operators()
    register_ui()
    
    # Register properties that need to be on the Scene
    # These were previously in __init__.py but belong in this module
    if not hasattr(bpy.types.Scene, "filter_by_epoch"):
        bpy.types.Scene.filter_by_epoch = BoolProperty(
            name="Filter by Epoch",
            description="Show only elements from the active epoch",
            default=False,
            update=lambda self, context: bpy.ops.em.filter_lists()
        )
    
    if not hasattr(bpy.types.Scene, "filter_by_activity"):
        bpy.types.Scene.filter_by_activity = BoolProperty(
            name="Filter by Activity",
            description="Show only elements from the active activity",
            default=False,
            update=lambda self, context: bpy.ops.em.filter_lists()
        )
    
    if not hasattr(bpy.types.Scene, "include_surviving_units"):
        bpy.types.Scene.include_surviving_units = BoolProperty(
            name="Include Surviving Units",
            description="Include units that survive in this epoch but were created in previous epochs",
            default=True,
            update=lambda self, context: bpy.ops.em.filter_lists() if context.scene.filter_by_epoch else None
        )
    
    if not hasattr(bpy.types.Scene, "show_reconstruction_units"):
        bpy.types.Scene.show_reconstruction_units = BoolProperty(
            name="Show Reconstruction Units",
            description="Show reconstruction units in the filtered list",
            default=True,
            update=lambda self, context: bpy.ops.em.filter_lists() if context.scene.filter_by_epoch else None
        )
    
    if not hasattr(bpy.types.Scene, "sync_list_visibility"):
        bpy.types.Scene.sync_list_visibility = BoolProperty(
            name="Sync Visibility",
            description="Synchronize proxy visibility with the current list (shows only proxies in the filtered list)",
            default=False,
            update=lambda self, context: bpy.ops.em.strat_sync_visibility()
        )
    
    if not hasattr(bpy.types.Scene, "sync_rm_visibility"):
        bpy.types.Scene.sync_rm_visibility = BoolProperty(
            name="Sync RM Visibility",
            description="Synchronize Representation Model visibility based on active epoch",
            default=False,
            update=lambda self, context: bpy.ops.em.strat_sync_visibility()
        )

def unregister():
    """Unregister all Stratigraphy Manager classes and properties."""
    # Remove properties
    if hasattr(bpy.types.Scene, "filter_by_epoch"):
        del bpy.types.Scene.filter_by_epoch
    
    if hasattr(bpy.types.Scene, "filter_by_activity"):
        del bpy.types.Scene.filter_by_activity
    
    if hasattr(bpy.types.Scene, "include_surviving_units"):
        del bpy.types.Scene.include_surviving_units
    
    if hasattr(bpy.types.Scene, "show_reconstruction_units"):
        del bpy.types.Scene.show_reconstruction_units
    
    if hasattr(bpy.types.Scene, "sync_list_visibility"):
        del bpy.types.Scene.sync_list_visibility
    
    if hasattr(bpy.types.Scene, "sync_rm_visibility"):
        del bpy.types.Scene.sync_rm_visibility
    
    # Unregister in reverse dependency order
    unregister_ui()
    unregister_operators()
    unregister_filters()
    unregister_data()