"""
Data structures for the Epoch Manager
This module contains all PropertyGroup definitions and data structures
needed for the Epoch Manager.

REFACTORED: PropertyGroup classes are registered ONLY by em_props.py
This file now handles ONLY Scene property attachment/removal.
"""

import bpy # type: ignore
from bpy.props import ( # type: ignore
    StringProperty,
    BoolProperty,
    FloatProperty,
    IntProperty,
    CollectionProperty,
    PointerProperty,
    FloatVectorProperty
)
from bpy.types import PropertyGroup # type: ignore


# =====================================================
# PROPERTY GROUP CLASSES
# =====================================================
# NOTE: These classes are registered by em_props.py
# We only define them here for import by other modules

class EPOCHListItem(PropertyGroup):
    """Period/Epoch information"""
    name: StringProperty(
        name="Name",
        description="Name of this epoch",
        default="Untitled"
    ) # type: ignore
    id: StringProperty(
        name="id",
        description="Unique identifier",
        default=""
    ) # type: ignore
    min_y: FloatProperty(
        name="Min Y Position",
        description="Minimum Y position",
        default=0.0
    ) # type: ignore
    max_y: FloatProperty(
        name="Max Y Position",
        description="Maximum Y position",
        default=0.0
    ) # type: ignore
    height: FloatProperty(
        name="Height",
        description="Height of epoch row",
        default=0.0
    ) # type: ignore
    epoch_color: StringProperty(
        name="Epoch Color",
        description="Color code for epoch",
        default=""
    ) # type: ignore
    start_time: FloatProperty(
        name="Start Time",
        description="Starting time for epoch",
        default=0.0
    ) # type: ignore
    end_time: FloatProperty(
        name="End Time",
        description="Ending time for epoch",
        default=0.0
    ) # type: ignore
    use_toggle: BoolProperty(name="Toggle", default=True) # type: ignore
    is_locked: BoolProperty(name="Locked", default=True) # type: ignore
    is_selected: BoolProperty(name="Selected", default=False) # type: ignore
    rm_models: BoolProperty(name="RM Models", default=False) # type: ignore
    reconstruction_on: BoolProperty(name="Reconstruction", default=False) # type: ignore
    unique_id: StringProperty(default="") # type: ignore
    epoch_RGB_color: FloatVectorProperty(
        name="Epoch RGB Color",
        subtype="COLOR",
        size=3,
        min=0.0,
        max=1.0,
        default=(0.5, 0.5, 0.5)
    ) # type: ignore
    wire_color: FloatVectorProperty(
        name="Wire Color",
        subtype='COLOR',
        default=(0.2, 0.2, 0.2),
        min=0.0, max=1.0,
        description="Wire color of the group"
    ) # type: ignore


class EMUSItem(PropertyGroup):
    """Information about a stratigraphic unit"""
    name: StringProperty(name="Name", default="") # type: ignore
    description: StringProperty(name="Description", default="") # type: ignore
    status: StringProperty(name="Status", default="") # type: ignore
    y_pos: StringProperty(name="y_pos", default="") # type: ignore


def update_epoch_selection(self, context):
    """
    Update callback for epoch_list_index.
    This function is called whenever the selected epoch changes.
    """
    # Implementazione della logica di update se necessario
    pass


# =====================================================
# REGISTRATION FUNCTIONS
# =====================================================

def register_data():
    """
    Register Epoch Manager data structures.
    
    REFACTORED: PropertyGroup classes are registered by em_props.py
    This function now ONLY handles Scene property attachment.
    """
    # ❌ PropertyGroup registration rimosso (gestito da em_props.py)
    
    # ✅ SOLO Scene properties NON gestite da em_props
    # Setup collection properties if not yet existing
    if not hasattr(bpy.types.Scene, "epoch_list"):
        bpy.types.Scene.epoch_list = CollectionProperty(type=EPOCHListItem)
    
    # IMPORTANTE: Registra il callback direttamente
    if hasattr(bpy.types.Scene, "epoch_list_index"):
        del bpy.types.Scene.epoch_list_index
        
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
    """
    Unregister Epoch Manager data structures.
    
    REFACTORED: PropertyGroup classes are unregistered by em_props.py
    This function now ONLY handles Scene property removal.
    """
    # ✅ SOLO rimozione Scene properties
    if hasattr(bpy.types.Scene, "epoch_list"):
        del bpy.types.Scene.epoch_list
    
    if hasattr(bpy.types.Scene, "epoch_list_index"):
        del bpy.types.Scene.epoch_list_index
    
    if hasattr(bpy.types.Scene, "selected_epoch_us_list"):
        del bpy.types.Scene.selected_epoch_us_list
        
    if hasattr(bpy.types.Scene, "selected_epoch_us_list_index"):
        del bpy.types.Scene.selected_epoch_us_list_index
    
    # ❌ PropertyGroup unregistration rimosso (gestito da em_props.py)