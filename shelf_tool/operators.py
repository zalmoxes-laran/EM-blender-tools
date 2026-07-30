"""Operators for the EM Shelf tool.

A folder picker, a 3D-first scan that drives the acquisition pipeline in-process,
and standalone save/load + remove. All heavy lifting is in shelf_backend.py (which
calls s3dgraphy); these operators are thin Blender wrappers. NO hatting (C2).
"""

from __future__ import annotations

import os

import bpy
from bpy.types import Operator

from . import shelf_backend

_STALE = ("Shelf unavailable: the active s3dgraphy is stale — activate the "
          "dev/updated s3dgraphy (./em.sh s3d), then reopen.")


class EM_OT_shelf_set_folder(Operator):
    bl_idname = "em.shelf_set_folder"
    bl_label = "Set project folder"
    bl_description = "Choose the project folder to scan (opens a folder browser)"
    bl_options = {'REGISTER'}

    directory: bpy.props.StringProperty(subtype='DIR_PATH')  # type: ignore

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        context.scene.em_shelf.folder = self.directory
        for area in context.screen.areas:
            area.tag_redraw()
        return {'FINISHED'}


class EM_OT_shelf_scan(Operator):
    bl_idname = "em.shelf_scan"
    bl_label = "Scan for 3D"
    bl_description = ("Scan the project folder for 3D files and acquire each onto "
                      "the Shelf (import + origin)")
    bl_options = {'REGISTER'}

    def execute(self, context):
        if not shelf_backend.shelf_supported():
            self.report({'ERROR'}, _STALE)
            return {'CANCELLED'}
        p = context.scene.em_shelf
        folder = bpy.path.abspath(p.folder) if p.folder else ""
        if not folder or not os.path.isdir(folder):
            self.report({'WARNING'}, "Set a valid project folder first.")
            return {'CANCELLED'}
        try:
            res = shelf_backend.scan_folder(folder, recursive=p.recursive)
        except Exception as exc:
            self.report({'ERROR'}, f"Scan failed: {exc}")
            return {'CANCELLED'}
        p.status = (f"Scanned {res['scanned']} 3D file(s) — Shelf has "
                    f"{res['shelf_count']} resource(s)")
        for area in context.screen.areas:
            area.tag_redraw()
        return {'FINISHED'}


class EM_OT_shelf_new(Operator):
    bl_idname = "em.shelf_new"
    bl_label = "New Shelf"
    bl_description = "Start a new empty Shelf (unsaved)"
    bl_options = {'REGISTER'}

    def execute(self, context):
        if not shelf_backend.shelf_supported():
            self.report({'ERROR'}, _STALE)
            return {'CANCELLED'}
        shelf_backend.new_shelf()
        context.scene.em_shelf.status = "New shelf"
        for area in context.screen.areas:
            area.tag_redraw()
        return {'FINISHED'}


class EM_OT_shelf_save(Operator):
    bl_idname = "em.shelf_save"
    bl_label = "Save Shelf"
    bl_description = "Save the Shelf as a standalone .em.json (reusable in any study)"
    bl_options = {'REGISTER'}

    filepath: bpy.props.StringProperty(subtype='FILE_PATH')  # type: ignore
    filter_glob: bpy.props.StringProperty(default="*.em.json;*.json", options={'HIDDEN'})  # type: ignore

    def invoke(self, context, event):
        if shelf_backend.active_shelf() is None:
            self.report({'WARNING'}, "No shelf yet — scan or New Shelf first.")
            return {'CANCELLED'}
        self.filepath = shelf_backend.active_path() or "shelf.em.json"
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        path = self.filepath
        if path and not path.endswith(".json"):
            path += ".em.json"
        try:
            saved = shelf_backend.save_shelf(path)
        except Exception as exc:
            self.report({'ERROR'}, f"Save failed: {exc}")
            return {'CANCELLED'}
        context.scene.em_shelf.status = f"Saved → {os.path.basename(saved)}"
        return {'FINISHED'}


class EM_OT_shelf_load(Operator):
    bl_idname = "em.shelf_load"
    bl_label = "Load Shelf"
    bl_description = "Load a standalone Shelf .em.json"
    bl_options = {'REGISTER'}

    filepath: bpy.props.StringProperty(subtype='FILE_PATH')  # type: ignore
    filter_glob: bpy.props.StringProperty(default="*.em.json;*.json", options={'HIDDEN'})  # type: ignore

    def invoke(self, context, event):
        if not shelf_backend.shelf_supported():
            self.report({'ERROR'}, _STALE)
            return {'CANCELLED'}
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        if not os.path.isfile(self.filepath):
            self.report({'WARNING'}, "Pick an existing .em.json shelf.")
            return {'CANCELLED'}
        try:
            _g, warnings = shelf_backend.load_shelf(self.filepath)
        except Exception as exc:
            self.report({'ERROR'}, f"Load failed: {exc}")
            return {'CANCELLED'}
        for w in warnings:
            print(f"[EM Shelf] warning: {w}")
        context.scene.em_shelf.status = (f"Loaded {len(shelf_backend.cards())} "
                                         f"resource(s)")
        for area in context.screen.areas:
            area.tag_redraw()
        return {'FINISHED'}


class EM_OT_shelf_remove(Operator):
    bl_idname = "em.shelf_remove"
    bl_label = "Remove"
    bl_description = "Remove this resource from the Shelf"
    bl_options = {'REGISTER', 'UNDO'}

    resource_id: bpy.props.StringProperty()  # type: ignore

    def execute(self, context):
        if not self.resource_id:
            return {'CANCELLED'}
        shelf_backend.remove(self.resource_id)
        context.scene.em_shelf.status = "Removed"
        for area in context.screen.areas:
            area.tag_redraw()
        return {'FINISHED'}


classes = (
    EM_OT_shelf_set_folder,
    EM_OT_shelf_scan,
    EM_OT_shelf_new,
    EM_OT_shelf_save,
    EM_OT_shelf_load,
    EM_OT_shelf_remove,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
