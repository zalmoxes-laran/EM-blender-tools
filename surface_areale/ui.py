"""
UI panels for the Surface Areale system.
Organized under a parent 'RM to Proxy' panel in the EM Annotator tab.
Uses a checklist pattern: all 5 requirements must be green before drawing.
"""

import bpy
from bpy.types import Panel
from .. import icons_manager


def _get_graph_safe(context):
    """Get the active s3dgraphy graph, or None."""
    em_tools = context.scene.em_tools
    if em_tools.active_file_index < 0:
        return None
    try:
        from s3dgraphy import get_graph
        graph_info = em_tools.graphml_files[em_tools.active_file_index]
        return get_graph(graph_info.name)
    except Exception:
        return None


class VIEW3D_PT_SurfaceAreale(Panel):
    """Surface Areas creation panel with a 5-step requirement checklist.

    Top-level panel in the EM Annotator tab (promoted from the former
    RM to Proxy Suite). Sibling of the Proxy Box panel.
    """
    bl_label = "Surface Areas"
    bl_idname = "VIEW3D_PT_SurfaceAreale"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "EM Annotator"
    bl_order = 6
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        em_tools = getattr(context.scene, 'em_tools', None)
        if em_tools is None:
            return False
        if not getattr(em_tools, 'mode_em_advanced', False):
            return False
        return em_tools.active_file_index >= 0

    def draw_header(self, context):
        layout = self.layout
        sa_icon = icons_manager.get_icon_value("surface_area")
        if sa_icon:
            layout.label(text="", icon_value=sa_icon)
        else:
            layout.label(text="", icon='MOD_TRIANGULATE')

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        em_tools = scene.em_tools
        settings = em_tools.surface_areale
        graph = _get_graph_safe(context)

        # The help popup now lives at the end of the extraction-chain
        # row (below) — no standalone header row in the body.
        all_ok = True  # Track if all requirements are met

        # ── Row 1: Mesh → RM → Document (single-line extraction chain)
        # Walks the graph starting from the picked mesh and renders the
        # whole chain inline: status icon + label + object picker +
        # arrow + RM on/off indicator + arrow + document badge with
        # code. Fix actions (promote to RM, pick a document) appear on
        # follow-up rows inside the same box when needed.
        from .postprocess import is_mesh_an_rm, find_rm_document

        obj = settings.target_rm
        is_rm, rm_item = is_mesh_an_rm(obj, scene) if obj else (False, None)
        doc_node = None
        has_doc = False
        if is_rm and graph:
            doc_node = find_rm_document(scene, graph, obj)
            has_doc = doc_node is not None
        if not has_doc and settings.existing_document:
            has_doc = True

        box = layout.box()
        row = box.row(align=True)
        row.label(text="", icon='CHECKMARK' if obj else 'X')
        row.label(text="1. Mesh")
        row.prop(settings, "target_rm", text="")

        # RM on/off indicator — prefer dedicated RM_on/RM_off icons,
        # fall back to the existing show_all_RMs family when those
        # files aren't on disk yet.
        if is_rm:
            rm_badge = icons_manager.get_icon_value("RM_on") or \
                       icons_manager.get_icon_value("show_all_RMs")
        else:
            rm_badge = icons_manager.get_icon_value("RM_off") or \
                       icons_manager.get_icon_value("show_all_RMs_off")
        if rm_badge:
            row.label(text="", icon_value=rm_badge)
        else:
            row.label(text="", icon='MESH_CUBE' if is_rm else 'UNLINKED')

        # Document badge: only show the code when the extraction chain
        # actually found a document in the graph. The manually-picked
        # ``existing_document`` is the fallback used by the chain
        # summary further down; here we want an explicit "no D." so
        # the user sees at a glance that no doc is linked yet.
        doc_icon = icons_manager.get_icon_value("document")
        doc_code = doc_node.name if doc_node else "no D."
        if doc_icon:
            row.label(text=doc_code, icon_value=doc_icon)
        else:
            row.label(text=doc_code, icon='FILE_TEXT')

        # Help popup at the end of the chain row so the user finds it
        # right where the flow starts.
        help_op = row.operator(
            "em.help_popup", text="", icon='QUESTION', emboss=False)
        help_op.title = "Surface Areas"
        help_op.text = (
            "Four-step checklist to link a drawn area on a\n"
            "Representation Model to the extended matrix:\n"
            "  1. pick a mesh → confirm RM → link a Document\n"
            "  2. choose an Extractor method\n"
            "  3. name the Property being measured\n"
            "  4. assign the Stratigraphic Unit\n"
            "Then click Draw to sketch the area on the RM."
        )
        help_op.url = "panels/surface_areale.html#surface-areas"
        help_op.project = 'em_tools'

        # Inline fix rows — only when a step is unmet. Kept inside the
        # same box so the chain reads top-down.
        if not obj:
            hint = box.row()
            hint.enabled = False
            hint.label(
                text="Pick a mesh object to start the extraction chain.",
                icon='INFO')
            all_ok = False
        elif not is_rm:
            # Hint + promote action on the same row. The promote
            # operator registers the mesh in the active RM container.
            fix = box.row(align=True)
            fix.label(
                text="Not an RM — promotes to active container:",
                icon='INFO')
            fix.operator(
                "emtools.surface_areale_promote_to_rm",
                text="Promote", icon='ADD')
            all_ok = False
        elif not has_doc:
            hint = box.row()
            hint.enabled = False
            hint.label(
                text="No Document linked to this RM in the graph.",
                icon='INFO')
            hint = box.row()
            hint.enabled = False
            hint.label(
                text="Pick an existing one or create a new master.",
                icon='BLANK1')
            from ..master_document_helpers import (
                draw_document_picker_with_create_button)
            draw_document_picker_with_create_button(
                box, scene,
                target_owner=settings,
                target_prop_name="existing_document",
                create_new_operator=(
                    "emtools.surface_areale_create_doc"),
                create_new_label="+ Add New Document...",
            )
            has_doc = bool(settings.existing_document)

        if not has_doc:
            all_ok = False

        # ── Req 2: Extractor ────────────────────────────────────────
        # Compact one-line layout: status + number + prop field.
        has_extr = bool(settings.extractor_name)
        ext_box = layout.box()
        ext_row = ext_box.row(align=True)
        ext_row.label(text="", icon='CHECKMARK' if has_extr else 'X')
        ext_row.label(text="2. Extractor")
        ext_row.prop(settings, "extractor_name", text="")
        if not has_extr:
            all_ok = False

        # ── Req 3: Property ─────────────────────────────────────────
        has_prop = bool(settings.property_name)
        prop_box = layout.box()
        prop_row = prop_box.row(align=True)
        prop_row.label(text="", icon='CHECKMARK' if has_prop else 'X')
        prop_row.label(text="3. Property")
        prop_row.prop(settings, "property_name", text="")
        if not has_prop:
            all_ok = False

        # ── Req 4: Stratigraphic Unit ────────────────────────────────
        # Always a single path: pick an existing US from the list, or
        # click ``+`` to launch the shared ``strat.add_us`` dialog.
        has_us = bool(settings.linked_us_name)
        us_box = layout.box()
        us_row = us_box.row(align=True)
        us_row.label(text="", icon='CHECKMARK' if has_us else 'X')
        us_row.label(text="4. SU")
        from ..us_helpers import draw_add_us_button
        if hasattr(em_tools, 'stratigraphy') \
                and em_tools.stratigraphy.units:
            us_row.prop_search(
                settings, "linked_us_name",
                em_tools.stratigraphy, "units",
                text="")
        else:
            us_row.prop(
                settings, "linked_us_name", text="")
        draw_add_us_button(us_row, text="")
        if not has_us:
            all_ok = False

        # ── Chain Summary (collapsed) ─────────────────────────────────
        box = layout.box()
        row = box.row()
        row.prop(settings, "show_chain_summary",
                 icon='TRIA_DOWN' if settings.show_chain_summary else 'TRIA_RIGHT',
                 text="Chain Summary", emboss=False)

        if settings.show_chain_summary:
            us_name = settings.linked_us_name
            doc_name = doc_node.name if doc_node else (settings.existing_document or "?")
            rm_name = obj.name if obj else "?"

            col = box.column(align=True)
            col.scale_y = 0.8
            col.label(text=f"{us_name or '?'} --has_property--> {settings.property_name}")
            col.label(text=f"  --has_data_provenance--> {doc_name}.N")
            col.label(text=f"  --extracted_from--> {doc_name}")
            col.label(text=f"  --has_representation_model--> {rm_name}")

        # ── Draw Button ───────────────────────────────────────────────
        layout.separator()

        if settings.is_drawing:
            row = layout.row(align=True)
            row.alert = True
            row.label(text="Drawing active...", icon='GREASEPENCIL')
            layout.label(text=f"Phase: {settings.drawing_phase}")
            layout.label(text="[B] Whisker | [Enter] Confirm | [Esc] Cancel")
        else:
            row = layout.row(align=True)
            row.scale_y = 1.5
            row.enabled = all_ok
            row.operator("emtools.draw_surface_areale", icon='GREASEPENCIL')


