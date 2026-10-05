"""`Files` (tab EM Scene since 5 Oct 2026; once `Resources & Shelf`, then in EM
Room) — the face of the shared Resource layer.

F1 (MICRO-DOVE-LAVORI, 5 Oct 2026): Set DosCo folder, Scan, New EM project and
Reorder are one menu, «Project folder…»; «Promote to MinIO» went (the upload is
one: Upload, per file — the operator is in `_dead_code/resources_tab/`); the
outer «DTC» box that only wrapped the DTC section went, the DTC consultation
itself stays (B6 took it out of the EM Data Tree: this is the one place EM Tools
draws it).

EM16-UX (11-09-2026). This panel used to be labelled "EM Scene", i.e. it was
named after the tab that contains it, which said nothing about what it holds.
Renamed, and two of its sections removed: **Documents** and **Representation
Models** were signposts reading *managed in the Document Manager panel* — a
panel holds only what it owns, and a section whose whole content is a pointer
elsewhere is a row of height spent on navigation.

Sections now:

  * **DTC** — the Digital Twin Chain, IN CONSULTATION ONLY. The chain is the
    graph of the storage, not of the interpretation: authoring moved to EM
    Studio, and Blender registers what it consumes. A line in the section says
    so, and the same section no longer appears in the EM Data Tree.
  * **Object store (MinIO)** — the graph's local resources with a **Promote to
    MinIO** action (in-process s3dgraphy; keeps the stable ID; repoints locator).

And the **Shelf** is now a CHILD PANEL (`shelf_tool/ui.py`), absorbed from the
former `EM Shelf` tab, because its UIList with the built-in name filter is the
thing of value there and a list nested in a box loses room. The poorer inline
shelf section this panel used to draw is gone with it: two shelf views in one
panel is one too many.

The DosCo / scan folder is set with a folder picker (Set DosCo folder). All graph
reads go through s3dgraphy (em.json = truth).
"""

from __future__ import annotations

import bpy

from . import operators, resource_backend
from ..ui_helpers import draw_s3dgraphy_too_old


class EM_PT_resources(bpy.types.Panel):
    # P3 · named after EMStudio's window (the space is Contents, its
    # window of the files is Storage)
    bl_label = "Storage"
    bl_idname = "EM_PT_resources"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "EM Scene"
    bl_parent_id = "EM_PT_scene_contents"  # P3: EMStudio's Contents
    bl_order = 1
    bl_options = {"DEFAULT_CLOSED"}
    bl_description = "The shared Resource layer of this graph: where each file is"

    def draw(self, context):
        layout = self.layout
        p = getattr(context.scene, "em_resources", None)
        if p is None:
            return

        # Blocker surface: the bundled s3dgraphy may be too old for R0/R1.
        if not resource_backend.resources_supported():
            # EM16-UX/B7 · UNA riga più un bottone che apre il dettaglio.
            # Erano quattro righe per una funzione dichiarata opzionale, e un
            # box rosso alto quattro righe insegna a non leggere il rosso.
            draw_s3dgraphy_too_old(layout, "Resource layer unavailable",
                              "Resource layer")
            return

        from ..functions import check_active_graph
        ok, graph = check_active_graph(context, show_message=False)
        if not (ok and graph is not None):
            layout.label(text="No graph selected in the EM Data Tree.", icon='INFO')
            return

        # `backend` e `graph_code` servivano alla sezione Shelf, che è diventata
        # un pannello figlio: qui resta solo la cartella.
        _ok2, _graph, folder, _graph_code = operators._active(context)

        # F1 · the project folder in ONE row: where it is, and its menu (Set
        # DosCo folder, Scan, New EM project, Reorder)
        frow = layout.row(align=True)
        frow.label(text=(folder if folder else "no DosCo folder set"),
                   icon='FILE_FOLDER')
        frow.menu("EM_MT_project_folder", text="Project folder…")
        if p.status:
            layout.label(text=p.status)

        # R1/R2 · where each file is, with ONE resolver and the common signs
        try:
            from ..sync_manager import file_states
            file_states.draw(layout, context)
        except Exception as exc:                   # noqa: BLE001
            layout.label(text=f"Files: {exc}", icon='ERROR')

        # EM16-UX · «Documents» e «Representation Models» sono spariti: erano
        # due cartelli che dicevano solo «managed in the Document Manager
        # panel». Un pannello tiene solo ciò che possiede.
        #
        # …e la sezione «Shelf» pure, perché lo Shelf è adesso un pannello
        # FIGLIO (shelf_tool/ui.py) con la sua UIList filtrabile: due viste
        # dello stesso Shelf nello stesso pannello sono una di troppo.
        # MICRO risorsa-file · le revisioni ancora citate: i byte sono cambiati,
        # e qualcuno punta ancora a quelli vecchi. Si chiede, non si sposta.
        from .. import resource_revisions as _rr
        try:
            in_attesa = _rr.pending_revisions(graph)
        except Exception:                          # noqa: BLE001
            in_attesa = []
        if in_attesa:
            self._section(layout, p, "show_revisions",
                          f"Revisions ({len(in_attesa)} waiting)",
                          lambda box: self._draw_revisions(box, in_attesa))
        # MICRO-EMTOOLS-DEV26 · i sigilli: le risorse con un `.stamp.json`
        # accanto. Misurato: prima di questo nessun pannello di EMtools
        # leggeva un timbro. La sezione c'è solo quando ce n'è almeno uno.
        try:
            sigilli = operators.stamped_resources(context, graph)
        except Exception:                          # noqa: BLE001
            sigilli = []
        if sigilli:
            self._section(layout, p, "show_seals", f"Seals ({len(sigilli)})",
                          lambda box: self._draw_seals(box, p, sigilli))
        # D1 (E.D., 5 Oct 2026) · the DTC is no longer a section here: «al
        # massimo una card per dire da dove viene un asset selezionato». The
        # card of the row chosen with its «Where it comes from» button (`provenance_card`); the authoring
        # of processes is EMStudio's (`dtc_authoring.ui.draw_dtc_section` stays
        # importable, drawn by no panel)
        from .. import provenance_card
        provenance_card.draw(layout, context,
                             getattr(context.window_manager, "em_provenance_resource", ""))

    # ── section helper ──────────────────────────────────────────────────────────
    def _section(self, layout, p, prop, title, body):
        box = layout.box()
        header = box.row(align=True)
        header.prop(p, prop, text=title,
                    icon="TRIA_DOWN" if getattr(p, prop) else "TRIA_RIGHT",
                    emboss=False)
        if getattr(p, prop):
            body(box)

    # ── Revisions — pointing_at_old, and the question ─────────────────────────
    def _draw_revisions(self, box, in_attesa):
        box.label(text="New bytes, new revision — still cited:", icon='INFO')
        for r in in_attesa:
            col = box.column(align=True)
            col.label(text=r["old_name"], icon='FILE_REFRESH')
            row = col.row(align=True)
            row.label(text=f"{len(r['citing'])} citation(s)")
            op = row.operator("em.move_citations", text="Move…")
            op.old_id = r["old_id"]
            op.new_id = r["new_id"]

    # ── Seals — the stamp under a beautiful skin ────────────────────────────
    #
    # E.D.: «codice sì, ma nascosto in maniera elegante sotto una pelle
    # esteticamente bella». EMStudio presses a wax seal; Blender does not
    # animate, so the panel keeps the same ORDER: the seal and the words on
    # top, the check beside the seal, the code under a closed triangle.
    def _draw_seals(self, box, p, sigilli):
        from .. import resource_seal
        from ..icons_manager import get_custom_icon
        seal_icon = get_custom_icon("seal")
        for r, _path, seal in sigilli:
            check = seal.get("check") or {}
            state = check.get("state", "unreadable") if "error" not in seal else "unreadable"
            mark = resource_seal.MARK.get(state, "▲")
            row = box.row(align=True)
            row.alert = state in ("differs", "missing", "unreadable")
            kw = {"icon_value": seal_icon} if seal_icon else {"icon": 'KEYTYPE_KEYFRAME_VEC'}
            row.label(text=f"{r['name'] or r['id'][:8]}   {mark}", **kw)
            is_open = p.active_seal == r["id"]
            op = row.operator("em.seal_open", text="", emboss=False,
                              icon='TRIA_DOWN' if is_open else 'TRIA_LEFT')
            op.resource_id = r["id"]
            if is_open:
                self._draw_seal_card(box, p, r, seal, state, seal_icon)
        foot = box.row()
        foot.alignment = 'RIGHT'
        foot.operator("em.seal_verify_again", icon='FILE_REFRESH')

    def _draw_seal_card(self, box, p, r, seal, state, seal_icon):
        card = box.box()
        if "error" in seal:
            card.label(text="The stamp cannot be read here", icon='ERROR')
            for line in _wrap(seal["error"], _chars(card_width=True)):
                card.label(text=line)
            return
        w = seal["words"]
        top = card.row()
        left = top.column()
        left.ui_units_x = 2.4
        if seal_icon:
            left.template_icon(icon_value=seal_icon, scale=2.2)
        words = top.column(align=True)
        width = _chars(seal_column=True)
        words.label(text="Stamped")
        for line in _wrap(w["what"], width):
            words.label(text=line)
        words.separator(factor=0.5)
        for line in _wrap(w["origin"], width):
            words.label(text=line)
        for i, line in enumerate(_wrap(w["who"], width - 3)):
            words.label(text=line, icon='USER' if i == 0 else 'BLANK1')
        meta = " · ".join(x for x in (w["when"], w["with_what"]) if x)
        for i, line in enumerate(_wrap(meta, width - 3)):
            words.label(text=line, icon='TIME' if i == 0 else 'BLANK1')

        # the check, beside the seal — ✓ or ▲, then in words
        check = seal["check"]
        ccol = card.column(align=True)
        ccol.alert = state in ("differs", "missing")
        mark = {"ok": "✓", "unverifiable": "·"}.get(state, "▲")
        for i, line in enumerate(_wrap(f"{mark}  {check['line']}", _chars())):
            ccol.label(text=line)

        # «Technical details», closed to begin with
        tech = card.row(align=True)
        tech.alignment = 'LEFT'
        tech.prop(p, "show_seal_tech", text="Technical details",
                  icon='TRIA_DOWN' if p.show_seal_tech else 'TRIA_RIGHT',
                  emboss=False)
        if p.show_seal_tech:
            body = card.column()
            col = body.column(align=True)
            col.scale_y = 0.85
            width = _chars() - 2
            for key, value in seal["technical"]:
                col.label(text=f"{key}:")
                for line in _wrap(value, width, hard=True):
                    col.label(text="   " + line)
            if seal["canonical"]:
                col.separator()
                # Blender's font has no ␀ (U+2400): the NUL of the canonical
                # form is shown as «·», and said so
                for line in _wrap("canonical list of the members (role, path, "
                                  "digest; NUL-separated in the form, shown "
                                  "here as ·):", width):
                    col.label(text=line)
                for line in seal["canonical"]:
                    role, path, digest = line.split(" ␀ ")
                    for i, part in enumerate(_wrap(f"{role} · {path} ·", width - 3)):
                        col.label(text=("   " if i == 0 else "      ") + part)
                    for part in _wrap(digest, width - 6, hard=True):
                        col.label(text="      " + part)
            col.separator()
            for i, line in enumerate(_wrap(seal["stamp_path"], width - 3, hard=True)):
                col.label(text=line, icon='FILE_TEXT' if i == 0 else 'BLANK1')
            op = body.operator("em.seal_copy_json", icon='COPYDOWN')
            op.resource_id = r["id"]

