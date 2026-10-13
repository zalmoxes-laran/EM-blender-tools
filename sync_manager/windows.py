"""N1 · the windows «Where you work» opens, instead of drawing it all.

The panel shows where you are and the commands the place makes possible
(`panel.py`); everything that is a CHOICE opens here, as a window:

* **Change…** (`em.where_change`) — the three places, the same content as
  EM ▸ Mode (`draw_places`, one function for both);
* **Choose the node** (`em.node_choose`) — opens by itself when a gesture needs
  a node and none is chosen. The two finders of before (`nodes_find` and
  `server_discover`/`server_probe`) are one: This computer, The local network,
  Saved; each node by its host and port; an address that probes itself as it
  is typed; Use, Forget, the personal node. The local network is listed as it
  is found — making the Sidecar reach it is an advanced setup, not added here;
* **Enter a collaborative room…** (`em.room_enter`) — Your rooms, Shared with
  you, the filter, by id, from a link (`em.room_open_link`);
* **Permissions…** (`em.sidecar_permissions`) — what EMStudio may land here,
  whether it may model in this scene, and what EMStudio itself accepts;
* **Log…** (`em.sync_log`) — the last refusals and transitions, and the last
  inbound message (what was a box of the panel);
* **Room settings…** (`em.room_settings`) — members, roles, invitations and who
  sees the study, for whoever may assign them (C1);
* the snapshots of the .blend and the starting package are Project storage's
  (EM Scene ▸ Contents), no longer a window.

MICRO una verità (13 Oct 2026): Change…, Choose the node and Enter a
collaborative room are the three steps of ONE window — never one window over
another, «‹ Back» to go back.

What the panel used to explain in lines of grey text is in the tooltips of
these operators.
"""

import time
from typing import Any, Dict, List

import bpy  # type: ignore

from . import where

#: transitions and other events of «where you work», newest first, for Log…
TRANSITIONS: List[Dict[str, str]] = []


def note_transition(text: str) -> None:
    TRANSITIONS.insert(0, {"at": time.strftime("%H:%M:%S"), "text": str(text)})
    del TRANSITIONS[12:]


def _base(context) -> str:
    return str(getattr(context.scene, "em_room_url", "") or "").strip().rstrip("/")


def _redraw() -> None:
    try:
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                area.tag_redraw()
    except Exception:  # noqa: BLE001
        pass


# ── ONE window, in steps (MICRO una verità, 13 Oct 2026) ────────────────────
#
# E.D.: «ci sono molti sottomenu da aprire». In a room, Change… opened «Where
# you work», and «Choose the node…» opened a SECOND window over the first. Now
# Change…, Choose the node and Enter a collaborative room are the three steps
# of ONE window: a step is a property of the window manager (`em_where_step`),
# so moving between them redraws the same window — never one over another —
# and «‹ Back» goes back without closing. A gesture that leaves (Use, Enter,
# a place) closes it; what follows opens alone, one window at a time.

STEP_PLACES, STEP_NODE, STEP_ROOMS = "places", "node", "rooms"
_STEPPING = {"busy": False}


def _on_step(self, context):
    """Entering a step reads what it shows: the nodes, or the node's rooms.
    A room step without a node goes to the node step first."""
    if _STEPPING["busy"]:
        return
    _STEPPING["busy"] = True
    try:
        wm = context.window_manager
        if wm.em_where_step == STEP_ROOMS and not _base(context):
            wm.em_where_then = "enter"
            wm.em_where_step = STEP_NODE
        if wm.em_where_step == STEP_NODE:
            _look_for_nodes(context)
        elif wm.em_where_step == STEP_ROOMS:
            _load_rooms(context)
    finally:
        _STEPPING["busy"] = False


def _look_for_nodes(context) -> None:
    from . import node_choice
    try:
        node_choice.find(str(context.window_manager.em_node_address or ""))
        node_choice.personal("status")
    except Exception as exc:  # noqa: BLE001 — the window still opens
        node_choice.FOUND.clear()
        node_choice.FOUND["suggestion"] = f"could not look for nodes: {exc}"


