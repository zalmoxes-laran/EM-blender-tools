# proxy_inflate_manager/helpers.py
"""Shared helpers for adding/removing Solidify (inflate) modifiers on proxies.

`auto_inflate_for_export` / `cleanup_auto_inflate` are designed to be called
around an export to temporarily inflate proxies, then remove the modifiers.
The `export_pre_hook` / `export_post_hook` pair wraps that for operator patching.
"""


def get_inflate_name(obj_name):
    """Standardized name of the Solidify modifier used for inflation."""
    return f"{obj_name}_inflate"


def auto_inflate_for_export(context, objects_to_export):
    """Add inflate modifiers to objects that need them before export.

    Returns a list of objects that had modifiers added, so the caller can
    hand that list to `cleanup_auto_inflate` after the export finishes.
    """
    if not (hasattr(context.scene, "proxy_auto_inflate_on_export") and
            context.scene.em_tools.proxy_auto_inflate_on_export):
        return []

    modified_objects = []

    for obj in objects_to_export:
        if obj.type != 'MESH':
            continue

        has_inflate = any("_inflate" in mod.name for mod in obj.modifiers)
        if has_inflate:
            continue

        mod = obj.modifiers.new(name=get_inflate_name(obj.name), type='SOLIDIFY')

        if hasattr(context.scene, "proxy_inflate_thickness"):
            mod.thickness = context.scene.em_tools.proxy_inflate_thickness
            mod.offset = context.scene.em_tools.proxy_inflate_offset
        else:
            mod.thickness = 0.01
            mod.offset = 0.0

        mod.use_even_offset = True
        mod.use_quality_normals = True
        mod.use_rim = True
        mod.use_rim_only = False
        modified_objects.append(obj)

    return modified_objects


def cleanup_auto_inflate(modified_objects):
    """Remove temporary inflation modifiers added by `auto_inflate_for_export`."""
    for obj in modified_objects:
        for mod in obj.modifiers[:]:
            if "_inflate" in mod.name:
                obj.modifiers.remove(mod)


def export_pre_hook(self, context):
    """Called before export to add inflation modifiers if auto-inflate is on.

    Relies on `self.objects_to_export`; falls back to `context.selected_objects`.
    Stores the list of modified objects on `self.temp_inflated_objects` so the
    corresponding post-hook can clean them up.
    """
    objects_to_export = getattr(self, 'objects_to_export', context.selected_objects)
    modified_objects = auto_inflate_for_export(context, objects_to_export)
    self.temp_inflated_objects = modified_objects


def export_post_hook(self):
    """Called after export to remove temporary inflation modifiers."""
    if hasattr(self, 'temp_inflated_objects'):
        cleanup_auto_inflate(self.temp_inflated_objects)
        del self.temp_inflated_objects
