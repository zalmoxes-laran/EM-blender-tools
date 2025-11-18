"""
Proxy Box Creator Module
Enhanced with paradata support
"""

from . import data
from . import operators
from . import ui
from . import utils
from . import document_picker      # NEW
from . import ui_enhanced          # NEW
from . import create_enhanced      # NEW


def register():
    """Register all components"""
    print("   [proxy_box_creator] Starting registration...")
    
    # Register in order
    data.register()
    operators.register()
    ui.register()
    document_picker.register()     # NEW
    ui_enhanced.register()         # NEW
    create_enhanced.register()     # NEW
    
    print("   [proxy_box_creator] ✓ Module registration complete")


def unregister():
    """Unregister all components"""
    print("   [proxy_box_creator] Starting unregistration...")
    
    # Unregister in reverse order
    create_enhanced.unregister()   # NEW
    ui_enhanced.unregister()       # NEW
    document_picker.unregister()   # NEW
    ui.unregister()
    operators.unregister()
    data.unregister()
    
    print("   [proxy_box_creator] ✓ Module unregistration complete")


__all__ = [
    'data',
    'operators',
    'ui',
    'utils',
    'document_picker',
    'ui_enhanced',
    'create_enhanced',
]