def _load_rooms(context) -> None:
    from . import rooms_ui
    if not len(context.window_manager.em_rooms_cache) or \
            rooms_ui.STATO.get("base") != _base(context):
        try:
            bpy.ops.em.room_list_refresh(wait=True)
        except RuntimeError as exc:      # the node's refusal, said in the window
            rooms_ui.STATO["error"] = str(exc)
    for item in context.window_manager.em_rooms_cache:
        if item.title:
            where.ROOM_TITLES[item.room_id] = item.title


def _back(layout, context) -> None:
    layout.prop_enum(context.window_manager, "em_where_step", STEP_PLACES, text="‹ Back")


def draw_places(layout, context, *, window: bool = False) -> None:
    """The three places — «Change…» and EM ▸ Mode draw the same. In the
    window the node and the rooms are steps of it, not other windows."""
    from . import operators as ops
    state = where.read_state(context)
    wm = context.window_manager
    layout.label(text="Where you work")
    for row_ in where.place_rows(state):
        row = layout.row()
        mark = "RADIOBUT_ON" if row_["now"] else "RADIOBUT_OFF"
        if row_["now"]:
            # where you are is not a button: nothing to choose there
            row.label(text=row_["label"], icon=mark)
        elif row_["value"] == where.PLACE_HERE:
            row.operator("em.set_mode", text=row_["label"], icon=mark).mode = ops.MODE_STANDALONE
        elif row_["value"] == where.PLACE_EMSTUDIO:
            row.operator("em.set_mode", text=row_["label"], icon=mark).mode = ops.MODE_SIDECAR
        elif window:
            row.prop_enum(wm, "em_where_step", STEP_ROOMS, text=f"{row_['label']}…", icon=mark)
        else:
            row.operator("em.room_enter", text=f"{row_['label']}…", icon=mark)
    node = where.host_of(_base(context))
    line = layout.row(align=True)
    line.label(text=f"Node: {node or 'none chosen'}", icon="WORLD")
    if window:
        line.prop_enum(wm, "em_where_step", STEP_NODE, text="Choose the node…")
    else:
        line.operator("em.where_change", text="Choose the node…").step = STEP_NODE


def draw_node_step(layout, context) -> None:
    """Choose the node — one row per node (`node_choice.one_row_per_node`):
    the one in use says so and has no Use; the others Use; the saved ones ✕."""
    from . import node_choice, servers
    from ..state_symbols import sign
    wm = context.window_manager
    found = node_choice.FOUND
    saved = [s["url"] for s in servers.saved()]
    urls = [n.get("url") for g in ("local", "lan", "saved", "typed") for n in found.get(g) or []]
    idents = {str(u).rstrip("/"): node_choice.identity_of(u) for u in urls if u}
    from . import room as room_cfg
    using = (room_cfg.room().get("base_url") or _base(context)) or ""
    rows = node_choice.one_row_per_node(found, idents, in_use=using, saved=saved)
    tip = node_choice.advice(rows, personal_on=bool(node_choice.PERSONAL.get("running")
                                                    or node_choice.PERSONAL.get("pid")))
    head = layout.row(align=True)
    _back(head, context)
    head.label(text="Choose the node", icon="WORLD")
    if tip["sentence"]:
        layout.label(text=tip["sentence"], icon="INFO")
    col = layout.column(align=True)
    if not rows:
        col.label(text="No node found", icon="BLANK1")
    for n in rows:
        line = col.row(align=True)
        icon = sign("node.reachable" if n["reachable"] else "node.unreachable")[0]
        facts = " · ".join(x for x in (n.get("version", ""),
                                        "personal" if n.get("profile") == "personal" else "",
                                        {"local": "this computer", "lan": "local network",
                                         "saved": "saved", "typed": ""}.get(n["where"], "")) if x)
        line.label(text=f"{where.host_of(n['url'])}" + (f"  {facts}" if facts else ""), icon=icon)
        right = line.row(align=True)
        right.ui_units_x = 6
        if n["in_use"]:
            right.label(text="● in use")
        elif n["reachable"]:
            op = right.operator("em.node_use", text="Use")
            op.url, op.then = n["url"], wm.em_where_then
        else:
            right.label(text="")
        if n["saved"]:
            right.operator("em.server_forget", text="", icon="X").url = n["url"]
        else:
            right.label(text="", icon="BLANK1")
        if wm.em_node_details and len(n["addresses"]) > 1:
            more = col.row()
            more.active = False
            more.label(text="also " + ", ".join(where.host_of(a) for a in n["addresses"]
                                                if a != n["url"]), icon="BLANK1")
    if any(len(n["addresses"]) > 1 for n in rows):
        layout.prop(wm, "em_node_details", text="Details: every address of a node")
    if tip["turn_on"]:
        op = layout.operator("em.node_personal", text="Turn on a node on this computer",
                             icon="PLAY")
        op.action, op.lan = "start", False
    elif node_choice.PERSONAL.get("running") or node_choice.PERSONAL.get("pid"):
        acts = layout.row(align=True)
        acts.label(text="Personal node on", icon="HOME")
        acts.operator("em.node_personal", text="Turn off").action = "stop"
    try:
        layout.prop(wm, "em_node_address", text="Another node",
                    placeholder="https://node.example.org")
    except TypeError:                     # a Blender without placeholders
        layout.prop(wm, "em_node_address", text="Another node (https://…)")


