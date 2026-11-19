"""``em`` in Blender (MICRO-PL19, row W16 of the extensions plan).

EM Tools is the host of s3Dgraphy's scripting API in this Blender: the same
``from s3dgraphy import em`` as in EMStudio and in a script, on the ACTIVE graph
of EM Setup, every write one step through the contract (with its DTC, its line
in the Log and its «Undo»); ``em.app`` with Blender's selection and 3D view; the
plugins whose ``hosts`` names ``blender`` under EM ▸ Plugin; «Open EM console»
and «Run as EM script» behind Experimental (D-7). See ``core.py`` (no bpy).
"""

from . import i18n


def register():
    i18n.register()
    from . import blender, operators
    operators.register()
    blender.install()


def unregister():
    from . import blender, operators
    blender.uninstall()
    operators.unregister()
    i18n.unregister()
