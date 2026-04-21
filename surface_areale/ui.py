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


class VIEW3D_PT_RMToProxy(Panel):
    """Parent panel for RM-to-Proxy tools (experimental — shipping in EM 1.6)."""
    bl_label = "Representation Model to Proxy (Experimental)"
    bl_idname = "VIEW3D_PT_RMToProxy"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "EM Annotator"
    bl_order = 5

    @classmethod
    def poll(cls, context):
        em_tools = getattr(context.scene, 'em_tools', None)
        if em_tools is None:
            return False
        return getattr(em_tools, 'experimental_features', False)

    def draw_header(self, context):
        layout = self.layout
        icon_id = icons_manager.get_icon_value("RM2Proxy")
        if icon_id:
            layout.label(text="", icon_value=icon_id)
        else:
            layout.label(text="", icon='EXPERIMENTAL')

    def draw(self, context):
        layout = self.layout
        em_tools = context.scene.em_tools

        # Red experimental header row (same pattern as Proxy Inflate Manager)
        header = layout.row()
        header.alert = True
        header.label(text="Surface Areas / RM2Proxy is experimental — EM 1.6 preview",
                     icon='EXPERIMENTAL')

        if em_tools.active_file_index < 0:
            layout.label(text="Load a GraphML first", icon='ERROR')


