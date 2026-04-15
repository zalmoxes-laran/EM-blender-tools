"""
Tapestry Integration for EM-blender-tools
==========================================

Integrates EM-blender-tools with EM-Tapestry for AI-powered photorealistic
reconstruction of archaeological proxies.

Features:
- Render setup for EXR multilayer with Cryptomatte
- Camera view analysis for visible proxies
- Automatic mask extraction per proxy
- JSON generation from s3Dgraphy graph
- Direct submission to Tapestry server

Properties are registered in em_props.py as scene.em_tools.tapestry

Author: EM-Tapestry Team
License: GPL-3.0
"""

import bpy

# Import submodules
from . import properties
from . import ui_panel
from . import operators

# Version info
bl_info = {
    "name": "Tapestry Integration",
    "author": "EM-Tapestry Team",
    "version": (1, 0, 0),
    "blender": (4, 0, 0),
    "location": "View3D > EM Bridge > Tapestry",
    "description": "Export archaeological proxies to Tapestry for AI reconstruction",
    "category": "EM Tools",
}


# Modules to register
modules = (
    properties,  # Property groups (registered via em_props.py too)
    operators,   # Operators
    ui_panel,    # UI panels
)


def register():
    """Register Tapestry integration"""
    # Register all modules
    for module in modules:
        module.register()


def unregister():
    """Unregister Tapestry integration"""
    # Unregister modules in reverse order
    for module in reversed(modules):
        module.unregister()


if __name__ == "__main__":
    register()
