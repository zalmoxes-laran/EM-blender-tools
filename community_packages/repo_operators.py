"""The operators of the repositories in EM Tools (MICRO-PL26, X6).

Add / read / remove a repository, its token, its two switches, «Allow
online access»; install or update an entry with the confirmation of the two
panels and the plan; «Update all»; the check at start-up. The work is in
``repositories.py`` (no bpy) and in ``s3dgraphy.extensions``.
"""
from __future__ import annotations

import os

import bpy  # type: ignore
from bpy.props import BoolProperty, StringProperty  # type: ignore
from bpy.types import Operator  # type: ignore

from . import core
from . import repositories as R
from .i18n import tr
from .operators import _redraw, _sync_plugins, lang


def _net() -> None:
    """Blender's «Allow Online Access» over ours, before anything is read."""
    R.respect_blender(getattr(bpy.app, "online_access", None))


def _fail(op, exc) -> set:
    op.report({'ERROR'}, "; ".join(core.error_texts(exc, lang())))
    return {'CANCELLED'}


def _say(op, lines, level='INFO') -> None:
    for line in lines:
        print(f"[EM repositories] {line}")
    if lines:
        op.report({level}, " · ".join(lines[:4]) + (" …" if len(lines) > 4 else ""))


def _done(context) -> None:
    R.forget_cache()
    core.forget_cache()
    _redraw(context)


# ── the switch ──────────────────────────────────────────────────────────────

class EMPKG_OT_online_access(Operator):
    bl_idname = "empkg.online_access"
    bl_label = "Allow online access"
    bl_description = ("Let the repositories on the internet be read, for every EM tool of this computer; "
                      "folders and file:// are read all the same")
    bl_options = {'INTERNAL'}

    on: BoolProperty(options={'HIDDEN'})  # type: ignore

    def execute(self, context):
        R.library().set_online_access(self.on)
        _done(context)
        return {'FINISHED'}


# ── the repositories ────────────────────────────────────────────────────────

class EMPKG_OT_repo_add(Operator):
    bl_idname = "empkg.repo_add"
    bl_label = "Add repository…"
    bl_description = "Add a repository of extensions: a folder of the lab, a NAS, or an index on the internet"
    bl_options = {'INTERNAL'}

    url: StringProperty(name="Address", description="https://…/index.json, file://…, or a folder")  # type: ignore
    folder: StringProperty(name="Or a folder", subtype='DIR_PATH')  # type: ignore
    official: BoolProperty(name="ExtendedMatrix (official)", default=False)  # type: ignore
    repo_name: StringProperty(name="Name", description="Lower-case letters, digits, - and _; "
                                                       "from the address when empty")  # type: ignore
    token: StringProperty(name="Access token", subtype='PASSWORD')  # type: ignore
    check_on_startup: BoolProperty(name="Check for updates at start-up", default=False)  # type: ignore

    def invoke(self, context, event):
        if not R.available():
            self.report({'ERROR'}, tr("The bundled s3dgraphy has no repositories (older than dev125)"))
            return {'CANCELLED'}
        self.url = self.folder = self.repo_name = self.token = ""
        self.official = self.check_on_startup = False
        return context.window_manager.invoke_props_dialog(self, width=520, confirm_text=tr("Add"))

    def draw(self, context):
        col = self.layout.column()
        col.prop(self, "official")
        sub = col.column()
        sub.enabled = not self.official
        sub.prop(self, "url")
        sub.prop(self, "folder")
        col.prop(self, "repo_name")
        col.prop(self, "token")
        col.prop(self, "check_on_startup")
        col.label(text=tr("The token is kept on this computer only and sent only to the index's address"),
                  icon='INFO')

    def execute(self, context):
        _net()
        X = R.library()
        url = (X.OFFICIAL_URL if self.official else
               (bpy.path.abspath(self.folder) if self.folder.strip() else self.url)).strip()
        if not url:
            self.report({'ERROR'}, tr("Write an address or choose a folder"))
            return {'CANCELLED'}
        try:
            got = R.add_and_read(url, name=self.repo_name, token=self.token, check_on_startup=self.check_on_startup)
        except Exception as exc:  # noqa: BLE001 — the library says why, nothing added
            return _fail(self, exc)
        lines = [tr("Repository added: {name}").format(name=got["repository"]["name"])]
        lines += R.sync_lines(got["sync"], lang(), tr)
        _say(self, lines)
        _done(context)
        return {'FINISHED'}


