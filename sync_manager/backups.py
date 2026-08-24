"""Blend backups: keeping a copy of the workshop somewhere that is not the laptop.

## What this is, and what it deliberately is not

The **shared** data already has its versioning and it is not this: em.json, the
glTF of record and the DTC resources are content-addressed, so *the version is
the hash* and *the history is the DTC*. Nothing here touches them.

A `.blend` is the workshop, not the medium. Heavy linked survey models, light
proxy work, a reconstruction phase that gets heavy again — its day-to-day
versioning belongs on this disk, where it already is. What this disk cannot do is
survive itself. So: **one deliberate act** that puts the current `.blend` into
the room's backup namespace as an opaque object, and a list to get it back.

Three rules the UI is built around:

* **deliberate.** There is no save handler and there will not be one. A backup on
  every save is a quota, not a safety net.
* **honest about staleness.** Blender archives the file on DISK. If the session
  has unsaved changes, the bytes on disk are not what you are looking at — so the
  operator refuses, and offers to save first as a checkbox rather than doing it
  behind your back.
* **restore is a download, not a revert.** The snapshot lands beside the current
  file with its own name; opening it is a person's decision, and overwriting the
  file somebody is working in is never ours.
"""

from __future__ import annotations

import os

import bpy

#: The last listing, in memory. NOT a Scene property: a collection property is
#: saved inside the .blend, and a list of somebody's backup digests is session
#: state, not part of the document. (Same reason the room token is not one.)
_listing: list = []
_note: str = ""


def listing() -> list:
    return list(_listing)


def note() -> str:
    return _note


def _human(size) -> str:
    value = float(size or 0)
    for unit in ("B", "kB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.0f} {unit}" if unit == "B" or value >= 10 \
                else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.0f} TB"


def _blend_bytes():
    """(bytes, filename) of the file on disk, or a sentence saying why not."""
    path = bpy.data.filepath
    if not path:
        return None, ("this session has never been saved: there is no .blend to "
                      "archive yet — save it once, then keep a snapshot")
    try:
        with open(path, "rb") as handle:
            return (handle.read(), os.path.basename(path)), ""
    except OSError as exc:
        return None, f"could not read {os.path.basename(path)}: {exc}"


class EM_OT_blend_backup_archive(bpy.types.Operator):
    bl_idname = "em.blend_backup_archive"
    bl_label = "Archive a .blend snapshot (safety)"
    bl_description = ("Keep a copy of this .blend in the room's store as an "
                      "opaque safety snapshot. Deliberate, not automatic — and "
                      "it archives the file on disk, not the unsaved session")

    label: bpy.props.StringProperty(
        name="Label", default="",
        description="What this snapshot is, in your own words — it is how you "
                    "will recognise it in six months")
    save_first: bpy.props.BoolProperty(
        name="Save the file first", default=False,
        description="This archives the bytes ON DISK. Tick to save the session "
                    "before archiving; untick and a modified session is refused "
                    "rather than archived stale")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "label")
        layout.prop(self, "save_first")
        if bpy.data.is_dirty and not self.save_first:
            layout.label(text="Unsaved changes: the snapshot would be the file "
                              "on disk, not what you see.", icon="ERROR")
        layout.label(text="Opaque backup — not a publishable asset, cited by "
                          "nothing.", icon="INFO")

    def execute(self, context):
        from . import room

        if not room.is_configured():
            self.report({"ERROR"}, "no room: join one first (a snapshot goes "
                                   "through the room's auth)")
            return {"CANCELLED"}
        if bpy.data.is_dirty:
            if not self.save_first:
                self.report({"ERROR"},
                            "unsaved changes: archiving would keep the file on "
                            "disk, not this session. Save first (or tick the box)")
                return {"CANCELLED"}
            try:
                bpy.ops.wm.save_mainfile()
            except RuntimeError as exc:
                self.report({"ERROR"}, f"could not save: {exc}")
                return {"CANCELLED"}
        payload, why = _blend_bytes()
        if payload is None:
            self.report({"ERROR"}, why)
            return {"CANCELLED"}
        data, filename = payload
        try:
            record = room.put_blend_backup(data, label=self.label,
                                           filename=filename)
        except room.RoomError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        _refresh(self)
        if record.get("created"):
            self.report({"INFO"},
                        f"kept {filename} ({_human(record.get('size'))}) as "
                        f"{str(record.get('sha256'))[:12]}…")
        else:
            # dedup, said out loud: silence here would read as a failed upload
            self.report({"INFO"},
                        "these exact bytes were already kept — one snapshot, "
                        "not two (nothing changed since the last one)")
        return {"FINISHED"}


class EM_OT_blend_backup_list(bpy.types.Operator):
    bl_idname = "em.blend_backup_list"
    bl_label = "Refresh the backup list"
    bl_description = "Ask the room which snapshots you kept here"

    def execute(self, context):
        return {"FINISHED"} if _refresh(self) else {"CANCELLED"}


def _refresh(reporter) -> bool:
    global _listing, _note
    from . import room

    if not room.is_configured():
        _listing, _note = [], "no room joined"
        return False
    try:
        _listing = room.list_blend_backups()
        _note = ""
    except room.RoomError as exc:
        _listing, _note = [], str(exc)
        if reporter is not None:
            reporter.report({"ERROR"}, str(exc))
        return False
    return True


class EM_OT_blend_backup_restore(bpy.types.Operator):
    bl_idname = "em.blend_backup_restore"
    bl_label = "Restore a snapshot"
    bl_description = ("Download this snapshot BESIDE the current file. It does "
                      "not replace what you are working in — opening it is your "
                      "decision")

    sha256: bpy.props.StringProperty(name="Snapshot", default="")

    def execute(self, context):
        from . import room

        if not self.sha256:
            self.report({"ERROR"}, "no snapshot named")
            return {"CANCELLED"}
        try:
            data = room.get_blend_backup(self.sha256)
        except room.RoomError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        target = _restore_path(self.sha256)
        if os.path.exists(target):
            # never over anything, and never over the file in use
            self.report({"ERROR"}, f"{os.path.basename(target)} already exists: "
                                   f"refusing to overwrite it")
            return {"CANCELLED"}
        try:
            with open(target, "wb") as handle:
                handle.write(data)
        except OSError as exc:
            self.report({"ERROR"}, f"could not write the snapshot: {exc}")
            return {"CANCELLED"}
        self.report({"INFO"}, f"restored to {os.path.basename(target)} "
                              f"({_human(len(data))}) — open it when you want to")
        return {"FINISHED"}


def _restore_path(sha256: str) -> str:
    """Beside the current file, named by the snapshot. Never the current name.

    A restore that landed on `scavo.blend` would destroy the very work the
    backup was supposed to protect, at the exact moment somebody is panicking.
    """
    current = bpy.data.filepath
    folder = os.path.dirname(current) or bpy.app.tempdir
    stem = os.path.splitext(os.path.basename(current))[0] or "restored"
    return os.path.join(folder, f"{stem}-snapshot-{str(sha256)[:12]}.blend")


_CLASSES = (EM_OT_blend_backup_archive, EM_OT_blend_backup_list,
            EM_OT_blend_backup_restore)


def register():
    for cls in _CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    global _listing, _note
    _listing, _note = [], ""
    for cls in reversed(_CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:  # noqa: BLE001 — unregistering must not fail
            pass
