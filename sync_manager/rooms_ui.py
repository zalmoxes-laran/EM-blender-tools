"""R1 · the room list in the Sync panel: a cache, a UIList, and three gestures.

The pure half (fetch, grouping, the id rule) is `rooms_list.py`; this is the
Blender half. Three gestures:

* **Refresh** (`em.room_list_refresh`) — `GET {node}/v1/rooms` with this
  session's access. The fetch runs on a THREAD: the dev node lists 361 rooms for
  `dev`, and a panel that froze while a slow node answered would be a worse
  panel than the text field it replaces. The answer lands in the cache on the
  main thread, through a one-shot `bpy.app.timers` (the only bpy call that is
  safe from another thread). `wait=True` does it inline — for a headless run,
  where timers do not fire while a script is running.
* **Pick** (`em.room_pick`) — sets the room and joins it (`join_room`, the same
  door as before; the link door `em.room_open_link` stays as it is).
* **+ New room** (`em.room_create`) — a NAME, the id derived from it by the
  shared rule, `POST /v1/rooms`: you are its owner. Then you are in it.

**Where the cache lives: the WindowManager**, not the Scene. A list of rooms is
an answer of the node for this session; written into the .blend it would be a
stale list travelling with the file to somebody with other rights.

**The access.** Same rule as `room.py`: in memory only. Refresh with an empty
token field uses the one this session already holds (a joined room, an earlier
refresh); failing that it signs in through the browser like the join does
(`handoff.sign_in`); a node with no sign-in is listed without one, and that is
said.
"""

from __future__ import annotations

import threading
import time

import bpy  # type: ignore

from . import room as room_cfg
from . import rooms_list

#: The answer of the last fetch, handed from the worker thread to the main one.
_ARRIVO = {"rooms": None, "error": "", "base": "", "pending": False}
_LOCK = threading.Lock()

#: What the panel says under the list: the count, the time, or the refusal.
STATO = {"line": "", "error": "", "at": "", "base": ""}


class EM_PG_room_item(bpy.types.PropertyGroup):
    room_id: bpy.props.StringProperty()  # type: ignore
    title: bpy.props.StringProperty()  # type: ignore
    role: bpy.props.StringProperty()  # type: ignore
    owner: bpy.props.StringProperty()  # type: ignore
    group: bpy.props.StringProperty()  # type: ignore
    implicit: bpy.props.BoolProperty()  # type: ignore


class EM_UL_rooms(bpy.types.UIList):
    """One class, two lists: `list_id` says which group («mine» / «shared»).

    The filter is the panel's own field (`em_rooms_filter`), shared by both
    lists, so typing once narrows both groups — 361 rows on the dev node."""

    def draw_item(self, context, layout, data, item, icon, active_data,
                  active_propname, index):
        row = layout.row(align=True)
        label = item.title or item.room_id
        if item.title and item.title != item.room_id:
            label = f"{item.title}  ·  {item.room_id}"
        row.label(text=label, icon="COMMUNITY" if item.group == "mine" else "USER")
        if item.group != "mine":
            row.label(text=item.role or "?")
        row.operator("em.room_pick", text="", icon="LINKED").room_id = item.room_id

    def filter_items(self, context, data, propname):
        items = getattr(data, propname)
        wanted = self.list_id or "mine"
        text = str(getattr(context.window_manager, "em_rooms_filter", "") or "")
        flags = []
        for item in items:
            keep = (item.group == wanted and rooms_list.matches(
                {"room_id": item.room_id, "title": item.title}, text))
            flags.append(self.bitflag_filter_item if keep else 0)
        return flags, []


# ── the fetch ────────────────────────────────────────────────────────────────

def _fill(wm, rooms) -> dict:
    """Put a fetched list into the cache, grouped. → the groups."""
    groups = rooms_list.group_rooms(rooms)
    cache = wm.em_rooms_cache
    cache.clear()
    for name in (rooms_list.GROUP_MINE, rooms_list.GROUP_SHARED):
        for room in groups[name]:
            item = cache.add()
            item.room_id = str(room.get("room_id") or "")
            item.title = str(room.get("title") or "")
            item.role = str(room.get("your_role") or "")
            item.owner = str(room.get("owner") or "")
            item.group = name
            item.implicit = bool(room.get("implicit"))
    return groups


def _apply_arrival():
    """Main thread: the worker's answer into the cache. One-shot timer."""
    with _LOCK:
        if not _ARRIVO["pending"]:
            return None
        rooms, error, base = _ARRIVO["rooms"], _ARRIVO["error"], _ARRIVO["base"]
        _ARRIVO["pending"] = False
    STATO["at"] = time.strftime("%H:%M:%S")
    STATO["base"] = base
    if error:
        STATO["error"] = error
        STATO["line"] = ""
    else:
        try:
            groups = _fill(bpy.context.window_manager, rooms or [])
            STATO["error"] = ""
            STATO["line"] = rooms_list.summary(groups)
        except Exception as exc:  # noqa: BLE001 — said, never a dead timer
            STATO["error"] = f"could not show the list: {exc}"
    print(f"[rooms] {base}: {STATO['error'] or STATO['line']}")
    try:
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                area.tag_redraw()
    except Exception:  # noqa: BLE001
        pass
    return None


