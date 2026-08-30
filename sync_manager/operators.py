"""EMtools ⇄ EMStudio live-sync — operators + EVENT-DRIVEN dispatch (ADR-002
phase 1 selection + phase 2 op-log). EMtools is the HOST: it runs the
WebSocket server (sync_bridge.ws_server) and holds the live s3dgraphy graph;
EMStudio connects as a client.

No polling timer. Two directions, both event-driven:

  * OUTBOUND (Blender → EMStudio): a ``bpy.msgbus`` subscription on the active
    object fires ``_on_selection_changed`` on the MAIN thread whenever the
    selection changes → broadcast the node id. Zero polling.
  * INBOUND (EMStudio → Blender): the server thread's ``on_message`` callback
    schedules a ONE-SHOT ``bpy.app.timers.register(_drain_inbox,
    first_interval=0)`` (returns ``None`` → self-unregisters). It fires only
    when a message actually arrives, drains the queue on the MAIN thread and
    applies each message (select / op). ``timers.register`` is the one
    Blender API that is safe to call from a non-main thread.

The server thread only touches the socket + thread-safe queue and schedules
the one-shot; every ``bpy`` access happens on the main thread.

Known limitation: ``bpy.msgbus`` subscriptions are dropped when a new .blend
is loaded — start Sync AFTER opening the project (re-subscribe on load_post
is a later refinement).
"""

from __future__ import annotations

import json
import threading

import bpy  # type: ignore

from ..sync_bridge.ws_server import WsServer
from ..sync_bridge.wire import WIRE, WireError, envelope, read
from ..functions import is_graph_available, select_3D_obj
from ..operators.addon_prefix_helpers import (
    proxy_name_to_node_name,
    node_name_to_proxy_name,
)

_SOURCE = "emtools"

# Module-level session state (a single server per Blender instance).
_server: WsServer | None = None
_last_active_name: str | None = None
_last_selection: frozenset = frozenset()  # node_ids last selected (echo guard)
_pending_repop = False  # a structural op needs a list rebuild (batched per drain)

# msgbus subscription owner (opaque token; clear_by_owner removes the sub).
_msgbus_owner = object()

# One-shot inbound-drain scheduling guard. The flag is cleared at the START of
# every drain, so any message arriving during a drain re-schedules another
# drain — no lost wake-ups; at worst one redundant empty drain.
_drain_lock = threading.Lock()
_drain_scheduled = False


# --------------------------------------------------------------------------- #
# MODES1 · what THIS side does on the channel (mirror of EMStudio's control)
# --------------------------------------------------------------------------- #
#
# Four states, described from Blender's point of view — each side describes
# itself, so "send" always means "out of here":
#
#   off      no echo at all
#   send     Blender's selection reaches EMStudio; EMStudio's does not land here
#   receive  EMStudio's selection lands here; Blender's does not leave
#   both     the two follow each other
#
# Why it exists: **nobody has somebody else's state imposed on them without
# having chosen it.** One person on two screens wants `both`; two people working
# at once want `off` or one direction — and without this the Blender user could
# only unplug the whole server.
#
# It gates the EPHEMERAL traffic (selection + ops). `request_snapshot` and
# `request_save` are NOT gated: they are requests the client makes, not an echo,
# and refusing them would make a connected EMStudio look broken.

SYNC_DIRECTIONS = (
    ("off", "Off", "No echo: nothing leaves, nothing is applied"),
    ("send", "Send", "Blender's selection reaches EMStudio; EMStudio's does not land here"),
    ("receive", "Receive", "EMStudio's selection lands here; Blender's does not leave"),
    ("both", "Both", "The two screens follow each other"),
)


def _direction() -> str:
    """The current channel direction. Defaults to `both` — which IS the
    behaviour that existed before this control, so nothing changes for anyone
    until they choose."""
    try:
        return str(getattr(bpy.context.scene, "em_sync_direction", "both") or "both")
    except Exception:  # noqa: BLE001 — no scene (headless import): assume both
        return "both"


def _sends() -> bool:
    return _direction() in ("send", "both")


def _receives() -> bool:
    return _direction() in ("receive", "both")


def _on_accept_commands_changed(self, context):
    """Consent changed → tell the client at once.

    The affordance on the other side is drawn from `host_info`; without this it
    would stay greyed out until the next reconnection, and the user who just
    ticked the box would think the box does nothing.
    """
    try:
        ok, graph = is_graph_available(context)
        _send_host_info(context, graph if ok else None)
    except Exception as exc:  # noqa: BLE001
        print(f"[sync] could not announce the consent change: {exc}")


def _accepts_commands() -> bool:
    """CMD1 · does this host let EMStudio act on the scene?

    A separate switch from the sync direction, and OFF by default. Mirroring a
    selection is a reflection; executing a command MODELS IN YOUR SCENE, and the
    stronger act gets the explicit consent — nobody models in somebody else's
    Blender because a socket was open.
    """
    try:
        return bool(getattr(bpy.context.scene, "em_accept_commands", False))
    except Exception:  # noqa: BLE001
        return False


def is_running() -> bool:
    return _server is not None and _server.running


def client_count() -> int:
    return _server.client_count() if _server else 0


# --------------------------------------------------------------------------- #
# helpers (main thread)
# --------------------------------------------------------------------------- #

def _node_id_for_object(obj, graph) -> str | None:
    """Blender object → its graph node's UUID, or None if it is not an EM
    proxy. Name-based (obj name = '<graph_code>.<node.name>')."""
    if obj is None or graph is None:
        return None
    node_name = proxy_name_to_node_name(obj.name)
    finder = getattr(graph, "find_node_by_name", None)
    node = finder(node_name) if callable(finder) else None
    return getattr(node, "node_id", None) if node else None


def _frame_selected():
    """Best-effort 'view selected' in the first 3D viewport."""
    try:
        win = bpy.context.window
        for area in (win.screen.areas if win and win.screen else []):
            if area.type == "VIEW_3D":
                region = next((r for r in area.regions if r.type == "WINDOW"), None)
                if region:
                    with bpy.context.temp_override(area=area, region=region):
                        bpy.ops.view3d.view_selected()
                break
    except Exception:
        pass


def _redraw():
    try:
        for area in bpy.context.screen.areas:
            area.tag_redraw()
    except Exception:
        pass


def _apply_incoming_select(node_id: str, context, graph) -> bool:
    """Select + frame the object for an incoming node id. Returns True if a
    matching object was selected."""
    finder = getattr(graph, "find_node_by_id", None)
    node = finder(node_id) if callable(finder) else None
    if not node:
        return False
    select_3D_obj(node.name, context=context, graph=graph)
    _frame_selected()
    return True


def _apply_incoming_select_many(node_ids, active_id, context, graph) -> bool:
    """Select ALL proxies for a peer's multi-selection (mirrors Blender's
    active/selected model): the active node reuses select_3D_obj (deselects
    all, handles visibility, sets it active), the others are added on top."""
    finder = getattr(graph, "find_node_by_id", None)
    if not callable(finder):
        return False
    active_node = finder(active_id) if active_id else None
    if active_node is not None:
        select_3D_obj(active_node.name, context=context, graph=graph)
    else:
        try:
            bpy.ops.object.select_all(action="DESELECT")
        except Exception:
            pass
    for nid in node_ids:
        if nid == active_id:
            continue
        node = finder(nid)
        if node is None:
            continue
        obj = bpy.data.objects.get(
            node_name_to_proxy_name(node.name, context=context, graph=graph))
        if obj is not None:
            try:
                obj.select_set(True)
            except Exception:
                pass
    _frame_selected()
    return True


def _reflect_in_em_list(context, node, patch: dict):
    """Mirror a node patch onto its EMListItem so the EM panel updates.

    EMListItems are keyed by NAME (the node_id field is frequently empty on
    populated items), so we match name first and fall back to node_id. A
    targeted patch keeps the current selection; a full repopulate
    (populate_blender_lists_from_graph) is the tool for STRUCTURAL ops
    (add/delete) — the lists are a projection of the graph, the s3dgraphy
    multigraph in memory is the source of truth."""
    try:
        units = context.scene.em_tools.stratigraphy.units
    except Exception:
        return
    nid = getattr(node, "node_id", None)
    for item in units:
        if item.name == node.name or (nid and getattr(item, "node_id", "") == nid):
            if "description" in patch:
                item.description = patch["description"]
            return


def _node_from_payload(payload: dict):
    """Build an s3dgraphy Node from an EMStudio node op payload, reusing the
    emjson importer's type-resolving instantiator (degrades to a base Node on
    unknown types)."""
    try:
        from s3dgraphy.importer.emjson_importer import _instantiate
        node = _instantiate(payload.get("node_type", ""), payload, [])
    except Exception as exc:  # noqa: BLE001
        print(f"[sync] node instantiate failed: {exc}")
        return None
    if node is not None and "description" in payload:
        try:
            node.description = payload["description"]
        except Exception:
            pass
    return node


def _repopulate(context, graph):
    """Full rebuild of the Blender EM lists from the graph — the correct tool
    for STRUCTURAL ops (add/delete node/edge); the lists are a projection.

    MUST clear first: populate_blender_lists_from_graph APPENDS (no internal
    clear), so without this repeated calls duplicate every row."""
    try:
        from ..populate_lists import (
            populate_blender_lists_from_graph,
            clear_lists,
        )
        clear_lists(context)
        populate_blender_lists_from_graph(context, graph)
    except Exception as exc:  # noqa: BLE001
        print(f"[sync] repopulate failed: {exc}")


def _apply_op(msg: dict, context, graph):
    """Apply an op-log operation from EMStudio to the live s3dgraphy graph
    (ADR-002 phase 2). Handles update_node (targeted) + structural
    add/delete of nodes and edges (full list repopulate).

    `msg` is the op's BODY (WIRE 2's `payload`), so `msg["source"]` here — if a
    verb ever has one — is the op's own field and nothing else's.""" 
    op = msg.get("op")
    if graph is None:
        return

    if op == "update_node":
        node_id = msg.get("node_id")
        patch = msg.get("patch") or {}
        finder = getattr(graph, "find_node_by_id", None)
        node = finder(node_id) if callable(finder) else None
        if not node or "description" not in patch:
            return
        node.description = patch["description"]
        _reflect_in_em_list(context, node, patch)
        _redraw()
        return

    changed = False
    try:
        if op == "add_node":
            nd = msg.get("node") or {}
            nid = nd.get("id")
            if nid and not graph.find_node_by_id(nid):
                node = _node_from_payload(nd)
                if node is not None:
                    graph.add_node(node, overwrite=True)
                    changed = True
        elif op == "delete_node":
            nid = msg.get("node_id")
            if nid and graph.find_node_by_id(nid):
                graph.remove_node(nid)
                changed = True
        elif op == "add_edge":
            ed = msg.get("edge") or {}
            if ed.get("id") and ed.get("source") and ed.get("target"):
                graph.add_edge(
                    ed["id"], ed["source"], ed["target"],
                    ed.get("edge_type") or "generic_connection")
                changed = True
        elif op == "delete_edge":
            ed = msg.get("edge") or {}
            if ed.get("id"):
                graph.remove_edge(ed["id"])
                changed = True
    except Exception as exc:  # noqa: BLE001
        print(f"[sync] _apply_op {op} failed: {exc}")
        return

    if changed:
        # batched: the actual list rebuild + redraw happen once at the end of
        # the inbox drain (a group op is add_node + N add_edges → 1 rebuild)
        global _pending_repop
        _pending_repop = True


def emit_op(op: dict):
    """Emit a local (Blender-side) graph mutation to connected clients
    (ADR-002 phase 2, reverse direction). No-op when the sync server is off.
    `op` is the BODY of the operation — `{"op": "update_node", "node_id": …,
    "patch": …}`. WIRE 2 puts it inside `payload`, so a field of the op can
    never collide with a word of the envelope (an `add_edge` carries
    `source`/`target` as its endpoints; the wire's `source` is who sent it).

    P4.4 · the same operation goes to the ROOM when we are in one. Same gate
    (`_sends()`): the direction control governs what leaves this Blender, and it
    would be a strange control that stopped the message to the person next to
    you and let it through to the server.
    """
    if not _sends():          # MODES1 · off / receive: nothing leaves
        return
    from .room_session import SESSION

    srv = _server
    if srv is not None and srv.running:
        body = {k: v for k, v in op.items() if k != "type"}
        try:
            srv.broadcast(json.dumps(envelope("op", body, source=_SOURCE)))
        except Exception as exc:  # noqa: BLE001
            print(f"[sync] emit_op failed: {exc}")
    if SESSION.joined:
        try:
            SESSION.send_op(op)
        except Exception as exc:  # noqa: BLE001
            print(f"[room] emit_op failed: {exc}")


def _host_info(context, graph):
    """Describe what this host (Blender/EMtools) is editing so the EMStudio
    client can show it in the footer sidecar badge: tool · document · database.
    All fields optional — a field is omitted when unknown."""
    # CMD1 · the client cannot guess whether commands will be executed, and an
    # affordance that is offered and then refused is worse than one that is
    # greyed out. So the host DECLARES it, and EMStudio reads it.
    info = {"tool": "Blender · EMtools", "accepts_commands": _accepts_commands()}
    # CONNECTOR · and the DESCRIPTOR: what this host is, how it can be reached,
    # what it speaks and what it can do — declared before anything happens, so
    # EMStudio's registry can accept it (or refuse it with a reason) instead of
    # discovering at the first write that the two do not understand each other.
    # Same frame as `tool` and `accepts_commands`, which were the first two
    # answers to the same question.
    try:
        from .connector import descriptor as _connector_descriptor
        info["connector"] = _connector_descriptor(
            accepts_commands=info["accepts_commands"])
    except Exception as exc:  # noqa: BLE001
        # A host that cannot describe itself still pairs: the client falls back to
        # what it DOES declare (older peers sent no descriptor at all). Said, not
        # swallowed — a silent absence here would look like a stale EMStudio.
        print(f"[connector] descriptor unavailable: {exc}")
    try:
        em_tools = context.scene.em_tools
        idx = em_tools.active_file_index
        if 0 <= idx < len(em_tools.graphml_files):
            entry = em_tools.graphml_files[idx]
            if getattr(entry, "graphml_path", ""):
                info["file"] = bpy.path.basename(entry.graphml_path)
            emdb = getattr(entry, "emdb_filepath", "")
            if emdb:
                info["database"] = bpy.path.basename(emdb)
    except Exception:  # noqa: BLE001
        pass
    if "file" not in info and graph is not None:
        # no file entry known → fall back to the graph name/id as a label
        label = getattr(graph, "name", None) or getattr(graph, "graph_id", "")
        if label:
            info["label"] = str(label)
    return info


def _send_host_info(context, graph):
    """Push a standalone host_info message (e.g. when the active graph
    changes). EMStudio also accepts `host` piggy-backed on the snapshot."""
    srv = _server
    if srv is None or not srv.running:
        return
    srv.broadcast(json.dumps(
        envelope("host_info", _host_info(context, graph), source=_SOURCE)))


def _send_snapshot(graph, context=None):
    """Host → client: send the active graph as an .em.json doc (ADR-002
    snapshot-READ). Triggered by a client's ``request_snapshot`` on connect —
    this is what makes 'sync mode = see Blender's data'. The host metadata
    (tool/file/database) rides along as `host` for the sidecar badge."""
    srv = _server
    if srv is None or not srv.running or graph is None:
        return
    try:
        from ..emjson_support import graph_to_emjson_dict
        doc = graph_to_emjson_dict(graph)
    except Exception as exc:  # noqa: BLE001
        print(f"[sync] snapshot build failed: {exc}")
        return
    srv.broadcast(json.dumps(envelope(
        "snapshot",
        {"doc": doc, "host": _host_info(context or bpy.context, graph)},
        source=_SOURCE)))


def _handle_message(raw: str, context, graph, ok: bool):
    """Dispatch one inbound message (main thread).

    WIRE 2: the envelope says WHO and WHAT KIND, the payload holds the body. A
    message from another protocol version is refused with a line in the console
    rather than half-read — half-reading a frame is how an edge lost its
    endpoints.
    """
    global _last_active_name, _last_selection
    try:
        msg = json.loads(raw)
    except (ValueError, TypeError):
        return
    if msg.get("source") == _SOURCE:
        return  # our own echo
    try:
        mtype, payload = read(msg)
    except WireError as exc:
        print(f"[sync] refused a message: {exc}")
        return
    # MODES1 · the ephemeral channels are gated; the requests below are not.
    if mtype in ("select", "op") and not _receives():
        return
    if mtype == "select" and ok and (payload.get("node_id") or payload.get("node_ids")):
        node_ids = payload.get("node_ids")
        active_id = payload.get("node_id")
        if node_ids:
            _apply_incoming_select_many(node_ids, active_id, context, graph)
            _last_selection = frozenset(node_ids)
        elif active_id:
            _apply_incoming_select(active_id, context, graph)
            _last_selection = frozenset([active_id])
        # suppress the echo the outbound msgbus callback would otherwise send
        active = getattr(context.view_layer.objects, "active", None)
        _last_active_name = active.name if active else _last_active_name
    elif mtype == "op" and ok:
        _apply_op(payload, context, graph)
    elif mtype == "request_snapshot" and ok:
        _send_snapshot(graph, context)
    elif mtype == "request_save":
        _save_emjson_on_host()
    elif mtype == "command":
        _handle_command(payload, context, graph if ok else None)


def _handle_command(msg, context, graph):
    """CMD1 · execute a command from EMStudio (MAIN thread) and answer.

    NOT gated by the sync direction: a command is an explicit act by a person at
    the other end, not an echo, so turning the selection mirror off must not
    silently disable the 3D arm. It is gated by CONSENT, which is a different
    question and has its own switch.

    A refusal is ANSWERED, not swallowed: the client is waiting, and a command
    that vanishes looks exactly like a command that failed.
    """
    from . import commands as cmds

    cmd_id = str(msg.get("cmd_id") or "")
    if not _accepts_commands():
        print(f"[sync] command refused ({msg.get('verb')}): consent is off "
              f"(EM Server ▸ Accept commands from EMStudio)")
        _send_command_result({
            "ok": False, "cmd_id": cmd_id,
            "error": "this host does not accept commands (the Blender user has "
                     "not enabled 'Accept commands from EMStudio')"})
        return
    result = cmds.execute(msg, context, graph)
    _send_command_result(result)
    if result.get("ok"):
        # a command changed the graph: the lists must show it
        global _pending_repop
        _pending_repop = True


def _send_command_result(result):
    srv = _server
    if srv is None or not srv.running:
        return
    try:
        srv.broadcast(json.dumps(
            envelope("command_result", result, source=_SOURCE)))
    except Exception as exc:  # noqa: BLE001
        print(f"[sync] command_result failed: {exc}")


def _save_emjson_on_host():
    """A Sidecar client (EMStudio) is leaving sync and asked us — the host — to
    persist the canonical graph (ADR-002 §4). Save the active graph's em.json
    in place via export.em_save (falls back to a Save-As dialog if the entry
    has no em.json path yet)."""
    try:
        import bpy
        res = bpy.ops.export.em_save()
        print(f"[EMStudio sync] request_save → export.em_save {res}")
    except Exception as exc:  # pragma: no cover — surface in the console
        print(f"[EMStudio sync] request_save failed: {exc}")


# --------------------------------------------------------------------------- #
# INBOUND — one-shot drain (scheduled from the server thread)
# --------------------------------------------------------------------------- #

def _drain_inbox():
    """One-shot timer callback (MAIN thread): drain + apply every queued
    message, then unregister (return None).

    Two sources feed the same drain: the clients connected TO us (the server's
    inbox) and the room we are connected to (P4.4). Deliberately one drain and
    not two — a message is a message, `_handle_message` already dispatches by
    type, and two timers would mean two orders in which the same op could land.
    """
    global _drain_scheduled, _pending_repop
    with _drain_lock:
        _drain_scheduled = False  # cleared first: messages arriving now re-arm
    from .room_session import SESSION
    srv = _server
    if srv is None and not SESSION.joined:
        return None
    context = bpy.context
    ok, graph = is_graph_available(context)
    _pending_repop = False
    while srv is not None:
        try:
            raw = srv.inbox.get_nowait()
        except Exception:
            break
        _handle_message(raw, context, graph, ok)
    for message in SESSION.drain():
        # the room's frames are the same wire; `select` from a room carries a
        # `connection_id` (somebody else's awareness) and must NOT move our own
        # selection — the bug P4.3 found in EMStudio, not repeated here
        if (message.get("type") == "select"
                and (message.get("payload") or {}).get("connection_id")):
            continue
        _handle_message(json.dumps(message), context, graph, ok)
    if SESSION.joined:
        SESSION.ack()
    if _pending_repop:  # batch: one list rebuild for the whole drained burst
        _repopulate(context, graph)
        _redraw()
        _pending_repop = False
    return None  # one-shot


def _schedule_drain(_payload=None):
    """WsServer on_message callback — runs on the SERVER thread. Only touches
    the guard + bpy.app.timers.register (thread-safe)."""
    global _drain_scheduled
    with _drain_lock:
        if _drain_scheduled:
            return
        _drain_scheduled = True
    try:
        bpy.app.timers.register(_drain_inbox, first_interval=0.0)
    except Exception:
        with _drain_lock:
            _drain_scheduled = False


# --------------------------------------------------------------------------- #
# OUTBOUND — msgbus selection subscription (main thread)
# --------------------------------------------------------------------------- #

def _on_selection_changed(*_args):
    """msgbus notify (MAIN thread): the active object changed → broadcast the
    FULL current selection (active + others), mirroring Blender's model, unless
    it matches what we just applied from an inbound message (echo guard)."""
    global _last_active_name, _last_selection
    srv = _server
    if srv is None or not srv.running:
        return
    if not _sends():          # MODES1 · off / receive: my selection stays here
        return
    context = bpy.context
    ok, graph = is_graph_available(context)
    if not ok:
        return
    sel_ids = []
    for obj in getattr(context, "selected_objects", []) or []:
        nid = _node_id_for_object(obj, graph)
        if nid and nid not in sel_ids:
            sel_ids.append(nid)
    sel_set = frozenset(sel_ids)
    if sel_set == _last_selection:
        return  # unchanged — nothing to broadcast (also suppresses our echo)
    _last_selection = sel_set
    active = getattr(context.view_layer.objects, "active", None)
    _last_active_name = active.name if (active and active.select_get()) else None
    active_id = (
        _node_id_for_object(active, graph)
        if (active and active.select_get())
        else (sel_ids[0] if sel_ids else None)
    )
    if not sel_ids and not active_id:
        return
    body = {"node_id": active_id}
    if len(sel_ids) > 1:
        body["node_ids"] = sel_ids
    srv.broadcast(json.dumps(envelope("select", body, source=_SOURCE)))


def _subscribe_selection():
    bpy.msgbus.subscribe_rna(
        key=(bpy.types.LayerObjects, "active"),
        owner=_msgbus_owner,
        args=(),
        notify=_on_selection_changed,
    )


def _unsubscribe_selection():
    try:
        bpy.msgbus.clear_by_owner(_msgbus_owner)
    except Exception:
        pass


# --------------------------------------------------------------------------- #
# lifecycle
# --------------------------------------------------------------------------- #

def _start(port: int):
    global _server, _last_active_name, _last_selection, _drain_scheduled
    if is_running():
        return
    _last_active_name = None
    _last_selection = frozenset()
    with _drain_lock:
        _drain_scheduled = False
    srv = WsServer(port=port, on_message=_schedule_drain)
    srv.start()
    _server = srv
    _subscribe_selection()


def _stop():
    global _server, _drain_scheduled
    _unsubscribe_selection()
    if bpy.app.timers.is_registered(_drain_inbox):
        try:
            bpy.app.timers.unregister(_drain_inbox)
        except ValueError:
            pass
    with _drain_lock:
        _drain_scheduled = False
    if _server:
        _server.stop()
        _server = None


# --------------------------------------------------------------------------- #
# P4.4 · the ROOM (Blender as a client, not only as a host)
# --------------------------------------------------------------------------- #

def room_status(context=None) -> dict:
    """What to show about the room: joined, who else is there, which room."""
    from . import room as room_cfg
    from .room_session import SESSION

    info = room_cfg.room()
    info.update({"joined": SESSION.joined,
                 "room_id": SESSION.room_id or info.get("room_id"),
                 "members": len(SESSION.members),
                 "host": SESSION.host_tool,
                 "author": SESSION.author,
                 "role": SESSION.role,
                 "can_write": SESSION.can_write,
                 "error": SESSION.error})
    return info


#: The three states a session can be in, with the names EMStudio uses. One
#: vocabulary across the two apps: somebody switching between them should not
#: have to learn that "Room" here is "Hub" there.
MODE_STANDALONE = "standalone"
MODE_SIDECAR = "sidecar"
MODE_HUB = "hub"


def session_mode(context=None) -> str:
    """Which mode this Blender is in — DERIVED, never chosen.

    The design turn (EM_design_room-come-workspace §3) is that the ROOM is the
    primitive and the mode follows from belonging: join a room and you are in
    Hub mode because you are in a room, not because somebody pressed a third
    button that then has to be kept in agreement with reality. Leave, and the
    mode goes back on its own.

    The order is the precedence, and it is the honest one: being in a room is a
    stronger fact than serving a bridge, so a Blender doing both reads as Hub —
    that is where the shared document is.
    """
    from .room_session import SESSION

    if SESSION.joined:
        return MODE_HUB
    if is_running():
        return MODE_SIDECAR
    return MODE_STANDALONE


def _list_adopted_graphs(context) -> list:
    """Give every adopted graph a row in the EM Data Tree, and return the NEW ones.

    The manager holds the graphs; `em_tools.graphml_files` is what the panel
    lists and what `is_graph_available` reads — a row per graph, keyed by
    `graph_id`, because that name is what `get_graph()` is asked for. Without a
    row the session is in the state this function exists to end: loaded and
    invisible.

    The same act the em.json importer performs (`importer_emjson.py`), minus the
    file: a room's document arrives over a socket, so there is no path to
    remember and `graphml_path` stays empty. That is not a gap to fill with the
    temporary file this adoption wrote — it is deleted a few lines later, and a
    row pointing at it would offer a reload that cannot work.

    Idempotent by `graph_id`: re-joining a room must not grow the list.
    """
    em_tools = getattr(context.scene, "em_tools", None)
    if em_tools is None or not hasattr(em_tools, "graphml_files"):
        return []
    from s3dgraphy import get_graph
    from s3dgraphy.container import is_shelf_member
    from s3dgraphy.multigraph.multigraph import multi_graph_manager

    added = []
    for graph_id, graph in multi_graph_manager.graphs.items():
        # The shelf is a graph of LinkNodes, not a project: it has no place in a
        # list of things you can draw.
        if is_shelf_member(graph):
            continue
        if any(row.name == graph_id for row in em_tools.graphml_files):
            continue
        row = em_tools.graphml_files.add()
        row.name = graph_id
        row.graphml_path = ""
        if hasattr(row, "file_format"):
            row.file_format = "EMJSON"
        attrs = getattr(graph, "attributes", {}) or {}
        if "graph_code" in attrs and hasattr(row, "graph_code"):
            row.graph_code = attrs["graph_code"]
        added.append(graph_id)

    # An index pointing nowhere is the same failure as an empty list, and a
    # session that had rows already may be pointing at one of them — so only
    # move it when it is not currently on something that resolves.
    index = getattr(em_tools, "active_file_index", -1)
    rows = em_tools.graphml_files
    if not (0 <= index < len(rows) and get_graph(rows[index].name) is not None):
        for i, row in enumerate(rows):
            if get_graph(row.name) is not None:
                em_tools.active_file_index = i
                break
    return added


def _count_for_active_row(context, graph) -> None:
    """Refresh the row's cached counters (US/USV · Epochs · Properties · Documents).

    The panel reads those numbers off the row, not off the graph, and the
    importer fills them at import. Without this the tree lists the graph and its
    units and then heads the panel with four zeros — which is the same wrong
    answer the empty tree gave, in smaller type.
    """
    em_tools = getattr(context.scene, "em_tools", None)
    if em_tools is None:
        return
    index = getattr(em_tools, "active_file_index", -1)
    if not (0 <= index < len(em_tools.graphml_files)):
        return
    try:
        from ..populate_lists import update_graph_statistics
        update_graph_statistics(context, graph, em_tools.graphml_files[index])
    except Exception as exc:  # noqa: BLE001 — a count is not worth an adoption
        print(f"[sync] could not refresh the graph statistics: {exc}")


def _adoption_note(graph, listed: list, overwritten: int, warnings: int) -> str:
    """What the adoption actually did, in the words of what changed.

    The old message said "N node(s) merged", where N counted only the nodes
    OVERWRITTEN by UUID — so a room whose six units were all new reported
    "0 node(s) merged" over a successful adoption. It was true and it read as a
    failure, which is the worst kind of accurate.
    """
    what = []
    if graph is not None:
        name = getattr(graph, "graph_id", "?")
        what.append(f"«{name}»: {len(getattr(graph, 'nodes', []) or [])} node(s), "
                    f"{len(getattr(graph, 'edges', []) or [])} edge(s)")
    if listed:
        what.append(f"{len(listed)} graph(s) added to the EM Data Tree")
    what.append(f"{overwritten} node(s) overwritten by UUID")
    what.append(f"{warnings} warning(s)")
    return "adopted the room's document — " + " · ".join(what)


def _adopt_snapshot(doc: dict, context) -> str:
    """Take the room's document into this Blender — or say why we did not.

    A room snapshot is a **container** (several graphs + the shelf), and it is
    merged, never substituted: merging is the offline "integrate later" and the
    less expensive mistake, while replacing a populated session would throw away
    work that is only in this .blend.

    **The geometry.** Adoption reads the document; the models the document
    describes are fetched by their own act — `em.materialise_geometry`, the
    consuming half of DP-76 (`materialise.py`). It is an action and not a
    consequence, for the same reason the command channel is opt-in: downloading
    somebody's meshes into your file is more than reading their graph. Whoever
    wants it at adoption time says so once, with
    `Scene.em_materialise_on_adopt`, and this function honours it — with the
    same rules as the manual action (resident only, embargo skipped with a
    reason, content-addressed so it never duplicates).

    **Declared limit.** The merge lands in the multigraph manager, which is what
    the lists and the 3D scene are drawn from; a session that already holds
    graphs therefore has to be repopulated.
    """
    import json as _json
    import tempfile

    if not isinstance(doc, dict) or not doc:
        return "the room sent no document"
    path = None
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".em.json", delete=False,
                                         encoding="utf-8") as handle:
            _json.dump(doc, handle, ensure_ascii=False)
            path = handle.name
        from ..emjson_support import merge_container_from_emjson
        report, warnings = merge_container_from_emjson(path)
        # `merged_nodes` is a COUNT in the library we run against (measured:
        # s3dgraphy 1.6.0.dev14 returns 14, an int) and was a list of ids in
        # earlier ones. `len()` on the int raised inside this try, so the whole
        # adoption reported "could not adopt the room's document: object of type
        # 'int' has no len()" — after the merge had already succeeded. Read both
        # shapes: a number in a message is not worth failing an adoption for.
        merged = getattr(report, "merged_nodes", 0)
        overwritten = merged if isinstance(merged, int) else len(merged or [])
        # THE MERGE IS NOT THE ARRIVAL. `merge_container_from_emjson` writes into
        # the multigraph manager; the EM Data Tree is drawn from
        # `em_tools.graphml_files`, and `is_graph_available` asks THAT list. In a
        # Blender that was empty the list has no rows, so the check said no, the
        # repopulate never ran, and the panel offered "Add graph" over six units
        # that were already loaded. Registering the graphs is what makes the
        # adoption visible — and it is the same act the importer performs.
        listed = _list_adopted_graphs(context)
        ok, graph = is_graph_available(context)
        if ok:
            _repopulate(context, graph)
            _count_for_active_row(context, graph)
            _redraw()
        note = _adoption_note(graph if ok else None, listed, overwritten,
                              len(warnings))
        # …and, only if somebody asked for it, the geometry (DP-76). A failure
        # here must not undo an adoption that worked: the document IS adopted,
        # and the meshes are a second act reported beside it.
        if ok and getattr(context.scene, "em_materialise_on_adopt", False):
            try:
                from .materialise import materialise, summarise
                note += " · geometry: " + summarise(materialise(graph))
            except Exception as exc:  # noqa: BLE001 — said, never fatal
                note += f" · geometry not materialised: {exc}"
        return note
    except Exception as exc:  # noqa: BLE001 — a failed adoption must be SAID
        return f"could not adopt the room's document: {exc}"
    finally:
        if path:
            try:
                import os
                os.remove(path)
            except OSError:
                pass


def join_room(context, base_url: str, room_id: str, token: str,
              adopt: bool = True) -> dict:
    """Enter a room: connect, read the arrival, optionally adopt the document.

    Returns `{ok, message, plan, …}`. The token is handed to `room.py`, which
    keeps it in memory for this session and never writes it anywhere.
    """
    from . import room as room_cfg
    from .room_session import SESSION

    room_cfg.set_room(base_url, room_id, token)
    try:
        arrival = SESSION.join(since=SESSION.last_applied)
    except Exception as exc:  # noqa: BLE001 — the reason belongs to the user
        return {"ok": False, "message": str(exc)}
    _schedule_drain()
    SESSION.client._on_message = lambda _raw: _schedule_drain()

    note = ""
    if adopt and arrival.get("snapshot"):
        note = _adopt_snapshot(
            (arrival["snapshot"].get("payload") or {}).get("doc") or {}, context)
    plan = arrival.get("plan")
    if plan == "resync" and SESSION.last_applied:
        # a REBASE, not a first arrival: the two look the same to `plan_rejoin`
        # (no base and an old base both mean "take the document"), but only one
        # of them is worth telling the user about
        # the room has compacted past our base: replaying our history would
        # re-assert facts that were already settled and forgotten
        note = (note + " · " if note else "") + \
            "re-synced from the room's document (our base was older than its " \
            "compaction point)"
    return {"ok": True, "plan": plan, "room": SESSION.room_id,
            "members": len(SESSION.members), "host": SESSION.host_tool,
            "message": note or "joined"}


def leave_room() -> None:
    from . import room as room_cfg
    from .room_session import SESSION

    SESSION.leave()
    room_cfg.forget_token()      # the credential goes when the membership does


class EM_OT_server_probe(bpy.types.Operator):
    """Ask the address in the field what it is — before trying to join it.

    A URL somebody typed is a hope; `/v1/health` turns it into a fact, and the
    failures are the useful half (refused, no such host, a TLS the OS does not
    trust). Reported, never raised: "check this address" must be a thing you can
    do twice."""

    bl_idname = "em.server_probe"
    bl_label = "Probe this server"

    def execute(self, context):
        from . import servers

        answer = servers.probe(getattr(context.scene, "em_room_url", ""))
        if answer.get("ok"):
            self.report({"INFO"},
                        f"{answer['url']} — {answer.get('service')} "
                        f"{answer.get('version')} · auth: {answer.get('auth')} · "
                        f"{answer.get('rooms')} room(s)")
            servers.remember(answer["url"], answer.get("service") or "")
        else:
            self.report({"WARNING"},
                        f"{answer.get('url')}: {answer.get('error')}")
        return {"FINISHED"}


class EM_OT_server_discover(bpy.types.Operator):
    """Find an StratiGraph Server on this network — by asking, not by browsing.

    Blender's Python has no `zeroconf`, so there is no mDNS browsing here and
    none is simulated. What this does is probe the addresses that are worth
    trying (this machine, this machine's Bonjour name) and remember whatever
    answers. The other Mac is reached as `<name>.local`, which the operating
    system resolves without any library."""

    bl_idname = "em.server_discover"
    bl_label = "Find a server"

    def execute(self, context):
        from . import servers

        result = servers.discover()
        for found in result["found"]:
            servers.remember(found["url"], found.get("service") or "")
        if result["found"]:
            context.scene.em_room_url = result["found"][0]["url"]
            self.report({"INFO"},
                        f"found {len(result['found'])}: "
                        + ", ".join(f["url"] for f in result["found"]))
        else:
            self.report({"WARNING"},
                        "nothing answered on this machine or its Bonjour name — "
                        "type the address of the server you were given")
        if result.get("browsing_unavailable"):
            print("[em] " + result["browsing_unavailable"])
        return {"FINISHED"}


class EM_OT_server_use(bpy.types.Operator):
    """Put a saved server in the field."""

    bl_idname = "em.server_use"
    bl_label = "Use this server"

    url: bpy.props.StringProperty(default="")  # type: ignore

    def execute(self, context):
        context.scene.em_room_url = self.url
        return {"FINISHED"}


class EM_OT_server_forget(bpy.types.Operator):
    """Take a server off the saved list. The list is this installation's, not
    the .blend's, so this does not touch anybody's project."""

    bl_idname = "em.server_forget"
    bl_label = "Forget this server"

    url: bpy.props.StringProperty(default="")  # type: ignore

    def execute(self, context):
        from . import servers

        servers.forget(self.url)
        return {"FINISHED"}


class EM_OT_room_join(bpy.types.Operator):
    bl_idname = "em.room_join"
    bl_label = "Join / leave an EM room"
    bl_description = ("Connect this Blender to an StratiGraph Server room: adopt its "
                      "document, send and receive edits, publish models into "
                      "its store")

    token: bpy.props.StringProperty(
        name="Token", default="", subtype="PASSWORD",
        description=("Access token for this room. Kept in memory for this "
                     "session only — never written to the .blend or to disk"))
    adopt: bpy.props.BoolProperty(
        name="Adopt the room's document", default=True,
        description=("Merge what the room holds into this session (additive — "
                     "nothing here is replaced)"))

    def invoke(self, context, event):
        from .room_session import SESSION
        if SESSION.joined:
            return self.execute(context)
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        from .room_session import SESSION
        if SESSION.joined:
            leave_room()
            self.report({"INFO"}, "left the room (token forgotten)")
            return {"FINISHED"}
        base = str(getattr(context.scene, "em_room_url", "") or "").strip()
        room_id = str(getattr(context.scene, "em_room_id", "") or "").strip()
        if not base or not room_id:
            self.report({"ERROR"}, "set the room address and id first")
            return {"CANCELLED"}
        result = join_room(context, base, room_id, self.token, adopt=self.adopt)
        self.token = ""          # not even in the operator's own memory
        if not result["ok"]:
            self.report({"ERROR"}, result["message"])
            return {"CANCELLED"}
        self.report({"INFO"}, f"room {result['room']}: {result['message']}")
        return {"FINISHED"}