def draw_rooms_step(layout, context) -> None:
    """Enter a collaborative room — the node's rooms, by id, from a link."""
    from . import rooms_ui
    wm = context.window_manager
    head = layout.row(align=True)
    _back(head, context)
    head.label(text=f"Rooms on {where.host_of(_base(context))}", icon="COMMUNITY")
    head.prop_enum(wm, "em_where_step", STEP_NODE, text="Another node…")
    head.operator("em.room_list_refresh", text="Refresh")
    if rooms_ui.STATO.get("error"):
        layout.label(text=rooms_ui.STATO["error"][:90], icon="ERROR")
    layout.prop(wm, "em_rooms_filter", text="", icon="VIEWZOOM")
    groups = {g: [i for i in wm.em_rooms_cache if i.group == g] for g in ("mine", "shared")}
    for group, title, icon, index in (("mine", "Your rooms", "USER", "em_rooms_index_mine"),
                                      ("shared", "Shared with you", "COMMUNITY",
                                       "em_rooms_index_shared")):
        if not groups[group]:
            sub = layout.row()
            sub.active = False
            sub.label(text=f"{title}: none", icon=icon)
            continue
        layout.label(text=title, icon=icon)
        layout.template_list("EM_UL_rooms", group, wm, "em_rooms_cache", wm, index, rows=4)
        picked = rooms_ui.picked(wm, group)
        if picked is not None:
            sub = layout.row()
            sub.active = False
            sub.label(text=picked.room_id, icon="BLANK1")
    by = layout.row(align=True)
    by.prop(context.scene, "em_room_id", text="By id")
    by.operator("em.room_reconnect", text="Enter")
    link = layout.row(align=True)
    try:
        link.prop(wm, "em_room_link_text", text="From a link",
                  placeholder="stratigraph://open?server=…&room=…")
    except TypeError:
        link.prop(wm, "em_room_link_text", text="From a link")
    link.operator_context = "EXEC_DEFAULT"
    go = link.operator("em.room_open_link", text="Enter")
    go.link = wm.em_room_link_text


class EM_OT_where_change(bpy.types.Operator):
    """Change where you work: on this computer, with EMStudio on this
    computer, or in a collaborative room — the node and the rooms are steps of
    this same window"""

    bl_idname = "em.where_change"
    bl_label = "Change where you work"

    step: bpy.props.StringProperty(default=STEP_PLACES, options={"SKIP_SAVE"})  # type: ignore
    then: bpy.props.StringProperty(default="", options={"HIDDEN", "SKIP_SAVE"})  # type: ignore

    def invoke(self, context, event):
        wm = context.window_manager
        wm.em_where_then = self.then
        if wm.em_where_step != self.step:
            wm.em_where_step = self.step       # its update reads the step
        else:
            _on_step(None, context)
        return wm.invoke_popup(self, width=520)

    def draw(self, context):
        draw_window(self.layout, context)

    def execute(self, context):
        return {"FINISHED"}


def draw_window(layout, context) -> None:
    step = context.window_manager.em_where_step
    if step == STEP_NODE:
        draw_node_step(layout, context)
    elif step == STEP_ROOMS:
        draw_rooms_step(layout, context)
    else:
        draw_places(layout, context, window=True)