class EM_MT_project_folder(bpy.types.Menu):
    """F1 · the project folder: where the DosCo is, the scan, a new EM project
    with the standard tree, and the reorder by the EM standard"""

    bl_idname = "EM_MT_project_folder"
    bl_label = "Project folder"

    def draw(self, context):
        layout = self.layout
        layout.operator("em.resources_set_dosco_folder", icon='FILE_FOLDER')
        layout.operator("em.resources_scan", icon='FILE_REFRESH')
        layout.separator()
        layout.operator("em.new_em_project", icon="NEWFOLDER")
        layout.operator("em.reorder_em_project", icon="SORTALPHA")


def _chars(seal_column=False, card_width=False):
    """How many characters fit on a line of the sidebar, measured from the
    region's width: a label does not wrap, and a cut word («…») hides exactly
    the part a reader came for."""
    try:
        region = bpy.context.region
        scale = bpy.context.preferences.system.ui_scale or 1.0
        usable = region.width / scale - 46          # panel, box and card margins
    except Exception:                              # noqa: BLE001
        usable = 260
    if seal_column:
        usable -= 2.4 * 20 + 10                    # the seal's column
    return max(18, int(usable / 7.1))


def _wrap(text, width, hard=False):
    """Words over lines of at most ``width`` characters; ``hard`` also cuts a
    word longer than a line (a digest, a path)."""
    if hard:
        width = max(12, int(width * 0.86))         # digits are wider than words
    lines, line = [], ""
    for word in str(text).split():
        while hard and len(word) > width:
            if line:
                lines.append(line)
                line = ""
            lines.append(word[:width])
            word = word[width:]
        if line and len(line) + 1 + len(word) > width:
            lines.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    if line:
        lines.append(line)
    return lines


classes = (EM_MT_project_folder, EM_PT_resources)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
