"""The operators and menus of ``em`` in Blender (MICRO-PL19, W16).

* **EM ▸ Plugin** — the plugins of this computer whose ``hosts`` names
  ``blender``, each with its mark (W15a) and its commands (``when`` held
  against the selection); «Undo «…»»; «Reload the plugins»; «EM Log»; with
  Experimental on (D-7, as EMStudio's console): «Open EM console».
* **Text Editor ▸ Text ▸ Run as EM script** (Experimental): the text runs with
  ``em``; each write is one step, the code in its DTC (D-8).
"""
from __future__ import annotations

import base64
import contextlib
import io
import os
import traceback

import bpy  # type: ignore
from bpy.props import BoolProperty, StringProperty  # type: ignore
from bpy.types import Menu, Operator  # type: ignore

from . import blender as emb
from . import core
from .i18n import lang_code, tr


def _em_said(messages, fallback: str = "") -> str:
    """A sentence of em / the contract in the interface's language."""
    if isinstance(messages, dict):
        return messages.get(lang_code()) or messages.get("en") or fallback
    return fallback


def _why(exc: BaseException) -> str:
    msgs = getattr(exc, "messages", None)
    return _em_said(msgs, str(exc)) if msgs else str(exc)


# ── the console ─────────────────────────────────────────────────────────────

def _console_area():
    for win in bpy.context.window_manager.windows:
        for area in win.screen.areas:
            if area.type == 'CONSOLE':
                region = next((r for r in area.regions if r.type == 'WINDOW'), None)
                if region is not None:
                    return win, area, region
    return None


def prepare_console(namespace: dict) -> dict:
    """``em`` (and ``bpy``) in a console's namespace — what «Open EM console»
    puts there. Measured without a window: the namespace is a dict."""
    from s3dgraphy import em
    namespace.setdefault("bpy", bpy)
    namespace["em"] = em
    return namespace


def _banner() -> list:
    from s3dgraphy import em
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        em.help(lang_code())
    return [tr("em is ready · host: blender · em.help()")] + buf.getvalue().splitlines()[1:]


def _fill_console(win, area, region) -> bool:
    """``em`` into the console of ``region`` and the banner in its scrollback."""
    try:
        try:
            import _console_python as console_python  # type: ignore — Blender 4.2+ / 5.x
        except ImportError:
            import console_python  # type: ignore — older Blenders
        console, _out, _err = console_python.get_console(hash(region))
        prepare_console(console.locals)
    except Exception:  # noqa: BLE001 — another Blender: type the import
        with bpy.context.temp_override(window=win, area=area, region=region):
            bpy.ops.console.clear_line()
            bpy.ops.console.insert(text="from s3dgraphy import em")
            bpy.ops.console.execute(interactive=True)
    with bpy.context.temp_override(window=win, area=area, region=region):
        for line in _banner():
            bpy.ops.console.scrollback_append(text=line, type='INFO')
    area.tag_redraw()
    return True


class EMSCRIPT_OT_open_console(Operator):
    bl_idname = "emscript.open_console"
    bl_label = "Open EM console"
    bl_description = "Open Blender's Python console with em ready (from s3dgraphy import em), EM Tools as its host"

    @classmethod
    def poll(cls, context):
        return core.available() and emb.HOST is not None

    def execute(self, context):
        found = _console_area()
        if found is not None:
            _fill_console(*found)
            return {'FINISHED'}
        # a new window, its area turned into a console, filled once it exists
        try:
            bpy.ops.wm.window_new()
            win = context.window_manager.windows[-1]
            win.screen.areas[0].type = 'CONSOLE'
        except Exception:  # noqa: BLE001 — no window (headless)
            self.report({'WARNING'}, tr("No 3D-view window to open the console from"))
            return {'CANCELLED'}

        def _later():
            got = _console_area()
            if got is not None:
                _fill_console(*got)
            return None
        bpy.app.timers.register(_later, first_interval=0.2)
        return {'FINISHED'}


