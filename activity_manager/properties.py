# activity_manager/properties.py

import bpy
from bpy.props import (
    CollectionProperty,
    FloatProperty,
    IntProperty,
    StringProperty,
)
from bpy.types import PropertyGroup


def update_activity_filtered_lists_if_needed(self, context):
    # Se il filtro per attività è attivo, aggiorna la lista principale
    if context.scene.filter_by_activity:
        bpy.ops.em.filter_lists()


class ActivityItem(PropertyGroup):
    name: StringProperty(
        name="Nome Attività",
        description="Nome dell'attività",
    ) # type: ignore
    epoch_name: StringProperty(
        name="Nome Epoca",
        description="Nome dell'epoca",
    ) # type: ignore
    description: StringProperty(
        name="Descrizione",
        description="Descrizione dell'attività",
    ) # type: ignore
    y_pos: FloatProperty(
        name="Posizione Y",
        description="Posizione Y del nodo",
    ) # type: ignore


class ActivityManagerProperties(PropertyGroup):
    activities: CollectionProperty(type=ActivityItem) # type: ignore
    active_index: IntProperty(
        update=lambda self, context: update_activity_filtered_lists_if_needed(self, context)
    ) # type: ignore


classes = (
    ActivityItem,
    ActivityManagerProperties,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.activity_manager = bpy.props.PointerProperty(type=ActivityManagerProperties)


def unregister():
    del bpy.types.Scene.activity_manager
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
