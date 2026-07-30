"""EM Shelf tool UI — a SEPARATE N-panel tab ("EM Shelf"), distinct from EM Scene.

A 3D-first project-folder search that populates a Shelf of acquired resources; each
card reflects the fields the acquisition mapping offers (name, media type, size in
bytes) + a tier badge (Tier 0 = "import + origin"). Standalone save/load. NO
hatting here (that is C2). All data comes from shelf_backend (in-process s3dgraphy).
"""

from __future__ import annotations

import bpy

from . import shelf_backend


class EM_PT_shelf(bpy.types.Panel):
    bl_label = "EM Shelf"
    bl_idname = "EM_PT_shelf"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "EM Shelf"

    def draw(self, context):
        layout = self.layout
        p = getattr(context.scene, "em_shelf", None)
        if p is None:
            return

        layout.label(text="Un-hatted resource library (3D-first search).",
                     icon='ASSET_MANAGER')

        # Blocker: the bundled s3dgraphy may predate the Shelf / acquisition ops.
        if not shelf_backend.shelf_supported():
            b = layout.box()
            b.alert = True
            b.label(text="Shelf unavailable", icon='ERROR')
            b.label(text="The bundled s3dgraphy is out of date.")
            b.label(text="Activate the dev/updated s3dgraphy (./em.sh s3d),")
            b.label(text="then reopen this panel.")
            return

        # ── project folder + 3D-first scan ────────────────────────────────────
        src = layout.box()
        src.label(text="Project folder", icon='FILE_FOLDER')
        row = src.row(align=True)
        row.prop(p, "folder", text="")
        row.operator("em.shelf_set_folder", text="", icon='FILEBROWSER')
        srow = src.row(align=True)
        srow.prop(p, "recursive")
        srow.operator("em.shelf_scan", icon='VIEWZOOM')

        # ── shelf file (standalone em.json) ───────────────────────────────────
        frow = layout.row(align=True)
        frow.operator("em.shelf_new", icon='FILE_NEW')
        frow.operator("em.shelf_save", icon='EXPORT')
        frow.operator("em.shelf_load", icon='IMPORT')
        path = shelf_backend.active_path()
        if path:
            layout.label(text=f"file: {path}", icon='CHECKMARK')
        if p.status:
            layout.label(text=p.status, icon='INFO')

        # ── cards ──────────────────────────────────────────────────────────────
        cards = shelf_backend.cards()
        layout.label(text=f"Shelf — {len(cards)} resource(s)")
        if not cards:
            layout.box().label(text="— empty. Set a folder and Scan for 3D.",
                               icon='INFO')
            return
        for c in cards:
            box = layout.box()
            head = box.row(align=True)
            icon = 'MESH_DATA' if c["exists"] else 'ERROR'
            head.label(text=c["name"], icon=icon)
            rm = head.operator("em.shelf_remove", text="", icon='X')
            rm.resource_id = c["resource_id"]
            # fields reflecting the mapping (name/media_type/size) + tier badge
            meta = box.row(align=True)
            mt = c["media_type"] or c["resource_type"] or "?"
            meta.label(text=mt, icon='FILE_3D')
            meta.label(text=shelf_backend.human_size(c["size"]))
            box.label(text=c["tier"], icon='INFO')
            if not c["exists"]:
                box.label(text="(file not found on disk)", icon='ERROR')


classes = (EM_PT_shelf,)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