# ── a text as an EM script ──────────────────────────────────────────────────

def run_script(code: str, name: str = "<text>") -> dict:
    """Run ``code`` with ``em`` in a fresh namespace; its writes are the
    SCRIPT's (``emtools.script``, the code in the DTC). → ``{ok, writes, error}``."""
    host = emb.HOST
    before = len(host.steps)
    ns = prepare_console({"__name__": "__main__", "__file__": name})
    try:
        with host.running(code):
            exec(compile(code, name, "exec"), ns)          # noqa: S102 — the person's own script
    except Exception as exc:  # noqa: BLE001 — said, Blender stays up
        tb = traceback.format_exception_only(type(exc), exc)
        return {"ok": False, "writes": len(host.steps) - before, "error": _why(exc) or "".join(tb).strip()}
    return {"ok": True, "writes": len(host.steps) - before, "error": None}


class EMSCRIPT_OT_run_text(Operator):
    bl_idname = "emscript.run_text"
    bl_label = "Run as EM script"
    bl_description = "Run this text with em; what it writes is one step each, its code kept in the DTC"

    @classmethod
    def poll(cls, context):
        return (core.available() and emb.HOST is not None
                and getattr(getattr(context, "space_data", None), "text", None) is not None)

    def execute(self, context):
        text = context.space_data.text
        code = text.as_string()
        if not code.strip():
            self.report({'WARNING'}, tr("No text to run"))
            return {'CANCELLED'}
        out = run_script(code, text.name)
        if not out["ok"]:
            self.report({'ERROR'}, tr("The script failed: {error}").format(error=out["error"]))
            return {'CANCELLED'}
        self.report({'INFO'}, tr("Script run: {n} write(s)").format(n=out["writes"]))
        return {'FINISHED'}


# ── undo, reload, the Log ───────────────────────────────────────────────────

class EMSCRIPT_OT_undo(Operator):
    bl_idname = "emscript.undo"
    bl_label = "Undo the last EM write"
    bl_description = "Undo the newest act written through em (a script, the console, a plugin)"

    @classmethod
    def poll(cls, context):
        return emb.HOST is not None and emb.HOST.last_undoable() is not None

    def execute(self, context):
        step, result = emb.HOST.undo()
        if step is None:
            self.report({'INFO'}, tr("Nothing to undo"))
            return {'CANCELLED'}
        if not result.ok:
            self.report({'ERROR'}, tr("Not undone: {why}").format(why=result.message))
            return {'CANCELLED'}
        self.report({'INFO'}, tr("Undone: {label}").format(label=step.label))
        return {'FINISHED'}


class EMSCRIPT_OT_reload_plugins(Operator):
    bl_idname = "emscript.reload_plugins"
    bl_label = "Reload the plugins"
    bl_description = "Read enabled.json again (and the development folder, with Experimental on)"

    @classmethod
    def poll(cls, context):
        return core.available() and emb.HOST is not None

    def execute(self, context):
        em = core.em_module()
        got = emb.sync_plugins()
        # a development copy is read again from its files (W15a)
        for p in list(got):
            if getattr(p, "dev", False):
                try:
                    em.plugins.reload(p.id, core.HOST)
                except Exception:  # noqa: BLE001
                    pass
        got = em.plugins.loaded()
        loaded = sum(1 for p in got if p.state == "loaded")
        self.report({'INFO'}, tr("Plugins: {loaded} loaded, {other} not").format(
            loaded=loaded, other=len(got) - loaded))
        emb.redraw()
        return {'FINISHED'}


