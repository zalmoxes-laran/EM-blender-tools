"""3D Document Manager package — manage documents as spatial-temporal entities.

Placed in EM Annotator tab alongside RM Manager and Anastylosis Manager.
Provides image import → textured quad → camera creation workflow.
"""

from .data import register_data, unregister_data
from .operators import register_operators, unregister_operators
from .ui import register_ui, unregister_ui

__all__ = ["register", "unregister"]


def register():
    """Register all 3D Document Manager components."""
    register_data()
    register_operators()
    register_ui()


def unregister():
    """Unregister all 3D Document Manager components."""
    unregister_ui()
    unregister_operators()
    unregister_data()
