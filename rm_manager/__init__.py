import bpy  # type: ignore

from .data import (
    RMItem,
    RMEpochItem,
    RMSettings,
    register_data,
    unregister_data,
)
from .handlers import update_rm_list_on_graph_load
from .operators import register_operators, unregister_operators
from .ui import register_ui, unregister_ui

__all__ = [
    "RMItem",
    "RMEpochItem",
    "RMSettings",
    "register",
    "unregister",
]


def register():
    register_data()
    register_operators()
    register_ui()

    if update_rm_list_on_graph_load not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(update_rm_list_on_graph_load)


def unregister():
    if update_rm_list_on_graph_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(update_rm_list_on_graph_load)

    unregister_ui()
    unregister_operators()
    unregister_data()
