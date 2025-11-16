"""
Proxy Box Creator Module
Creates box-shaped proxies from 7 measured points with optional extractor/combiner annotation.
"""

import bpy
from bpy.utils import register_class, unregister_class

# Import submodules
from . import data
from . import operators
from . import ui
from . import utils


# Module metadata
bl_info = {
    "name": "Proxy Box Creator",
    "author": "EM Tools Development Team",
    "version": (1, 0, 0),
    "blender": (4, 4, 0),
    "location": "View3D > Sidebar > EM Annotator",
    "description": "Create box-shaped archaeological proxies from measured points",
    "category": "EM Tools",
}

__all__ = ['register', 'unregister']


def register():
    """Register all classes and properties for the Proxy Box Creator module."""
    print("=" * 60)
    print("STARTING PROXY BOX CREATOR REGISTRATION")
    print("=" * 60)
    
    # Register in proper dependency order

    try:
        print("2. Registering operators...")
        data.register()
        print("   ✓ Operators registration complete")
    except Exception as e:
        print(f"   ✗ ERROR in operators registration: {e}")
        import traceback
        traceback.print_exc()

    try:
        print("2. Registering operators...")
        operators.register()
        print("   ✓ Operators registration complete")
    except Exception as e:
        print(f"   ✗ ERROR in operators registration: {e}")
        import traceback
        traceback.print_exc()
    
    try:
        print("3. Registering UI panels...")
        ui.register()
        print("   ✓ UI registration complete")
    except Exception as e:
        print(f"   ✗ ERROR in UI registration: {e}")
        import traceback
        traceback.print_exc()
    
    print("=" * 60)
    print("✓ Proxy Box Creator module registered")
    print("=" * 60)


def unregister():
    """Unregister all classes and properties for the Proxy Box Creator module."""
    # Unregister in reverse dependency order
    ui.unregister()
    operators.unregister()
    data.unregister()
    
    print("✓ Proxy Box Creator module unregistered")


if __name__ == "__main__":
    register()