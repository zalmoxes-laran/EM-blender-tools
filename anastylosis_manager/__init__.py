"""
Anastylosis Manager Module
Modular structure for Anastylosis (RMSF) functionality.

Organization:
    properties.py       -> PropertyGroups (AnastylisisItem, AnastylisisSettings, AnastylosisSFNodeItem)
    graph_utils.py      -> graph cleanup helper + visibility analysis/apply
    operators_list.py   -> list CRUD operators (update/select/add/remove/cleanup/...)
    operators_link.py   -> SF/VSF linking operators (link/confirm/search/assign)
    operators_files.py  -> open the linked .blend (the levels of detail are the asset
                           versions': sync_manager/asset_versions.py, U1)
    ui.py               -> UIList, Panel, load_post handler
"""

from . import properties
from . import operators_list
from . import operators_link
from . import operators_files
from . import ui

# Re-export PropertyGroups for backward compatibility (em_props imports them from here)
from .properties import (
    AnastylisisItem,
    AnastylisisSettings,
    AnastylosisSFNodeItem,
)

__all__ = [
    'register',
    'unregister',
    'AnastylisisItem',
    'AnastylisisSettings',
    'AnastylosisSFNodeItem',
]


def register():
    # NOTE: PropertyGroups in properties.py are registered centrally by em_props.
    operators_list.register()
    operators_link.register()
    operators_files.register()
    ui.register()


def unregister():
    ui.unregister()
    operators_files.unregister()
    operators_link.unregister()
    operators_list.unregister()