def log_lines(host) -> list:
    """The Log as ``(text, icon)`` lines, newest first: the acts and what
    ``em.app.notify`` said."""
    out = []
    for s in reversed(host.steps):
        who = s.plugin["id"] if s.plugin else s.caller
        tmpl = "{when} · {label} · {who} · undone" if s.undone else "{when} · {label} · {who}"
        out.append((tr(tmpl).format(when=s.when, label=s.label, who=who),
                    'LOOP_BACK' if s.undone else ('PLUGIN' if s.plugin else 'CONSOLE')))
    for n in emb.NOTICES:
        out.append((f"{n['when']} · {n['text']}",
                    {'error': 'ERROR', 'warning': 'INFO'}.get(n['level'], 'DOT')))
    return out


class EMSCRIPT_OT_show_log(Operator):
    bl_idname = "emscript.show_log"
    bl_label = "EM Log"
    bl_description = "What em wrote in this Blender, and what it said"

    def invoke(self, context, event):
        return context.window_manager.invoke_popup(self, width=520)

    def draw(self, context):
        col = self.layout.column(align=True)
        lines = log_lines(emb.HOST) if emb.HOST is not None else []
        if not lines:
            col.label(text=tr("Nothing written yet"), icon='INFO')
        for text, icon in lines[:30]:
            col.label(text=text, icon=icon)

    def execute(self, context):
        return {'FINISHED'}


# ── a plugin's command ──────────────────────────────────────────────────────

_pending_file = {}


class EMSCRIPT_OT_run_plugin_command(Operator):
    bl_idname = "emscript.run_plugin_command"
    bl_label = "Run a plugin's command"
    bl_description = "A command of a plugin, through the contract"
    bl_options = {'INTERNAL'}

    plugin: StringProperty(options={'HIDDEN'})  # type: ignore
    command: StringProperty(options={'HIDDEN'})  # type: ignore
    filepath: StringProperty(subtype='FILE_PATH', options={'HIDDEN', 'SKIP_SAVE'})  # type: ignore
    saving: BoolProperty(default=False, options={'HIDDEN', 'SKIP_SAVE'})  # type: ignore

    @classmethod
    def description(cls, context, properties):
        em = core.em_module()
        p = em.plugins.get(properties.plugin) if em is not None else None
        if p is None:
            return cls.bl_description
        badge = core.badge_of(p.source, bool(p.meta.get("verified")))
        return f"{p.id} {p.version} ({p.source})" + (f" · {tr(badge)}" if badge else "")

    def _decl(self):
        em = core.em_module()
        p = em.plugins.get(self.plugin) if em is not None else None
        return p, (p.commands.get(self.command) if p is not None else None)

    def invoke(self, context, event):
        _p, c = self._decl()
        if c is not None and core.wants_path(c.slots):
            context.window_manager.fileselect_add(self)          # a reader's file first
            return {'RUNNING_MODAL'}
        return self._run(context)

    def execute(self, context):
        if self.saving:
            return self._save()
        return self._run(context)

    def _run(self, context):
        em = core.em_module()
        _p, c = self._decl()
        if c is None:
            self.report({'ERROR'}, _em_said((em.plugins.invoke(self.plugin, self.command).data or {})
                                            .get("messages"), "?"))
            return {'CANCELLED'}
        slots = core.fill_slots(c.slots, emb.selected_node_ids(context), bpy.path.abspath(self.filepath) or None)
        res = em.plugins.invoke(self.plugin, self.command, slots,
                                author=emb.HOST.author() if emb.HOST else None)
        if not res.ok:
            self.report({'ERROR'}, _em_said((res.data or {}).get("messages"), res.message))
            return {'CANCELLED'}
        data = res.data or {}
        if data.get("file"):
            # an exporter: the person says where (a plugin never writes for them)
            _pending_file[(self.plugin, self.command)] = data["file"]
            self.saving = True
            self.filepath = data["file"].get("name") or "export"
            context.window_manager.fileselect_add(self)
            return {'RUNNING_MODAL'}
        value = data.get("value")
        label = c.label_in(lang_code())
        self.report({'INFO'}, tr("Done: {label}").format(label=label) + (f" → {value}" if value is not None else ""))
        emb.redraw()
        return {'FINISHED'}

    def _save(self):
        f = _pending_file.pop((self.plugin, self.command), None)
        if not f:
            return {'CANCELLED'}
        path = bpy.path.abspath(self.filepath)
        if os.path.isdir(path):
            path = os.path.join(path, f.get("name") or "export")
        data = base64.b64decode(f["b64"]) if "b64" in f else str(f.get("text") or "").encode("utf-8")
        with open(path, "wb") as fh:
            fh.write(data)
        self.report({'INFO'}, tr("Saved: {path}").format(path=path))
        return {'FINISHED'}


# ── the menu ────────────────────────────────────────────────────────────────

def draw_plugin_sections(layout, context) -> None:
    """The plugins and their commands (also measured headless on a recording layout)."""
    if not core.available():
        layout.label(text=tr("The bundled s3dgraphy has no em (older than dev124)"), icon='ERROR')
        return
    graph = emb.active_graph()
    ids = emb.selected_node_ids(context) if graph is not None else []
    sections = core.menu_sections(lang_code(), document=graph is not None,
                                  types=core.selected_types(graph, ids))
    if not sections:
        layout.label(text=tr("No plugin for Blender on this computer"), icon='DOT')
    for sec in sections:
        head = tr("{name} {version} · {badge}").format(name=sec.name, version=sec.version, badge=tr(sec.badge)) \
            if sec.badge else f"{sec.name} {sec.version}"
        layout.label(text=head, icon='PLUGIN')
        if sec.state != "loaded":
            layout.label(text=tr("not loaded: {why}").format(why=sec.why), icon='ERROR')
            continue
        if not sec.commands:
            layout.label(text=tr("no command"), icon='BLANK1')
        for c in sec.commands:
            row = layout.row()
            row.enabled = c.enabled
            op = row.operator(EMSCRIPT_OT_run_plugin_command.bl_idname, text=c.label,
                              icon='EXPORT' if c.exporter else ('FILEBROWSER' if c.path else 'BLANK1'))
            op.plugin, op.command = c.plugin, c.id


class EMSCRIPT_MT_plugins(Menu):
    bl_idname = "EMSCRIPT_MT_plugins"
    bl_label = "Plugin"
    bl_description = "Python plugins and the EM console"

    def draw(self, context):
        layout = self.layout
        draw_plugin_sections(layout, context)
        layout.separator()
        host = emb.HOST
        last = host.last_undoable() if host is not None else None
        if last is not None:
            layout.operator(EMSCRIPT_OT_undo.bl_idname, text=tr("Undo «{label}»").format(label=last.label),
                            icon='LOOP_BACK')
        layout.operator(EMSCRIPT_OT_show_log.bl_idname, icon='TEXT')
        layout.operator(EMSCRIPT_OT_reload_plugins.bl_idname, icon='FILE_REFRESH')
        if emb.experimental():
            layout.separator()
            layout.operator(EMSCRIPT_OT_open_console.bl_idname, icon='CONSOLE')


def _draw_text_menu(self, context):
    if emb.experimental():
        self.layout.separator()
        self.layout.operator(EMSCRIPT_OT_run_text.bl_idname, icon='SCRIPT')


classes = (
    EMSCRIPT_OT_open_console,
    EMSCRIPT_OT_run_text,
    EMSCRIPT_OT_undo,
    EMSCRIPT_OT_reload_plugins,
    EMSCRIPT_OT_show_log,
    EMSCRIPT_OT_run_plugin_command,
    EMSCRIPT_MT_plugins,
)


def register():
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except ValueError:
            pass
    try:
        bpy.types.TEXT_MT_text.append(_draw_text_menu)
    except Exception:  # noqa: BLE001
        pass


def unregister():
    try:
        bpy.types.TEXT_MT_text.remove(_draw_text_menu)
    except Exception:  # noqa: BLE001
        pass
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass
