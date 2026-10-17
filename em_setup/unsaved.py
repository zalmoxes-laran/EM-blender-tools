"""MICRO salva (17 Oct 2026) · the unsaved mark on the em.json, in Blender.

What changed is measured by ``emjson_state`` (no bpy): this module only feeds
it the scene — the graphs of each em.json of the tree and the RM containers —
on a timer, never in a panel's draw (a fingerprint of Templu Mare takes
~80 ms). The panel reads :func:`reasons`; saving the .blend while an em.json
is behind the scene says so in the status bar. A warning only: nothing here
ever writes the em.json.
"""

from __future__ import annotations

import bpy  # type: ignore
from bpy.app.handlers import persistent  # type: ignore

from .. import emjson_state, graph_origins

#: seconds between two measures while an em.json is open
INTERVAL = 2.5
#: seconds the status bar keeps the warning after a .blend save
STATUS_SECONDS = 20.0

#: origin path → why the file is behind the scene (what the panel reads)
_NOW: dict = {}


def _abspath(path: str) -> str:
    return bpy.path.abspath(path)


def container_rows(scene) -> list:
    return [(c.label or c.doc_name or "", c.doc_node_id or "",
             c.group_node_id or "", tuple(e.name for e in c.mesh_names))
            for c in getattr(scene, "rm_containers", ())]


def _graphs_of(rows, origin) -> dict:
    from s3dgraphy import get_graph
    out = {}
    for gid in graph_origins.members_of(rows, origin, abspath=_abspath):
        graph = get_graph(gid)
        if graph is not None and getattr(graph, "nodes", None):
            out[gid] = graph
    return out


def mark(context, path: str, *, saved: bool = True) -> None:
    """The em.json at ``path`` now holds what the scene holds: after a load
    (``saved=False``) or a save. Never fails the load or the save."""
    try:
        scene = context.scene
        rows = list(scene.em_tools.graphml_files)
        origin = graph_origins.file_origin(path, abspath=_abspath)
        emjson_state.mark_saved(origin.path, _graphs_of(rows, origin),
                                container_rows(scene), saved=saved)
        _NOW[origin.path] = emjson_state.unsaved(
            origin.path, _graphs_of(rows, origin), container_rows(scene))
    except Exception as exc:  # noqa: BLE001
        print(f"[em.json unsaved] mark skipped: {exc}")


def measure(scene) -> bool:
    """Measure every em.json of the scene's tree. → whether anything moved."""
    em_tools = getattr(scene, "em_tools", None)
    if em_tools is None:
        return False
    rows = list(em_tools.graphml_files)
    moved = False
    seen = set()
    for origin, _indices in graph_origins.tree(rows, abspath=_abspath):
        if not origin.is_emjson or not emjson_state.known(origin.path):
            continue
        seen.add(origin.path)
        said = emjson_state.unsaved(origin.path, _graphs_of(rows, origin),
                                    container_rows(scene))
        if said != _NOW.get(origin.path):
            _NOW[origin.path] = said
            moved = True
    for path in [p for p in _NOW if p not in seen]:
        del _NOW[path]
        moved = True
    return moved


def reasons(origin) -> list:
    """Why ``origin``'s em.json is behind the scene (empty: it is not)."""
    return list(_NOW.get(getattr(origin, "path", ""), ()) or ())


def _redraw() -> None:
    for window in getattr(bpy.context.window_manager, "windows", ()):
        for area in window.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()


def _tick():
    try:
        if measure(bpy.context.scene):
            _redraw()
    except Exception as exc:  # noqa: BLE001 — a timer that raises is dropped by Blender
        print(f"[em.json unsaved] measure skipped: {exc}")
    return INTERVAL


def warning_line(scene) -> str:
    """The status bar line when the .blend is saved and an em.json is not."""
    behind = [p for p, said in _NOW.items() if said]
    if not behind:
        return ""
    import os
    names = ", ".join(os.path.basename(p) for p in behind)
    return (f"{names}: the em.json has unsaved changes — EM Data Tree › "
            f"Save em.json (the .blend does not carry the graph)")


def _clear_status():
    for window in getattr(bpy.context.window_manager, "windows", ()):
        try:
            window.workspace.status_text_set(None)
        except Exception:  # noqa: BLE001
            pass
    return None


@persistent
def on_blend_saved(*_args):
    """Saving the .blend: if an em.json is behind the scene, one line in the
    status bar (and the console). Only a warning — never a save."""
    try:
        scene = bpy.context.scene
        measure(scene)
        line = warning_line(scene)
    except Exception as exc:  # noqa: BLE001
        print(f"[em.json unsaved] check on .blend save skipped: {exc}")
        return
    if not line:
        return
    try:
        from ..functions import em_log
        em_log(line, "WARNING")
    except Exception:  # noqa: BLE001
        print(f"[EM WARNING] {line}")
    if bpy.app.background:
        return
    for window in getattr(bpy.context.window_manager, "windows", ()):
        try:
            window.workspace.status_text_set(line)
        except Exception:  # noqa: BLE001
            pass
    if bpy.app.timers.is_registered(_clear_status):
        bpy.app.timers.unregister(_clear_status)
    bpy.app.timers.register(_clear_status, first_interval=STATUS_SECONDS)


@persistent
def on_blend_loaded(*_args):
    """A new .blend: what this session knew of the em.json files is not its."""
    _NOW.clear()
    emjson_state._SAVED.clear()


def register():
    if not bpy.app.timers.is_registered(_tick):
        bpy.app.timers.register(_tick, first_interval=INTERVAL, persistent=True)
    if on_blend_saved not in bpy.app.handlers.save_post:
        bpy.app.handlers.save_post.append(on_blend_saved)
    if on_blend_loaded not in bpy.app.handlers.load_pre:
        bpy.app.handlers.load_pre.append(on_blend_loaded)


def unregister():
    if bpy.app.timers.is_registered(_tick):
        bpy.app.timers.unregister(_tick)
    if bpy.app.timers.is_registered(_clear_status):
        bpy.app.timers.unregister(_clear_status)
    for handlers, fn in ((bpy.app.handlers.save_post, on_blend_saved),
                         (bpy.app.handlers.load_pre, on_blend_loaded)):
        if fn in handlers:
            handlers.remove(fn)
