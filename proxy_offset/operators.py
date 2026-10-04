"""U2 · the operators of «Offset proxy» (see the package's docstring)."""

import bpy
from bpy.props import EnumProperty
from bpy.types import Operator

from . import MODIFIER, old_inflate_names, said

SCOPES = [("ACTIVE", "Active proxy", ""), ("SELECTED", "Selected", ""),
          ("ALL", "All proxies", "Every proxy of the stratigraphy list")]


def all_proxies(context):
    """The proxies of the stratigraphy list, found as the list finds them;
    with no list (no graph loaded), the meshes of the «Proxy» collection, as
    the old «Inflate All» did."""
    from ..functions import get_proxy_from_list_item
    out, seen = [], set()
    for item in context.scene.em_tools.stratigraphy.units:
        obj = get_proxy_from_list_item(item, context=context)
        if obj is not None and obj.type == 'MESH' and obj.name not in seen:
            seen.add(obj.name)
            out.append(obj)
    if not out:
        coll = bpy.data.collections.get("Proxy")
        out = [o for o in (coll.all_objects if coll else []) if o.type == 'MESH']
    return out


def targets(context, scope):
    if scope == "ACTIVE":
        obj = context.active_object
        return [obj] if obj is not None and obj.type == 'MESH' else []
    if scope == "ALL":
        return all_proxies(context)
    return [o for o in context.selected_objects if o.type == 'MESH']


def distance(context) -> float:
    return float(context.scene.em_tools.proxy_offset_distance)


def put_offset(obj, dist: float) -> bool:
    """Add (or update) the offset on ``obj``; True when it was added."""
    mod = obj.modifiers.get(MODIFIER)
    added = mod is None
    if added:
        mod = obj.modifiers.new(name=MODIFIER, type='DISPLACE')
    mod.direction = 'NORMAL'
    mod.space = 'LOCAL'
    mod.mid_level = 0.0
    mod.texture = None
    # Displace works in the object's space: a scaled proxy is given the
    # distance in WORLD units
    scale = max(abs(s) for s in obj.matrix_world.to_scale()) or 1.0
    mod.strength = dist / scale
    mod.show_in_editmode = True
    return added


def refresh_all(scene) -> int:
    """The distance changed: every proxy already offset follows it."""
    dist = float(scene.em_tools.proxy_offset_distance)
    n = 0
    for obj in bpy.data.objects:
        if obj.type == 'MESH' and obj.modifiers.get(MODIFIER) is not None:
            put_offset(obj, dist)
            n += 1
    return n


def count_offset() -> int:
    return sum(1 for o in bpy.data.objects if o.type == 'MESH' and o.modifiers.get(MODIFIER) is not None)


def count_old_inflate() -> int:
    return sum(1 for o in bpy.data.objects
               if o.type == 'MESH' and old_inflate_names(m.name for m in o.modifiers if m.type == 'SOLIDIFY'))


class EM_OT_proxy_offset(Operator):
    """Move the proxy a little outside the surface it annotates (along its
    normals, with a modifier: the mesh is not touched), so it does not
    z-fight with the RM"""

    bl_idname = "em.proxy_offset"
    bl_label = "Offset proxy"
    bl_options = {'REGISTER', 'UNDO'}

    scope: EnumProperty(items=SCOPES, default="SELECTED")  # type: ignore

    def execute(self, context):
        objs = targets(context, self.scope)
        dist = distance(context)
        for obj in objs:
            put_offset(obj, dist)
        self.report({'INFO'} if objs else {'WARNING'}, said("offset", len(objs), dist))
        return {'FINISHED'} if objs else {'CANCELLED'}


class EM_OT_proxy_offset_remove(Operator):
    """Bring the proxy back on the surface: remove its offset"""

    bl_idname = "em.proxy_offset_remove"
    bl_label = "Back on the surface"
    bl_options = {'REGISTER', 'UNDO'}

    scope: EnumProperty(items=SCOPES, default="SELECTED")  # type: ignore

    def execute(self, context):
        n = 0
        for obj in targets(context, self.scope):
            mod = obj.modifiers.get(MODIFIER)
            if mod is not None:
                obj.modifiers.remove(mod)
                n += 1
        self.report({'INFO'} if n else {'WARNING'}, said("remove", n, distance(context)))
        return {'FINISHED'} if n else {'CANCELLED'}


class EM_OT_proxy_old_inflate_remove(Operator):
    """Remove the Solidify modifiers of the old inflation (`<name>_inflate`)
    from every object of the file"""

    bl_idname = "em.proxy_old_inflate_remove"
    bl_label = "Remove the old inflation"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        n = 0
        for obj in bpy.data.objects:
            if obj.type != 'MESH':
                continue
            for mod in list(obj.modifiers):
                if mod.type == 'SOLIDIFY' and old_inflate_names([mod.name]):
                    obj.modifiers.remove(mod)
                    n += 1
        self.report({'INFO'}, f"{n} old inflate modifier(s) removed")
        return {'FINISHED'}


classes = (EM_OT_proxy_offset, EM_OT_proxy_offset_remove, EM_OT_proxy_old_inflate_remove)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass
