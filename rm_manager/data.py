import bpy  # type: ignore
from bpy.props import (  # type: ignore
    BoolProperty,
    CollectionProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
)
from bpy.types import PropertyGroup  # type: ignore

__all__ = [
    "RMEpochItem",
    "RMItem",
    "RMSettings",
    "register_data",
    "unregister_data",
]


class RMEpochItem(PropertyGroup):
    """Properties for an epoch associated with an RM model"""

    name: StringProperty(
        name="Epoch Name",
        description="Name of the epoch",
        default="",
    )  # type: ignore
    epoch_id: StringProperty(
        name="Epoch ID",
        description="ID of the epoch node in the graph",
        default="",
    )  # type: ignore
    is_first_epoch: BoolProperty(
        name="Is First Epoch",
        description="Whether this is the first epoch for the RM",
        default=False,
    )  # type: ignore


class RMItem(PropertyGroup):
    """Properties for RM models in the list"""

    name: StringProperty(
        name="Name",
        description="Name of the RM model",
        default="Unnamed",
    )  # type: ignore
    first_epoch: StringProperty(
        name="First Epoch",
        description="First epoch this RM belongs to",
        default="",
    )  # type: ignore
    is_publishable: BoolProperty(
        name="Publishable",
        description="Whether this RM model is publishable",
        default=True,
    )  # type: ignore
    node_id: StringProperty(
        name="Node ID",
        description="ID of the RM node in the graph",
        default="",
    )  # type: ignore
    object_exists: BoolProperty(
        name="Object Exists",
        description="Whether the object exists in the scene",
        default=False,
    )  # type: ignore
    epoch_mismatch: BoolProperty(
        name="Epoch Mismatch",
        description="Indicates if there's a mismatch between the graph and the object epochs",
        default=False,
    )  # type: ignore
    epochs: CollectionProperty(
        type=RMEpochItem,
        name="Associated Epochs",
    )  # type: ignore
    active_epoch_index: IntProperty(
        name="Active Epoch Index",
        default=0,
    )  # type: ignore


class RMSettings(PropertyGroup):
    zoom_to_selected: BoolProperty(
        name="Zoom to Selected",
        description="Zoom to the selected object when clicked in the list",
        default=True,
    )  # type: ignore

    show_mismatches: BoolProperty(
        name="Show Epoch Mismatches",
        description="Highlight objects with mismatches between scene and graph epochs",
        default=True,
    )  # type: ignore

    auto_update_on_load: BoolProperty(
        name="Auto Update on Graph Load",
        description="Automatically update RM list when a graph is loaded",
        default=True,
    )  # type: ignore

    show_settings: BoolProperty(
        name="Show Settings",
        description="Show or hide the settings section",
        default=False,
    )  # type: ignore


def _register_class_once(cls):
    try:
        bpy.utils.register_class(cls)
    except ValueError:
        # Already registered from a previous run, unregister and try again
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
        bpy.utils.register_class(cls)


def register_data():
    for cls in (RMEpochItem, RMItem, RMSettings):
        _register_class_once(cls)

    if not hasattr(bpy.types.Scene, "rm_list"):
        bpy.types.Scene.rm_list = CollectionProperty(type=RMItem)
    if not hasattr(bpy.types.Scene, "rm_list_index"):
        bpy.types.Scene.rm_list_index = IntProperty(name="Index for RM list", default=0)
    if not hasattr(bpy.types.Scene, "rm_settings"):
        bpy.types.Scene.rm_settings = PointerProperty(type=RMSettings)


def unregister_data():
    if hasattr(bpy.types.Scene, "rm_settings"):
        del bpy.types.Scene.rm_settings
    if hasattr(bpy.types.Scene, "rm_list_index"):
        del bpy.types.Scene.rm_list_index
    if hasattr(bpy.types.Scene, "rm_list"):
        del bpy.types.Scene.rm_list

    for cls in reversed((RMSettings, RMItem, RMEpochItem)):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
