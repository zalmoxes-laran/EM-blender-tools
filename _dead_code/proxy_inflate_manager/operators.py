# proxy_inflate_manager/operators.py
"""Operators that add/activate/deactivate/remove Solidify inflate modifiers on proxies."""

import bpy
from bpy.types import Operator

from .helpers import get_inflate_name


def _count_inflated_meshes():
    count = 0
    for obj in bpy.data.objects:
        if obj.type == 'MESH':
            for mod in obj.modifiers:
                if "_inflate" in mod.name:
                    count += 1
                    break
    return count


class EM_OT_ProxyAddInflate(Operator):
    bl_idname = "em.proxy_add_inflate"
    bl_label = "Add Inflate Modifier"
    bl_description = "Add Solidify modifier to selected proxies"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        selection = context.selected_objects
        if not selection:
            self.report({'WARNING'}, "No objects selected")
            return {'CANCELLED'}

        count = 0
        for obj in selection:
            if obj.type != 'MESH':
                continue
            if get_inflate_name(obj.name) in obj.modifiers:
                continue

            mod = obj.modifiers.new(name=get_inflate_name(obj.name), type='SOLIDIFY')
            mod.thickness = context.scene.em_tools.proxy_inflate_thickness
            mod.offset = context.scene.em_tools.proxy_inflate_offset
            mod.use_even_offset = True
            mod.use_quality_normals = True
            mod.use_rim = True
            mod.use_rim_only = False
            count += 1

        context.scene.proxy_inflate_stats = _count_inflated_meshes()
        self.report({'INFO'}, f"Added inflation to {count} proxies")
        return {'FINISHED'}


class EM_OT_ProxyActivateInflate(Operator):
    bl_idname = "em.proxy_activate_inflate"
    bl_label = "Activate Inflate Modifiers"
    bl_description = "Activate Solidify modifiers on selected proxies"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        selection = context.selected_objects
        if not selection:
            self.report({'WARNING'}, "No objects selected")
            return {'CANCELLED'}

        count = 0
        for obj in selection:
            if obj.type != 'MESH':
                continue
            for mod in obj.modifiers:
                if "_inflate" in mod.name and not mod.show_viewport:
                    mod.show_viewport = True
                    count += 1

        self.report({'INFO'}, f"Activated inflation on {count} proxies")
        return {'FINISHED'}


class EM_OT_ProxyDeactivateInflate(Operator):
    bl_idname = "em.proxy_deactivate_inflate"
    bl_label = "Deactivate Inflate Modifiers"
    bl_description = "Deactivate Solidify modifiers on selected proxies"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        selection = context.selected_objects
        if not selection:
            self.report({'WARNING'}, "No objects selected")
            return {'CANCELLED'}

        count = 0
        for obj in selection:
            if obj.type != 'MESH':
                continue
            for mod in obj.modifiers:
                if "_inflate" in mod.name and mod.show_viewport:
                    mod.show_viewport = False
                    count += 1

        self.report({'INFO'}, f"Deactivated inflation on {count} proxies")
        return {'FINISHED'}


class EM_OT_ProxyRemoveInflate(Operator):
    bl_idname = "em.proxy_remove_inflate"
    bl_label = "Remove Inflate Modifiers"
    bl_description = "Remove Solidify modifiers from selected proxies"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        selection = context.selected_objects
        if not selection:
            self.report({'WARNING'}, "No objects selected")
            return {'CANCELLED'}

        count = 0
        for obj in selection:
            if obj.type != 'MESH':
                continue
            for mod in obj.modifiers[:]:
                if "_inflate" in mod.name:
                    obj.modifiers.remove(mod)
                    count += 1

        context.scene.proxy_inflate_stats = max(0, context.scene.proxy_inflate_stats - count)
        self.report({'INFO'}, f"Removed inflation from {count} proxies")
        return {'FINISHED'}


class EM_OT_ProxyInflateAll(Operator):
    bl_idname = "em.proxy_inflate_all"
    bl_label = "Inflate All Proxies"
    bl_description = "Add Solidify modifier to all proxies without one"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        count = 0
        proxy_collection = bpy.data.collections.get('Proxy')

        if proxy_collection:
            targets = [obj for obj in proxy_collection.objects if obj.type == 'MESH']
        else:
            strat = context.scene.em_tools.stratigraphy
            if not strat.units:
                self.report({'WARNING'}, "No 'Proxy' collection found and no em_list available")
                return {'CANCELLED'}
            targets = []
            for item in strat.units:
                obj = bpy.data.objects.get(item.name)
                if obj and obj.type == 'MESH':
                    targets.append(obj)
            if not targets:
                self.report({'WARNING'}, "No proxies found in em_list")
                return {'CANCELLED'}

        for obj in targets:
            if get_inflate_name(obj.name) in obj.modifiers:
                continue

            mod = obj.modifiers.new(name=get_inflate_name(obj.name), type='SOLIDIFY')
            if hasattr(context.scene, "proxy_inflate_thickness"):
                mod.thickness = context.scene.em_tools.proxy_inflate_thickness
                mod.offset = context.scene.em_tools.proxy_inflate_offset
            else:
                mod.thickness = 0.01
                mod.offset = 0.0
                mod.merge_threshold = 0.0001

            mod.use_even_offset = True
            mod.use_quality_normals = True
            mod.use_rim = True
            mod.use_rim_only = False
            count += 1

        if hasattr(context.scene, "proxy_inflate_stats"):
            context.scene.proxy_inflate_stats = _count_inflated_meshes()

        self.report({'INFO'}, f"Added inflation to {count} proxies")
        return {'FINISHED'}


classes = (
    EM_OT_ProxyAddInflate,
    EM_OT_ProxyActivateInflate,
    EM_OT_ProxyDeactivateInflate,
    EM_OT_ProxyRemoveInflate,
    EM_OT_ProxyInflateAll,
)


def register():
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except ValueError:
            pass


def unregister():
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass
