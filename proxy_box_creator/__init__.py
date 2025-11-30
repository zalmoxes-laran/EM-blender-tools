"""
Proxy Box Creator Module
Enhanced with paradata support
"""

from . import data
from . import operators            # NEW
from . import ui
from . import utils
from . import document_picker
from . import create_enhanced


def register():
    """Register all components"""
    print("   [proxy_box_creator] Starting registration...")

    # Register in order
    data.register()
    operators.register()           # NEW
    ui.register()
    document_picker.register()
    create_enhanced.register()

    print("   [proxy_box_creator] ✓ Module registration complete")


def unregister():
    """Unregister all components"""
    print("   [proxy_box_creator] Starting unregistration...")

    # Unregister in reverse order
    create_enhanced.unregister()
    document_picker.unregister()
    ui.unregister()
    operators.unregister()         # NEW
    data.unregister()

    print("   [proxy_box_creator] ✓ Module unregistration complete")


__all__ = [
    'data',
    'operators',
    'ui',
    'utils',
    'document_picker',
    'create_enhanced',
]