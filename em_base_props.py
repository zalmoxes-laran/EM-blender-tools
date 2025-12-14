"""
EM-Tools Base PropertyGroup Classes
====================================

Base PropertyGroup classes that are used throughout the addon.
These are defined separately to avoid circular import issues.
"""

import bpy
from bpy.props import StringProperty, BoolProperty
from bpy.types import PropertyGroup


class EDGESListItem(PropertyGroup):
    """Edge information for graph edges"""
    id_node: StringProperty(
        name="id",
        description="Unique identifier for this edge",
        default=""
    )  # type: ignore
    source: StringProperty(
        name="source",
        description="Source node ID",
        default=""
    )  # type: ignore
    target: StringProperty(
        name="target",
        description="Target node ID",
        default=""
    )  # type: ignore
    edge_type: StringProperty(
        name="type",
        description="Type of edge connection",
        default=""
    )  # type: ignore


class EMviqListErrors(PropertyGroup):
    """Error tracking for EMviq exports"""
    name: StringProperty(
        name="Object",
        description="The object with an error",
        default=""
    )  # type: ignore
    description: StringProperty(
        name="Description",
        description="Description of the error",
        default=""
    )  # type: ignore
    material: StringProperty(
        name="Material",
        description="Associated material",
        default=""
    )  # type: ignore
    texture_type: StringProperty(
        name="Texture Type",
        description="Type of texture with error",
        default=""
    )  # type: ignore


class EMListParadata(PropertyGroup):
    """ParaData node information"""
    name: StringProperty(
        name="Name",
        description="Name of this paradata item",
        default="Untitled"
    )  # type: ignore
    description: StringProperty(
        name="Description",
        description="Description of this paradata item",
        default=""
    )  # type: ignore
    icon: StringProperty(
        name="Icon",
        description="Icon code for UI display",
        default="RESTRICT_INSTANCED_ON"
    )  # type: ignore
    icon_url: StringProperty(
        name="URL Icon",
        description="Icon for URL status",
        default="WORLD_DATA"
    )  # type: ignore
    url: StringProperty(
        name="URL",
        description="URL associated with this paradata",
        default=""
    )  # type: ignore
    id_node: StringProperty(
        name="Node ID",
        description="Unique node identifier",
        default=""
    )  # type: ignore


class EM_epochs_belonging_ob(PropertyGroup):
    """Association between objects and epochs"""
    epoch: StringProperty(
        name="Epoch",
        description="Associated epoch",
        default="Untitled"
    )  # type: ignore


class EM_Other_Settings(PropertyGroup):
    """General settings for EM Tools"""
    select_all_layers: BoolProperty(name="Select Visible Layers", default=True)  # type: ignore
    unlock_obj: BoolProperty(name="Unlock Objects", default=False)  # type: ignore
    unhide_obj: BoolProperty(name="Unhide Objects", default=True)  # type: ignore
    em_proxy_sync: BoolProperty(
        name="Selecting a proxy you select the corresponding EM",
        default=False
    )  # type: ignore
    em_proxy_sync2: BoolProperty(
        name="Selecting an EM you select the corresponding proxy",
        default=False
    )  # type: ignore
    em_proxy_sync2_zoom: BoolProperty(
        name="Option to zoom to proxy",
        default=False
    )  # type: ignore
    soloing_mode: BoolProperty(name="Soloing mode", default=False)  # type: ignore


# Classes to register (in order)
BASE_PROPERTY_CLASSES = [
    EDGESListItem,
    EMviqListErrors,
    EMListParadata,
    EM_epochs_belonging_ob,
    EM_Other_Settings,
]


def register():
    """Register base PropertyGroup classes"""
    print("[em_base_props] Registering base PropertyGroup classes...")
    for cls in BASE_PROPERTY_CLASSES:
        try:
            bpy.utils.register_class(cls)
            print(f"[em_base_props] ✓ Registered {cls.__name__}")
        except ValueError as e:
            print(f"[em_base_props] ⚠ Warning: Could not register {cls.__name__}: {e}")
    print("[em_base_props] ✓ Registration complete")


def unregister():
    """Unregister base PropertyGroup classes"""
    print("[em_base_props] Unregistering base PropertyGroup classes...")
    for cls in reversed(BASE_PROPERTY_CLASSES):
        try:
            bpy.utils.unregister_class(cls)
            print(f"[em_base_props] ✓ Unregistered {cls.__name__}")
        except RuntimeError as e:
            print(f"[em_base_props] ⚠ Warning: Could not unregister {cls.__name__}: {e}")
    print("[em_base_props] ✓ Unregistration complete")
