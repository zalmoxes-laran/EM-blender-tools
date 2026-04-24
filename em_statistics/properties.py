# em_statistics/properties.py

import bpy
from bpy.props import BoolProperty, EnumProperty, PointerProperty
from bpy.types import PropertyGroup

from .materials import get_material_items


class EMSceneProperties(PropertyGroup):
    export_volume: BoolProperty(name="Calculate Volume", default=True)
    export_weight: BoolProperty(name="Calculate weight", default=False)
    material_list: EnumProperty(name="Material", items=get_material_items)


classes = (
    EMSceneProperties,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.em_properties = PointerProperty(type=EMSceneProperties)


def unregister():
    del bpy.types.Scene.em_properties
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
