# em_setup/__init__.py
"""
EM Setup Module
Manages GraphML files, auxiliary files, and import settings
"""

import bpy
from bpy.utils import register_class, unregister_class

# Import submodules
from . import properties
from . import utils
from . import operators

# Import UI classes from old em_setup file
import sys
import os
# Get parent directory to import em_setup_old
parent_dir = os.path.dirname(__file__)
sys.path.insert(0, parent_dir)

try:
    from .em_setup_old import (
        # Helper functions
        get_pyarchinit_mappings,
        get_emdb_mappings,
        validate_enum_value,
        validate_all_mapping_enums,
        get_us_doc_previews_callback,
        get_mapping_description,

        # UI Classes (not migrated yet)
        AUXILIARY_UL_files,
        EMTOOLS_UL_files,
        EM_SetupPanel,
        AUXILIARY_MT_context_menu,
    )
    UI_CLASSES_LOADED = True
except ImportError as e:
    print(f"⚠️ [em_setup/__init__.py] Warning: Could not import UI classes from em_setup_old: {e}")
    UI_CLASSES_LOADED = False

__all__ = [
    'register',
    'unregister',
    'get_em_tools_version',
    # Export PropertyGroups for backward compatibility
    'AuxiliaryFileProperties',
    'EMToolsProperties',
    'EMToolsSettings',
    'GraphMLFileItem',
    # Export helper functions
    'get_pyarchinit_mappings',
    'get_emdb_mappings',
    'validate_enum_value',
    'validate_all_mapping_enums',
    'get_us_doc_previews_callback',
    'get_mapping_description',
    # Export utils functions
    'auto_import_auxiliary_files',
]

# Re-export get_em_tools_version for compatibility
from .operators import get_em_tools_version

# Re-export PropertyGroups that are used elsewhere
from .properties import (
    AuxiliaryFileProperties,
    EMToolsProperties,
    EMToolsSettings,
    GraphMLFileItem,
)

# Re-export utils functions
from .utils import auto_import_auxiliary_files


def register():
    """Register all EM Setup classes and properties."""
    # Register in proper dependency order
    properties.register()
    operators.register()

    # Register UI classes (from em_setup_old.py)
    if UI_CLASSES_LOADED:
        ui_classes = [
            AUXILIARY_UL_files,
            EMTOOLS_UL_files,
            EM_SetupPanel,
            AUXILIARY_MT_context_menu,
        ]

        for cls in ui_classes:
            try:
                bpy.utils.register_class(cls)
            except ValueError as e:
                print(f"Warning: EM Setup UI class registration error for {cls.__name__}: {e}")


def unregister():
    """Unregister all EM Setup classes and properties."""
    # Unregister UI classes first
    if UI_CLASSES_LOADED:
        ui_classes = [
            AUXILIARY_MT_context_menu,
            EM_SetupPanel,
            EMTOOLS_UL_files,
            AUXILIARY_UL_files,
        ]

        for cls in ui_classes:
            try:
                bpy.utils.unregister_class(cls)
            except Exception as e:
                print(f"Error unregistering EM Setup UI class {cls.__name__}: {e}")

    # Then unregister operators and properties
    operators.unregister()
    properties.unregister()
