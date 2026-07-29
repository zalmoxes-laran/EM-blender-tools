"""EM Scene tab UI.

A panel in the "EM Scene" N-panel tab, the face of the shared Resource layer.
Sections:

  * **Documents** — points to the existing **Document Manager** panel (in this
    same tab); NOT a duplicate list.
  * **Representation Models** — RM face (managed by the RM Manager panel here).
  * **DTC** — the Digital Twin Chain section (reuses the DTC authoring renderer).
  * **Shelf** — the un-hatted resources (orphans) with a Create-Document (hat)
    action that ADOPTS the FS stable ID as the node id. (A richer search+library
    Shelf v2 is a later session.)
  * **Object store (MinIO)** — the graph's local resources with a **Promote to
    MinIO** action (in-process s3dgraphy; keeps the stable ID; repoints locator).

The DosCo / scan folder is set with a folder picker (Set DosCo folder). All graph
reads go through s3dgraphy (em.json = truth).
"""

from __future__ import annotations

import bpy

from . import operators, resource_backend


class EM_PT_resources(bpy.types.Panel):
    bl_label = "EM Scene"
    bl_idname = "EM_PT_resources"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "EM Scene"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        p = getattr(context.scene, "em_resources", None)
        if p is None:
            return

        layout.label(text="The shared Resource layer for this graph.", icon='ASSET_MANAGER')

        # Blocker surface: the bundled s3dgraphy may be too old for R0/R1.
        if not resource_backend.resources_supported():
            b = layout.box()
            b.alert = True
            b.label(text="Resource layer unavailable", icon='ERROR')
            b.label(text="The bundled s3dgraphy is out of date.")
            b.label(text="Activate the dev/updated s3dgraphy (./em.sh s3d),")
            b.label(text="then reopen this panel.")
            return

        from ..functions import check_active_graph
        ok, graph = check_active_graph(context, show_message=False)
        if not (ok and graph is not None):
            layout.label(text="No graph selected in EM Setup.", icon='INFO')
            return

        _ok2, _graph, folder, graph_code = operators._active(context)
        backend = operators.get_cached_backend(folder)

        # DosCo / scan folder — folder picker + current path, then Scan.
        fbox = layout.box()
        fbox.operator("em.resources_set_dosco_folder", icon='FILE_FOLDER')
        fbox.label(text=(folder if folder else "— no DosCo folder set —"),
                   icon='CHECKMARK' if folder else 'INFO')
        srow = fbox.row(align=True)
        srow.operator("em.resources_scan", icon='FILE_REFRESH')
        if p.status:
            srow.label(text=p.status)

        self._section(layout, p, "show_documents", "Documents", self._draw_documents)
        self._section(layout, p, "show_rm", "Representation Models", self._draw_rm)
        self._section(layout, p, "show_dtc", "DTC",
                      lambda box: self._draw_dtc(box, context))
        self._section(layout, p, "show_shelf", "Shelf",
                      lambda box: self._draw_shelf(box, graph, backend, graph_code))
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

    # ── Documents → the existing Document Manager (no duplicate list) ─────────────
    def _draw_documents(self, box):
        box.label(text="Managed in the Document Manager panel (this tab).",
                  icon='FILE_TEXT')

    # ── Representation Models (managed by the RM Manager panel) ───────────────────
    def _draw_rm(self, box):
        box.label(text="Manage RMs in the RM Manager panel (this tab).", icon='MESH_DATA')

    # ── DTC (reuse the authoring renderer) ────────────────────────────────────────
    def _draw_dtc(self, box, context):
        try:
            from ..dtc_authoring.ui import draw_dtc_section
            draw_dtc_section(box, context)
        except Exception:
            box.label(text="DTC authoring available in the EM Data Tree.", icon='NODETREE')

    # ── Shelf (un-hatted resources) ───────────────────────────────────────────────
    def _draw_shelf(self, box, graph, backend, graph_code):
        box.label(text="Un-hatted resources (not yet a Document / RM).", icon='UGLYPACKAGE')
        if backend is None:
            box.label(text="Press Scan to index the folder.", icon='INFO')
            return
        shelf = resource_backend.shelf_entries(graph, backend, graph_code=graph_code)
        if not shelf:
            box.label(text="— Shelf empty (all resources hatted / matched)")
            return
        for e in shelf:
            row = box.row(align=True)
            row.label(text=f"{e['filename']}  ·  {e['key_id']}", icon='FILE_BLANK')
            op = row.operator("em.resources_hat_document", text="", icon='FILE_NEW')
            op.resource_id = e["resource_id"]
            op.key_id = e["key_id"]

    # ── Object store (MinIO) — Promote local resources (mirrors EMStudio) ─────────
    def _draw_minio(self, box, graph):
        box.label(text="Upload a local resource; keeps its stable ID.", icon='EXPORT')
        supported = resource_backend.minio_supported()
        if not supported:
            b = box.box()
            b.label(text="MinIO promote unavailable", icon='INFO')
            b.label(text="Needs dev s3dgraphy (./em.sh s3d) + the 'minio' extra,")
            b.label(text="and S3_* env (source dev-stack/.env).")
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
