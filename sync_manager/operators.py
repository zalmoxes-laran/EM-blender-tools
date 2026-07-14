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

# msgbus subscription owner (opaque token; clear_by_owner removes the sub).
_msgbus_owner = object()

# One-shot inbound-drain scheduling guard. The flag is cleared at the START of
# every drain, so any message arriving during a drain re-schedules another
# drain — no lost wake-ups; at worst one redundant empty drain.
_drain_lock = threading.Lock()
_drain_scheduled = False


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
    add/delete of nodes and edges (full list repopulate)."""
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
        _repopulate(context, graph)
        _redraw()


def emit_op(op: dict):
    """Emit a local (Blender-side) graph mutation to connected clients
    (ADR-002 phase 2, reverse direction). No-op when the sync server is off.
    `op` is a dict like {"type":"op","op":"update_node","node_id":..,"patch":..}."""
    srv = _server
    if srv is None or not srv.running:
        return
    payload = {"v": 1, "source": _SOURCE}
    payload.update(op)
    try:
        srv.broadcast(json.dumps(payload))
    except Exception as exc:  # noqa: BLE001
        print(f"[sync] emit_op failed: {exc}")


def _send_snapshot(graph):
    """Host → client: send the active graph as an .em.json doc (ADR-002
    snapshot-READ). Triggered by a client's ``request_snapshot`` on connect —
    this is what makes 'sync mode = see Blender's data'."""
    srv = _server
    if srv is None or not srv.running or graph is None:
        return
    try:
        from ..emjson_support import graph_to_emjson_dict
        doc = graph_to_emjson_dict(graph)
    except Exception as exc:  # noqa: BLE001
        print(f"[sync] snapshot build failed: {exc}")
        return
    srv.broadcast(json.dumps(
        {"v": 1, "type": "snapshot", "doc": doc, "source": _SOURCE}))


def _handle_message(raw: str, context, graph, ok: bool):
    """Dispatch one inbound message (main thread)."""
    global _last_active_name, _last_selection
    try:
        msg = json.loads(raw)
    except (ValueError, TypeError):
        return
    if msg.get("source") == _SOURCE:
        return  # our own echo
    mtype = msg.get("type")
    if mtype == "select" and ok and (msg.get("node_id") or msg.get("node_ids")):
        node_ids = msg.get("node_ids")
        active_id = msg.get("node_id")
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
        _apply_op(msg, context, graph)
    elif mtype == "request_snapshot" and ok:
        _send_snapshot(graph)


# --------------------------------------------------------------------------- #
# INBOUND — one-shot drain (scheduled from the server thread)
# --------------------------------------------------------------------------- #

def _drain_inbox():
    """One-shot timer callback (MAIN thread): drain + apply every queued
    message, then unregister (return None)."""
    global _drain_scheduled
    with _drain_lock:
        _drain_scheduled = False  # cleared first: messages arriving now re-arm
    srv = _server
    if srv is None:
        return None
    context = bpy.context
    ok, graph = is_graph_available(context)
    while True:
        try:
            raw = srv.inbox.get_nowait()
        except Exception:
            break
        _handle_message(raw, context, graph, ok)
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
    msg = {"v": 1, "type": "select", "node_id": active_id, "source": _SOURCE}
    if len(sel_ids) > 1:
        msg["node_ids"] = sel_ids
    srv.broadcast(json.dumps(msg))


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
    if not hasattr(bpy.types.Scene, "em_sync_port"):
        bpy.types.Scene.em_sync_port = bpy.props.IntProperty(
            name="Sync Port", default=8788, min=1024, max=65535,
            description="WebSocket port EMStudio connects to")
    bpy.utils.register_class(EM_OT_sync_toggle)


def unregister():
    _stop()
    bpy.utils.unregister_class(EM_OT_sync_toggle)
    if hasattr(bpy.types.Scene, "em_sync_port"):
        del bpy.types.Scene.em_sync_port
