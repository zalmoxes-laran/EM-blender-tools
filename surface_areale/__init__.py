"""
Surface Areale module for EM-Tools.
Creates surface proxy meshes on Representation Models for archaeological documentation.
"""

from . import data
from . import operators
from . import ui


def register():
    data.register()
    operators.register()
    ui.register()
    # Load benchmark calibration from disk (no-op if file doesn't exist)
    try:
        from .benchmark import load_calibration
        load_calibration()
    except Exception:
        pass


def unregister():
    ui.unregister()
    operators.unregister()
    data.unregister()