def _on_address(self, context):
    """The address probes itself while it is typed: a moment after the last
    key (a probe per key would freeze the window on a slow node)."""
    typed = str(getattr(self, "em_node_address", "") or "").strip()
    _PROBE["typed"] = typed
    if not typed:
        return
    if not bpy.app.timers.is_registered(_probe_typed):
        bpy.app.timers.register(_probe_typed, first_interval=0.6)


_PROBE: Dict[str, str] = {"typed": ""}


def _probe_typed():
    from . import node_choice
    typed = _PROBE.get("typed") or ""
    try:
        node_choice.find(typed)
    except Exception as exc:  # noqa: BLE001 — a probe never breaks typing
        node_choice.FOUND["suggestion"] = f"{typed}: {exc}"
    _redraw()
    return None


class EM_OT_node_choose(bpy.types.Operator):
    """Choose the node: one row per node (whatever the addresses it answers
    on), the one in use marked. Opens by itself when a gesture needs a node and
    none is chosen — the node step of the one window"""

    bl_idname = "em.node_choose"
    bl_label = "Choose the node"

    then: bpy.props.StringProperty(default="", options={"HIDDEN", "SKIP_SAVE"})  # type: ignore

    def execute(self, context):
        return bpy.ops.em.where_change("INVOKE_DEFAULT", step=STEP_NODE, then=self.then)

    def invoke(self, context, event):
        return self.execute(context)


class EM_OT_node_use(bpy.types.Operator):
    """Use this node: it becomes the node of this project (saved in the list of
    this computer), and the gesture that needed a node goes on"""

    bl_idname = "em.node_use"
    bl_label = "Use this node"

    url: bpy.props.StringProperty(default="")  # type: ignore
    then: bpy.props.StringProperty(default="", options={"HIDDEN"})  # type: ignore

    def execute(self, context):
        from . import servers
        url = str(self.url or "").strip().rstrip("/")
        if not url:
            return {"CANCELLED"}
        context.scene.em_room_url = url
        try:
            servers.remember(url, where.host_of(url))
        except Exception:  # noqa: BLE001 — the choice stands without the list
            pass
        note_transition(f"node: {where.host_of(url)}")
        self.report({"INFO"}, f"node {where.host_of(url)}")
        # what needed a node goes on — in the SAME window, at its step
        if self.then == "enter":
            bpy.ops.em.where_change("INVOKE_DEFAULT", step=STEP_ROOMS)
        elif self.then == "create":
            bpy.ops.em.room_bring("INVOKE_DEFAULT")
        return {"FINISHED"}


def need_node(context, then: str) -> bool:
    """True when a node is chosen; otherwise the window opens at its node
    step, and the gesture `then` goes on after Use."""
    if _base(context):
        return True
    bpy.ops.em.where_change("INVOKE_DEFAULT", step=STEP_NODE, then=then)
    return False


class EM_OT_room_enter(bpy.types.Operator):
    """Enter a collaborative room: yours, the ones shared with you (with your
    role there), one by its id, or one from a stratigraph:// link. Blender
    joins it directly — the rooms step of the one window"""

    bl_idname = "em.room_enter"
    bl_label = "Enter a collaborative room"

    def execute(self, context):
        if not need_node(context, "enter"):
            return {"FINISHED"}
        return bpy.ops.em.where_change("INVOKE_DEFAULT", step=STEP_ROOMS)

    def invoke(self, context, event):
        return self.execute(context)


class EM_OT_room_reconnect(bpy.types.Operator):
    """Enter the room of this project again (its id is saved with the file):
    sign in if needed, and what was waiting is sent"""

    bl_idname = "em.room_reconnect"
    bl_label = "Reconnect"

    def execute(self, context):
        if not _base(context):
            bpy.ops.em.where_change("INVOKE_DEFAULT", step=STEP_NODE, then="enter")
            return {"FINISHED"}
        if not str(getattr(context.scene, "em_room_id", "") or "").strip():
            bpy.ops.em.where_change("INVOKE_DEFAULT", step=STEP_ROOMS)
            return {"FINISHED"}
        from . import operators as ops
        if ops.current_session(context).joined:
            self.report({"INFO"}, "already in the room")
            return {"FINISHED"}
        result = bpy.ops.em.room_join("EXEC_DEFAULT")
        note_transition(f"reconnect {context.scene.em_room_id}: {result}")
        return result


