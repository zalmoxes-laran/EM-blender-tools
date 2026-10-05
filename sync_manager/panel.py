"""«Where you work» — the head of the tab EM (T1/Z1, decided by E.D. on 5 Oct 2026).

Until today this was the panel «Room» of a tab of its own, «EM Room», with 31
commands: three mode chips, two node finders, the room list, a field for the
room, the permissions, the archive, the scene check, and half its rows lines of
grey text that commanded nothing (measured in `SCRIVANIA-pannello-room.md`).
E.D.: a whole tab for the connection is too much. It is now the first panel of
**EM** — the study in this scene — above the EM Data Tree, which with the
invariants of 5 October is the tree «origin (a file or a room) → graphs»: the
room is an origin, so the two panels sit together.

**The four zones, like EMStudio's bar** (`where.py`, pure): *where you work*
(«□ On this computer · <the study's file>», «⇄ With EMStudio · N clients · same
document ✓/≠», «▣ <title> · <node> · N present») with **Change…**; *who you
are* («dev ✓ · ★ owner», or «not signed in to a node — none needed here»);
*the message*, one sentence, the most recent useful one (the outcome of a
transition, the wait for the browser with Cancel, an expired access with Sign
in again, «⊘ your role does not write», «Last time this file worked with
EMStudio» with Reconnect — where a red alarm used to greet every reopened
file); *the log*, the sync and the refusals counted, with **Log…**.

**Under them, only what the place makes possible:**
on this computer, Work with EMStudio · Enter a collaborative room… · Create a
collaborative room from this study…; with EMStudio, Stop working with EMStudio
and «Accepts from EMStudio: … · may/may not model here» with Permissions…; in a
room, the counts of the scene, Sync the scene…, Archive this .blend, Leave the
room, Open in EMStudio, and the room's menu (Room settings…, The .blend in the
room…, Log…). Everything that is a choice opens a window (`windows.py`).

**The names.** The mode's values stay `standalone`/`sidecar`/`hub` — they are
saved in every .blend and declared on the wire (`operators.MODE_*`); what a
person reads are the three places.
"""

from __future__ import annotations

import bpy  # type: ignore

from . import operators as ops
from . import where

#: the commands of the first place, drawn in this order: `(bl_idname, text,
#: icon, props)`. The inventory test reads the panel through a fake layout and
#: counts the commands of each place (3 / 2 / 4 + the menu).
HERE_COMMANDS = (
    ("em.set_mode", "Work with EMStudio", "LINKED", {"mode": ops.MODE_SIDECAR}),
    ("em.room_enter", "Enter a collaborative room…", "COMMUNITY", {}),
    ("em.room_bring", "Create a collaborative room from this study…", "ADD", {}),
)


class VIEW3D_PT_em_sync(bpy.types.Panel):
    bl_label = "Where you work"
    bl_idname = "VIEW3D_PT_em_sync"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "EM"
    bl_order = 0
    #: the width when it is called as a popover (the shots of the report)
    bl_ui_units_x = 22

    def draw_header(self, context):
        # closed, the panel is one line: the place's sign
        z = where.zones(where.read_state(context))
        self.layout.label(text="", icon=z["place"][0] if z["healthy"] else "ERROR")

    def draw(self, context):
        layout = self.layout
        state = where.read_state(context)
        z = where.zones(state)
        self._zones(layout, z)
        layout.separator()
        place = state["place"]
        if place == where.PLACE_ROOM:
            self._in_room(layout, context, state)
        elif place == where.PLACE_EMSTUDIO:
            self._with_emstudio(layout, context)
        else:
            self._here(layout, context)

    # ── the four zones ──────────────────────────────────────────────────────

    def _zones(self, layout, z):
        col = layout.column(align=True)
        row = col.row(align=True)
        row.alert = not z["healthy"]
        row.label(text=z["place"][1], icon=z["place"][0])
        row.operator("em.where_change", text="Change…")
        col.label(text=z["who"][1], icon=z["who"][0])
        msg = z["message"]
        if msg["text"]:
            row = col.row(align=True)
            row.alert = bool(msg.get("alert"))
            row.label(text=msg["text"][:80], icon=msg["icon"])
            if msg.get("op"):
                op = row.operator(msg["op"], text=msg["op_text"])
                for key, value in (msg.get("op_props") or {}).items():
                    setattr(op, key, value)
        row = col.row(align=True)
        row.label(text=z["log"][1], icon=z["log"][0])
        row.operator("em.sync_log", text="Log…")

    # ── the commands of each place ──────────────────────────────────────────

    def _here(self, layout, context):
        col = layout.column(align=True)
        graph_ok = ops.grafo_caricato(context)
        for idname, text, icon, props in HERE_COMMANDS:
            row = col.row(align=True)
            if idname == "em.room_bring":
                # a room is built around a study: there must be one loaded
                row.enabled = graph_ok
            op = row.operator(idname, text=text, icon=icon)
            for key, value in props.items():
                setattr(op, key, value)

    def _with_emstudio(self, layout, context):
        from . import windows
        layout.operator("em.set_mode", text="Stop working with EMStudio",
                        icon="UNLINKED").mode = ops.MODE_STANDALONE
        row = layout.row(align=True)
        row.label(text=windows.permissions_line(context)[:80])
        row.operator("em.sidecar_permissions", text="Permissions…")

    def _in_room(self, layout, context, state):
        from . import scene_check
        # V1 · not in the room now (a dropped connection, a file reopened):
        # Sync reconnects by itself first, Open in EMStudio waits for the room
        offline = bool(state.get("offline") or state.get("not_connected"))
        col = layout.column(align=True)
        if scene_check.ULTIMA_VERIFICA.get("counts"):
            col.label(text=scene_check.ULTIMA_VERIFICA["counts"][:90])
        row = col.row(align=True)
        row.operator("em.scene_check", text="Sync the scene…", icon="FILE_REFRESH")
        row = col.row(align=True)
        row.operator("em.blend_backup_archive", text="Archive this .blend", icon="EXPORT")
        row.operator("em.room_leave", text="Leave the room", icon="UNLINKED")
        row = col.row(align=True)
        sub = row.row(align=True)
        sub.enabled = not offline
        sub.operator("em.room_open_elsewhere", text="Open in EMStudio", icon="WINDOW")
        row.menu("EM_MT_room_more", text="", icon="DOWNARROW_HLT")


def register():
    bpy.utils.register_class(VIEW3D_PT_em_sync)


def unregister():
    bpy.utils.unregister_class(VIEW3D_PT_em_sync)
