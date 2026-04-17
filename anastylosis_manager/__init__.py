"""
Anastylosis Manager Module
Modular structure for Anastylosis (RMSF) functionality.

Organization:
    properties.py       -> PropertyGroups (AnastylisisItem, AnastylisisSettings, AnastylosisSFNodeItem)
    lod_utils.py        -> LOD constants + name/fallback helpers + detect_lod_variants
    graph_utils.py      -> graph cleanup helper + visibility analysis/apply
    operators_list.py   -> list CRUD operators (update/select/add/remove/cleanup/...)
    operators_link.py   -> SF/VSF linking operators (link/confirm/search/assign)
    operators_lod.py    -> LOD switching + menus + open linked .blend
    ui.py               -> UIList, Panel, load_post handler
"""

from . import properties
from . import operators_list
from . import operators_link
from . import operators_lod
from . import ui

# Re-export PropertyGroups for backward compatibility (em_props imports them from here)
from .properties import (
    AnastylisisItem,
    AnastylisisSettings,
    AnastylosisSFNodeItem,
)

# Re-export LOD helpers for external callers that historically imported them
from .lod_utils import detect_lod_variants

__all__ = [
    'register',
    'unregister',
    'AnastylisisItem',
    'AnastylisisSettings',
    'AnastylosisSFNodeItem',
    'detect_lod_variants',
]


def register():
    # NOTE: PropertyGroups in properties.py are registered centrally by em_props.
    operators_list.register()
    operators_link.register()
    operators_lod.register()
    ui.register()


def unregister():
    ui.unregister()
    operators_lod.unregister()
    operators_link.unregister()
    operators_list.unregister()