class EM_OT_room_leave(bpy.types.Operator):
    """Leave the room: the access is forgotten; edits the room had not
    confirmed are kept with this file and sent at the next entry"""

    bl_idname = "em.room_leave"
    bl_label = "Leave the room"

    def execute(self, context):
        from . import operators as ops
        from . import room_session as _rs
        session = ops.current_session(context)
        room_id = session.room_id or ops.saved_room(context).get("room_id")
        base = session.base_url
        ops.leave_room()
        kept = _rs.parked_for(base, room_id) if room_id else 0
        note_transition(f"left {room_id}" + (f" · {kept} edit(s) kept" if kept else ""))
        self.report({"INFO"}, f"left {room_id or 'the room'}"
                    + (f" · {kept} edit(s) kept for the next entry" if kept else ""))
        _redraw()
        return {"FINISHED"}


# ── With EMStudio: Permissions… ─────────────────────────────────────────────

def permissions_line(context) -> str:
    from . import operators as ops
    accept = str(getattr(context.scene, "em_sync_accept", "everything"))
    models = bool(getattr(context.scene, "em_accept_commands", False))
    theirs = ops.dichiarazione_del_pari().get("accept")
    line = (f"Accepts from EMStudio: {accept} · "
            f"{'may model here' if models else 'may not model here'}")
    if theirs and theirs != "everything":
        line += f" · EMStudio accepts {theirs}"
    return line


class EM_OT_sidecar_permissions(bpy.types.Operator):
    """What EMStudio may land here (refused on arrival, where you can see
    yourself refusing: nothing leaves this side gated), whether it may model
    in this scene, and what EMStudio itself accepts"""

    bl_idname = "em.sidecar_permissions"
    bl_label = "Permissions"

    def invoke(self, context, event):
        return context.window_manager.invoke_popup(self, width=420)

    def draw(self, context):
        from . import operators as ops
        layout = self.layout
        layout.label(text="What EMStudio may land here", icon="IMPORT")
        layout.prop(context.scene, "em_sync_accept", expand=True)
        layout.prop(context.scene, "em_accept_commands",
                    text="EMStudio may model in this scene")
        theirs = ops.dichiarazione_del_pari().get("accept")
        if theirs:
            row = layout.row()
            row.alert = theirs != "everything"
            row.label(text=f"EMStudio accepts: {theirs}",
                      icon="CHECKMARK" if theirs == "everything" else "CANCEL")
        port = layout.row(align=True)
        port.label(text=f"Bridge on 127.0.0.1:{ops.porta_sidecar()}", icon="PLUGIN")
        port.operator("em.open_addon_preferences", text="", icon="PREFERENCES")

    def execute(self, context):
        return {"FINISHED"}


# ── Log… ────────────────────────────────────────────────────────────────────

class EM_OT_sync_log(bpy.types.Operator):
    """The last edits not applied, the last transitions, and the last message
    that arrived (with its keys: diagnostics)"""

    bl_idname = "em.sync_log"
    bl_label = "Log"

    #: P1 · drawn as the scene's word in a room: its tooltip is the numbers
    scene: bpy.props.BoolProperty(default=False, options={"SKIP_SAVE"})  # type: ignore

    @classmethod
    def description(cls, context, properties):
        if getattr(properties, "scene", False):
            from . import scene_check
            numbers = where.scene_status(scene_check.ULTIMA_VERIFICA.get("tally"))[2]
            if numbers:
                return f"The scene: {numbers}. Click for the Log"
        return cls.__doc__

    def invoke(self, context, event):
        return context.window_manager.invoke_popup(self, width=520)

    def draw(self, context):
        from . import operators as ops
        from . import scene_check
        layout = self.layout
        z = where.zones(where.read_state(context))
        if z["log"][1]:
            layout.label(text=z["log"][1], icon=z["log"][0])
        # the scene's word is the room's state, beside the icon that opened
        # this: here only the numbers behind it (MICRO una verità)
        _icon, _word, numbers = where.scene_status(scene_check.ULTIMA_VERIFICA.get("tally"))
        if numbers:
            layout.label(text=numbers[:110], icon="INFO")
        box = layout.box()
        box.label(text="Not applied", icon="CANCEL")
        for r in ops.RIFIUTI[:8] or []:
            box.label(text=f"{r['ora']} · {r['frase']}"[:110])
        if not ops.RIFIUTI:
            box.label(text="none this session", icon="BLANK1")
        box = layout.box()
        box.label(text="Transitions", icon="FORWARD")
        for t in TRANSITIONS[:8]:
            box.label(text=f"{t['at']} · {t['text']}"[:110])
        if not TRANSITIONS:
            box.label(text="none this session", icon="BLANK1")
        last = ops.ULTIMO_MESSAGGIO
        if last.get("esito"):
            box = layout.box()
            head = box.row()
            head.label(text="Last inbound", icon="IMPORT")
            head.label(text=last.get("ora", ""))
            box.label(text=f"{last['tipo']}: {last['esito']}"[:110])
            if last.get("chiavi"):
                box.label(text=f"payload keys: {last['chiavi']}"[:110])

    def execute(self, context):
        return {"FINISHED"}


