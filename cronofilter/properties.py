# cronofilter/properties.py
"""PropertyGroups for CronoFilter chronological horizons."""

import bpy
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    IntProperty,
    StringProperty,
)
from bpy.types import PropertyGroup


def _hex_to_rgb(hex_color):
    """Convert hex color string to normalized RGB tuple for Blender."""
    if not hex_color or not hex_color.startswith('#'):
        return (0.5, 0.5, 0.5)
    try:
        h = hex_color.lstrip('#')
        return tuple(int(h[i:i+2], 16) / 255.0 for i in (0, 2, 4))
    except (ValueError, IndexError):
        return (0.5, 0.5, 0.5)


class CF_ChronologicalHorizon(PropertyGroup):
    """Individual chronological horizon data"""
    label: StringProperty(
        name="Label",
        description="Name/label for this chronological horizon",
        default="New Horizon"
    ) # type: ignore

    start_time: IntProperty(
        name="Start Time",
        description="Start time (years, negative for BC)",
        default=0
    ) # type: ignore

    end_time: IntProperty(
        name="End Time",
        description="End time (years, negative for BC)",
        default=100
    ) # type: ignore

    color: bpy.props.FloatVectorProperty(
        name="Color",
        description="Color for this horizon",
        subtype='COLOR',
        default=(0.5, 0.5, 0.5),
        min=0.0,
        max=1.0,
        size=3
    ) # type: ignore

    enabled: BoolProperty(
        name="Enabled",
        description="Include this horizon in exports",
        default=True
    ) # type: ignore


class CF_CronoFilterSettings(PropertyGroup):
    """Main settings for CronoFilter"""
    horizons: CollectionProperty(
        type=CF_ChronologicalHorizon,
        name="Chronological Horizons"
    ) # type: ignore

    active_horizon_index: IntProperty(
        name="Active Horizon Index",
        default=0
    ) # type: ignore

    expanded: BoolProperty(
        name="Panel Expanded",
        description="Show/hide CronoFilter panel",
        default=False
    ) # type: ignore


classes = (
    CF_ChronologicalHorizon,
    CF_CronoFilterSettings,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.cf_settings = bpy.props.PointerProperty(type=CF_CronoFilterSettings)


def unregister():
    if hasattr(bpy.types.Scene, 'cf_settings'):
        delattr(bpy.types.Scene, 'cf_settings')
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
