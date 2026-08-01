"""EM Shelf tool UI — a SEPARATE N-panel tab ("EM Shelf"), distinct from EM Scene.

A 3D-first project-folder search populates a Shelf of acquired resources. The
resources are shown in a scalable **UIList** (one compact row each, built-in
name filter/sort — essential with hundreds of items); the ACTIVE row's fields
(name, media type, size in bytes, tier badge) are shown in a details box below,
with the Hat and Remove actions. Hat opens a dialog where the user picks the
FACET explicitly (RM / RMSF / RMDoc / Document) and a compatible target; the
facets are not exclusive, so the same resource can be hatted more than once. All
data comes from shelf_backend (in-process s3dgraphy) mirrored into
scene.em_shelf.items.
"""

from __future__ import annotations

import bpy

from . import shelf_backend


class SHELF_UL_resources(bpy.types.UIList):
    """One compact row per shelf resource: icon + name + tier badge (+ size)."""

    def draw_item(self, context, layout, data, item, icon, active_data,
                  active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)
            row.label(text=item.name or item.resource_id[:8],
                      icon='MESH_DATA' if item.exists else 'ERROR')
            badge = row.row()
            badge.alignment = 'RIGHT'
            badge.label(text=item.tier_short)      # compact "T0"
            badge.label(text=item.size_text)        # size to the right
        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text=item.tier_short)

    # rely on the built-in name filter/sort (filters on item.name) — the funnel
    # in the UIList header lets the user type-to-filter hundreds of resources.


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

        # ── shelf scope (standalone file vs project multigraph) ───────────────
        layout.prop(p, "shelf_scope", text="")
        frow = layout.row(align=True)
        frow.operator("em.shelf_new", icon='FILE_NEW')
        frow.operator("em.shelf_save", icon='EXPORT')
        frow.operator("em.shelf_load", icon='IMPORT')
        path = shelf_backend.active_path()
        if path:
            layout.label(text=f"file: {path}", icon='CHECKMARK')
        mg = shelf_backend.multigraph_id()
        if mg:
            layout.label(text=f"project member: {mg}", icon='OUTLINER')
        # project-scope persistence: sidecar beside the .blend (not in the Heriverse export)
        if p.shelf_scope == 'PROJECT':
            if bpy.data.filepath:
                layout.label(text="auto-saved beside the .blend on save", icon='INFO')
            else:
                w = layout.box()
                w.alert = True
                w.label(text="Save the .blend to persist the project shelf",
                        icon='ERROR')
                w.label(text="(or use Save Shelf for a standalone file)")
        if p.status:
            layout.label(text=p.status, icon='INFO')

        # ── resource list (scalable UIList + name funnel) ─────────────────────
        layout.label(text=f"Shelf — {len(p.items)} resource(s)")
        layout.template_list("SHELF_UL_resources", "", p, "items",
                             p, "active_index", rows=6)

        # ── details for the ACTIVE resource ───────────────────────────────────
        if 0 <= p.active_index < len(p.items):
            it = p.items[p.active_index]
            box = layout.box()
            box.label(text=it.name or it.resource_id[:8],
                      icon='MESH_DATA' if it.exists else 'ERROR')
            box.label(text=f"Type: {it.media_type or it.resource_type or '?'}",
                      icon='FILE_3D')
            box.label(text=f"Size: {it.size_text}")
            box.label(text=it.tier_label or "Tier 0 · import + origin", icon='INFO')
            if not it.exists:
                box.label(text="(file not found on disk)", icon='ERROR')
            # Hat: pick the facet (RM / RMSF / RMDoc / Document) + its target.
            # Facets are not exclusive — Hat the same resource again for another.
            box.label(text="Hat under a facet (RM · RMSF · RMDoc · Document)",
                      icon='PRESET')
            actions = box.row(align=True)
            hat = actions.operator("em.shelf_hat", text="Hat…", icon='IMPORT')
            hat.resource_id = it.resource_id
            rm = actions.operator("em.shelf_remove", text="", icon='X')
            rm.resource_id = it.resource_id
        else:
            layout.box().label(text="— empty. Set a folder and Scan for 3D.",
                               icon='INFO')


classes = (SHELF_UL_resources, EM_PT_shelf)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
