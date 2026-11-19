"""The Blender half of EM Tools' ``em`` host (MICRO-PL19, W16): what needs ``bpy``.

* :func:`install` — at registration, EM Tools becomes the host of ``em`` in
  this Blender (``em.host.install``): ``from s3dgraphy import em`` in the Python
  console, in a script, in a plugin, reads the ACTIVE graph of EM Setup and
  writes through the seam as one step of EM Tools' Log;
* :class:`BlenderApp` — ``em.app`` in Blender (SPEC-plugin §2.4): the selection
  (objects ↔ nodes, the way the selection bridge with EMStudio maps them), the
  3D view's camera in the scene's frame, ``frame``, ``notify`` (status bar,
  Log, console), ``commands.run`` for the plugins' commands; ``view`` and
  ``pick`` do not exist here and say so (``em.NotAvailable``);
* after every act: the lists of EM Tools rebuilt (or the field mirrored), the
  same operations sent to a room or to EMStudio (``sync_manager.emit_op``),
  the panels redrawn;
* the events Blender can tell: ``selection-changed`` (depsgraph, only when
  someone listens), ``document-opened``/``document-closed`` (the active graph
  changed), ``document-saved`` (an em.json written, ``em_setup.unsaved``),
  ``locale-changed``;
* the plugins with ``hosts = blender``: :func:`sync_plugins` loads them (the
  development folder too, when EM ▸ Utils ▸ Experimental is on — D-7/W15a).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import bpy  # type: ignore

from . import core

#: the host installed by this add-on (None: an older s3dgraphy, or not registered)
HOST: Optional[core.BlenderHost] = None
#: what notify() said, newest first (the panel's Log shows it with the steps)
NOTICES: List[Dict[str, str]] = []

_last_selection: Optional[frozenset] = None
_last_document: Optional[str] = None
_last_locale: Optional[str] = None


# ── what the host reads ─────────────────────────────────────────────────────

def _context():
    return bpy.context


def active_graph():
    try:
        from ..community_packages.operators import active_graph as _active
        return _active(_context())
    except Exception:  # noqa: BLE001
        return None


def active_overlay():
    try:
        from ..community_packages.operators import active_state
        return active_state(_context())[0]
    except Exception:  # noqa: BLE001
        return None


def author() -> Optional[str]:
    """The room's identity when in a room, else the iD of the Preferences
    (declared, not verified) — the same answer a stamp made in Blender gives."""
    try:
        from ..birth_stamp import current_operator
        op = current_operator()
        return str(op.get("id")) if op and op.get("id") else None
    except Exception:  # noqa: BLE001
        return None


def language() -> str:
    try:
        from ..vocabulary_labels import blender_lang
        return blender_lang(getattr(bpy.app.translations, "locale", ""))
    except Exception:  # noqa: BLE001
        return "en"


def addon_version() -> Optional[str]:
    try:
        from ..sync_manager.connector import addon_version as _v
        return _v()
    except Exception:  # noqa: BLE001
        return None


def experimental() -> bool:
    try:
        return bool(_context().scene.em_tools.experimental_features)
    except Exception:  # noqa: BLE001
        return False


# ── objects and nodes ───────────────────────────────────────────────────────

def node_ids_of_objects(objects, graph) -> List[str]:
    from ..sync_manager.operators import _node_id_for_object
    out: List[str] = []
    for obj in objects:
        nid = _node_id_for_object(obj, graph)
        if nid and nid not in out:
            out.append(nid)
    return out


def selected_node_ids(context=None) -> List[str]:
    """The selected objects as nodes of the active graph, the active one first."""
    context = context or _context()
    graph = active_graph()
    if graph is None:
        return []
    objs = list(getattr(context, "selected_objects", None) or
                [o for o in bpy.data.objects if o.select_get()])
    active = getattr(getattr(context, "view_layer", None), "objects", None)
    active = getattr(active, "active", None)
    if active is not None and active in objs:
        objs.remove(active)
        objs.insert(0, active)
    return node_ids_of_objects(objs, graph)


def objects_of_nodes(ids, graph) -> list:
    """The objects that stand for these nodes: a proxy by its name (with the
    graph's prefix), the inventory's objects by the ids they carry."""
    from ..operators.addon_prefix_helpers import node_name_to_proxy_name
    from ..sync_manager.operators import _objects_for_ids
    out = []
    for nid in ids:
        node = graph.find_node_by_id(nid)
        if node is None:
            continue
        obj = bpy.data.objects.get(node_name_to_proxy_name(node.name, context=_context(), graph=graph))
        if obj is not None and obj not in out:
            out.append(obj)
    for obj in _objects_for_ids(list(ids)):
        if obj not in out:
            out.append(obj)
    return out


def _view3d():
    """``(area, region, region_3d)`` of the first 3D view, or None (headless)."""
    wm = getattr(bpy.context, "window_manager", None)
    for win in getattr(wm, "windows", []) or []:
        for area in win.screen.areas:
            if area.type == "VIEW_3D":
                region = next((r for r in area.regions if r.type == "WINDOW"), None)
                space = area.spaces.active
                if region is not None and getattr(space, "region_3d", None) is not None:
                    return win, area, region, space.region_3d
    return None


# ── em.app ──────────────────────────────────────────────────────────────────

class BlenderApp:
    """``em.app`` in EM Tools."""

    def _em(self):
        return core.em_module()

    def _no(self, feature: str):
        from s3dgraphy.em.errors import NotAvailable
        raise NotAvailable(feature, core.HOST)

    def selection(self) -> List[str]:
        return selected_node_ids()

    def select(self, ids) -> None:
        ids = [str(getattr(i, "id", i)) for i in ids]
        graph = active_graph()
        objs = objects_of_nodes(ids, graph) if graph is not None else []
        for o in bpy.context.view_layer.objects:
            if o.select_get():
                o.select_set(False)
        for o in objs:
            try:
                o.hide_set(False)
                o.select_set(True)
            except Exception:  # noqa: BLE001 — an object outside the view layer
                pass
        if objs:
            try:
                bpy.context.view_layer.objects.active = objs[0]
            except Exception:  # noqa: BLE001
                pass

    def view(self, name: str) -> None:
        self._no("view")                     # SPEC §2.4: no windows to open in Blender

    def notify(self, msg: str, level: str = "info") -> None:
        import time
        level = level if level in ("info", "warning", "error") else "info"
        NOTICES.insert(0, {"when": time.strftime("%H:%M:%S"), "level": level, "text": str(msg)})
        del NOTICES[core.LOG_MAX:]
        print(f"[em] {level}: {msg}")
        try:
            ws = bpy.context.workspace
            if ws is not None:
                ws.status_text_set(f"EM · {msg}")

                def _clear():
                    try:
                        ws.status_text_set(None)
                    except Exception:  # noqa: BLE001
                        pass
                    return None
                bpy.app.timers.register(_clear, first_interval=8.0)
        except Exception:  # noqa: BLE001 — headless: the console and the Log say it
            pass
        redraw()

    def run_command(self, command_id: str, **slots: Any) -> Any:
        """``<plugin>/<command>`` — a plugin's command through the contract,
        with this session's author. Its value (or an exporter's file) back; a
        refusal raises ``em.Refused`` with the contract's words."""
        em = self._em()
        pid, _, cid = str(command_id).partition("/")
        if not cid:
            self._no(f"commands.run({command_id})")
        res = em.plugins.invoke(pid, cid, dict(slots), author=HOST.author() if HOST else None)
        if not res.ok:
            from s3dgraphy.em.errors import Refused
            raise Refused(res, (res.data or {}).get("messages"))
        data = res.data or {}
        return data.get("file") or data.get("value")

    def camera(self) -> Dict[str, Any]:
        v = _view3d()
        if v is None:
            self._no("space.camera")
        from mathutils import Vector  # type: ignore
        r3d = v[3]
        forward = r3d.view_rotation @ Vector((0.0, 0.0, -1.0))
        return core.camera_state(tuple(r3d.view_location), tuple(forward), float(r3d.view_distance))

    def set_camera(self, camera: Dict[str, Any]) -> None:
        v = _view3d()
        if v is None:
            self._no("space.set_camera")
        from mathutils import Vector  # type: ignore
        target, forward, dist = core.view_of(camera)
        r3d = v[3]
        r3d.view_location = Vector(target)
        r3d.view_rotation = Vector(forward).to_track_quat('-Z', 'Y')
        r3d.view_distance = dist
        v[2].tag_redraw()

    def frame(self, ids) -> None:
        self.select(ids)
        v = _view3d()
        if v is None:
            return
        win, area, region, _ = v
        try:
            with bpy.context.temp_override(window=win, area=area, region=region):
                bpy.ops.view3d.view_selected()
        except Exception:  # noqa: BLE001
            pass

    def pick(self, prompt: str, primitive: str = "point") -> Any:
        # a script cannot wait for a modal tool on Blender's one thread: the
        # points are placed with Proxy Box / the 3D cursor, then read
        self._no("space.pick")

    def __bool__(self) -> bool:
        return True

    def __repr__(self) -> str:
        return "<em.app of blender>"


# ── after an act ────────────────────────────────────────────────────────────

def redraw() -> None:
    try:
        for win in bpy.context.window_manager.windows:
            for area in win.screen.areas:
                area.tag_redraw()
    except Exception:  # noqa: BLE001
        pass


def after_apply(step: core.Step, delta: Any, result: Any) -> None:
    """The lists follow the graph; a room / EMStudio gets the same operations
    (a proposal stays here: it is not in the document until baked)."""
    context = _context()
    graph = active_graph()
    try:
        from ..sync_manager import operators as sync
    except Exception:  # noqa: BLE001
        sync = None
    if sync is not None and graph is not None:
        if core.structural(delta):
            sync._repopulate(context, graph)
        else:
            for op in delta.ops:
                node = graph.find_node_by_id(str(op.get("node_id") or ""))
                if node is not None:
                    sync._reflect_in_em_list(context, node)
        if not step.volatile:
            for op in core.wire_ops(delta):
                try:
                    sync.emit_op(op)
                except Exception as exc:  # noqa: BLE001 — the act is here; the wire says
                    print(f"[em] not sent: {exc}")
    redraw()


# ── the events Blender can tell ─────────────────────────────────────────────

def _listening(event: str) -> bool:
    try:
        from s3dgraphy.em import events
        return bool(events.listeners(event).get(event))
    except Exception:  # noqa: BLE001
        return False


