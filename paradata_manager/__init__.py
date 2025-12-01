"""Paradata Manager package"""

from .data import register_data, unregister_data
from .operators import register_operators, unregister_operators
from .ui import register_ui, unregister_ui

__all__ = ["register", "unregister"]


def register():
    """Register all Paradata Manager components."""
    register_data()
    register_operators()
    register_ui()


def unregister():
    """Unregister all Paradata Manager components."""
    unregister_ui()
    unregister_operators()
    unregister_data()
