"""EMtools ⇄ EMStudio live-sync — operators + main-thread pump (ADR-002
phase 1: ephemeral selection). EMtools is the HOST: it runs the WebSocket
server (sync_bridge.ws_server) and holds the live s3dgraphy graph; EMStudio
connects as a client.

Two directions, both driven by a single ``bpy.app.timers`` callback on the
MAIN thread (bpy is not thread-safe):
  * inbound  — drain the server's inbox; a peer ``select`` picks + frames the
    matching 3D object (``functions.select_3D_obj``);
  * outbound — poll the active object; when the user selects a different EM
    proxy, broadcast its node id.

The server thread only touches the socket + thread-safe queue/lock; every
Blender API call happens here, in the timer.
"""

from __future__ import annotations

import json

import bpy  # type: ignore

from ..sync_bridge.ws_server import WsServer
from ..functions import is_graph_available, select_3D_obj
from ..operators.addon_prefix_helpers import proxy_name_to_node_name

_SOURCE = "emtools"

# Module-level session state (a single server per Blender instance).
_server: WsServer | None = None
_last_active_name: str | None = None
_POLL_INTERVAL = 0.25


def is_running() -> bool:
    return _server is not None and _server.running


def client_count() -> int:
    return _server.client_count() if _server else 0


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
    """Best-effort 'view selected' in the first 3D viewport (timers have no
    region context of their own)."""
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


def _apply_incoming(node_id: str, context, graph) -> bool:
    """Select + frame the object for an incoming node id. Returns True if a
    matching object was selected."""
    finder = getattr(graph, "find_node_by_id", None)
    node = finder(node_id) if callable(finder) else None
    if not node:
        return False
    select_3D_obj(node.name, context=context, graph=graph)
    _frame_selected()
    return True


def _pump():
    """Timer callback (main thread). Returns the next interval, or None to
    stop when the server is gone."""
    global _last_active_name
    srv = _server
    if srv is None or not srv.running:
        return None

    context = bpy.context
    ok, graph = is_graph_available(context)

    # --- inbound: peer selections → pick the 3D object ---------------------
    while True:
        try:
            raw = srv.inbox.get_nowait()
        except Exception:
            break
        try:
            msg = json.loads(raw)
        except (ValueError, TypeError):
            continue
        if msg.get("source") == _SOURCE:
            continue  # our own echo
        if msg.get("type") == "select" and msg.get("node_id") and ok:
            if _apply_incoming(msg["node_id"], context, graph):
                active = getattr(context.view_layer.objects, "active", None)
                # suppress the echo the outbound poll would otherwise send
                _last_active_name = active.name if active else _last_active_name

    # --- outbound: local selection → broadcast the node id -----------------
    active = getattr(context.view_layer.objects, "active", None)
    name = active.name if (active and active.select_get()) else None
    if name != _last_active_name:
        _last_active_name = name
        if name and ok:
            node_id = _node_id_for_object(active, graph)
            if node_id:
                srv.broadcast(json.dumps(
                    {"v": 1, "type": "select", "node_id": node_id, "source": _SOURCE}))

    return _POLL_INTERVAL


def _start(port: int):
    global _server, _last_active_name
    if is_running():
        return
    _server = WsServer(port=port)
    _server.start()
    _last_active_name = None
    if not bpy.app.timers.is_registered(_pump):
        bpy.app.timers.register(_pump, first_interval=_POLL_INTERVAL)


def _stop():
    global _server
    if bpy.app.timers.is_registered(_pump):
        try:
            bpy.app.timers.unregister(_pump)
        except ValueError:
            pass
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
