"""UI for the Proxy Box Creator (DP-47 / DP-07 two-step flow).

Single, tightly-scoped panel — nested under the "RM to Proxy Suite"
parent (see :mod:`rm_to_proxy_suite`), sibling of Surface Areas.

Top to bottom:

1. Step 1 Document anchor (pick from selected / search / clear).
2. Step 2 seven measurement points (click Record per row; when the
   anchor is set + Propagate is on, the document and a gap-aware
   extractor id are filled automatically).
3. Parameters — pivot, active US (drives the proxy name at Create
   time), Proxy collection toggle.
4. Create + Clear-All buttons.
"""

import bpy  # type: ignore
from bpy.types import Panel  # type: ignore

from .. import icons_manager
from .operators import POINT_TYPE_LABELS


def _active_us_name(context):
    """Return the active Stratigraphic Unit's name (empty when none).

    ``settings.target_us_name`` is a computed property whose getter
    already reads ``strat.units[strat.units_index].name`` — so the
    two are always in sync and we can just delegate.
    """
    return context.scene.em_tools.proxy_box.target_us_name or ""


class PROXYBOX_PT_main_panel(Panel):
    """Main panel for Proxy Box.

    Top-level panel in the EM Annotator tab (promoted from the former
    RM to Proxy Suite wrapper). Sibling of Surface Areas.
    """
    bl_label = "Proxy Box"
    bl_idname = "PROXYBOX_PT_main_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "EM Annotator"
    bl_order = 5
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        em_tools = getattr(context.scene, 'em_tools', None)
        if em_tools is None:
            return False
        if getattr(context.scene, 'landscape_mode_active', False):
            return False
        if not getattr(em_tools, 'mode_em_advanced', False):
            return False
        return True

    def draw_header(self, context):
        layout = self.layout
        icon_id = icons_manager.get_icon_value("show_all_proxies")
        if icon_id:
            layout.label(text="", icon_value=icon_id)
        else:
            layout.label(text="", icon='MESH_CUBE')

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        em_tools = scene.em_tools
        settings = em_tools.proxy_box

        # The panel header already shows "Proxy Box" + its icon via
        # draw_header/bl_label — no extra title row in the body.
        if em_tools.active_file_index < 0:
            layout.label(text="Load a GraphML first.", icon='ERROR')
            return

        # ── Row 1: Mesh → RM → Document (compact, mirrors Surface Areas)
        # status + "1. Mesh" + mesh picker + RM_on/off badge +
        # document badge + help popup. The Document is auto-resolved
        # from the picked mesh via its RM container; pick_from_selected
        # / search_document remain available below as fallbacks when
        # no chain is present (e.g. mesh not yet promoted to RM).
        from ..surface_areale.postprocess import is_mesh_an_rm

        obj = settings.target_mesh
        is_rm, _rm_item = is_mesh_an_rm(obj, scene) if obj else (False, None)
        has_doc = bool(settings.document_node_id)
        doc_icon = icons_manager.get_icon_value("document")
        doc_code = (settings.document_node_name
                    or settings.document_node_id) if has_doc else "no D."

        anchor_box = layout.box()
        row = anchor_box.row(align=True)
        row.label(text="", icon='CHECKMARK' if has_doc else 'X')
        row.label(text="1. Mesh")
        row.prop(settings, "target_mesh", text="")

        # RM on/off — same fallback ladder used by Surface Areas.
        if is_rm:
            rm_badge = (icons_manager.get_icon_value("RM_on")
                        or icons_manager.get_icon_value("show_all_RMs"))
        else:
            rm_badge = (icons_manager.get_icon_value("RM_off")
                        or icons_manager.get_icon_value("show_all_RMs_off"))
        if rm_badge:
            row.label(text="", icon_value=rm_badge)
        else:
            row.label(text="", icon='MESH_CUBE' if is_rm else 'UNLINKED')

        if doc_icon:
            row.label(text=doc_code, icon_value=doc_icon)
        else:
            row.label(text=doc_code, icon='FILE_TEXT')

        help_op = row.operator(
            "em.help_popup", text="", icon='QUESTION', emboss=False)
        help_op.title = "Proxy Box"
        help_op.text = (
            "Step 1: pick the target mesh — the linked Document is\n"
            "resolved automatically via the RM container. Use\n"
            "'pick from selected' / 'search' below as fallbacks if\n"
            "the chain isn't set up yet.\n"
            "Step 2: record the 7 measurement points (Record per row).\n"
            "The proxy name comes from the active Stratigraphic Unit."
        )
        help_op.url = "panels/proxy_box_creator.html#_Proxy_Box_Creator"
        help_op.project = 'em_tools'

        # Propagate-to-all-points toggle stays on its own row inside
        # the same box. Pick-from-selected / search-document /
        # clear-document have been retired: the target_mesh picker
        # already resolves the chain automatically and the user can
        # change the mesh to swap anchor.
        if has_doc:
            anchor_box.prop(settings, "propagate_doc_to_points")

        # ── Step 2: 7 measurement points ─────────────────────────────
        recorded_count = sum(1 for p in settings.points[:7]
                             if p.is_recorded)
        points_box = layout.box()
        pts_hdr = points_box.row(align=True)
        pts_hdr.label(
            text="",
            icon='CHECKMARK' if recorded_count == 7 else 'X')
        pts_hdr.label(text=f"2. Points  ({recorded_count}/7)")

        for i in range(7):
            row = points_box.row(align=True)
            label = POINT_TYPE_LABELS.get(i, f"Point {i + 1}")
            # Keep the row compact — a single line per point.
            if i < len(settings.points) and settings.points[i].is_recorded:
                icon = 'CHECKMARK'
                pos = settings.points[i].position
                coord = f"({pos[0]:.2f}, {pos[1]:.2f}, {pos[2]:.2f})"
            else:
                icon = 'RADIOBUT_OFF'
                coord = "—"
            row.label(text=f"{label}", icon=icon)
            row.label(text=coord)
            op = row.operator(
                "proxybox.record_point", text="", icon='MOUSE_LMB')
            op.point_index = i

            # When the paradata is filled in (propagate on, anchor set),
            # show the extractor id so the user can verify before Create.
            if (i < len(settings.points)
                    and settings.points[i].is_recorded
                    and settings.points[i].extractor_id):
                sub = points_box.row(align=True)
                sub.scale_y = 0.85
                sub.label(
                    text=f"    → {settings.points[i].extractor_id}",
                    icon='EMPTY_AXIS')

        # Clear-all-points lives at the bottom of the Points box so it
        # stays scoped to its section.
        points_box.separator()
        points_box.operator(
            "proxybox.clear_all_points",
            text="Clear All Points", icon='X')

        # ── Step 3: Active US (compact one-line like Surface Areas SU)
        strat = em_tools.stratigraphy
        us_name = _active_us_name(context)
        has_us = bool(us_name)
        from ..us_helpers import draw_add_us_button

        us_box = layout.box()
        us_row = us_box.row(align=True)
        us_row.label(text="", icon='CHECKMARK' if has_us else 'X')
        us_row.label(text="3. SU")
        if strat.units:
            us_row.prop_search(
                settings, "target_us_name",
                strat, "units",
                text="")
            draw_add_us_button(us_row, text="")
        else:
            us_row.label(text="No units yet", icon='INFO')
            draw_add_us_button(us_row, text="")

        # ── Create + box settings (pivot / collection / persistence)
        # Create Proxy lives at the top of this box so the action sits
        # right next to the parameters that govern it. Below it: pivot,
        # collection toggle, persist-on-create.
        all_recorded = recorded_count == 7
        all_have_doc = all(
            bool(p.source_document) for p in settings.points[:7]) \
            if len(settings.points) >= 7 else False
        all_have_ext = all(
            bool(p.extractor_id) for p in settings.points[:7]) \
            if len(settings.points) >= 7 else False
        can_create = (all_recorded
                      and all_have_doc
                      and all_have_ext
                      and has_us)

        opts_box = layout.box()
        create_row = opts_box.row(align=True)
        create_icon = icons_manager.get_icon_value("surface_area")
        if can_create:
            if create_icon:
                create_row.operator(
                    "proxybox.create_proxy_enhanced",
                    text="Create Proxy", icon_value=create_icon)
            else:
                create_row.operator(
                    "proxybox.create_proxy_enhanced",
                    text="Create Proxy", icon='ADD')
        else:
            create_row.enabled = False
            if not all_recorded:
                msg = "Record all 7 points first"
            elif not all_have_doc:
                msg = "Set the anchor document (Step 1)"
            elif not all_have_ext:
                msg = "Missing extractor ids — re-record with Propagate on"
            else:
                msg = "Select the Active US first"
            create_row.operator(
                "proxybox.create_proxy_enhanced",
                text=msg, icon='ERROR')

        opts_col = opts_box.column(align=True)
        opts_col.prop(settings, "pivot_location", text="Pivot")
        opts_col.prop(settings, "use_proxy_collection")
        opts_col.prop(settings, "persist_after_create")

        # ── Chain Summary (collapsible) ──────────────────────────────
        # Mirrors the Surface Areas panel's summary: shows the
        # paradata chain that will be committed to the graph on
        # Create, so the user can sanity-check node names and arrow
        # directions without leaving the panel.
        layout.separator()
        summary_box = layout.box()
        head = summary_box.row()
        head.prop(
            settings, "show_chain_summary",
            icon=('TRIA_DOWN' if settings.show_chain_summary
                  else 'TRIA_RIGHT'),
            text="Chain Summary",
            emboss=False,
        )
        if settings.show_chain_summary:
            us_name_cs = _active_us_name(context) or "?"
            doc_name_cs = (settings.document_node_name or "?")
            ext_ids_cs = [p.extractor_id
                          for p in settings.points[:7]
                          if p.extractor_id]
            ext_join = ", ".join(ext_ids_cs) if ext_ids_cs else "?"
            col = summary_box.column(align=True)
            col.scale_y = 0.85
            col.label(
                text=f"{us_name_cs}  --has_property-->  "
                     f"{us_name_cs}_proxy_geometry")
            col.label(
                text=f"  --has_data_provenance-->  C.N (new)")
            col.label(
                text=f"  <--is_combined_in--  {ext_join}")
            col.label(
                text=f"  <--has_extractor--  {doc_name_cs}")

        # Create button + Clear-all-points relocated: Create lives in
        # the opts_box (above the Pivot prop) and Clear-all-points sits
        # at the bottom of the Step 2 Points box.


classes = [PROXYBOX_PT_main_panel]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