class EM_OT_room_open_link(bpy.types.Operator):
    """Open a room from a HANDOFF LINK — the fourth consumer of one contract.

    `stratigraph://open?server=<addr>&room=<id>`, produced by the room browser on
    a StratiGraph Server (and by the Catalog for a study). It kills the manual
    configuration: no address to type, no room name, and above all no token to
    paste — the link carries a PLACE and never a permission, and this signs in
    against that server itself (`handoff.py`, PKCE, token in memory).

    **Nothing new is built here.** The link supplies `{server, room}`, the
    sign-in supplies the token, and `join_room` does exactly what it always did.

    The manual fields stay, and are the declared fallback: a node in a trench with
    no browser signs in with neither this nor a realm, and taking that away to
    make a point would break the honest case.
    """

    bl_idname = "em.room_open_link"
    bl_label = "Open room from link"
    bl_description = ("Paste a stratigraph:// handoff link: EMtools reads the "
                      "server and the room from it, signs you in, and joins — "
                      "no address, no room name, no token to type")

    link: bpy.props.StringProperty(
        name="Link", default="",
        description="stratigraph://open?server=…&room=… (it carries no token)")
    adopt: bpy.props.BoolProperty(
        name="Adopt the room's document", default=True,
        description=("Merge what the room holds into this session (additive — "
                     "nothing here is replaced)"))

    def invoke(self, context, event):
        if not self.link:
            # a link is usually on the clipboard: that is how it arrived
            try:
                pasted = str(context.window_manager.clipboard or "").strip()
            except Exception:  # noqa: BLE001 — no clipboard on some builds
                pasted = ""
            if pasted.startswith("stratigraph://"):
                self.link = pasted
        return context.window_manager.invoke_props_dialog(self, width=520)

    def execute(self, context):
        from . import handoff

        try:
            where = handoff.resolve(self.link)
        except handoff.HandoffError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        except Exception as exc:  # noqa: BLE001 — the network, the realm
            self.report({"ERROR"}, f"sign-in did not complete: {exc}")
            return {"CANCELLED"}

        # …and the panel now SHOWS where we are, so the fallback fields and the
        # live session never disagree about which room this is
        context.scene.em_room_url = where["server"]
        context.scene.em_room_id = where["room"]
        token = where.get("token") or ""
        if not token:
            # a node running open: not an error, but SAID — otherwise a working
            # laptop is indistinguishable from a token flow that never ran
            self.report({"INFO"},
                        f"{where['server']} has no sign-in configured "
                        f"(running open) — joining without a token")
        result = join_room(context, where["server"], where["room"], token,
                           adopt=self.adopt)
        self.link = ""            # not even in the operator's own memory
        if not result["ok"]:
            self.report({"ERROR"}, result["message"])
            return {"CANCELLED"}
        self.report({"INFO"}, f"room {result['room']}: {result['message']}")
        return {"FINISHED"}


class EM_OT_sync_toggle(bpy.types.Operator):
    bl_idname = "em.sync_toggle"
    bl_label = "Toggle EMStudio Sync"
    bl_description = "Start/stop the WebSocket server EMStudio connects to for live selection sync"

    def execute(self, context):
        if is_running():
            _stop()
            self.report({"INFO"}, "EMStudio sync stopped")
        else:
            port = int(getattr(context.scene, "em_sync_port", 8788))
            try:
                _start(port)
            except OSError as exc:
                self.report({"ERROR"}, f"Could not start sync server on {port}: {exc}")
                return {"CANCELLED"}
            self.report({"INFO"}, f"EMStudio sync listening on ws://localhost:{port}")
        return {"FINISHED"}


def register():
    if not hasattr(bpy.types.Scene, "em_sync_direction"):
        bpy.types.Scene.em_sync_direction = bpy.props.EnumProperty(
            name="Sync",
            items=SYNC_DIRECTIONS,
            default="both",
            description=(
                "What this side does on the live channel. Alone on two screens: "
                "Both. Somebody else working at the same time: Off, or one "
                "direction"))
    if not hasattr(bpy.types.Scene, "em_accept_commands"):
        bpy.types.Scene.em_accept_commands = bpy.props.BoolProperty(
            name="Accept commands from EMStudio",
            default=False,
            description=(
                "Let EMStudio act on THIS scene (model a proxy, import a "
                "geometry). Off by default: a command changes your scene, which "
                "is more than mirroring a selection"),
            update=_on_accept_commands_changed)
    if not hasattr(bpy.types.Scene, "em_sync_port"):
        bpy.types.Scene.em_sync_port = bpy.props.IntProperty(
            name="Sync Port", default=8788, min=1024, max=65535,
            description="WebSocket port EMStudio connects to")
    # P4.4 · the room. The address and the id are saved with the project (they
    # are not secrets and re-typing them every session is friction); the TOKEN
    # is not a property at all — it lives in memory in `room.py`, because a
    # credential saved in a .blend travels with every copy of that .blend.
    if not hasattr(bpy.types.Scene, "em_room_url"):
        bpy.types.Scene.em_room_url = bpy.props.StringProperty(
            name="Room server", default="",
            description="Address of the StratiGraph Server holding the room "
                        "(e.g. https://em.example.org)")
    if not hasattr(bpy.types.Scene, "em_room_id"):
        bpy.types.Scene.em_room_id = bpy.props.StringProperty(
            name="Room", default="",
            description="Which room on that server")
    bpy.utils.register_class(EM_OT_sync_toggle)
    bpy.utils.register_class(EM_OT_room_join)
    bpy.utils.register_class(EM_OT_room_open_link)
    bpy.utils.register_class(EM_OT_server_probe)
    bpy.utils.register_class(EM_OT_server_discover)
    bpy.utils.register_class(EM_OT_server_use)
    bpy.utils.register_class(EM_OT_server_forget)


def unregister():
    _stop()
    try:
        leave_room()
    except Exception:  # noqa: BLE001 — unregistering must not fail on a socket
        pass
    for cls in (EM_OT_server_forget, EM_OT_server_use, EM_OT_server_discover,
                EM_OT_server_probe):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:  # noqa: BLE001 — unregistering must not fail
            pass
    bpy.utils.unregister_class(EM_OT_room_open_link)
    bpy.utils.unregister_class(EM_OT_room_join)
    bpy.utils.unregister_class(EM_OT_sync_toggle)
    if hasattr(bpy.types.Scene, "em_room_url"):
        del bpy.types.Scene.em_room_url
    if hasattr(bpy.types.Scene, "em_room_id"):
        del bpy.types.Scene.em_room_id
    if hasattr(bpy.types.Scene, "em_sync_port"):
        del bpy.types.Scene.em_sync_port
    if hasattr(bpy.types.Scene, "em_sync_direction"):
        del bpy.types.Scene.em_sync_direction
    if hasattr(bpy.types.Scene, "em_accept_commands"):
        del bpy.types.Scene.em_accept_commands
