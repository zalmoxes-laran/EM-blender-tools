"""Dead code (U1, MICRO-EMTOOLS-MENO-E-MEGLIO, 4 Oct 2026): RM Manager's own
change of level, replaced by the one of the asset versions
(`sync_manager/asset_versions.py`: `switch`, `em.asset_lod_step`,
`em.asset_set_level`, `em.asset_level_menu`), which RM Manager's panel now
calls. Kept for reading, never imported. What it did more than the versions —
the `_LODn` meshes of the same library, the `_LODn` objects of the scene, the
nearest-heavier fallback — is in `asset_versions.named_levels` and
`resolve_level`.
"""
import re

import bpy
from bpy.props import IntProperty
from bpy.types import Operator

LOD_MIN_LEVEL = 0
LOD_MAX_LEVEL = 4
LOD_SUFFIX_RE = re.compile(r"^(.+)_LOD(\d+)$")
LOD_FALLBACK_WARNING = "Some Levels of Detail were not found. Fallback applied to the nearest available LOD."


def _split_lod_name(name):
    """Return (base_name, lod_level) if name ends with _LOD#, else (None, None)."""
    m = LOD_SUFFIX_RE.match(name or "")
    if not m:
        return None, None
    return m.group(1), int(m.group(2))


def _get_active_lod(item_name):
    """Get active LOD level from object name or mesh datablock name."""
    _, lod = _split_lod_name(item_name)
    if lod is not None:
        return lod
    obj = bpy.data.objects.get(item_name)
    if obj and obj.type == 'MESH' and obj.data:
        _, lod = _split_lod_name(obj.data.name)
        if lod is not None:
            return lod
    return 0


def detect_lod_variants(obj_name):
    """Find LOD variants by checking both object names and mesh datablock names."""
    base_name, _ = _split_lod_name(obj_name)
    if base_name is None:
        # Object name has no LOD suffix — check mesh datablock name
        obj = bpy.data.objects.get(obj_name)
        if obj and obj.type == 'MESH' and obj.data:
            mesh_base, _ = _split_lod_name(obj.data.name)
            if mesh_base is not None:
                base_name = mesh_base
        if base_name is None:
            base_name = obj_name  # fallback

    variants = []
    seen = set()
    pattern = re.compile(r"^" + re.escape(base_name) + r"_LOD(\d+)$")
    for obj in bpy.data.objects:
        # Check object name
        m = pattern.match(obj.name)
        if m and obj.name not in seen:
            variants.append((int(m.group(1)), obj.name))
            seen.add(obj.name)
            continue
        # Check mesh datablock name (for linked mesh objects)
        if obj.type == 'MESH' and obj.data:
            m2 = pattern.match(obj.data.name)
            if m2 and obj.name not in seen:
                variants.append((int(m2.group(1)), obj.name))
                seen.add(obj.name)

    variants.sort(key=lambda x: x[0])
    return variants


def _resolve_lod_with_fallback(available_levels, requested_level, min_level=LOD_MIN_LEVEL, max_level=LOD_MAX_LEVEL):
    """Clamp request to [min,max] and fallback to highest available <= request."""
    if not available_levels:
        return None

    req = max(min_level, min(max_level, int(requested_level)))
    levels_in_range = sorted({lvl for lvl in available_levels if min_level <= lvl <= max_level})
    if not levels_in_range:
        return None

    lower_or_equal = [lvl for lvl in levels_in_range if lvl <= req]
    if lower_or_equal:
        return max(lower_or_equal)
    return min(levels_in_range)


def _rename_object_to_lod(obj, target_lod):
    base_name, _ = _split_lod_name(obj.name)
    if base_name is None:
        return
    obj.name = f"{base_name}_LOD{target_lod}"


