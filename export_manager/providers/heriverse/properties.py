# export_manager/providers/heriverse/properties.py
"""Heriverse-specific Scene properties.

These live on bpy.types.Scene (not on a PropertyGroup aggregator) because the
legacy exporter code and several panels already read them via scene.heriverse_*.
Registered/unregistered with the provider so the lifecycle is self-contained.
"""

import bpy
from bpy.props import BoolProperty, IntProperty, StringProperty


def _scene_props():
    """Return an iterable of (attr_name, Blender property) to attach to Scene."""
    path_opts = {'PATH_SUPPORTS_BLEND_RELATIVE'} if bpy.app.version >= (4, 5, 0) else set()

    return [
        ("heriverse_export_path", StringProperty(
            name="Heriverse Export Path",
            description="Path where to export Heriverse project",
            subtype='DIR_PATH',
            default="",
            options=path_opts,
        )),
        ("heriverse_project_name", StringProperty(
            name="Heriverse Project Name",
            description="Name of the Heriverse project",
            default="",
        )),
        ("heriverse_export_panorama", BoolProperty(
            name="Export Default Panorama",
            description="Export the default panorama (defsky.jpg) to the project",
            default=True,
        )),
        ("heriverse_enable_compression", BoolProperty(
            name="Enable Texture Compression",
            description="Enable compression for textures in Heriverse export",
            default=True,
        )),
        ("heriverse_texture_max_res", IntProperty(
            name="Max Resolution",
            description="Maximum resolution for texture edges",
            default=4096, min=512, max=8192,
        )),
        ("heriverse_texture_quality", IntProperty(
            name="Texture Quality",
            description="JPEG compression quality (100=lossless, 80=good, 60=compressed, 40=heavily compressed)",
            default=80, min=10, max=100,
        )),
        ("heriverse_paradata_texture_compression", BoolProperty(
            name="Compress ParaData Textures",
            description="Enable compression for textures in ParaData objects",
            default=True,
        )),
        ("heriverse_paradata_texture_quality", IntProperty(
            name="ParaData Texture Quality",
            description="JPEG compression quality for ParaData textures",
            default=75, min=10, max=100,
        )),
        ("heriverse_rmdoc_texture_max_res", IntProperty(
            name="ParaData Max Resolution",
            description="Maximum resolution for ParaData textures",
            default=2048, min=512, max=8192,
        )),
        ("heriverse_rmdoc_texture_quality", IntProperty(
            name="ParaData Quality",
            description="JPEG compression quality for ParaData textures (100=lossless, 80=good, 60=compressed, 40=heavily compressed)",
            default=60, min=10, max=100,
        )),
        ("heriverse_preserve_rmdoc_transform", BoolProperty(
            name="Preserve ParaData Transforms",
            description="Save and restore original position, rotation and scale of ParaData objects during export",
            default=True,
        )),
    ]


def register():
    for attr, prop in _scene_props():
        setattr(bpy.types.Scene, attr, prop)


def unregister():
    for attr, _prop in _scene_props():
        if hasattr(bpy.types.Scene, attr):
            delattr(bpy.types.Scene, attr)
