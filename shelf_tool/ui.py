"""EM Shelf tool UI — a CHILD panel of `Resources & Shelf`, in the EM Scene tab.

EM16-UX (11-09-2026): the `EM Shelf` tab is gone and this panel moved under
`Resources & Shelf`. Absorbed as a CHILD PANEL and not as a section, and the
choice is about the one thing of value in here: the **UIList with its built-in
name filter and sort**. A `template_list` nested in a box inside another panel
gets squeezed — the filter funnel is the first thing to lose room — while a
child panel keeps the list at full width and keeps its own collapse state.
Nothing in the panel body changed.

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
from ..ui_helpers import draw_s3dgraphy_too_old


class SHELF_UL_resources(bpy.types.UIList):
    """One compact row per shelf resource: icon + name + tier badge (+ size)."""

    #: WHERE the bytes are → the icon that says it at a glance. Data, not an
    #: if-chain, and keyed by the library's own values (`RESIDENCE`).
    RESIDENCE_ICONS = {"disk": 'FILE_FOLDER', "minio": 'URL', "uri": 'WORLD'}
    #: …and whether it is already part of the study. `used_in_graph` is the one
    #: worth a solid mark: it is the answer to "have I already brought this in?"
    MODE_ICONS = {"used_in_graph": 'LINKED', "only_shelf": 'UNLINKED'}
    #: the role, compacted for a row that also has to hold a name
    ROLE_SHORT = {"comparandum": "cmp", "internal_source": "src"}

    def draw_item(self, context, layout, data, item, icon, active_data,
                  active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)
            # residence first: it answers "can I even open this?" before the name
            # matters (a URI-only entry has no file here at all)
            if item.residence:
                row.label(text="", icon=self.RESIDENCE_ICONS.get(
                    item.residence, 'QUESTION'))
            row.label(text=item.name or item.resource_id[:8],
                      icon='MESH_DATA' if item.exists else 'ERROR')
            badge = row.row()
            badge.alignment = 'RIGHT'
            if item.role:
                badge.label(text=self.ROLE_SHORT.get(item.role, item.role[:3]))
            if item.mode:
                badge.label(text="", icon=self.MODE_ICONS.get(item.mode, 'DOT'))
            badge.label(text=item.tier_short)      # compact "T0"
            badge.label(text=item.size_text)        # size to the right
        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text=item.tier_short)

    # rely on the built-in name filter/sort (filters on item.name) — the funnel
    # in the UIList header lets the user type-to-filter hundreds of resources.


class EM_PT_shelf(bpy.types.Panel):
    bl_label = "Shelf"
    bl_idname = "EM_PT_shelf"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "EM Scene"
    bl_parent_id = "EM_PT_resources"
    bl_order = 1
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        p = getattr(context.scene, "em_shelf", None)
        if p is None:
            return

        layout.label(text="Un-hatted resource library (3D-first search).",
                     icon='ASSET_MANAGER')

        # Blocker: the bundled s3dgraphy may predate the Shelf / acquisition ops.
        if not shelf_backend.shelf_supported():
            # EM16-UX/B7 · una riga, e la frase intera dietro il `?`.
            draw_s3dgraphy_too_old(layout, "Shelf unavailable", "The Shelf")
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

        # ── the shelf the PROJECT already carries ─────────────────────────────
        #
        # Blender does not export the shelf: it is already a member of the
        # container (a ShelfGraph in the em.json). So the first thing this panel
        # offers is to LIST that one — no file, no import — and then to bring one
        # entry at a time into the scene.
        proj = shelf_backend.project_shelf()
        pbox = layout.box()
        if proj is not None:
            active = shelf_backend.active_shelf()
            pbox.label(text="This project carries a shelf", icon='ASSET_MANAGER')
            row = pbox.row(align=True)
            row.operator("em.shelf_adopt_project",
                         text="Read the project's shelf", icon='IMPORT')
            row.enabled = active is not proj
            if active is proj:
                pbox.label(text="…and you are looking at it.", icon='CHECKMARK')
        else:
            pbox.label(text="This project carries no shelf yet — scan a folder, "
                            "or open a project that has one.", icon='INFO')
        if not shelf_backend.table_supported():
            # the three columns are the library's to answer; saying so beats
            # showing empty cells that look like "no"
            w = pbox.row()
            w.alert = True
            w.label(text="role/mode/residence need a newer s3dgraphy",
                    icon='ERROR')

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
            # the three the library answers, spelled out where there is room
            if it.residence or it.role or it.mode:
                said = box.row(align=True)
                if it.residence:
                    said.label(text=it.residence,
                               icon=SHELF_UL_resources.RESIDENCE_ICONS.get(
                                   it.residence, 'QUESTION'))
                said.label(text=it.role or "role: not stated",
                           icon='PRESET' if it.role else 'DOT')
                if it.mode:
                    said.label(text=it.mode.replace("_", " "),
                               icon=SHELF_UL_resources.MODE_ICONS.get(
                                   it.mode, 'DOT'))
            if not it.exists and it.residence != "uri":
                box.label(text="(file not found on disk)", icon='ERROR')
            # MATERIALIZE = hat it into the active study graph, which for the
            # mesh facets also imports the geometry. On demand, one entry at a
            # time: that is the point of browsing a shelf instead of importing a
            # whole library. The facet stays a DECISION (the dialog), because
            # what a resource is in the argument is not something to guess.
            box.label(text="Materialize under a facet (RM · RMSF · RMDoc · Document)",
                      icon='PRESET')
            actions = box.row(align=True)
            hat = actions.operator("em.shelf_hat", text="Materialize…",
                                   icon='IMPORT')
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
