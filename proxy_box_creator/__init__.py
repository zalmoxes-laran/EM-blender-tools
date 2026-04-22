"""Proxy Box Creator — two-step flow (DP-47 / DP-07).

Step 1 anchors the proxy chain on a DocumentNode; Step 2 records the
seven measurement points that define the box and auto-generate
extractors under that document.
"""

from . import data
from . import operators
from . import ui
from . import utils
from . import create_enhanced


def register():
    data.register()
    operators.register()
    ui.register()
    create_enhanced.register()


def unregister():
    create_enhanced.unregister()
    ui.unregister()
    operators.unregister()
    data.unregister()


__all__ = [
    'data',
    'operators',
    'ui',
    'utils',
    'create_enhanced',
]
