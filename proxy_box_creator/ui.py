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
    """Return the active Stratigraphic Unit's name, or ``""``.

    Prefers ``settings.target_us_name`` when set (ProxyBox's own picker);
    falls back to the Stratigraphy Manager's ``units[units_index]``
    when it isn't.
    """
    settings = context.scene.em_tools.proxy_box
    if settings.target_us_name:
        return settings.target_us_name
    strat = context.scene.em_tools.stratigraphy
    if (not strat.units
            or strat.units_index < 0
            or strat.units_index >= len(strat.units)):
        return ""
    return strat.units[strat.units_index].name or ""


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

        # Active US — drives the proxy mesh name at Create time. The
        # picker writes ``settings.target_us_name`` via ``prop_search``,
        # matching the pattern Surface Areas uses for the same purpose.
        # The active US in the Stratigraphy Manager acts as a fallback
        # when nothing is picked here.
        us_name = _active_us_name(context)
        strat = em_tools.stratigraphy
        if strat.units:
            params_box.prop_search(
                settings, "target_us_name",
                strat, "units",
                text="Active US",
                icon='MOD_EXPLODE')
            if settings.target_us_name:
                params_box.label(
                    text=f"Proxy name → {settings.target_us_name}",
                    icon='OUTLINER_OB_MESH')
            elif us_name:
                params_box.label(
                    text=f"Proxy name → {us_name}  "
                         f"(from Stratigraphy Manager)",
                    icon='OUTLINER_OB_MESH')
            else:
                params_box.label(
                    text="Pick an Active US — the proxy mesh will take "
                         "its name.",
                    icon='ERROR')
        else:
            params_box.label(
                text="No stratigraphic units available.", icon='INFO')

        # ── Create / Clear ───────────────────────────────────────────
        layout.separator()
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
                      and bool(us_name))

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
