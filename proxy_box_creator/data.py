"""
Data structures for the Proxy Box Creator
This module contains all PropertyGroup definitions and data structures.
"""

import bpy
from bpy.props import (
    StringProperty,
    BoolProperty,
    FloatVectorProperty,
    IntProperty,
    CollectionProperty,
    EnumProperty
)
from bpy.types import PropertyGroup


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
        name="Create Extractors",
        description="Create extractor and combiner nodes in the graph (annotation mode). If disabled, only creates the geometry",
        default=True
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
    ProxyBoxPointSettings,
    ProxyBoxSettings,
]


def register():
    """Register all PropertyGroup classes"""
    print("   [data.py] Starting registration...")
    
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
            print(f"   [data.py] ✓ Registered {cls.__name__}")
        except ValueError as e:
            print(f"   [data.py] ⚠ Warning: Could not register {cls.__name__}: {e}")
    
    # Add property to EMToolsSettings
    from bpy.props import PointerProperty
    
    print("   [data.py] Attempting to add proxy_box_settings to EMToolsSettings...")
    
    # We need to import EMToolsSettings directly from em_setup module
    # We can't use bpy.context.scene during registration (it's a RestrictedContext)
    try:
        # Import from the extension's em_setup module
        import sys
        
        # The module path will be bl_ext.vscode_development.EM-blender-tools.em_setup
        # But we need to handle the dash in the name
        em_setup_module_name = None
        for module_name in sys.modules.keys():
            if 'EM-blender-tools.em_setup' in module_name or 'EM_blender_tools.em_setup' in module_name:
                em_setup_module_name = module_name
                break
        
        if em_setup_module_name:
            em_setup_module = sys.modules[em_setup_module_name]
            EMToolsSettings = em_setup_module.EMToolsSettings
            
            if not hasattr(EMToolsSettings, 'proxy_box_settings'):
                # CRITICAL: We need to unregister and re-register EMToolsSettings
                # to make Blender recognize the new property properly
                
                # First, remove Scene.em_tools temporarily
                if hasattr(bpy.types.Scene, 'em_tools'):
                    del bpy.types.Scene.em_tools
                    print("   [data.py] Temporarily removed Scene.em_tools")
                
                # Unregister the class
                try:
                    bpy.utils.unregister_class(EMToolsSettings)
                    print("   [data.py] Unregistered EMToolsSettings")
                except:
                    pass
                
                # Add the new property to the class
                EMToolsSettings.proxy_box_settings = PointerProperty(
                    type=ProxyBoxSettings,
                    name="Proxy Box Settings"
                )
                print("   [data.py] ✓ Added proxy_box_settings property")
                
                # Re-register the class
                bpy.utils.register_class(EMToolsSettings)
                print("   [data.py] Re-registered EMToolsSettings")
                
                # Re-create Scene.em_tools
                bpy.types.Scene.em_tools = PointerProperty(type=EMToolsSettings)
                print("   [data.py] Re-created Scene.em_tools")
                
                print("   [data.py] ✓ Successfully integrated proxy_box_settings")
            else:
                print("   [data.py] ⚠ proxy_box_settings already exists")
        else:
            print("   [data.py] ✗ Could not find em_setup module in sys.modules")
            
    except Exception as e:
        print(f"   [data.py] ✗ Error adding property: {e}")
        import traceback
        traceback.print_exc()
    
    print("   [data.py] ✓ Data structures registration complete")


def unregister():
    """Unregister all PropertyGroup classes"""
    print("   [data.py] Starting unregistration...")
    
    # Remove the property from EMToolsSettings first
    try:
        import sys
        
        # Find the em_setup module
        em_setup_module_name = None
        for module_name in sys.modules.keys():
            if 'EM-blender-tools.em_setup' in module_name or 'EM_blender_tools.em_setup' in module_name:
                em_setup_module_name = module_name
                break
        
        if em_setup_module_name:
            em_setup_module = sys.modules[em_setup_module_name]
            EMToolsSettings = em_setup_module.EMToolsSettings
            
            if hasattr(EMToolsSettings, 'proxy_box_settings'):
                del EMToolsSettings.proxy_box_settings
                print("   [data.py] ✓ Removed proxy_box_settings from EMToolsSettings")
    except Exception as e:
        print(f"   [data.py] ⚠ Could not remove proxy_box_settings: {e}")
    
    # Unregister classes in reverse order
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
            print(f"   [data.py] ✓ Unregistered {cls.__name__}")
        except RuntimeError as e:
            print(f"   [data.py] ⚠ Warning: Could not unregister {cls.__name__}: {e}")
    
    print("   [data.py] ✓ Data structures unregistration complete")


if __name__ == "__main__":
    register()