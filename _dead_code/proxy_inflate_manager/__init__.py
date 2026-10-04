"""
Proxy Inflate Manager Module
Adds Solidify modifiers to proxy meshes (useful before export).

Organization:
    helpers.py    -> get_inflate_name + auto_inflate_for_export + cleanup + export_pre/post hooks
    operators.py  -> EM_OT_ProxyAdd/Activate/Deactivate/Remove/InflateAll
    ui.py         -> VIEW3D_PT_ProxyInflatePanel (sub-panel of Visual Manager, gated by experimental_features)

Scene property `proxy_inflate_stats` is owned by this module.
Scene.em_tools.proxy_inflate_thickness / proxy_inflate_offset / proxy_auto_inflate_on_export
are owned by em_props.py and only consumed here.
"""

import bpy

from . import helpers, operators, ui

# Re-export helpers so external hook callers (if any) can import from the top level
from .helpers import (
    get_inflate_name,
    auto_inflate_for_export,
    cleanup_auto_inflate,
    export_pre_hook,
    export_post_hook,
)

__all__ = [
    'register',
    'unregister',
    'get_inflate_name',
    'auto_inflate_for_export',
    'cleanup_auto_inflate',
    'export_pre_hook',
    'export_post_hook',
]


def register():
    bpy.types.Scene.proxy_inflate_stats = bpy.props.IntProperty(
        name="Inflated Proxy Count",
        default=0,
    )
    operators.register()
    ui.register()


def unregister():
    ui.unregister()
    operators.unregister()
    if hasattr(bpy.types.Scene, "proxy_inflate_stats"):
        del bpy.types.Scene.proxy_inflate_stats