def _worker(base: str, token):
    try:
        rooms, error = rooms_list.list_rooms(base, token), ""
    except Exception as exc:  # noqa: BLE001 — the reason belongs to the user
        rooms, error = None, str(exc)
    with _LOCK:
        _ARRIVO.update({"rooms": rooms, "error": error, "base": base,
                        "pending": True})
    try:
        bpy.app.timers.register(_apply_arrival, first_interval=0.0)
    except Exception:  # noqa: BLE001 — headless: the caller drains by hand
        pass


def _access_for(base: str, typed: str, resume=None):
    """→ (token or None, how). Typed wins; then the session's; then sign-in —
    in the browser, WITHOUT freezing Blender: `signin_ui.Waiting` is raised and
    `resume` opens the door again when the browser comes back."""
    from . import signin_ui
    return signin_ui.access_or_wait(base, typed, resume)


def _keep_access(base: str, token) -> None:
    """In memory, for the pick that follows — never on disk (room.py's rule)."""
    if token:
        room_cfg.set_room(base, room_cfg._session.get("room_id"), token)


class EM_OT_room_list_refresh(bpy.types.Operator):
    """Ask the node which rooms you can enter — yours, and the ones shared with
    you with your role there. Off the UI thread: a slow node does not freeze
    Blender."""

    bl_idname = "em.room_list_refresh"
    bl_label = "Refresh the room list"
    bl_description = ("Ask the node which rooms you can enter: yours, and the "
                      "ones shared with you (with your role)")

    token: bpy.props.StringProperty(  # type: ignore
        name="Token", default="", subtype="PASSWORD", options={"SKIP_SAVE"},
        description=("Leave EMPTY: the session's access is used, or you sign in "
                     "through your browser. Kept in memory only"))
    wait: bpy.props.BoolProperty(default=False, options={"HIDDEN", "SKIP_SAVE"})  # type: ignore

    def execute(self, context):
        base = str(getattr(context.scene, "em_room_url", "") or "").strip().rstrip("/")
        if not base:
            self.report({"ERROR"}, "set the node address first (Server)")
            return {"CANCELLED"}
        from .signin_ui import Waiting
        wait = self.wait
        try:
            token, how = _access_for(
                base, self.token,
                resume=lambda: bpy.ops.em.room_list_refresh(wait=wait))
        except Waiting as exc:
            self.report({"INFO"}, str(exc))
            return {"FINISHED"}
        except Exception as exc:  # noqa: BLE001
            self.report({"ERROR"}, f"sign-in did not complete: {exc}")
            return {"CANCELLED"}
        self.token = ""
        _keep_access(base, token)
        if how == "open-node":
            self.report({"INFO"}, f"{base} has no sign-in configured — "
                                  f"listing without a token")
        STATO.update({"line": "asking the node…", "error": ""})
        if self.wait:
            _worker(base, token)
            _apply_arrival()
            if STATO["error"]:
                self.report({"ERROR"}, STATO["error"])
                return {"CANCELLED"}
            self.report({"INFO"}, STATO["line"])
            return {"FINISHED"}
        threading.Thread(target=_worker, args=(base, token), daemon=True,
                         name="em-rooms-list").start()
        return {"FINISHED"}


class EM_OT_room_pick(bpy.types.Operator):
    """Enter this room: it becomes the room of this project, and Blender joins
    it directly (not behind EMStudio)."""

    bl_idname = "em.room_pick"
    bl_label = "Enter this room"
    bl_description = "Enter this room: Blender joins it directly"

    room_id: bpy.props.StringProperty(default="")  # type: ignore

    def execute(self, context):
        from . import operators as ops

        base = str(getattr(context.scene, "em_room_url", "") or "").strip()
        if not base or not self.room_id:
            self.report({"ERROR"}, "no node or no room to enter")
            return {"CANCELLED"}
        from .signin_ui import Waiting
        room_id = self.room_id
        try:
            token, _how = _access_for(
                base, "", resume=lambda: bpy.ops.em.room_pick(room_id=room_id))
        except Waiting as exc:
            self.report({"INFO"}, str(exc))
            return {"FINISHED"}
        except Exception as exc:  # noqa: BLE001 — the realm, the network
            self.report({"ERROR"}, f"sign-in did not complete: {exc}")
            return {"CANCELLED"}
        token = token or ""
        from . import room_session as _rs
        if any(s.joined and s.room_id == self.room_id
               for _g, s in _rs.sessions()):
            self.report({"INFO"}, f"already in {self.room_id}")
            return {"FINISHED"}
        # M2 · a room already joined is ANOTHER graph's room: it stays joined,
        # and this one is entered beside it with its own session.
        context.scene.em_room_id = self.room_id
        result = ops.join_manual(context, base, self.room_id, token)
        if not result["ok"]:
            self.report({"ERROR"}, result["message"])
            return {"CANCELLED"}
        self.report({"INFO"}, f"room {result['room']}: {result['message']}")
        return {"FINISHED"}


