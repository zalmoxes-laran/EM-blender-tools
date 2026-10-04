"""U5 · the images of the units and of the finds (see core.py)."""


def register():  # pragma: no cover — bpy
    from . import blender
    blender.register()


def unregister():  # pragma: no cover — bpy
    from . import blender
    blender.unregister()
