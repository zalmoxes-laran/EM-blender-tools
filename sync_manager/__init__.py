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
- scene_check : S1 · the scene as a cache of the graph: here / missing (fetched) /
                changed / external / only here (marked, never uploaded)
- inventory   : P3 · the graph's resources in four groups (pure, no bpy)
- asset_upload: P3 · THE upload function (HEAD, streamed PUT, resumable door)
- bring       : P3 · «Bring into a room…»: room, inventory, uploads, models, seed, enter
- asset_versions: A1–A3 · an asset and its versions: one library .blend per
                asset, ONE object whose mesh changes («LOD ▸»), the cache checked
                mesh by mesh
- scene_package: B1 · the .blend as a starter package, a room attachment
- backups     : the `.blend` safety archive — opaque snapshots into the room's
                store, on demand (NOT versioning of the shared data, which is
                content-addressed already)
"""

from __future__ import annotations

from . import (asset_versions, backups, bring, file_states, materialise, node_choice,
               operators, panel, rooms_ui, scene_check, scene_package)


def register():
    operators.register()
    materialise.register()
    scene_check.register()
    backups.register()
    rooms_ui.register()
    bring.register()
    asset_versions.register()
    file_states.register()
    node_choice.register()
    scene_package.register()
    panel.register()


def unregister():
    panel.unregister()
    scene_package.unregister()
    node_choice.unregister()
    file_states.unregister()
    asset_versions.unregister()
    bring.unregister()
    rooms_ui.unregister()
    backups.unregister()
    scene_check.unregister()
    materialise.unregister()
    operators.unregister()