class EM_OT_room_create(bpy.types.Operator):
    """A new room on this node, from a name: you are its owner, and you enter it."""

    bl_idname = "em.room_create"
    bl_label = "New room"
    bl_description = ("Create a room on this node from a name (you become its "
                      "owner) and enter it")

    name: bpy.props.StringProperty(  # type: ignore
        name="Name", default="", options={"SKIP_SAVE"},
        description="The room's name; its id is derived from it")
    enter: bpy.props.BoolProperty(  # type: ignore
        name="Enter it", default=True, options={"SKIP_SAVE"})

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=420)

    def draw(self, context):
        col = self.layout.column()
        col.prop(self, "name")
        derived = rooms_list.room_id_from_name(self.name)
        col.label(text=f"id: {derived or '— (a name with letters or digits)'}",
                  icon="INFO")
        col.prop(self, "enter")

    def execute(self, context):
        base = str(getattr(context.scene, "em_room_url", "") or "").strip().rstrip("/")
        if not base:
            self.report({"ERROR"}, "set the node address first (Server)")
            return {"CANCELLED"}
        from .signin_ui import Waiting
        name, enter = self.name, self.enter
        try:
            token, _how = _access_for(
                base, "",
                resume=lambda: bpy.ops.em.room_create(name=name, enter=enter))
            created = rooms_list.create_room(base, token, self.name)
        except Waiting as exc:
            self.report({"INFO"}, str(exc))
            return {"FINISHED"}
        except Exception as exc:  # noqa: BLE001 — the node's sentence
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        _keep_access(base, token)
        item = context.window_manager.em_rooms_cache.add()
        item.room_id = str(created.get("room_id") or "")
        item.title = str(created.get("title") or "")
        item.role = str(created.get("your_role") or "owner")
        item.group = rooms_list.group_of(created)
        context.scene.em_room_id = item.room_id
        self.report({"INFO"}, f"room {item.room_id} created — you are its "
                              f"{item.role}")
        if self.enter:
            return bpy.ops.em.room_pick(room_id=item.room_id)
        return {"FINISHED"}


def draw_list(layout, context) -> None:
    """The «Rooms on this node» block of the Sync panel."""
    wm = context.window_manager
    box = layout.box()
    head = box.row(align=True)
    head.label(text="Rooms on this node", icon="COMMUNITY")
    head.operator("em.room_list_refresh", text="", icon="FILE_REFRESH")
    head.operator("em.room_create", text="New room", icon="ADD")
    if not len(wm.em_rooms_cache):
        box.label(text=STATO["error"] or STATO["line"]
                  or "Refresh to see the rooms you can enter.",
                  icon="ERROR" if STATO["error"] else "INFO")
        return
    box.prop(wm, "em_rooms_filter", text="", icon="VIEWZOOM")
    box.label(text="Your rooms", icon="USER")
    box.template_list("EM_UL_rooms", "mine", wm, "em_rooms_cache",
                      wm, "em_rooms_index_mine", rows=4)
    box.label(text="Shared with you", icon="COMMUNITY")
    box.template_list("EM_UL_rooms", "shared", wm, "em_rooms_cache",
                      wm, "em_rooms_index_shared", rows=4)
    riga = box.row()
    riga.alert = bool(STATO["error"])
    riga.label(text=(STATO["error"] or f"{STATO['line']} · {STATO['at']}")[:80],
               icon="ERROR" if STATO["error"] else "INFO")


_CLASSES = (EM_PG_room_item, EM_UL_rooms, EM_OT_room_list_refresh,
            EM_OT_room_pick, EM_OT_room_create)


def register():
    for cls in _CLASSES:
        bpy.utils.register_class(cls)
    wm = bpy.types.WindowManager
    wm.em_rooms_cache = bpy.props.CollectionProperty(type=EM_PG_room_item)
    wm.em_rooms_index_mine = bpy.props.IntProperty(default=-1)
    wm.em_rooms_index_shared = bpy.props.IntProperty(default=-1)
    wm.em_rooms_filter = bpy.props.StringProperty(
        name="Filter", default="",
        description="Narrow both lists: words in the room's id or title")


def unregister():
    wm = bpy.types.WindowManager
    for name in ("em_rooms_filter", "em_rooms_index_shared",
                 "em_rooms_index_mine", "em_rooms_cache"):
        if hasattr(wm, name):
            delattr(wm, name)
    for cls in reversed(_CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:  # noqa: BLE001 — unregistering must not fail
            pass