# ── C1 · Room settings… ─────────────────────────────────────────────────────

ROOM_SETTINGS: Dict[str, Any] = {}


def _room_access_token():
    from . import room as room_cfg
    return room_cfg._session.get("token")


def load_room_settings(base: str, room_id: str) -> Dict[str, Any]:
    """Members, invitations and who sees, as the node says them (each its own
    refusal: an editor reads who sees but not the member list)."""
    from . import room_access
    token = _room_access_token()
    out: Dict[str, Any] = {"room_id": room_id, "base": base}
    for key, call in (("members", lambda: room_access.members(base, token, room_id)),
                      ("invites", lambda: room_access.invites(base, token, room_id)),
                      ("access", lambda: room_access.study_access(base, token, room_id))):
        try:
            out[key] = call()
        except Exception as exc:  # noqa: BLE001 — the node's sentence, kept
            out[key + "_error"] = str(exc)
    ROOM_SETTINGS.clear()
    ROOM_SETTINGS.update(out)
    acc = out.get("access") or {}
    try:
        wm = bpy.context.window_manager
        wm.em_rs_visibility = acc.get("visibility") or "restricted"
        wm.em_rs_embargo = acc.get("embargo") or ""
    except Exception:  # noqa: BLE001 — headless without the properties
        pass
    return out


class EM_OT_room_settings(bpy.types.Operator):
    """Who takes part in this room (by ORCID, with a role), invitation links,
    and who sees the study — for whoever may assign them (admin, owner)"""

    bl_idname = "em.room_settings"
    bl_label = "Room settings"

    def invoke(self, context, event):
        from . import room as room_cfg
        here = room_cfg.room()
        if not here.get("room_id"):
            self.report({"ERROR"}, "not in a room")
            return {"CANCELLED"}
        load_room_settings(here["base_url"], here["room_id"])
        return context.window_manager.invoke_popup(self, width=560)

    def draw(self, context):
        wm = context.window_manager
        layout = self.layout
        rs = ROOM_SETTINGS
        mem = rs.get("members") or {}
        layout.label(text=f"Room {rs.get('room_id')} · your role: "
                          f"{mem.get('your_role') or '?'}", icon="COMMUNITY")
        box = layout.box()
        box.label(text="Members", icon="USER")
        if rs.get("members_error"):
            box.label(text=rs["members_error"][:100], icon="LOCKED")
        else:
            if mem.get("owner"):
                box.label(text=f"★ {mem['owner']} · owner")
            for m in mem.get("members") or []:
                box.label(text=f"{m['orcid']} · {m['role']}")
            for g in mem.get("groups") or []:
                box.label(text=f"team {g.get('name') or g.get('group_id')} · {g['role']}")
            add = box.row(align=True)
            add.prop(wm, "em_rs_orcid", text="")
            add.prop(wm, "em_rs_role", text="")
            add.operator("em.room_member_add", text="Add")
        box = layout.box()
        box.label(text="Invite with a link", icon="LINKED")
        row = box.row(align=True)
        row.prop(wm, "em_rs_link_role", text="")
        row.prop(wm, "em_rs_days", text="Days")
        row.prop(wm, "em_rs_uses", text="Uses")
        row.operator("em.room_invite_new", text="New link")
        if wm.em_rs_link:
            line = box.row(align=True)
            line.label(text=wm.em_rs_link[:80])
            line.operator("em.room_invite_copy", text="Copy", icon="COPYDOWN")
            box.label(text="Copy it now: the node keeps only a fingerprint of the link.",
                      icon="INFO")
        live = [i for i in rs.get("invites") or [] if i.get("state") == "live"]
        if live:
            box.label(text=f"{len(live)} link(s) live", icon="BLANK1")
        box = layout.box()
        box.label(text="Who sees the study", icon="HIDE_OFF")
        if rs.get("access_error"):
            box.label(text=rs["access_error"][:100], icon="LOCKED")
        row = box.row(align=True)
        row.prop(wm, "em_rs_visibility", expand=True)
        row = box.row(align=True)
        row.prop(wm, "em_rs_embargo", text="Embargo until")
        row.operator("em.room_study_access_set", text="Apply")

    def execute(self, context):
        return {"FINISHED"}


def _where_room():
    from . import room as room_cfg
    here = room_cfg.room()
    return here.get("base_url"), here.get("room_id")


class EM_OT_room_member_add(bpy.types.Operator):
    """Give this ORCID a role in the room (the node checks you may assign it)"""

    bl_idname = "em.room_member_add"
    bl_label = "Add a member"

    def execute(self, context):
        from . import room_access
        wm = context.window_manager
        base, room_id = _where_room()
        try:
            room_access.set_member(base, _room_access_token(), room_id,
                                   wm.em_rs_orcid, wm.em_rs_role)
        except Exception as exc:  # noqa: BLE001 — the node's sentence
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        self.report({"INFO"}, f"{wm.em_rs_orcid}: {wm.em_rs_role}")
        note_transition(f"member {wm.em_rs_orcid} as {wm.em_rs_role}")
        wm.em_rs_orcid = ""
        load_room_settings(base, room_id)
        return {"FINISHED"}


class EM_OT_room_invite_new(bpy.types.Operator):
    """A new invitation link: the role it offers, how many days it lives and
    how many times it can be used (0 = no limit)"""

    bl_idname = "em.room_invite_new"
    bl_label = "New invitation link"

    def execute(self, context):
        from . import handoff, room_access
        wm = context.window_manager
        base, room_id = _where_room()
        token = _room_access_token()
        try:
            made = room_access.invite(base, token, room_id, wm.em_rs_link_role,
                                      days=wm.em_rs_days, uses=wm.em_rs_uses)
        except Exception as exc:  # noqa: BLE001
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        doors = handoff.open_targets(base, room_id, token=token) or {}
        wm.em_rs_link = room_access.link_for(doors.get("web") or doors.get("scheme") or "",
                                             made.get("token") or "")
        INVITED.append({"role": made.get("role"), "link": wm.em_rs_link,
                        "token_id": made.get("token_id")})
        role = str(made.get("role") or "")
        self.report({"INFO"}, f"{'an' if role[:1] in 'aeiou' else 'a'} {role} link: "
                              f"copy it now")
        load_room_settings(base, room_id)
        return {"FINISHED"}


#: the links minted this session (the referto says who was invited)
INVITED: List[Dict[str, Any]] = []


class EM_OT_room_invite_copy(bpy.types.Operator):
    """Copy the new link to the clipboard"""

    bl_idname = "em.room_invite_copy"
    bl_label = "Copy the link"

    def execute(self, context):
        context.window_manager.clipboard = context.window_manager.em_rs_link
        self.report({"INFO"}, "link copied")
        return {"FINISHED"}


class EM_OT_room_study_access_set(bpy.types.Operator):
    """Write who sees the study in its header: restricted (the room's people)
    or public, and an embargo date (empty: none)"""

    bl_idname = "em.room_study_access_set"
    bl_label = "Who sees the study"

    def execute(self, context):
        from . import room_access
        wm = context.window_manager
        base, room_id = _where_room()
        try:
            got = room_access.set_study_access(base, _room_access_token(), room_id,
                                               visibility=wm.em_rs_visibility,
                                               embargo=wm.em_rs_embargo)
        except Exception as exc:  # noqa: BLE001
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        self.report({"INFO"}, f"{got.get('visibility')}"
                    + (f", embargo until {got['embargo']}" if got.get("embargo") else ""))
        load_room_settings(base, room_id)
        return {"FINISHED"}