def track_document() -> None:
    """``document-closed`` / ``document-opened`` when the active graph changed."""
    global _last_document
    graph = active_graph()
    gid = getattr(graph, "graph_id", None) if graph is not None else None
    if gid == _last_document:
        return
    from s3dgraphy.em import events
    if _last_document is not None:
        events.emit("document-closed", {"graph_id": _last_document, "path": None})
    _last_document = gid
    if gid is not None:
        events.emit("document-opened", {"graph_id": gid, "path": _path_of_active()})


def _path_of_active() -> Optional[str]:
    try:
        from ..community_packages.operators import active_row
        from .. import graph_origins
        row = active_row(_context())
        return graph_origins.origin_of(row, abspath=bpy.path.abspath).path if row is not None else None
    except Exception:  # noqa: BLE001
        return None


def document_marked(path: str, saved: bool) -> None:
    """Called by ``em_setup.unsaved.mark``: an em.json loaded or written."""
    if HOST is None:
        return
    try:
        track_document()
        if saved:
            from s3dgraphy.em import events
            graph = active_graph()
            events.emit("document-saved", {"graph_id": getattr(graph, "graph_id", None), "path": path})
    except Exception as exc:  # noqa: BLE001 — never fails a load or a save
        print(f"[em] document event: {exc}")


@bpy.app.handlers.persistent
def _on_depsgraph(_scene, _depsgraph=None):
    global _last_selection, _last_locale
    if HOST is None:
        return
    try:
        track_document()
        if _listening("selection-changed"):
            ids = selected_node_ids()
            now = frozenset(ids)
            if now != _last_selection:
                _last_selection = now
                from s3dgraphy.em import events
                events.emit("selection-changed", {"ids": ids})
        loc = getattr(bpy.app.translations, "locale", "")
        if loc != _last_locale:
            first = _last_locale is None
            _last_locale = loc
            if not first:
                from s3dgraphy.em import events
                events.emit("locale-changed", {"lang": language()})
    except Exception as exc:  # noqa: BLE001 — a handler never breaks Blender
        print(f"[em] events: {exc}")


@bpy.app.handlers.persistent
def _on_load(_a=None, _b=None):
    """A new .blend: the host stays, its Log and the document start again."""
    global _last_document, _last_selection
    if HOST is None:
        return
    HOST.steps.clear()
    _last_document, _last_selection = None, None
    sync_plugins()


# ── the plugins of this Blender ─────────────────────────────────────────────

def sync_plugins() -> list:
    """Load what is active for ``blender`` (and, with Experimental on, the
    development folder); unload what is not. Cheap: one read of enabled.json."""
    em = core.em_module()
    if em is None or HOST is None:
        return []
    try:
        return em.plugins.sync(core.HOST, dev=experimental())
    except TypeError:                          # an s3dgraphy before W15a: no dev
        return em.plugins.sync(core.HOST)
    except Exception as exc:  # noqa: BLE001
        print(f"[em] plugins: {exc}")
        return []


# ── install / uninstall ─────────────────────────────────────────────────────

def install() -> Optional[core.BlenderHost]:
    """EM Tools becomes ``em``'s host in this Blender. None (and nothing
    installed) with an s3dgraphy older than ``em``."""
    global HOST
    em = core.em_module()
    if em is None:
        return None
    HOST = core.BlenderHost(graph=active_graph, overlay=active_overlay, author=author,
                            language=language, app=BlenderApp(), after_apply=after_apply,
                            addon_version=addon_version())
    em.host.install(HOST)
    for handlers, fn in ((bpy.app.handlers.depsgraph_update_post, _on_depsgraph),
                         (bpy.app.handlers.load_post, _on_load)):
        if fn not in handlers:
            handlers.append(fn)

    def _first():
        sync_plugins()
        return None
    try:
        bpy.app.timers.register(_first, first_interval=0.5)
    except Exception:  # noqa: BLE001 — no timers: the menu syncs when drawn
        pass
    return HOST


def uninstall() -> None:
    global HOST
    for handlers, fn in ((bpy.app.handlers.depsgraph_update_post, _on_depsgraph),
                         (bpy.app.handlers.load_post, _on_load)):
        while fn in handlers:
            handlers.remove(fn)
    em = core.em_module()
    if em is not None and HOST is not None:
        try:
            em.plugins.reset()
        except Exception:  # noqa: BLE001
            pass
        if em.host.current() is HOST:
            em.host.uninstall()
    HOST = None