def _switch_linked_mesh_lod(obj, requested_lod):
    """Switch linked mesh data to requested LOD with fallback to max available <= request."""
    if not obj or obj.type != 'MESH' or not obj.data or not obj.data.library:
        return False, None, None, "Object has no linked mesh library"

    mesh_name = obj.data.name
    base_name, _ = _split_lod_name(mesh_name)
    if base_name is None:
        return False, None, None, f"Mesh '{mesh_name}' has no _LODn suffix"

    lib_path = bpy.path.abspath(obj.data.library.filepath)
    target_mesh_name = None
    resolved_lod = None

    with bpy.data.libraries.load(lib_path, link=True) as (data_from, data_to):
        available_levels = []
        for name in data_from.meshes:
            m = LOD_SUFFIX_RE.match(name)
            if m and m.group(1) == base_name:
                available_levels.append(int(m.group(2)))

        resolved_lod = _resolve_lod_with_fallback(available_levels, requested_lod)
        if resolved_lod is None:
            return False, None, None, f"No LOD levels found for base '{base_name}' in library"

        target_mesh_name = f"{base_name}_LOD{resolved_lod}"
        data_to.meshes = [target_mesh_name]

    target_mesh = bpy.data.meshes.get(target_mesh_name)
    if target_mesh is None:
        return False, None, None, f"Mesh '{target_mesh_name}' could not be loaded from library"

    obj.data = target_mesh
    _rename_object_to_lod(obj, resolved_lod)
    return True, resolved_lod, target_mesh_name, None


class RM_OT_switch_lod(Operator):
    bl_idname = "rm.switch_lod"
    bl_label = "Switch LOD"
    bl_description = "Switch this RM item to a different Level of Detail"

    rm_index: IntProperty(
        name="RM Index",
        default=-1
    )  # type: ignore

    target_lod: IntProperty(
        name="Target LOD",
        default=0
    )  # type: ignore

    def execute(self, context):
        scene = context.scene

        if self.rm_index < 0:
            self.rm_index = scene.rm_list_index
        if self.rm_index < 0 or self.rm_index >= len(scene.rm_list):
            self.report({'ERROR'}, "Invalid RM index")
            return {'CANCELLED'}

        item = scene.rm_list[self.rm_index]
        obj = get_object_cache().get_object(item.name)
        requested_lod = max(LOD_MIN_LEVEL, min(LOD_MAX_LEVEL, int(self.target_lod)))

        if not obj:
            self.report({'ERROR'}, f"Object '{item.name}' not found in scene")
            return {'CANCELLED'}

        from .containers import rename_mesh_in_containers

        if obj.type == 'MESH' and obj.data and obj.data.library:
            old_name = item.name
            ok, resolved_lod, target_mesh_name, err = _switch_linked_mesh_lod(obj, requested_lod)
            if not ok:
                self.report({'ERROR'}, err or "LOD switch failed")
                return {'CANCELLED'}
            if resolved_lod != requested_lod:
                self.report({'WARNING'}, LOD_FALLBACK_WARNING)

            item.name = obj.name
            # Keep container.mesh_names entries pointing at the live
            # object name so the rm_list filter (which compares
            # item.name against container.mesh_names) doesn't drop
            # this mesh on the next redraw.
            if old_name != obj.name:
                rename_mesh_in_containers(scene, old_name, obj.name)
            item.active_lod = resolved_lod
            item.object_exists = True
            variants = detect_lod_variants(item.name)
            item.has_lod_variants = len(variants) > 1
            item.lod_count = len(variants)
            self.report({'INFO'}, f"Set LOD {resolved_lod} ({target_mesh_name})")
            return {'FINISHED'}

        variants = detect_lod_variants(item.name)
        if not variants:
            self.report({'ERROR'}, "No LOD variants found in scene")
            return {'CANCELLED'}

        by_level = {lod_level: lod_name for lod_level, lod_name in variants}
        resolved_lod = _resolve_lod_with_fallback(by_level.keys(), requested_lod)
        if resolved_lod is None or resolved_lod not in by_level:
            self.report({'ERROR'}, f"No usable LOD in range {LOD_MIN_LEVEL}-{LOD_MAX_LEVEL}")
            return {'CANCELLED'}
        if resolved_lod != requested_lod:
            self.report({'WARNING'}, LOD_FALLBACK_WARNING)

        target_name = by_level[resolved_lod]
        if target_name == item.name:
            item.active_lod = resolved_lod
            self.report({'INFO'}, f"Already at LOD {resolved_lod}")
            return {'FINISHED'}

        old_obj = obj
        new_obj = get_object_cache().get_object(target_name)
        if old_obj:
            old_obj.hide_viewport = True
            old_obj.hide_render = True
        if new_obj:
            new_obj.hide_viewport = False
            new_obj.hide_render = False

        old_name = item.name
        item.name = target_name
        # Same rationale as the linked-mesh path above: keep the
        # container's stored mesh name pointing at the LOD-variant
        # object that is now the active one.
        if old_name != target_name:
            rename_mesh_in_containers(scene, old_name, target_name)
        item.active_lod = resolved_lod
        item.object_exists = new_obj is not None
        item.has_lod_variants = len(variants) > 1
        item.lod_count = len(variants)
        self.report({'INFO'}, f"Set LOD {resolved_lod} ({target_name})")
        return {'FINISHED'}


