"""
Activity Manager Module
Modular structure for Activity (ActivityNodeGroup) functionality.

Organization:
    properties.py  -> PropertyGroups (ActivityItem, ActivityManagerProperties)
                      + Scene.activity_manager PointerProperty registration
    operators.py   -> ACTIVITY_OT_refresh_list
    ui.py          -> UIList + Panel
"""

from . import properties
from . import operators
from . import ui

from .properties import ActivityItem, ActivityManagerProperties

__all__ = [
    'register',
    'unregister',
    'ActivityItem',
    'ActivityManagerProperties',
]


def register():
    properties.register()
    operators.register()
    ui.register()


def unregister():
    ui.unregister()
    operators.unregister()
    properties.unregister()
