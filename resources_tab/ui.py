"""`Resources & Shelf` — the face of the shared Resource layer.

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
    bl_label = "Resources & Shelf"
    bl_idname = "EM_PT_resources"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "EM Scene"
    bl_order = 5
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        p = getattr(context.scene, "em_resources", None)
        if p is None:
            return

        layout.label(text="The shared Resource layer for this graph.", icon='ASSET_MANAGER')

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
            layout.label(text="No graph selected in EM Setup.", icon='INFO')
            return

        # `backend` e `graph_code` servivano alla sezione Shelf, che è diventata
        # un pannello figlio: qui resta solo la cartella.
        _ok2, _graph, folder, _graph_code = operators._active(context)

        # DosCo / scan folder — folder picker + current path, then Scan.
        fbox = layout.box()
        fbox.operator("em.resources_set_dosco_folder", icon='FILE_FOLDER')
        fbox.label(text=(folder if folder else "— no DosCo folder set —"),
                   icon='CHECKMARK' if folder else 'INFO')
        srow = fbox.row(align=True)
        srow.operator("em.resources_scan", icon='FILE_REFRESH')
        if p.status:
            srow.label(text=p.status)

        # EM16-UX · «Documents» e «Representation Models» sono spariti: erano
        # due cartelli che dicevano solo «managed in the Document Manager
        # panel». Un pannello tiene solo ciò che possiede.
        #
        # …e la sezione «Shelf» pure, perché lo Shelf è adesso un pannello
        # FIGLIO (shelf_tool/ui.py) con la sua UIList filtrabile: due viste
        # dello stesso Shelf nello stesso pannello sono una di troppo.
        self._section(layout, p, "show_dtc", "DTC",
                      lambda box: self._draw_dtc(box, context))
        self._section(layout, p, "show_minio", "Object store (MinIO)",
                      lambda box: self._draw_minio(box, graph))

    # ── section helper ──────────────────────────────────────────────────────────
    def _section(self, layout, p, prop, title, body):
        box = layout.box()
        header = box.row(align=True)
        header.prop(p, prop, text=title,
                    icon="TRIA_DOWN" if getattr(p, prop) else "TRIA_RIGHT",
                    emboss=False)
        if getattr(p, prop):
            body(box)

    # ── DTC (reuse the authoring renderer) ────────────────────────────────────────
    def _draw_dtc(self, box, context):
        try:
            from ..dtc_authoring.ui import draw_dtc_section
            draw_dtc_section(box, context)
        except Exception:
            box.label(text="DTC authoring available in the EM Data Tree.", icon='NODETREE')

    # ── Object store (MinIO) — Promote local resources (mirrors EMStudio) ─────────
    def _draw_minio(self, box, graph):
        box.label(text="Upload a local resource; keeps its stable ID.", icon='EXPORT')
        supported = resource_backend.minio_supported()
        if not supported:
            draw_s3dgraphy_too_old(box, "MinIO promote unavailable", "MinIO promote",
                              extra="Also needs the 'minio' extra and the S3_* "
                                    "environment (source dev-stack/.env).",
                              alert=False)
        resources = resource_backend.list_link_resources(graph)
        if not resources:
            box.label(text="— no resources (link nodes) yet")
            return
        for r in resources:
            row = box.row(align=True)
            row.label(text=f"{r['name'] or r['id'][:8]}  ·  {r['kind']}", icon='FILE')
            if r["kind"] == "local_path":
                sub = row.row(align=True)
                sub.enabled = supported
                op = sub.operator("em.resources_promote_minio", text="Promote")
                op.resource_id = r["id"]


classes = (EM_PT_resources,)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
