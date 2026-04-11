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


def unregister():
    ui.unregister()
    operators.unregister()
    data.unregister()
