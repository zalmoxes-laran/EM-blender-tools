"""Data structures for the Paradata Manager."""

import bpy
from bpy.props import (
    PointerProperty,
    StringProperty,
    BoolProperty,
    IntProperty,
    CollectionProperty,
)  # type: ignore
from bpy.types import PropertyGroup


class ParadataImageProps(PropertyGroup):
    """Properties for handling paradata images."""

    image_path: StringProperty(
        name="Image Path",
        description="Path or URL to the image",
    )  # type: ignore
    is_loading: BoolProperty(
        name="Is Loading",
        description="Whether the image is currently loading",
        default=False,
    )  # type: ignore
    loaded_image: PointerProperty(
        name="Loaded Image",
        type=bpy.types.Image,
    )  # type: ignore
    auto_load: BoolProperty(
        name="Auto-load Images",
        description="Automatically load images when selecting documents or extractors",
        default=True,
    )  # type: ignore

    # Track the last seen selections
    last_source_index: IntProperty(default=-1)  # type: ignore
    last_extractor_index: IntProperty(default=-1)  # type: ignore

    image_collection: CollectionProperty(type=bpy.types.PropertyGroup)  # type: ignore
    active_image_index: IntProperty(default=0)  # type: ignore


classes = (ParadataImageProps,)


def register_data():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.paradata_image = PointerProperty(type=ParadataImageProps)


def unregister_data():
    # Clean up images before unregistering
    try:
        if (
            hasattr(bpy.context, "scene")
            and hasattr(bpy.context.scene, "paradata_image")
            and bpy.context.scene.paradata_image.loaded_image
        ):
            bpy.data.images.remove(bpy.context.scene.paradata_image.loaded_image)
    except Exception:
        pass

    if hasattr(bpy.types.Scene, "paradata_image"):
        del bpy.types.Scene.paradata_image

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