# F1 · «The .blend in the room…» (`em.room_blend`) is gone (MICRO una verità,
# 13 Oct 2026): no menu opened it since MICRO tre pannelli, and what it showed
# — the snapshots with Restore, the starting package — is Project storage's.

class EM_MT_room_more(bpy.types.Menu):
    """The rest of what a room offers"""

    bl_idname = "EM_MT_room_more"
    bl_label = "Room"

    def draw(self, context):
        # MICRO tre pannelli · the archives of the .blend (list, Restore) are
        # in Project storage; the Log is the icon beside the room's state
        layout = self.layout
        layout.operator("em.blend_backup_archive", text="Archive this .blend", icon="EXPORT")
        layout.operator("em.room_settings", text="Room settings…", icon="PREFERENCES")
        layout.separator()
        layout.operator("em.room_leave", text="Leave the room", icon="UNLINKED")


_CLASSES = (EM_OT_where_change, EM_OT_node_choose, EM_OT_node_use, EM_OT_room_enter,
            EM_OT_room_reconnect, EM_OT_room_leave, EM_OT_sidecar_permissions,
            EM_OT_sync_log, EM_OT_room_settings, EM_OT_room_member_add,
            EM_OT_room_invite_new, EM_OT_room_invite_copy, EM_OT_room_study_access_set,
            EM_MT_room_more)


def register():
    for cls in _CLASSES:
        bpy.utils.register_class(cls)
    wm = bpy.types.WindowManager
    from .room_access import LINK_ROLES, MEMBER_ROLES
    wm.em_node_address = bpy.props.StringProperty(
        name="Address", default="", update=_on_address, options={"TEXTEDIT_UPDATE"},
        description="Another node's address, as https://host:port/path "
                    "(e.g. https://node.example.org): it is asked what it is while "
                    "you type")
    wm.em_where_step = bpy.props.EnumProperty(
        name="Step", update=_on_step, default=STEP_PLACES,
        items=((STEP_PLACES, "Where you work", "The three places"),
               (STEP_NODE, "The node", "Choose the node"),
               (STEP_ROOMS, "The rooms", "Enter a collaborative room")))
    wm.em_where_then = bpy.props.StringProperty(default="", options={"SKIP_SAVE"})
    wm.em_node_details = bpy.props.BoolProperty(
        name="Details", default=False, description="Every address a node answers on")
    wm.em_room_link_text = bpy.props.StringProperty(
        name="Link", default="",
        description="A stratigraph://open?server=…&room=… link (it carries no token)")
    wm.em_rs_orcid = bpy.props.StringProperty(name="ORCID", default="",
                                              description="0000-0000-0000-0000")
    wm.em_rs_role = bpy.props.EnumProperty(
        name="Role", items=[(r, r, "") for r in MEMBER_ROLES], default="editor")
    wm.em_rs_link_role = bpy.props.EnumProperty(
        name="Role", items=[(r, r, "") for r in LINK_ROLES], default="editor")
    wm.em_rs_days = bpy.props.IntProperty(name="Days", default=7, min=0,
                                          description="How long the link lives (0: no expiry)")
    wm.em_rs_uses = bpy.props.IntProperty(name="Uses", default=0, min=0,
                                          description="How many times it can be used (0: no limit)")
    wm.em_rs_link = bpy.props.StringProperty(name="Link", default="")
    wm.em_rs_visibility = bpy.props.EnumProperty(
        name="Visibility",
        items=(("restricted", "Restricted", "Only the room's people see the study"),
               ("public", "Public", "Anybody with its name reads the study")),
        default="restricted")
    wm.em_rs_embargo = bpy.props.StringProperty(
        name="Embargo", default="", description="YYYY-MM-DD; empty: no embargo")


def unregister():
    wm = bpy.types.WindowManager
    for name in ("em_rs_embargo", "em_rs_visibility", "em_rs_link", "em_rs_uses",
                 "em_rs_days", "em_rs_link_role", "em_rs_role", "em_rs_orcid",
                 "em_node_address", "em_where_step", "em_where_then",
                 "em_node_details", "em_room_link_text"):
        if hasattr(wm, name):
            delattr(wm, name)
    for cls in reversed(_CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:  # noqa: BLE001
            pass
