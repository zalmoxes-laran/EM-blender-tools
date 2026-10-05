"""
Heriverse exporter subpackage.

Organization:
    utils.py           -> clean_filename, find_layer_collection, get_collection_for_object
    gltf.py            -> export_gltf_with_animation_support (thin bpy.ops.export_scene.gltf wrapper)
    json_export.py     -> HERIVERSE_OT_export_json (bl_idname 'export.heriversejson')
    collections_op.py  -> HERIVERSE_OT_make_collections_visible (pre-export visibility helper)
    operator.py        -> EXPORT_OT_heriverse (the main 'export.heriverse' operator)

The monolithic operator.py is intentionally kept as a single file for now;
internal splitting can be tackled separately.
"""

from . import utils, gltf, json_export, collections_op, operator

# Re-exports used by other modules (export_threaded.py, addon root __init__.py)
from .utils import clean_filename, find_layer_collection, get_collection_for_object
from .gltf import export_gltf_with_animation_support
from .json_export import HERIVERSE_OT_export_json
from .collections_op import HERIVERSE_OT_make_collections_visible
from .operator import EXPORT_OT_heriverse

__all__ = [
    'register',
    'unregister',
    'clean_filename',
    'find_layer_collection',
    'get_collection_for_object',
    'export_gltf_with_animation_support',
    'HERIVERSE_OT_export_json',
    'HERIVERSE_OT_make_collections_visible',
    'EXPORT_OT_heriverse',
]


def register():
    operator.register()
    json_export.register()
    collections_op.register()


def unregister():
    collections_op.unregister()
    json_export.unregister()
    operator.unregister()
