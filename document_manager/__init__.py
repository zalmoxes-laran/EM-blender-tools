"""Document Manager package — dedicated management of documents as space-time entities."""

from .ui import register_ui, unregister_ui
from .operators import register_operators, unregister_operators

__all__ = ["register", "unregister"]


def register():
    """Register all Document Manager components."""
    register_operators()
    register_ui()


def unregister():
    """Unregister all Document Manager components."""
    unregister_ui()
    unregister_operators()
