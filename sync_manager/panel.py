"""Where you work — the FIRST ROW of the EM Data Tree (MICRO-EMTOOLS-PANNELLO,
E.D., 30 Oct 2026). Until then «Where you work» was a panel of its own above
the tree (T1/Z1, 5 Oct 2026; once the 31 commands of the tab «EM Room»): it
repeated EM ▸ Mode, then three lines of state and three buttons. E.D.: too
much for what it says. Now:

* **the chip** — an icon and a short word («On this computer» / «With
  EMStudio» / «Room: <title>») and a dot (green: connected and someone there;
  grey: nothing to connect, or nobody yet; red: something to fix). A click
  opens **EM ▸ Mode** — one source, `windows.draw_places` + the commands of
  the place below (`draw_place_commands`). The detail the lines used to say
  (file, who you are, node, bridge, clients, the last transition, the log) is
  the chip's tooltip (`where.chip`).
* **one row under it only when something is to be FIXED** (Reconnect, Sign in
  again, Cancel the wait, Download now): a call to action read only in a
  tooltip is a call nobody hears. The normal case draws nothing there.
* **in a room** the main gesture, Sync the scene…, stays an icon on the chip
  row; Open in EMStudio, Change…, Log… and the ⋯ of the room are in the menu.

Nothing was lost: every button of the old panel is in EM ▸ Mode (the inventory
test lists them). The four zones (`where.zones`) are the same, read the same.

**The names.** The mode's values stay `standalone`/`sidecar`/`hub` — they are
saved in every .blend and declared on the wire (`operators.MODE_*`); what a
person reads are the three places.
"""

from __future__ import annotations

import bpy  # type: ignore

from . import operators as ops
from . import where

#: the commands of the first place: `(bl_idname, text, icon, props)`. Work
#: with EMStudio and Enter a collaborative room… are the places of EM ▸ Mode
#: (`windows.draw_places`); Create a collaborative room… is under them.
HERE_COMMANDS = (
    ("em.set_mode", "Work with EMStudio", "LINKED", {"mode": ops.MODE_SIDECAR}),
    ("em.room_enter", "Enter a collaborative room…", "COMMUNITY", {}),
    ("em.room_bring", "Create a collaborative room from this study…", "ADD", {}),
)


#: the dot of the chip, by `where.chip`'s word
DOT_ICONS = {where.DOT_ON: "SEQUENCE_COLOR_04", where.DOT_IDLE: "SEQUENCE_COLOR_09",
             where.DOT_PROBLEM: "SEQUENCE_COLOR_01"}


def _icon(name: str) -> str:
    from ..functions import get_compatible_icon
    return get_compatible_icon(name)


class EM_OT_where_menu(bpy.types.Operator):
    """Where you work: on this computer, with EMStudio, or in a collaborative room"""

    bl_idname = "em.where_menu"
    bl_label = "Where you work"
    bl_description = ("Where you work: on this computer, with EMStudio, or in a "
                      "collaborative room")

    @classmethod
    def description(cls, context, properties):
        # the tooltip IS the old panel's lines: file, who, node, bridge,
        # clients, the last transition, the log
        try:
            return "\n".join(where.chip(where.read_state(context))["tip"])
        except Exception:  # noqa: BLE001 — a tooltip never fails
            return cls.bl_description

    def execute(self, context):
        bpy.ops.wm.call_menu(name="EM_MT_mode")
        return {"FINISHED"}


def draw_mode_row(layout, context, tools=None) -> None:
    """The chip, `tools(row)` on its right (the tree's + − ▾), and the one
    row of a gesture that fixes something, when there is one."""
    state = where.read_state(context)
    c = where.chip(state)
    row = layout.row(align=True)
    left = row.row(align=True)
    left.alert = c["dot"] == where.DOT_PROBLEM
    left.operator("em.where_menu", text=c["text"], icon=c["icon"])
    left.label(text="", icon=_icon(DOT_ICONS[c["dot"]]))
    if state.get("place") == where.PLACE_ROOM:
        # the room's main gesture stays in sight
        row.operator("em.scene_check", text="", icon="FILE_REFRESH")
    if tools is not None:
        row.separator()
        tools(row)
    a = c["action"]
    if a:
        fix = layout.row(align=True)
        fix.alert = a["alert"]
        fix.label(text=a["text"][:60], icon=a["icon"])
        op = fix.operator(a["op"], text=a["op_text"])
        for key, value in a["op_props"].items():
            setattr(op, key, value)


def draw_place_commands(layout, context) -> None:
    """Under the three places of EM ▸ Mode: what the place makes possible —
    the commands of the old panel, each once."""
    state = where.read_state(context)
    z = where.zones(state)
    place = state["place"]
    msg = z["message"]
    layout.separator()
    if msg.get("op"):
        op = layout.operator(msg["op"], text=msg["op_text"], icon=msg["icon"])
        for key, value in (msg.get("op_props") or {}).items():
            setattr(op, key, value)
    if place == where.PLACE_ROOM:
        st = z.get("state") or {}
        if st.get("op"):
            op = layout.operator(st["op"], text=st["op_text"], icon=st["icon"])
            for key, value in (st.get("op_props") or {}).items():
                setattr(op, key, value)
        offline = bool(state.get("offline") or state.get("not_connected"))
        layout.operator("em.scene_check", text="Sync the scene…", icon="FILE_REFRESH")
        sub = layout.row()
        sub.enabled = not offline
        sub.operator("em.open_in_emstudio", text="Open in EMStudio", icon="WINDOW")
        layout.operator("em.where_change", text="Change…", icon="PREFERENCES")
        layout.menu("EM_MT_room_more", text="Room", icon="THREE_DOTS")
    elif place == where.PLACE_EMSTUDIO:
        from . import windows
        # «Stop working with EMStudio» is the first place, On this computer
        layout.operator("em.sidecar_permissions", icon="LOCKED",
                        text=f"Permissions… ({windows.permissions_line(context)})")
    else:
        graph_ok = ops.grafo_caricato(context)
        for idname, text, icon, props in HERE_COMMANDS:
            if idname != "em.room_bring":
                continue           # the two others are the places above
            row = layout.row()
            # a room is built around a study: there must be one loaded
            row.enabled = graph_ok
            op = row.operator(idname, text=text, icon=icon)
            for key, value in props.items():
                setattr(op, key, value)
    layout.operator("em.sync_log", text="Log…", icon="TEXT")


def register():
    bpy.utils.register_class(EM_OT_where_menu)


def unregister():
    bpy.utils.unregister_class(EM_OT_where_menu)
