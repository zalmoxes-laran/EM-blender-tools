"""
Data structures for the Proxy Box Creator
This module contains all PropertyGroup definitions and data structures.

REFACTORED: No longer attempts to dynamically attach properties to EMToolsSettings.
The ProxyBoxSettings class is now referenced in em_props.py centrally.
"""

import bpy # type: ignore
from bpy.props import ( # type: ignore
    StringProperty,
    BoolProperty,
    FloatVectorProperty,
    IntProperty,
    CollectionProperty,
    EnumProperty
)
from bpy.types import PropertyGroup # type: ignore


class ProxyBoxPointSettings(PropertyGroup):
    """Settings for a single measurement point"""
    
    position: FloatVectorProperty(
        name="Position",
        description="3D coordinates of this point",
        subtype='XYZ',
        default=(0.0, 0.0, 0.0),
        precision=4
    )  # type: ignore
    
    source_document: StringProperty(
        name="Source Document ID",
        description="ID of the document node this point was extracted from",
        default=""
    )  # type: ignore
    
    source_document_name: StringProperty(
        name="Source Document Name",
        description="Display name of the source document",
        default=""
    )  # type: ignore
    
    extractor_id: StringProperty(
        name="Extractor Node ID",
        description="ID of the extractor node created for this point (e.g., D10.11)",
        default=""
    )  # type: ignore
    
    is_recorded: BoolProperty(
        name="Is Recorded",
        description="Whether this point has been recorded",
        default=False
    )  # type: ignore
    
    point_type: StringProperty(
        name="Point Type",
        description="Semantic type of this point",
        default=""
    )  # type: ignore


class ProxyBoxSettings(PropertyGroup):
    """Main settings for the Proxy Box Creator"""
    
    # Collection of 7 points
    points: CollectionProperty(
        type=ProxyBoxPointSettings,
        name="Measurement Points"
    )  # type: ignore
    
    # Mode toggle
    create_extractors: BoolProperty(
        name="ctivate Paradata Enrichment",
        description="Create extractor and combiner nodes in the graph (annotation mode). If disabled, only creates the geometry",
        default=False
    )  # type: ignore
    
    # Proxy settings
    proxy_name: StringProperty(
        name="Proxy Name",
        description="Name for the created proxy object",
        default="Wall_Proxy"
    )  # type: ignore
    
    pivot_location: EnumProperty(
        name="Pivot Location",
        description="Location of the object pivot point",
        items=[
            ('TOP', "Top", "Pivot at the top face (max Z)"),
            ('CENTER', "Center", "Pivot at geometric center"),
            ('BOTTOM', "Bottom", "Pivot at the bottom face (min Z)"),
        ],
        default='CENTER'
    )  # type: ignore
    
    use_proxy_collection: BoolProperty(
        name="Use Proxy Collection",
        description="Place the created proxy in the 'Proxy' collection. If disabled, uses active collection",
        default=True
    )  # type: ignore
    
    # Combiner info (auto-generated)
    combiner_id: StringProperty(
        name="Combiner ID",
        description="ID of the combiner node that will be created (e.g., C.10)",
        default=""
    )  # type: ignore
    
    # UI state
    show_point_details: BoolProperty(
        name="Show Point Details",
        description="Show detailed information for each point",
        default=False
    )  # type: ignore


# List of classes to register
classes = [
    #ProxyBoxPointSettings,
    #ProxyBoxSettings,
]


def register():
    """
    Register all PropertyGroup classes.
    
    REFACTORED: This function now ONLY registers the PropertyGroup classes.
    The property attachment to Scene happens in em_props.py centrally.
    
    The problematic code that tried to dynamically attach to EMToolsSettings
    has been REMOVED.
    """
    print("   [proxy_box/data.py] Starting registration...")
    
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
            print(f"   [proxy_box/data.py] ✓ Registered {cls.__name__}")
        except ValueError as e:
            print(f"   [proxy_box/data.py] ⚠ Warning: Could not register {cls.__name__}: {e}")
    
    print("   [proxy_box/data.py] ✓ Data structures registration complete")
    print("   [proxy_box/data.py] ℹ Property attachment handled by em_props.py")


def unregister():
    """
    Unregister all PropertyGroup classes.
    
    REFACTORED: This function now ONLY unregisters the PropertyGroup classes.
    The property removal from Scene happens in em_props.py centrally.
    """
    print("   [proxy_box/data.py] Starting unregistration...")
    
    # Unregister classes in reverse order
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
            print(f"   [proxy_box/data.py] ✓ Unregistered {cls.__name__}")
        except RuntimeError as e:
            print(f"   [proxy_box/data.py] ⚠ Warning: Could not unregister {cls.__name__}: {e}")
    
    print("   [proxy_box/data.py] ✓ Data structures unregistration complete")


if __name__ == "__main__":
    register()