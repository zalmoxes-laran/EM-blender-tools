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
    """Main panel for the Proxy Box Creator.

    Nested under the RM to Proxy Suite parent panel (see
    ``rm_to_proxy_suite.py``) — sibling of Surface Areas.
    """
    bl_label = "Proxy Box Creator"
    bl_idname = "PROXYBOX_PT_main_panel"
    bl_parent_id = "VIEW3D_PT_RMToProxySuite"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "EM Annotator"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        if not hasattr(context.scene, 'em_tools'):
            return False
        if getattr(context.scene, 'landscape_mode_active', False):
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

        # Help button (keeps the panel approachable without inflating the UI).
        header_row = layout.row(align=True)
        header_row.label(text="Proxy Box Creator", icon='MESH_CUBE')
        help_op = header_row.operator(
            "em.help_popup", text="", icon='QUESTION')
        help_op.title = "Proxy Box Creator"
        help_op.text = (
            "Step 1: pick an anchor Document from the selected mesh\n"
            "or the catalog. Step 2: record the 7 measurement points\n"
            "(Record per row). The proxy name comes from the active\n"
            "Stratigraphic Unit."
        )
        help_op.url = "panels/proxy_box_creator.html#_Proxy_Box_Creator"
        help_op.project = 'em_tools'

        if em_tools.active_file_index < 0:
            layout.label(text="Load a GraphML first.", icon='ERROR')
            return

        # ── Step 1: Document anchor ──────────────────────────────────
        box = layout.box()
        has_doc = bool(settings.document_node_id)
        row = box.row()
        row.label(
            text="1. Anchor Document",
            icon='CHECKMARK' if has_doc else 'RADIOBUT_OFF')

        if has_doc:
            info_row = box.row(align=True)
            info_row.label(
                text=settings.document_node_name
                     or settings.document_node_id,
                icon='FILE_TEXT')
            info_row.operator(
                "proxybox.pick_from_selected", text="", icon='EYEDROPPER')
            info_row.operator(
                "proxybox.search_document", text="", icon='VIEWZOOM')
            info_row.operator(
                "proxybox.clear_document", text="", icon='X')
            box.prop(settings, "propagate_doc_to_points")
        else:
            pick_row = box.row(align=True)
            pick_row.scale_y = 1.1
            pick_row.operator(
                "proxybox.pick_from_selected",
                text="Pick from selected",
                icon='EYEDROPPER')
            pick_row.operator(
                "proxybox.search_document",
                text="Search...",
                icon='VIEWZOOM')
            box.label(
                text="Selecting a mesh that's already linked to a "
                     "DocumentNode auto-resolves the anchor.",
                icon='INFO')

        # ── Step 2: 7 measurement points ─────────────────────────────
        layout.separator()
        points_box = layout.box()
        recorded_count = sum(1 for p in settings.points[:7]
                             if p.is_recorded)
        header = points_box.row()
        header.label(
            text=f"2. Measurement Points   ({recorded_count}/7)",
            icon='CHECKMARK' if recorded_count == 7 else 'RADIOBUT_OFF')

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

        # ── Parameters ───────────────────────────────────────────────
        layout.separator()
        params_box = layout.box()
        params_box.label(text="Parameters", icon='SETTINGS')

        col = params_box.column(align=True)
        col.prop(settings, "pivot_location", text="Pivot")
        col.prop(settings, "use_proxy_collection")
        col.prop(settings, "persist_after_create", icon='DISK_DRIVE')

        # Active US — two paths, mirroring Surface Areas:
        # - Create new US: toggle on, choose type/name/epoch. A fresh
        #   US is created at Create time and becomes the active one.
        # - Pick existing: ``prop_search`` bound to
        #   ``settings.target_us_name``, which is a computed property
        #   bidirectionally synced with ``strat.units_index`` (picking
        #   here moves the Stratigraphy Manager's active US and vice
        #   versa).
        params_box.prop(settings, "create_new_us")
        strat = em_tools.stratigraphy

        if settings.create_new_us:
            params_box.prop(settings, "new_us_type", text="Type")
            name_row = params_box.row(align=True)
            name_row.prop(settings, "new_us_name", text="Name")
            name_row.operator(
                "proxybox.suggest_next_us", text="", icon='ADD')
            # Toggle governs whether the "+ suggest next" button
            # draws from a per-type sequence (default, e.g. SF.1
            # is suggested even if US.1 exists) or from a shared
            # pool across every stratigraphic type (globally unique
            # numbering).
            params_box.prop(
                settings, "share_numbering_across_types",
                text="Shared numbering across US types")
            # Epoch is mandatory — every US needs a first-epoch
            # anchor. Flag the row visually when still empty so the
            # user sees the requirement without reading the gate msg.
            if hasattr(em_tools, 'epochs') and em_tools.epochs.list:
                epoch_row = params_box.row(align=True)
                epoch_row.alert = not bool(settings.new_us_epoch)
                epoch_row.prop_search(
                    settings, "new_us_epoch",
                    em_tools.epochs, "list", text="Epoch *")
            else:
                params_box.label(
                    text="No epochs defined — create one first.",
                    icon='ERROR')

            # Activity picker (optional). Shared widget — also flags
            # a warning when the picked Activity's epoch differs from
            # the US's.
            from ..us_helpers import draw_activity_picker
            draw_activity_picker(
                params_box, context.scene,
                settings, "new_us_activity",
                epoch_name=settings.new_us_epoch or None,
                text="Activity")
            if settings.new_us_name and settings.new_us_epoch:
                params_box.label(
                    text=f"Proxy name → {settings.new_us_name}",
                    icon='OUTLINER_OB_MESH')
            elif not settings.new_us_name:
                params_box.label(
                    text="Give the new US a name — the proxy mesh "
                         "will take it.",
                    icon='ERROR')
            else:
                params_box.label(
                    text="Pick the new US's first epoch (*).",
                    icon='ERROR')
        else:
            us_name = _active_us_name(context)
            if strat.units:
                params_box.prop_search(
                    settings, "target_us_name",
                    strat, "units",
                    text="Active US",
                    icon='MOD_EXPLODE')
                if us_name:
                    params_box.label(
                        text=f"Proxy name → {us_name}",
                        icon='OUTLINER_OB_MESH')
                else:
                    params_box.label(
                        text="Pick an Active US — the proxy mesh "
                             "will take its name.",
                        icon='ERROR')
            else:
                params_box.label(
                    text="No stratigraphic units yet — toggle "
                         "'Create new US' to add one.",
                    icon='INFO')

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

        # ── Create / Clear ───────────────────────────────────────────
        layout.separator()
        all_recorded = recorded_count == 7
        all_have_doc = all(
            bool(p.source_document) for p in settings.points[:7]) \
            if len(settings.points) >= 7 else False
        all_have_ext = all(
            bool(p.extractor_id) for p in settings.points[:7]) \
            if len(settings.points) >= 7 else False
        # US gate: two paths.
        # - Create-new: requires ``new_us_name`` AND ``new_us_epoch``
        #   (every US must have a first-epoch anchor; no year needed,
        #   but the epoch binding is part of the paradata contract).
        # - Reuse-existing: just needs the currently-active US name.
        if settings.create_new_us:
            has_us = (bool(settings.new_us_name)
                      and bool(settings.new_us_epoch))
        else:
            has_us = bool(_active_us_name(context))

        can_create = (all_recorded
                      and all_have_doc
                      and all_have_ext
                      and has_us)

        row = layout.row()
        row.scale_y = 1.5
        if can_create:
            row.operator(
                "proxybox.create_proxy_enhanced",
                text="Create Proxy",
                icon='ADD')
        else:
            row.enabled = False
            if not all_recorded:
                row.operator(
                    "proxybox.create_proxy_enhanced",
                    text="Record all 7 points first",
                    icon='ERROR')
            elif not all_have_doc:
                row.operator(
                    "proxybox.create_proxy_enhanced",
                    text="Set the anchor document (Step 1)",
                    icon='ERROR')
            elif not all_have_ext:
                row.operator(
                    "proxybox.create_proxy_enhanced",
                    text="Missing extractor ids — re-record with "
                         "Propagate on",
                    icon='ERROR')
            elif settings.create_new_us and not settings.new_us_name:
                row.operator(
                    "proxybox.create_proxy_enhanced",
                    text="Name the new US first",
                    icon='ERROR')
            elif settings.create_new_us and not settings.new_us_epoch:
                row.operator(
                    "proxybox.create_proxy_enhanced",
                    text="Pick the new US's epoch",
                    icon='ERROR')
            else:
                row.operator(
                    "proxybox.create_proxy_enhanced",
                    text="Select the Active US first",
                    icon='ERROR')

        layout.operator(
            "proxybox.clear_all_points",
            text="Clear All Points", icon='X')


classes = [PROXYBOX_PT_main_panel]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
