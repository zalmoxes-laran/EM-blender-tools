"""
Data structures for the Epoch Manager
This module contains all PropertyGroup definitions and data structures
needed for the Epoch Manager.
"""

import bpy
from bpy.props import (
    StringProperty,
    BoolProperty,
    FloatProperty,
    IntProperty,
    CollectionProperty,
    PointerProperty,
    FloatVectorProperty
)
from bpy.types import PropertyGroup

class EPOCHListItem(PropertyGroup):
    """Period/Epoch information"""
    name: StringProperty(
        name="Name",
        description="Name of this epoch",
        default="Untitled"
    )
    id: StringProperty(
        name="id",
        description="Unique identifier",
        default=""
    )
    min_y: FloatProperty(
        name="Min Y Position",
        description="Minimum Y position",
        default=0.0
    )
    max_y: FloatProperty(
        name="Max Y Position",
        description="Maximum Y position",
        default=0.0
    )
    height: FloatProperty(
        name="Height",
        description="Height of epoch row",
        default=0.0
    )
    epoch_color: StringProperty(
        name="Epoch Color",
        description="Color code for epoch",
        default=""
    )
    start_time: FloatProperty(
        name="Start Time",
        description="Starting time for epoch",
        default=0.0
    )
    end_time: FloatProperty(
        name="End Time",
        description="Ending time for epoch",
        default=0.0
    )
    use_toggle: BoolProperty(name="Toggle", default=True)
    is_locked: BoolProperty(name="Locked", default=True)
    is_selected: BoolProperty(name="Selected", default=False)
    rm_models: BoolProperty(name="RM Models", default=False)
    reconstruction_on: BoolProperty(name="Reconstruction", default=False)
    unique_id: StringProperty(default="")
    epoch_RGB_color: FloatVectorProperty(
        name="Epoch RGB Color",
        subtype="COLOR",
        size=3,
        min=0.0,
        max=1.0,
        default=(0.5, 0.5, 0.5)
    )
    wire_color: FloatVectorProperty(
        name="Wire Color",
        subtype='COLOR',
        default=(0.2, 0.2, 0.2),
        min=0.0, max=1.0,
        description="Wire color of the group"
    )

class EMUSItem(PropertyGroup):
    """Information about a stratigraphic unit"""
    name: StringProperty(name="Name", default="")
    description: StringProperty(name="Description", default="")
    status: StringProperty(name="Status", default="")
    y_pos: StringProperty(name="y_pos", default="")


def update_epoch_selection(self, context):
    """
    Update callback for epoch_list_index.
    This function is called whenever the selected epoch changes.
    """
    scene = context.scene
    
    # Safety check: verify that epoch_list exists and the index is valid
    if len(scene.epoch_list) == 0:
        scene.epoch_list_index = -1  # Changed from 0 to -1 for empty lists
        return
    
    # Verify the index is in range (including check for negative indices)
    if scene.epoch_list_index < 0 or scene.epoch_list_index >= len(scene.epoch_list):
        scene.epoch_list_index = 0
        return  # Add return to avoid running the rest of the function
    
    # At this point we know the index is valid and we can proceed
    print(f"\n--- Epoch selection changed to index {scene.epoch_list_index} ---")
    active_epoch = scene.epoch_list[scene.epoch_list_index]
    print(f"Active epoch: {active_epoch.name}")
    
    # First update the US list for the side panel
    try:
        bpy.ops.epoch_manager.update_us_list()
    except Exception as e:
        print(f"Error updating US list: {e}")
    
    # IMPORTANTE: Trigger sempre l'operatore di filtro quando cambia l'epoca,
    # ma solo se il filtro epoca è attivo
    if hasattr(scene, "filter_by_epoch") and scene.filter_by_epoch:
        print(f"Filtering is active - updating stratigraphy list for epoch: {active_epoch.name}")
        try:
            # Verifica primo che ci sia un grafo attivo
            from ..functions import is_graph_available
            graph_exists, _ = is_graph_available(context)
            
            if graph_exists:
                bpy.ops.em.filter_lists()
            else:
                print("Cannot apply filtering: No active graph")
        except Exception as e:
            print(f"Error filtering lists: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("Epoch filtering is not active - skipping list update")



def register_data():
    """Register all data classes."""
    classes = [
        EPOCHListItem,
        EMUSItem,
    ]
    
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except ValueError:
            # Class might already be registered
            pass
            
    # Setup collection properties if not yet existing
    if not hasattr(bpy.types.Scene, "epoch_list"):
        bpy.types.Scene.epoch_list = CollectionProperty(type=EPOCHListItem)
    
    # IMPORTANTE: Registra il callback direttamente
    if hasattr(bpy.types.Scene, "epoch_list_index"):
        del bpy.types.Scene.epoch_list_index  # Rimuovi la proprietà esistente
        
    # Ricrea la proprietà con il callback collegato direttamente
    bpy.types.Scene.epoch_list_index = IntProperty(
        name="Index for epoch_list",
        default=0,
        update=update_epoch_selection
    )
        
    if not hasattr(bpy.types.Scene, "selected_epoch_us_list"):
        bpy.types.Scene.selected_epoch_us_list = CollectionProperty(type=EMUSItem)
        
    if not hasattr(bpy.types.Scene, "selected_epoch_us_list_index"):
        bpy.types.Scene.selected_epoch_us_list_index = IntProperty(
            name="Index for selected_epoch_us_list",
            default=0
        )

def unregister_data():
    """Unregister all data classes."""
    # Remove collection properties
    if hasattr(bpy.types.Scene, "epoch_list"):
        del bpy.types.Scene.epoch_list
    
    if hasattr(bpy.types.Scene, "epoch_list_index"):
        del bpy.types.Scene.epoch_list_index
    
    if hasattr(bpy.types.Scene, "selected_epoch_us_list"):
        del bpy.types.Scene.selected_epoch_us_list
        
    if hasattr(bpy.types.Scene, "selected_epoch_us_list_index"):
        del bpy.types.Scene.selected_epoch_us_list_index
    
    # Unregister classes in reverse order
    classes = [
        EMUSItem,
        EPOCHListItem,
    ]
    
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except ValueError:
            # Class might already be unregistered
            pass