class VIEW3D_PT_SurfaceAreale(Panel):
    """Surface Areas creation panel with requirement checklist (experimental)."""
    bl_label = "Surface Areas (Experimental)"
    bl_idname = "VIEW3D_PT_SurfaceAreale"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "EM Annotator"
    bl_parent_id = "VIEW3D_PT_RMToProxy"

    @classmethod
    def poll(cls, context):
        return context.scene.em_tools.active_file_index >= 0

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        em_tools = scene.em_tools
        settings = em_tools.surface_areale
        graph = _get_graph_safe(context)
        experimental = getattr(em_tools, 'experimental_features', False)

        all_ok = True  # Track if all requirements are met

        # ── Req 1: RM Status ─────────────────────────────────────────
        from .postprocess import is_mesh_an_rm, find_rm_document

        box = layout.box()
        obj = settings.target_rm
        is_rm, rm_item = is_mesh_an_rm(obj, scene) if obj else (False, None)

        row = box.row()
        row.label(text="1. Representation Model",
                  icon='CHECKMARK' if is_rm else 'X')
        box.prop(settings, "target_rm", text="")

        if obj and not is_rm:
            box.label(text="Promote this mesh in the RM Manager", icon='INFO')
            all_ok = False
        elif not obj:
            all_ok = False

        # ── Req 2-4: Document / Extractor / Property (experimental only) ─
        if experimental:
            # ── Req 2: Document linked to RM ──────────────────────────
            box = layout.box()
            doc_node = None
            has_doc = False

            if is_rm and graph:
                doc_node = find_rm_document(scene, graph, obj)
                has_doc = doc_node is not None

            row = box.row()
            row.label(text="2. Document",
                      icon='CHECKMARK' if has_doc else 'X')

            if has_doc:
                box.label(text=f"{doc_node.name}", icon='FILE')
            elif is_rm:
                box.prop(settings, "create_new_document", text="Create New Document")
                if settings.create_new_document:
                    row = box.row(align=True)
                    row.prop(settings, "new_doc_name", text="Name")
                    row.operator("emtools.suggest_next_doc", text="", icon='ADD')
                    box.prop(settings, "new_doc_date", text="Date")
                    has_doc = bool(settings.new_doc_name)
                else:
                    if hasattr(scene, 'doc_list') and scene.doc_list:
                        box.prop_search(settings, "existing_document",
                                        scene, "doc_list", text="Document")
                    else:
                        box.prop(settings, "existing_document", text="Document")
                    has_doc = bool(settings.existing_document)

            if not has_doc:
                all_ok = False

            # ── Req 3: Extractor ──────────────────────────────────────
            box = layout.box()
            has_extr = bool(settings.extractor_name)
            row = box.row()
            row.label(text="3. Extractor",
                      icon='CHECKMARK' if has_extr else 'X')
            box.prop(settings, "extractor_name", text="Method")
            if not has_extr:
                all_ok = False

            # ── Req 4: Property ───────────────────────────────────────
            box = layout.box()
            has_prop = bool(settings.property_name)
            row = box.row()
            row.label(text="4. Property",
                      icon='CHECKMARK' if has_prop else 'X')
            box.prop(settings, "property_name", text="Name")
            if not has_prop:
                all_ok = False
        else:
            doc_node = None  # Not used in simple mode

        # ── US Target ─────────────────────────────────────────────────
        box = layout.box()
        has_us = False

        row = box.row()
        req_num = "5" if experimental else "2"

        # When the user picks an existing US there is nothing to
        # classify — the US already has its type. The ``us_type`` picker
        # is only meaningful when the operator will create a new US, so
        # it's shown only inside the Create-New branch below.

        if experimental:
            box.prop(settings, "create_new_us", text="Create New US")
            if settings.create_new_us:
                # Type picker is relevant only for NEW US creation.
                box.prop(settings, "us_type", text="Type")
                if settings.us_type == 'GENERIC':
                    has_us = True
                    row.label(text=f"{req_num}. Stratigraphic Unit",
                              icon='CHECKMARK')
                else:
                    r = box.row(align=True)
                    r.prop(settings, "new_us_name", text="Name")
                    r.operator("emtools.suggest_next_us", text="", icon='ADD')
                    has_us = bool(settings.new_us_name)

                    if hasattr(em_tools, 'epochs') and em_tools.epochs.list:
                        box.prop_search(settings, "new_us_epoch",
                                        em_tools.epochs, "list", text="Epoch")

                    # Optional stratigraphic link to an existing US.
                    # When the toggle is on, the user picks direction
                    # (is_after / is_before) and the target US.
                    link_box = box.box()
                    link_box.prop(settings, "add_stratigraphic_link",
                                  text="Add stratigraphic link (optional)")
                    if settings.add_stratigraphic_link:
                        link_box.prop(settings, "link_relation_type",
                                      text="Relation")
                        if hasattr(em_tools, 'stratigraphy') \
                                and em_tools.stratigraphy.units:
                            link_box.prop_search(
                                settings, "link_to_existing_us",
                                em_tools.stratigraphy, "units",
                                text="Target US")
                        else:
                            link_box.prop(settings, "link_to_existing_us",
                                          text="Target US")
            else:
                # Linking to an existing US — no Type picker.
                if hasattr(em_tools, 'stratigraphy') and em_tools.stratigraphy.units:
                    box.prop_search(settings, "linked_us_name",
                                    em_tools.stratigraphy, "units", text="Existing US")
                else:
                    box.prop(settings, "linked_us_name", text="US Name")
                has_us = bool(settings.linked_us_name)
        else:
            # 1.5 baseline — always link to an existing US; no Type picker.
            if hasattr(em_tools, 'stratigraphy') and em_tools.stratigraphy.units:
                box.prop_search(settings, "linked_us_name",
                                em_tools.stratigraphy, "units", text="Existing US")
            else:
                box.prop(settings, "linked_us_name", text="US Name")
            has_us = bool(settings.linked_us_name)

        # Update icon retroactively
        row.label(text=f"{req_num}. Stratigraphic Unit",
                  icon='CHECKMARK' if has_us else 'X')

        if not has_us:
            all_ok = False

        # ── Chain Summary (collapsed) — experimental only ─────────────
        if experimental:
            box = layout.box()
            row = box.row()
            row.prop(settings, "show_chain_summary",
                     icon='TRIA_DOWN' if settings.show_chain_summary else 'TRIA_RIGHT',
                     text="Chain Summary", emboss=False)

            if settings.show_chain_summary:
                us_name = settings.new_us_name if settings.create_new_us else settings.linked_us_name
                doc_name = doc_node.name if doc_node else (settings.new_doc_name or settings.existing_document or "?")
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
    VIEW3D_PT_RMToProxy,
    VIEW3D_PT_SurfaceAreale,
    VIEW3D_PT_SurfaceAreale_Settings,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
