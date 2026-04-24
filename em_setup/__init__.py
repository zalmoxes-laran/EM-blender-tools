"""
EM Setup Module
Modular structure for EM Setup functionality
"""

import bpy

# Import submodules
from . import properties
from . import operators
from . import resource_operators
from . import ui
from . import utils

# Re-export utility functions for external use
from .utils import auto_import_auxiliary_files

# Re-export helper functions that UI needs to expose
from .ui import (
    get_em_tools_version,
    validate_enum_value,
    validate_all_mapping_enums,
    get_mapping_description
)

# Re-export PropertyGroups for backward compatibility
from .properties import (
    AuxiliaryFileProperties,
    GraphMLFileItem,
    EMToolsProperties,
    EMToolsSettings,
)

# Module info
__all__ = [
    'register',
    'unregister',
    'auto_import_auxiliary_files',
    'get_em_tools_version',
    'validate_enum_value',
    'validate_all_mapping_enums',
    'get_mapping_description',
    'AuxiliaryFileProperties',
    'EMToolsProperties',
    'EMToolsSettings',
    'GraphMLFileItem',
]


def register():
    """Register all EM Setup classes and properties."""
    # Register in proper dependency order
    # Properties first (PropertyGroups)
    properties.register()

    # Then operators
    operators.register()
    resource_operators.register()

    # Finally UI (which may depend on properties and operators)
    ui.register()


def unregister():
    """Unregister all EM Setup classes and properties."""
    # Unregister in reverse order
    ui.unregister()
    resource_operators.unregister()
    operators.unregister()
    properties.unregister()
