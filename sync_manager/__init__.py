"""Sync Manager — live selection bridge EMtools ⇄ EMStudio (ADR-002 phase 1).

EMtools is the HOST: it runs a WebSocket server (``sync_bridge.ws_server``)
that EMStudio connects to as a client, and exchanges only the ephemeral
selection channel (no graph mutation → no data ownership concern). Clicking
an EM proxy in Blender highlights the node in EMStudio and vice versa.

Modules:
- operators   : server lifecycle, the bpy.app.timers main-thread pump, toggle op
- panel       : EM-tab panel (start/stop, status, port)
- materialise : DP-76's consuming half — the room's geometry into this scene
- rooms_list  : R1 · the node's rooms (`GET /v1/rooms`), grouped; the id rule
- rooms_ui    : R1 · the room list in the panel: cache, UIList, refresh/pick/new
- backups     : the `.blend` safety archive — opaque snapshots into the room's
                store, on demand (NOT versioning of the shared data, which is
                content-addressed already)
"""

from __future__ import annotations

from . import backups, materialise, operators, panel, rooms_ui


def register():
    operators.register()
    materialise.register()
    backups.register()
    rooms_ui.register()
    panel.register()


def unregister():
    panel.unregister()
    rooms_ui.unregister()
    backups.unregister()
    materialise.unregister()
    operators.unregister()
