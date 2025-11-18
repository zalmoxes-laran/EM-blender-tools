# stratigraphy_manager/__init__.py

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

# Update functions che non ritornano valori
def update_filter_by_epoch(self, context):
    """Update function per filter_by_epoch"""
    if hasattr(bpy.ops.em, 'filter_lists'):
        bpy.ops.em.filter_lists()

def update_filter_by_activity(self, context):
    """Update function per filter_by_activity"""
    if hasattr(bpy.ops.em, 'filter_lists'):
        bpy.ops.em.filter_lists()

def update_include_surviving(self, context):
    """Update function per include_surviving_units"""
    if context.scene.filter_by_epoch and hasattr(bpy.ops.em, 'filter_lists'):
        bpy.ops.em.filter_lists()

def update_show_reconstruction(self, context):
    """Update function per show_reconstruction_units"""
    if context.scene.filter_by_epoch and hasattr(bpy.ops.em, 'filter_lists'):
        bpy.ops.em.filter_lists()

def update_sync_visibility(self, context):
    """Update function per sync visibility"""
    if hasattr(bpy.ops.em, 'strat_sync_visibility'):
        bpy.ops.em.strat_sync_visibility()

def register():
    """Register all Stratigraphy Manager classes and properties."""
    # Register in proper dependency order
    register_data()
    register_filters()
    register_operators()
    register_ui()
    
    # ⚠️ CRITICAL FIX: Rimuovi prima le properties se esistono, 
    # poi ri-registrale CON le update functions
    # Questo garantisce che le callback vengano collegate correttamente
    
    if hasattr(bpy.types.Scene, "filter_by_epoch"):
        del bpy.types.Scene.filter_by_epoch
    bpy.types.Scene.filter_by_epoch = BoolProperty(
        name="Filter by Epoch",
        description="Show only elements from the active epoch",
        default=False,
        update=update_filter_by_epoch  # ✅ Update function collegata
    )
    
    if hasattr(bpy.types.Scene, "filter_by_activity"):
        del bpy.types.Scene.filter_by_activity
    bpy.types.Scene.filter_by_activity = BoolProperty(
        name="Filter by Activity",
        description="Show only elements from the active activity",
        default=False,
        update=update_filter_by_activity  # ✅ Update function collegata
    )
    
    if hasattr(bpy.types.Scene, "include_surviving_units"):
        del bpy.types.Scene.include_surviving_units
    bpy.types.Scene.include_surviving_units = BoolProperty(
        name="Include Surviving Units",
        description="Include units that survive in this epoch but were created in previous epochs",
        default=True,
        update=update_include_surviving  # ✅ Update function collegata
    )
    
    if hasattr(bpy.types.Scene, "show_reconstruction_units"):
        del bpy.types.Scene.show_reconstruction_units
    bpy.types.Scene.show_reconstruction_units = BoolProperty(
        name="Show Reconstruction Units",
        description="Show reconstruction units in the filtered list",
        default=True,
        update=update_show_reconstruction  # ✅ Update function collegata
    )
    
    if hasattr(bpy.types.Scene, "sync_list_visibility"):
        del bpy.types.Scene.sync_list_visibility
    bpy.types.Scene.sync_list_visibility = BoolProperty(
        name="Sync Visibility",
        description="Synchronize proxy visibility with the current list (shows only proxies in the filtered list)",
        default=False,
        update=update_sync_visibility  # ✅ Update function collegata
    )
    
    if hasattr(bpy.types.Scene, "sync_rm_visibility"):
        del bpy.types.Scene.sync_rm_visibility
    bpy.types.Scene.sync_rm_visibility = BoolProperty(
        name="Sync RM Visibility",
        description="Synchronize Representation Model visibility based on active epoch",
        default=False,
        update=update_sync_visibility  # ✅ Update function collegata
    )

def unregister():
    """Unregister all Stratigraphy Manager classes and properties."""
    # Unregister in reverse order
    unregister_ui()
    unregister_operators()
    unregister_filters()
    unregister_data()
    
    # Remove Scene properties
    properties_to_remove = [
        "filter_by_epoch",
        "filter_by_activity",
        "include_surviving_units",
        "show_reconstruction_units",
        "sync_list_visibility",
        "sync_rm_visibility",
    ]
    
    for prop_name in properties_to_remove:
        if hasattr(bpy.types.Scene, prop_name):
            delattr(bpy.types.Scene, prop_name)