class VIEW3D_PT_SurfaceAreale_Settings(Panel):
    """Advanced settings for Surface Areas"""
    bl_label = "Settings"
    bl_idname = "VIEW3D_PT_SurfaceAreale_Settings"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "EM Annotator"
    bl_parent_id = "VIEW3D_PT_SurfaceAreale"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        settings = context.scene.em_tools.surface_areale

        # Strategy selection with time estimates
        layout.prop(settings, "strategy")

        # LOD controls (only for BOOLEAN or AUTO strategy)
        if settings.strategy in ('BOOLEAN', 'AUTO'):
            col = layout.column(align=True)
            col.prop(settings, "use_lod")
            if settings.use_lod:
                col.prop(settings, "lod_factor")

        # Show time estimates if RM is selected
        if settings.target_rm and settings.target_rm.type == 'MESH':
            poly_count = len(settings.target_rm.data.polygons)
            try:
                from .benchmark import get_strategy_estimates, is_calibrated
                effective_count = poly_count
                if settings.use_lod and settings.lod_factor < 1.0:
                    effective_count = int(poly_count * settings.lod_factor)
                estimates = get_strategy_estimates(effective_count, 100)
                box = layout.box()
                box.scale_y = 0.8
                box.label(text=f"RM: {poly_count:,} polys", icon='INFO')
                if settings.use_lod and settings.lod_factor < 1.0:
                    box.label(text=f"  LOD: {effective_count:,} polys ({settings.lod_factor:.0%})")
                for strat, (t, label) in estimates.items():
                    icon = 'CHECKMARK' if strat == settings.strategy else 'DOT'
                    if settings.strategy == 'AUTO':
                        icon = 'DOT'
                    box.label(text=f"  {strat}: {label}", icon=icon)
                row = box.row()
                if is_calibrated():
                    row.label(text="Calibrated", icon='CHECKMARK')
                else:
                    row.operator("emtools.calibrate_benchmark", icon='TIME')
            except Exception:
                pass

        layout.separator()
        layout.label(text="Geometry:")
        col = layout.column(align=True)
        col.prop(settings, "offset_distance")
        col.prop(settings, "resample_distance")
        col.prop(settings, "max_triangles")
        col.prop(settings, "subdivision_iterations")
        col.prop(settings, "conformity_threshold")

        layout.separator()
        layout.label(text="GP Drawing:")
        col = layout.column(align=True)
        col.prop(settings, "gp_stroke_color", text="Color")
        col.prop(settings, "gp_stroke_thickness", text="Thickness")


classes = [
    VIEW3D_PT_SurfaceAreale,
    VIEW3D_PT_SurfaceAreale_Settings,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
