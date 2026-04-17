# anastylosis_manager/properties.py

import bpy
from bpy.props import BoolProperty, IntProperty, StringProperty
from bpy.types import PropertyGroup


class AnastylisisItem(PropertyGroup):
    """Properties for SpecialFind models in the anastylosis list"""
    name: StringProperty(
        name="Name",
        description="Name of the 3D model",
        default="Unnamed"
    )
    sf_node_id: StringProperty(
        name="SF Node ID",
        description="ID of the SpecialFind node this model is associated with",
        default=""
    )
    sf_node_name: StringProperty(
        name="SF Node Name",
        description="Name of the SpecialFind node",
        default=""
    )
    is_virtual: BoolProperty(
        name="Is Virtual",
        description="Whether this is a virtual reconstruction (VSF) or a real fragment (SF)",
        default=False
    )
    is_publishable: BoolProperty(
        name="Publishable",
        description="Whether this anastylosis model is publishable",
        default=True
    )
    node_id: StringProperty(
        name="Node ID",
        description="ID of the RMSF node in the graph",
        default=""
    )
    object_exists: BoolProperty(
        name="Object Exists",
        description="Whether the object exists in the scene",
        default=False
    )
    # LOD properties
    active_lod: IntProperty(
        name="Active LOD",
        description="Currently active LOD level for this object",
        default=0,
        min=0
    )
    has_lod_variants: BoolProperty(
        name="Has LOD Variants",
        description="Whether this object has LOD variants in the scene",
        default=False
    )
    lod_count: IntProperty(
        name="LOD Count",
        description="Number of LOD variants available",
        default=0,
        min=0
    )


class AnastylisisSettings(PropertyGroup):
    zoom_to_selected: BoolProperty(
        name="Zoom to Selected",
        description="Zoom to the selected object when clicked in the list",
        default=True
    )

    show_settings: BoolProperty(
        name="Show Settings",
        description="Show or hide the settings section",
        default=False
    )


class AnastylosisSFNodeItem(PropertyGroup):
    """Temporary item for SF node selection"""
    node_id: StringProperty(name="Node ID")
    name: StringProperty(name="Name")
    description: StringProperty(name="Description")


# NOTE: PropertyGroups are registered centrally by em_props.register(); this
# module only defines them. Do not call bpy.utils.register_class here or you
# will double-register and silently break the addon.
