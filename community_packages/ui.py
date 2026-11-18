"""What the community packages draw (MICRO-PL12, W9): a box in EM Tools'
Preferences, a box in the Visual Manager, a line in the 3D readings. Drawn by
the panels that own the place (``mapping_preferences``, ``visual_manager.ui``,
``readings_view.ui``), so nothing here registers a panel of its own.
"""
from __future__ import annotations

from . import core
from .i18n import tr
from .operators import active_state, lang


def _kind(kind: str) -> str:
    return tr({"community-package": "community package", "mixed": "mixed", "plugin": "plugin"}.get(kind, kind)) \
        if kind else ""


def draw_preferences(layout, context) -> None:
    box = layout.box()
    box.label(text=tr("Community packages"), icon='PACKAGE')
    P, _ = core.library()
    if P is None:
        box.label(text=tr("The bundled s3dgraphy has no community packages (older than dev117)"), icon='ERROR')
        return
    row = box.row(align=True)
    row.operator("empkg.install_from_disk", icon='IMPORT')
    row.operator("empkg.open_folder", icon='FILEBROWSER')
    row.operator("empkg.refresh", text="", icon='FILE_REFRESH')
    box.label(text=tr("The same packages as EMStudio, in {folder}").format(folder=str(P.profiles_dir().parent)),
              icon='INFO')
    try:
        _, missing, _, declared = active_state(context)
    except Exception:  # noqa: BLE001 — no scene in the Preferences: no file
        missing, declared = [], set()
    if missing:
        warn = box.row()
        warn.alert = True
        warn.label(text=tr("This file uses packages not installed here: {names}").format(
            names=core.missing_line(missing)), icon='ERROR')
    rows = core.package_rows(declared)
    if not rows:
        box.label(text=tr("No package installed on this computer"), icon='DOT')
        return
    lg = lang()
    for r in rows:
        sub = box.box()
        head = sub.row(align=True)
        head.label(text=f"{r.name} · {r.id} {r.version} · {_kind(r.kind)}".strip(" ·"),
                   icon='CHECKMARK' if r.used_by_file else 'PACKAGE')
        op = head.operator("empkg.remove", text=tr("Remove"), icon='TRASH')
        op.package_id = r.id
        col = sub.column(align=True)
        col.label(text=tr("data {version}").format(version=r.version) if r.data == "installed" else tr("no data"),
                  icon='FILE')
        if r.code == "installed":
            col.label(text=tr("code: installed in EMStudio, not run by EM Tools"), icon='SCRIPT')
        elif r.code == "not_installed":
            # the library's sentence already says «code not installed: …»
            text = (core.problem_text(r.code_reason, lg) if r.code_reason
                    else tr("code not installed: {reason}").format(reason="?"))
            col.label(text=text, icon='SCRIPT')
        if r.used_by_file:
            col.label(text=tr("used by this file"), icon='LINKED')
        if r.incomplete:
            warn = col.row()
            warn.alert = True
            warn.label(text=tr("incomplete: a required package is missing"), icon='ERROR')


def draw_visual_box(layout, context) -> None:
    """The colour schemes and vocabularies of the active packages."""
    if not core.available():
        return
    overlay, missing, _, _ = active_state(context)
    if missing:
        warn = layout.row()
        warn.alert = True
        warn.label(text=tr("This file uses packages not installed here: {names}").format(
            names=core.missing_line(missing)), icon='ERROR')
    if not overlay:
        return
    lg = lang()
    schemes = core.package_schemes(overlay, lg)
    vocabs = core.package_vocabularies(overlay, lg)
    if not schemes and not vocabs:
        return
    sub = layout.box()
    if schemes:
        sub.label(text=tr("Colour schemes of the packages"), icon='PACKAGE')
        for s in schemes:
            row = sub.row(align=True)
            if s["emc"] is None:
                row.alert = True
                row.label(text=f"{s['name']} · {tr('not a colour scheme')}", icon='ERROR')
                continue
            row.label(text=f"{s['name']} · {s['property']}", icon='COLOR')
            op = row.operator("empkg.apply_scheme", text=tr("Apply"), icon='COLOR')
            op.scheme_id = s["id"]
    if vocabs:
        sub.label(text=tr("Vocabularies of the packages"), icon='BOOKMARKS')
        for v in vocabs:
            scheme = v["scheme"].rstrip("/").rsplit("/", 1)[-1]
            if not v["installed"]:
                text, icon = tr("{label}: {scheme} {version} · not installed here").format(
                    label=v["label"], scheme=scheme, version=v["version"]), 'ERROR'
            elif v["installed_version"] != v["version"]:
                text, icon = tr("{label}: {scheme} {version} · installed {have}").format(
                    label=v["label"], scheme=scheme, version=v["version"], have=v["installed_version"]), 'INFO'
            else:
                text, icon = tr("{label}: {scheme} {version} · {n} terms").format(
                    label=v["label"], scheme=scheme, version=v["version"],
                    n=v["concepts"] if v["concepts"] is not None else "?"), 'CHECKMARK'
            sub.label(text=text, icon=icon)


def draw_measures(layout, context) -> None:
    """In the 3D readings: compute the measures the packages declare."""
    if not core.available():
        return
    overlay = active_state(context)[0]
    if not overlay or not overlay.combiner_types():
        return
    row = layout.row(align=True)
    row.label(text=tr("Measures of the packages"), icon='DRIVER_DISTANCE')
    row.operator("empkg.compute_measures", icon='PLAY')
