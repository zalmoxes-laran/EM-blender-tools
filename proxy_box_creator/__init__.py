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
    data.register()
    operators.register()
    ui.register()
    document_picker.register()
    create_enhanced.register()


def unregister():
    """Unregister all components"""
    create_enhanced.unregister()
    document_picker.unregister()
    ui.unregister()
    operators.unregister()
    data.unregister()


__all__ = [
    'data',
    'operators',
    'ui',
    'utils',
    'document_picker',
    'create_enhanced',
]