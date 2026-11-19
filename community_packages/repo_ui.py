"""The repositories in EM Tools' Preferences (MICRO-PL26, X6): below the
installed community packages, the same repositories EMStudio shows in its
«Extensions» window — the switch «Allow online access», each repository with
its state, «Add repository…», what they offer Blender with «Install» /
«Update», «Update all». The work is in ``repositories.py`` (no bpy).
"""
from __future__ import annotations

from . import repositories as R
from .i18n import tr
from .operators import lang


def _blender_online():
    import bpy  # type: ignore
    return getattr(bpy.app, "online_access", None)


KIND = {
    "data": "community package",
    "mixed": "mixed: data, and code for Blender",
    "data_only": "data (its code is not for Blender)",
    "code": "plugin for Blender",
}


def draw_repositories(layout, context) -> None:
    box = layout.box()
    box.label(text=tr("Repositories"), icon='WORLD')
    if not R.available():
        box.label(text=tr("The bundled s3dgraphy has no repositories (older than dev125)"), icon='INFO')
        return
    R.respect_blender(_blender_online())
    lg = lang()
    _draw_switch(box)
    line = R.startup_line(R.startup_state(), tr)
    if line:
        box.label(text=line, icon='INFO')
    repos = R.repositories()
    if not repos:
        box.label(text=tr("No repository yet: add a folder of the lab, or an index on the internet"), icon='DOT')
    for r in repos:
        _draw_repository(box, r, lg)
    row = box.row(align=True)
    row.operator("empkg.repo_add", icon='ADD')
    if repos:
        row.operator("empkg.repo_sync", text=tr("Refresh all"), icon='FILE_REFRESH').name = ""
    data = R.offers_cached()
    ups = [o for o in data["offers"] if o.update]
    if ups:
        row.operator("empkg.update_all", text=tr("Update all ({n})").format(n=len(ups)), icon='SORT_DESC')
    _draw_offers(box, data, lg)


def _draw_switch(box) -> None:
    st = R.online_state()
    row = box.row(align=True)
    if st["blender_off"]:
        row.label(text=tr("Online access is off in Blender (Preferences ▸ System ▸ Network): "
                          "only folders and file:// are read"), icon='UNLINKED')
        return
    if st["env"] is not None:
        row.label(text=tr("Online access: {state}, decided by the environment").format(
            state=tr("on") if st["on"] else tr("off")), icon='LINKED' if st["on"] else 'UNLINKED')
        return
    op = row.operator("empkg.online_access", text=tr("Allow online access"),
                      icon='CHECKBOX_HLT' if st["on"] else 'CHECKBOX_DEHLT', depress=st["on"])
    op.on = not st["on"]
    row.label(text=tr("one switch for this computer, EMStudio's too"))


def _draw_repository(box, r, lg) -> None:
    sub = box.box()
    head = sub.row(align=True)
    where = tr("folder") if r.get("local") else tr("on the internet")
    head.label(text=f"{r['name']} · {where}" + (f" · {tr('official')}" if r.get("official") else ""),
               icon='FILE_FOLDER' if r.get("local") else 'URL')
    head.operator("empkg.repo_sync", text="", icon='FILE_REFRESH').name = r["name"]
    head.operator("empkg.repo_remove", text="", icon='TRASH').name = r["name"]
    col = sub.column(align=True)
    col.label(text=str(r.get("url") or ""), icon='BLANK1')
    if r.get("error"):
        warn = col.row()
        warn.alert = True
        warn.label(text=R.problem_text(r["error"], lg), icon='ERROR')
    if r.get("synced_at"):
        col.label(text=tr("read {when}: {n} entries").format(
            when=str(r["synced_at"])[:16].replace("T", " "), n=r.get("entries") or 0), icon='CHECKMARK')
    elif not r.get("error"):
        col.label(text=tr("not read yet: «Refresh»"), icon='DOT')
    row = sub.row(align=True)
    for key, text in (("check_on_startup", "Check for updates at start-up"), ("trust_reviews", "Its reviews count")):
        on = bool(r.get(key))
        op = row.operator("empkg.repo_set", text=tr(text), icon='CHECKBOX_HLT' if on else 'CHECKBOX_DEHLT')
        op.name, op.key, op.value = r["name"], key, not on
    op = row.operator("empkg.repo_token", text=tr("Access token (set)") if r.get("has_token")
                      else tr("Access token…"), icon='KEY_HLT' if r.get("has_token") else 'KEY_DEHLT')
    op.name = r["name"]


def _draw_offers(box, data, lg) -> None:
    offers = data["offers"]
    if offers:
        box.label(text=tr("Offered by the repositories"), icon='IMPORT')
    for o in offers:
        row = box.row(align=True)
        badge = f" · {tr('verified')}" if o.verified else ""
        row.label(text=f"{o.name} {o.version} · {tr(KIND.get(o.kind, o.kind))} · {o.repo}{badge}",
                  icon='CHECKMARK' if o.verified else ('SCRIPT' if o.kind in ("mixed", "code") else 'PACKAGE'))
        if o.update:
            row.label(text=tr("installed {version}").format(version=o.installed))
            op = row.operator("empkg.install_from_repo", text=tr("Update"), icon='SORT_DESC')
        elif o.installed:
            row.label(text=tr("installed {version}").format(version=o.installed), icon='CHECKMARK')
            continue
        else:
            op = row.operator("empkg.install_from_repo", text=tr("Install"), icon='IMPORT')
        op.repo, op.package_id, op.version = o.repo, o.id, o.version
    if data["elsewhere"]:
        box.label(text=tr("{n} plugin(s) for EMStudio only, not listed here").format(n=data["elsewhere"]),
                  icon='INFO')
    for p in list(data["blocked"]) + list(data["other_platforms"]):
        warn = box.row()
        warn.alert = True
        warn.label(text=R.problem_text(p, lg), icon='ERROR')