class EMPKG_OT_repo_sync(Operator):
    bl_idname = "empkg.repo_sync"
    bl_label = "Refresh"
    bl_description = "Read the index of the repository again (all of them when none is named)"
    bl_options = {'INTERNAL'}

    name: StringProperty(options={'HIDDEN'})  # type: ignore

    def execute(self, context):
        _net()
        try:
            res = R.library().sync(self.name or None)
        except Exception as exc:  # noqa: BLE001
            return _fail(self, exc)
        lines = R.sync_lines(res, lang(), tr)
        ups = res.get("updates") or []
        if ups:
            lines.append(tr("Updates available: {list}").format(
                list=", ".join(f"{u['id']} {u.get('installed') or '?'} → {u['version']}" for u in ups)))
        _say(self, lines, 'WARNING' if any(not r.get("ok") for r in res.get("repositories") or []) else 'INFO')
        _done(context)
        return {'FINISHED'}


class EMPKG_OT_repo_remove(Operator):
    bl_idname = "empkg.repo_remove"
    bl_label = "Remove the repository"
    bl_description = "Forget this repository (EMStudio's too); what was installed from it stays"
    bl_options = {'INTERNAL'}

    name: StringProperty(options={'HIDDEN'})  # type: ignore

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=440, confirm_text=tr("Remove"))

    def draw(self, context):
        col = self.layout.column(align=True)
        col.label(text=tr("Remove the repository {name}?").format(name=self.name), icon='TRASH')
        col.label(text=tr("What was installed from it stays installed"), icon='BLANK1')

    def execute(self, context):
        if not R.library().remove_repository(self.name):
            self.report({'WARNING'}, tr("No repository called {name}").format(name=self.name))
            return {'CANCELLED'}
        self.report({'INFO'}, tr("Repository removed: {name}").format(name=self.name))
        _done(context)
        return {'FINISHED'}


class EMPKG_OT_repo_set(Operator):
    bl_idname = "empkg.repo_set"
    bl_label = "Change the repository"
    bl_description = "Check this repository at start-up, or let its reviews count (EMStudio's too)"
    bl_options = {'INTERNAL'}

    name: StringProperty(options={'HIDDEN'})  # type: ignore
    key: StringProperty(options={'HIDDEN'})  # type: ignore
    value: BoolProperty(options={'HIDDEN'})  # type: ignore

    def execute(self, context):
        if self.key not in ("check_on_startup", "trust_reviews", "enabled"):
            return {'CANCELLED'}
        try:
            R.library().update_repository(self.name, **{self.key: self.value})
        except Exception as exc:  # noqa: BLE001
            return _fail(self, exc)
        _done(context)
        return {'FINISHED'}


class EMPKG_OT_repo_token(Operator):
    bl_idname = "empkg.repo_token"
    bl_label = "Access token…"
    bl_description = "Set or clear the access token of this repository (sent only to the index's address)"
    bl_options = {'INTERNAL'}

    name: StringProperty(options={'HIDDEN'})  # type: ignore
    token: StringProperty(name="Access token", subtype='PASSWORD')  # type: ignore

    def invoke(self, context, event):
        self.token = ""
        return context.window_manager.invoke_props_dialog(self, width=420, confirm_text=tr("Save"))

    def draw(self, context):
        col = self.layout.column()
        col.prop(self, "token")
        col.label(text=tr("Empty: the token is cleared"), icon='INFO')

    def execute(self, context):
        try:
            R.library().update_repository(self.name, token=self.token or None)
        except Exception as exc:  # noqa: BLE001
            return _fail(self, exc)
        self.report({'INFO'}, (tr("Token set: {name}") if self.token else tr("Token cleared: {name}")).format(
            name=self.name))
        _done(context)
        return {'FINISHED'}


# ── installing from a repository ────────────────────────────────────────────

_previews = {}


def _key(op) -> str:
    return f"{op.repo}/{op.package_id}/{op.version}"


class EMPKG_OT_install_from_repo(Operator):
    bl_idname = "empkg.install_from_repo"
    bl_label = "Install from the repository"
    bl_description = "Install or update this extension from its repository, after the confirmation"
    bl_options = {'INTERNAL'}

    repo: StringProperty(options={'HIDDEN'})  # type: ignore
    package_id: StringProperty(options={'HIDDEN'})  # type: ignore
    version: StringProperty(options={'HIDDEN'})  # type: ignore
    with_code: BoolProperty(name="Install the code too: I trust it", default=False)  # type: ignore

    def _preview(self):
        _net()
        pv = R.preview(self.repo, self.package_id, self.version or None)
        _previews[_key(self)] = pv
        return pv

    def invoke(self, context, event):
        if not R.available():
            self.report({'ERROR'}, tr("The bundled s3dgraphy has no repositories (older than dev125)"))
            return {'CANCELLED'}
        try:
            pv = self._preview()
        except Exception as exc:  # noqa: BLE001 — not downloaded, not opened: the library says why
            return _fail(self, exc)
        # a reviewed code, or the same permissions, capabilities and source: no new question
        self.with_code = core.code_for_blender(pv) and not (pv.get("code") or {}).get("trust_needed", True)
        plan = core.plan_install(pv, with_code=True)
        text = tr("Install the data") if plan["action"] == "data" else tr("Install")
        return context.window_manager.invoke_props_dialog(self, width=600, confirm_text=text)

    def draw(self, context):
        pv = _previews.get(_key(self)) or {}
        lg = lang()
        col = self.layout.column(align=True)
        for text, icon, level in core.preview_lines(pv, lg, tr) + R.plan_lines(pv, lg, tr):
            row = col.row()
            row.alert = level == "error"
            row.label(text=text, icon=icon)
        if core.code_for_blender(pv):
            col.separator()
            col.prop(self, "with_code")

    def execute(self, context):
        lg = lang()
        pv = _previews.pop(_key(self), None)
        try:
            if pv is None:                  # run without the dialog (a script, -b)
                pv = self._preview()
                _previews.pop(_key(self), None)
            ans = R.install(self.repo, self.package_id, self.version or None, pv, with_code=self.with_code)
        except ValueError as exc:
            why = str(exc)
            text = {"plugin_only": "A plugin with no data, and its code does not run in Blender: install it in "
                                   "EMStudio (Tools ▸ Extensions…)",
                    "plugin_needs_trust": "A plugin with no data: tick «Install the code too» to install it",
                    "cycle": "The requirements go round in a circle: nothing installed"}.get(why)
            if text is None:
                text = "; ".join(core.problem_text(p, lg) for p in pv.get("errors") or []) or why
            else:
                text = tr(text)
            self.report({'ERROR'}, tr("Not installed: {why}").format(why=text))
            return {'CANCELLED'}
        except Exception as exc:  # noqa: BLE001 — nothing of it written: the library says why
            return _fail(self, exc)
        name = pv.get("name") or pv.get("id")
        if ans["action"] == "all":
            head = tr("Installed: {name} {version} from {repo} (data and code)" if (pv.get("data") or {}).get(
                "present") else "Installed: {name} {version} from {repo} (code)")
            _sync_plugins()
        elif ans.get("code_left_out"):
            head = tr("Installed: {name} {version} from {repo} (data; the code left out)")
        else:
            head = tr("Installed: {name} {version} from {repo} (data)")
        lines = [head.format(name=name, version=pv.get("version") or "", repo=self.repo)]
        lines += R.install_lines(ans, lg, tr)
        _say(self, lines)
        _done(context)
        return {'FINISHED'}


# ── «Update all» ────────────────────────────────────────────────────────────

_updates = {}


class EMPKG_OT_update_all(Operator):
    bl_idname = "empkg.update_all"
    bl_label = "Update all"
    bl_description = ("Install every update the repositories offer; the ones that would ask the trust "
                      "again are said first")
    bl_options = {'INTERNAL'}

    trust_too: BoolProperty(name="Update these too: I trust them", default=False)  # type: ignore

    def invoke(self, context, event):
        _net()
        try:
            ups = R.updates()
        except Exception as exc:  # noqa: BLE001
            return _fail(self, exc)
        if not ups:
            self.report({'INFO'}, tr("Everything is up to date"))
            return {'CANCELLED'}
        _updates["list"] = ups
        self.trust_too = False
        return context.window_manager.invoke_props_dialog(self, width=560, confirm_text=tr("Update"))

    def draw(self, context):
        ups = _updates.get("list") or []
        col = self.layout.column(align=True)
        ask = [u for u in ups if u.trust_needed]
        rest = [u for u in ups if not u.trust_needed]
        if ask:
            col.label(text=tr("These ask the trust again:"), icon='ERROR')
            for u in ask:
                why = ", ".join(u.trust_changes) or tr("source")
                text = f"{u.id} {u.installed} → {u.version} · {why}"
                if not u.for_blender:
                    text += " · " + tr("its code is not for Blender: update it in EMStudio")
                col.label(text=text, icon='BLANK1')
            if any(u.for_blender for u in ask):
                col.prop(self, "trust_too")
            col.separator()
        if rest:
            col.label(text=tr("These update without a question:"), icon='CHECKMARK')
            for u in rest:
                note = (" · " + tr("verified")) if u.verified else (
                    " · " + tr("data only (the code was left out)") if u.code_left_out else "")
                col.label(text=f"{u.id} {u.installed} → {u.version}{note}", icon='BLANK1')
        col.label(text=tr("The new data go beside the old: every file keeps the version it declares"), icon='INFO')

    def execute(self, context):
        _net()
        _updates.pop("list", None)
        try:
            res = R.update_all(trust_blender=self.trust_too)
        except Exception as exc:  # noqa: BLE001
            return _fail(self, exc)
        if res.get("updated"):
            _sync_plugins()
        lines = R.update_lines(res, lang(), tr)
        _say(self, lines, 'WARNING' if res.get("failed") or res.get("needs_trust") else 'INFO')
        _done(context)
        return {'FINISHED'}


# ── at start-up ─────────────────────────────────────────────────────────────

def _startup():
    """A few seconds after Blender is up, once: the repositories that ask
    are read, what is newer is said in the console and in the Preferences."""
    try:
        _net()
        state = R.startup_check()
        line = R.startup_line(state, tr)
        if line:
            print(f"[EM repositories] {line}")
    except Exception as exc:  # noqa: BLE001 — a start-up never fails for a repository
        print(f"[EM repositories] start-up check: {exc}")
    return None


classes = (
    EMPKG_OT_online_access,
    EMPKG_OT_repo_add,
    EMPKG_OT_repo_sync,
    EMPKG_OT_repo_remove,
    EMPKG_OT_repo_set,
    EMPKG_OT_repo_token,
    EMPKG_OT_install_from_repo,
    EMPKG_OT_update_all,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    if R.available() and not bpy.app.background and not os.environ.get("EM_NO_REPO_STARTUP"):
        try:
            bpy.app.timers.register(_startup, first_interval=6.0)
        except Exception:  # noqa: BLE001
            pass


def unregister():
    try:
        if bpy.app.timers.is_registered(_startup):
            bpy.app.timers.unregister(_startup)
    except Exception:  # noqa: BLE001
        pass
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass
