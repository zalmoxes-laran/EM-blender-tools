"""
CronoFilter Module - Custom Chronological Horizons Manager
==========================================================

Functionality to create, manage, and save custom chronological horizons
exported in the Heriverse format as part of the context section.

Organization:
    properties.py           -> PropertyGroups (CF_ChronologicalHorizon, CF_CronoFilterSettings)
                               + Scene.cf_settings PointerProperty + _hex_to_rgb helper
    operators.py            -> Add / Remove / Move / Save / Load / AutoHorizons operators
    ui.py                   -> CF_UL_HorizonList + CF_PT_CronoFilterPanel
    integration.py          -> Runtime integration helpers (horizon validation/preview)
    json_exporter_patch.py  -> Patch that wires custom horizons into the JSON exporter
"""

from . import properties, operators, ui
from . import integration, json_exporter_patch  # kept as siblings; they self-import where needed

from .properties import CF_ChronologicalHorizon, CF_CronoFilterSettings, _hex_to_rgb

__all__ = [
    'register',
    'unregister',
    'CF_ChronologicalHorizon',
    'CF_CronoFilterSettings',
]


def register():
    properties.register()
    operators.register()
    ui.register()


def unregister():
    ui.unregister()
    operators.unregister()
    properties.unregister()