class RM_OT_batch_switch_lod(Operator):
    bl_idname = "rm.batch_switch_lod"
    bl_label = "Batch Switch LOD"
    bl_description = "Switch LOD level for all RM items that have LOD variants"

    direction: IntProperty(
        name="Direction",
        description="+1 for higher LOD number, -1 for lower",
        default=1
    )  # type: ignore

    def execute(self, context):
        scene = context.scene
        switched = 0
        fallback_applied = False

        from .containers import rename_mesh_in_containers

        for item in scene.rm_list:
            obj = get_object_cache().get_object(item.name)
            if not obj or obj.type != 'MESH':
                continue

            target_lod = max(LOD_MIN_LEVEL, min(LOD_MAX_LEVEL, item.active_lod + self.direction))

            if obj.data and obj.data.library:
                old_name = item.name
                ok, resolved_lod, _target_mesh_name, _err = _switch_linked_mesh_lod(obj, target_lod)
                if ok:
                    if resolved_lod != target_lod:
                        fallback_applied = True
                    item.name = obj.name
                    if old_name != obj.name:
                        rename_mesh_in_containers(scene, old_name, obj.name)
                    item.active_lod = resolved_lod
                    item.object_exists = True
                    variants = detect_lod_variants(item.name)
                    item.has_lod_variants = len(variants) > 1
                    item.lod_count = len(variants)
                    switched += 1
                continue

            variants = detect_lod_variants(item.name)
            if len(variants) <= 1:
                continue

            by_level = {lod_level: lod_name for lod_level, lod_name in variants}
            resolved_lod = _resolve_lod_with_fallback(by_level.keys(), target_lod)
            if resolved_lod is None or resolved_lod not in by_level:
                continue
            if resolved_lod != target_lod:
                fallback_applied = True

            target_name = by_level[resolved_lod]
            if target_name == item.name:
                item.active_lod = resolved_lod
                continue

            old_obj = obj
            new_obj = get_object_cache().get_object(target_name)
            if old_obj:
                old_obj.hide_viewport = True
                old_obj.hide_render = True
            if new_obj:
                new_obj.hide_viewport = False
                new_obj.hide_render = False
            old_name = item.name
            item.name = target_name
            if old_name != target_name:
                rename_mesh_in_containers(scene, old_name, target_name)
            item.active_lod = resolved_lod
            item.object_exists = new_obj is not None
            item.has_lod_variants = len(variants) > 1
            item.lod_count = len(variants)
            switched += 1

        direction_text = "higher" if self.direction > 0 else "lower"
        if fallback_applied:
            self.report({'WARNING'}, LOD_FALLBACK_WARNING)
        self.report({'INFO'}, f"Switched {switched} items to {direction_text} LOD")
        return {'FINISHED'}


class RM_OT_batch_lod_selected(Operator):
    bl_idname = "rm.batch_lod_selected"
    bl_label = "Batch LOD for Selected Objects"
    bl_description = "Switch LOD level for all selected RM objects that have LOD variants"

    target_lod: IntProperty(
        name="Target LOD",
        default=0
    )  # type: ignore

    def execute(self, context):
        scene = context.scene
        switched = 0
        skipped = 0
        fallback_applied = False
        requested_lod = max(LOD_MIN_LEVEL, min(LOD_MAX_LEVEL, int(self.target_lod)))

        from .containers import rename_mesh_in_containers

        for obj in context.selected_objects:
            item = next((it for it in scene.rm_list if it.name == obj.name), None)
            if item is None:
                continue

            if obj.type == 'MESH' and obj.data and obj.data.library:
                old_name = item.name
                ok, resolved_lod, _target_mesh_name, _err = _switch_linked_mesh_lod(obj, requested_lod)
                if not ok:
                    skipped += 1
                    continue
                if resolved_lod != requested_lod:
                    fallback_applied = True
                item.name = obj.name
                if old_name != obj.name:
                    rename_mesh_in_containers(scene, old_name, obj.name)
                item.active_lod = resolved_lod
                item.object_exists = True
                variants = detect_lod_variants(item.name)
                item.has_lod_variants = len(variants) > 1
                item.lod_count = len(variants)
                switched += 1
                continue

            variants = detect_lod_variants(item.name)
            if not variants:
                skipped += 1
                continue

            by_level = {lod_level: lod_name for lod_level, lod_name in variants}
            resolved_lod = _resolve_lod_with_fallback(by_level.keys(), requested_lod)
            if resolved_lod is None or resolved_lod not in by_level:
                skipped += 1
                continue
            if resolved_lod != requested_lod:
                fallback_applied = True

            target_name = by_level[resolved_lod]
            if target_name == item.name:
                item.active_lod = resolved_lod
                continue

            old_obj = get_object_cache().get_object(item.name)
            new_obj = get_object_cache().get_object(target_name)
            if old_obj:
                old_obj.hide_viewport = True
                old_obj.hide_render = True
            if new_obj:
                new_obj.hide_viewport = False
                new_obj.hide_render = False
            old_name = item.name
            item.name = target_name
            if old_name != target_name:
                rename_mesh_in_containers(scene, old_name, target_name)
            item.active_lod = resolved_lod
            item.object_exists = new_obj is not None
            item.has_lod_variants = len(variants) > 1
            item.lod_count = len(variants)
            switched += 1

        if fallback_applied:
            self.report({'WARNING'}, LOD_FALLBACK_WARNING)
        msg = f"Switched {switched} objects to LOD {requested_lod}"
        if skipped > 0:
            msg += f" ({skipped} skipped - LOD not available)"
        self.report({'INFO'}, msg)
        return {'FINISHED'}


# Operator to open LOD popup menu for a specific row (fixes per-row index bug)
class RM_OT_open_lod_menu(Operator):
    bl_idname = "rm.open_lod_menu"
    bl_label = "Select LOD"
    bl_description = "Select LOD level for this item"
    bl_options = set()

    rm_index: IntProperty(default=-1)  # type: ignore

    def invoke(self, context, event):
        idx = self.rm_index
        scene = context.scene
        if idx < 0 or idx >= len(scene.rm_list):
            return {'CANCELLED'}
        item = scene.rm_list[idx]

        def draw_popup(self_menu, context):
            layout = self_menu.layout
            for lod_level in range(LOD_MIN_LEVEL, LOD_MAX_LEVEL + 1):
                is_active = (item.active_lod == lod_level)
                op = layout.operator("rm.switch_lod",
                    text=f"LOD {lod_level}" + (" (active)" if is_active else ""),
                    icon='CHECKMARK' if is_active else 'NONE')
                op.rm_index = idx
                op.target_lod = lod_level

        context.window_manager.popup_menu(draw_popup, title="Select LOD Level")
        return {'FINISHED'}


