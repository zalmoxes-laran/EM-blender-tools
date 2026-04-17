# anastylosis_manager/operators_lod.py
"""LOD switching operators and 'open linked file' helper."""

import os
import subprocess

import bpy
from bpy.props import IntProperty
from bpy.types import Operator

from .lod_utils import (
    LOD_MIN_LEVEL,
    LOD_MAX_LEVEL,
    LOD_FALLBACK_WARNING,
    _switch_linked_mesh_lod,
    _resolve_lod_with_fallback,
    detect_lod_variants,
)


class ANASTYLOSIS_OT_switch_lod(Operator):
    bl_idname = "anastylosis.switch_lod"
    bl_label = "Switch LOD"
    bl_description = "Switch this item to a different Level of Detail"

    anastylosis_index: IntProperty(
        name="Anastylosis Index",
        default=-1
    ) # type: ignore

    target_lod: IntProperty(
        name="Target LOD",
        default=0
    ) # type: ignore

    def execute(self, context):
        anastylosis = context.scene.em_tools.anastylosis

        if self.anastylosis_index < 0 or self.anastylosis_index >= len(anastylosis.list):
            self.report({'ERROR'}, "Invalid anastylosis index")
            return {'CANCELLED'}

        item = anastylosis.list[self.anastylosis_index]

        obj = bpy.data.objects.get(item.name)
        requested_lod = max(LOD_MIN_LEVEL, min(LOD_MAX_LEVEL, int(self.target_lod)))

        if not obj:
            self.report({'ERROR'}, f"Object '{item.name}' not found in scene")
            return {'CANCELLED'}

        # Linked mesh workflow: swap mesh datablock from library and fallback automatically.
        if obj.type == 'MESH' and obj.data and obj.data.library:
            ok, resolved_lod, target_mesh_name, err = _switch_linked_mesh_lod(obj, requested_lod)
            if not ok:
                self.report({'ERROR'}, err or "LOD switch failed")
                return {'CANCELLED'}
            if resolved_lod != requested_lod:
                self.report({'WARNING'}, LOD_FALLBACK_WARNING)

            item.name = obj.name
            item.active_lod = resolved_lod
            item.object_exists = True
            self.report({'INFO'}, f"Set LOD {resolved_lod} ({target_mesh_name})")
            return {'FINISHED'}

        # Local-scene workflow: switch visibility to an existing object variant in scene.
        variants = detect_lod_variants(item.name)
        if not variants:
            self.report({'ERROR'}, "No LOD variants found in scene")
            return {'CANCELLED'}

        by_level = {lod_level: lod_name for lod_level, lod_name in variants}
        resolved_lod = _resolve_lod_with_fallback(by_level.keys(), requested_lod)
        if resolved_lod is None or resolved_lod not in by_level:
            self.report({'ERROR'}, f"No usable LOD in range {LOD_MIN_LEVEL}-{LOD_MAX_LEVEL}")
            return {'CANCELLED'}

        target_name = by_level[resolved_lod]
        if resolved_lod != requested_lod:
            self.report({'WARNING'}, LOD_FALLBACK_WARNING)
        if target_name == item.name:
            item.active_lod = resolved_lod
            self.report({'INFO'}, f"Already at LOD {resolved_lod}")
            return {'FINISHED'}

        old_obj = obj
        new_obj = bpy.data.objects.get(target_name)
        if old_obj:
            old_obj.hide_viewport = True
            old_obj.hide_render = True
        if new_obj:
            new_obj.hide_viewport = False
            new_obj.hide_render = False

        item.name = target_name
        item.active_lod = resolved_lod
        item.object_exists = new_obj is not None

        self.report({'INFO'}, f"Set LOD {resolved_lod} ({target_name})")
        return {'FINISHED'}


class ANASTYLOSIS_OT_batch_switch_lod(Operator):
    bl_idname = "anastylosis.batch_switch_lod"
    bl_label = "Batch Switch LOD"
    bl_description = "Switch LOD level for all items that have LOD variants"

    direction: IntProperty(
        name="Direction",
        description="+1 for higher LOD number, -1 for lower",
        default=1
    ) # type: ignore

    def execute(self, context):
        anastylosis = context.scene.em_tools.anastylosis
        switched = 0
        fallback_applied = False

        for item in anastylosis.list:
            obj = bpy.data.objects.get(item.name)
            if not obj or obj.type != 'MESH':
                continue

            target_lod = max(LOD_MIN_LEVEL, min(LOD_MAX_LEVEL, item.active_lod + self.direction))

            if obj.data and obj.data.library:
                ok, resolved_lod, _target_mesh_name, _err = _switch_linked_mesh_lod(obj, target_lod)
                if ok:
                    if resolved_lod != target_lod:
                        fallback_applied = True
                    item.name = obj.name
                    item.active_lod = resolved_lod
                    item.object_exists = True
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
            new_obj = bpy.data.objects.get(target_name)
            if old_obj:
                old_obj.hide_viewport = True
                old_obj.hide_render = True
            if new_obj:
                new_obj.hide_viewport = False
                new_obj.hide_render = False
            item.name = target_name
            item.active_lod = resolved_lod
            item.object_exists = new_obj is not None
            switched += 1

        direction_text = "higher" if self.direction > 0 else "lower"
        if fallback_applied:
            self.report({'WARNING'}, LOD_FALLBACK_WARNING)
        self.report({'INFO'}, f"Switched {switched} items to {direction_text} LOD")
        return {'FINISHED'}


