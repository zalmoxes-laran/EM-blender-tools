"""Sync Manager — live selection bridge EMtools ⇄ EMStudio (ADR-002 phase 1).

EMtools is the HOST: it runs a WebSocket server (``sync_bridge.ws_server``)
that EMStudio connects to as a client, and exchanges only the ephemeral
selection channel (no graph mutation → no data ownership concern). Clicking
an EM proxy in Blender highlights the node in EMStudio and vice versa.

Modules:
- operators : server lifecycle, the bpy.app.timers main-thread pump, toggle op
- panel     : EM-tab panel (start/stop, status, port)
"""

from __future__ import annotations

from . import operators, panel


def register():
    operators.register()
    panel.register()


def unregister():
    panel.unregister()
    operators.unregister()
