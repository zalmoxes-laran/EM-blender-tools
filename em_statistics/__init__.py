"""
EM Statistics Module
Modular structure for mesh statistics CSV export.

Organization:
    materials.py   -> CSV loading, EnumProperty items, decimal formatting
    metrics.py     -> volume/weight/surface computation (bmesh)
    properties.py  -> EMSceneProperties + Scene.em_properties
    operators.py   -> EMExportCSV (ExportHelper)
    ui.py          -> EM_PT_ExportPanel
"""

from . import properties
from . import operators
from . import ui

from .properties import EMSceneProperties
from .materials import load_materials, format_decimal
from .metrics import calculate_object_metrics, is_mesh_closed

__all__ = [
    'register',
    'unregister',
    'EMSceneProperties',
    'load_materials',
    'format_decimal',
    'calculate_object_metrics',
    'is_mesh_closed',
]


def register():
    properties.register()
    operators.register()
    ui.register()


def unregister():
    ui.unregister()
    operators.unregister()
    properties.unregister()