class ANASTYLOSIS_OT_open_lod_menu(Operator):
    """Open LOD popup menu for a specific row (fixes per-row index bug)."""
    bl_idname = "anastylosis.open_lod_menu"
    bl_label = "Select LOD"
    bl_description = "Select LOD level for this item"
    bl_options = set()

    anastylosis_index: IntProperty(default=-1)  # type: ignore

    def invoke(self, context, event):
        idx = self.anastylosis_index
        anastylosis = context.scene.em_tools.anastylosis
        if idx < 0 or idx >= len(anastylosis.list):
            return {'CANCELLED'}
        item = anastylosis.list[idx]

        def draw_popup(self_menu, context):
            layout = self_menu.layout
            for lod_level in range(LOD_MIN_LEVEL, LOD_MAX_LEVEL + 1):
                is_active = (item.active_lod == lod_level)
                op = layout.operator("anastylosis.switch_lod",
                    text=f"LOD {lod_level}" + (" (active)" if is_active else ""),
                    icon='CHECKMARK' if is_active else 'NONE')
                op.anastylosis_index = idx
                op.target_lod = lod_level

        context.window_manager.popup_menu(draw_popup, title="Select LOD Level")
        return {'FINISHED'}


class ANASTYLOSIS_MT_batch_lod_selected(bpy.types.Menu):
    """Menu for batch LOD switch on selected 3D objects."""
    bl_label = "Batch LOD for Selected"
    bl_idname = "ANASTYLOSIS_MT_batch_lod_selected"

    def draw(self, context):
        layout = self.layout
        for level in range(LOD_MIN_LEVEL, LOD_MAX_LEVEL + 1):
            op = layout.operator("anastylosis.batch_lod_selected", text=f"Set LOD {level}")
            op.target_lod = level


class ANASTYLOSIS_OT_batch_lod_selected(Operator):
    bl_idname = "anastylosis.batch_lod_selected"
    bl_label = "Batch LOD for Selected Objects"
    bl_description = "Switch LOD level for all selected objects that have LOD variants"

    target_lod: IntProperty(
        name="Target LOD",
        default=0
    ) # type: ignore

    def execute(self, context):
        switched = 0
        skipped = 0
        fallback_applied = False
        anastylosis = context.scene.em_tools.anastylosis
        requested_lod = max(LOD_MIN_LEVEL, min(LOD_MAX_LEVEL, int(self.target_lod)))

        for obj in context.selected_objects:
            item_idx = None
            for i, item in enumerate(anastylosis.list):
                if item.name == obj.name:
                    item_idx = i
                    break
            if item_idx is None:
                continue

            item = anastylosis.list[item_idx]
            if obj.type == 'MESH' and obj.data and obj.data.library:
                ok, resolved_lod, _target_mesh_name, _err = _switch_linked_mesh_lod(obj, requested_lod)
                if not ok:
                    skipped += 1
                    continue
                if resolved_lod != requested_lod:
                    fallback_applied = True
                item.name = obj.name
                item.active_lod = resolved_lod
                item.object_exists = True
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

            old_obj = bpy.data.objects.get(item.name)
            new_obj = bpy.data.objects.get(target_name)
            if old_obj:
                old_obj.hide_viewport = True
                old_obj.hide_render = True
            if new_obj:
                new_obj.hide_viewport = False
                new_obj.hide_render = False
            item.name = target_name
            item.active_lod = resolved_lod
            item.object_exists = new_obj is not None
            switched += 1

        if fallback_applied:
            self.report({'WARNING'}, LOD_FALLBACK_WARNING)
        msg = f"Switched {switched} objects to LOD {requested_lod}"
        if skipped > 0:
            msg += f" ({skipped} skipped - LOD not available)"
        self.report({'INFO'}, msg)
        return {'FINISHED'}


class ANASTYLOSIS_OT_open_linked_file(Operator):
    """Open linked .blend file for this anastylosis object in a new Blender instance"""
    bl_idname = "anastylosis.open_linked_file"
    bl_label = "Open Linked File"
    bl_options = {"REGISTER", "UNDO"}

    anastylosis_index: IntProperty(
        name="Anastylosis Index",
        default=-1
    )  # type: ignore

    def execute(self, context):
        anastylosis = context.scene.em_tools.anastylosis
        index = self.anastylosis_index if self.anastylosis_index >= 0 else anastylosis.list_index
        if index < 0 or index >= len(anastylosis.list):
            self.report({'ERROR'}, "No anastylosis item selected")
            return {'CANCELLED'}

        item = anastylosis.list[index]
        obj = bpy.data.objects.get(item.name)
        if not obj:
            self.report({'ERROR'}, f"Object '{item.name}' not found in scene")
            return {'CANCELLED'}

        linked_file = None
        if obj.library:
            linked_file = obj.library.filepath
        elif obj.data and obj.data.library:
            linked_file = obj.data.library.filepath

        if not linked_file:
            self.report({'ERROR'}, f"Object '{obj.name}' is not linked from an external .blend")
            return {'CANCELLED'}

        linked_file = bpy.path.abspath(linked_file)
        if not os.path.exists(linked_file):
            self.report({'ERROR'}, f"Linked file not found: {linked_file}")
            return {'CANCELLED'}

        try:
            subprocess.Popen([bpy.app.binary_path, linked_file])
        except Exception as e:
            self.report({'ERROR'}, f"Failed to open linked file: {str(e)}")
            return {'CANCELLED'}

        self.report({'INFO'}, f"Opened linked file: {linked_file}")
        return {'FINISHED'}


classes = (
    ANASTYLOSIS_OT_open_lod_menu,
    ANASTYLOSIS_MT_batch_lod_selected,
    ANASTYLOSIS_OT_switch_lod,
    ANASTYLOSIS_OT_batch_switch_lod,
    ANASTYLOSIS_OT_batch_lod_selected,
    ANASTYLOSIS_OT_open_linked_file,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
