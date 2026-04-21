"""
StratiMiner operators for EM-blender-tools (EM Bridge tab).

Replaces the legacy two-step xlsx wizard (stratigraphy.xlsx +
em_paradata.xlsx) with the unified ``em_data.xlsx`` flow:

* :class:`STRATIMINER_OT_copy_prompt` — copies the StratiMiner
  extraction prompt (v5.4, single file with 5 typed sheets) to the
  clipboard. Accepts a documents folder and optional per-document
  catalog so the AI knows where the PDFs live.
* :class:`STRATIMINER_OT_import_em_data` — Action A: parse an existing
  ``em_data.xlsx``, build the graph in memory, and (optionally)
  immediately export it to a .graphml file. Uses
  ``UnifiedXLSXImporter`` under the hood.

Merge (Action B) is handled by the existing ``em.merge_xlsx_start``
operator in ``merge_conflict_ui.py``, which was updated to detect the
unified schema and delegate to :class:`UnifiedXLSXImporter` when the
input xlsx has the 5-sheet layout.
"""

import os
import bpy  # type: ignore
from bpy.props import StringProperty  # type: ignore

from ..functions import normalize_path


# ──────────────────────────────────────────────────────────────────────
# Copy StratiMiner prompt to clipboard
# ──────────────────────────────────────────────────────────────────────

class STRATIMINER_OT_copy_prompt(bpy.types.Operator):
    """Copy the StratiMiner extraction prompt (v5.4) to clipboard"""
    bl_idname = "stratiminer.copy_prompt"
    bl_label = "Copy StratiMiner Prompt"
    bl_description = (
        "Copy the StratiMiner extraction prompt (v5.4 unified schema) to "
        "the clipboard. Paste it into Claude / ChatGPT / Gemini alongside "
        "the PDFs in the documents folder; the AI will return a single "
        "em_data.xlsx file with 5 typed sheets"
    )
    bl_options = {'REGISTER'}

    def execute(self, context):
        em_tools = context.scene.em_tools

        try:
            from s3dgraphy import get_ai_prompt
        except ImportError:
            self.report({'ERROR'},
                        "s3dgraphy not found or outdated (missing get_ai_prompt)")
            return {'CANCELLED'}

        language = (em_tools.xlsx_wizard_prompt_language or "").strip()
        folder = (em_tools.stratiminer_documents_folder or "").strip()
        in_place = bool(getattr(em_tools, "stratiminer_dosco_in_place", True))
        # When NOT in-place, the target folder takes precedence in what we
        # report to the AI so it knows where the DosCo will end up.
        if not in_place:
            target = (em_tools.stratiminer_dosco_target_folder or "").strip()
            reported_folder = target if target else folder
        else:
            reported_folder = folder

        try:
            prompt = get_ai_prompt(
                language=language if language else None,
                include_validation=em_tools.xlsx_wizard_prompt_validation,
                include_checklist=em_tools.xlsx_wizard_prompt_checklist,
                include_stratigraphy_only=getattr(
                    em_tools, "xlsx_wizard_prompt_stratigraphy_only", False),
                documents_folder=reported_folder if reported_folder else None,
                dosco_in_place=in_place,
                ai_has_filesystem_access=bool(getattr(
                    em_tools, "stratiminer_ai_has_filesystem", True)),
            )
        except FileNotFoundError as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to build prompt: {e}")
            return {'CANCELLED'}

        bpy.context.window_manager.clipboard = prompt
        self.report({'INFO'},
                    f"StratiMiner prompt copied ({len(prompt)} chars)")
        return {'FINISHED'}


# ──────────────────────────────────────────────────────────────────────
# Action A — Import em_data.xlsx as new graph
# ──────────────────────────────────────────────────────────────────────

class STRATIMINER_OT_import_em_data(bpy.types.Operator):
    """Parse em_data.xlsx and optionally export it to a GraphML"""
    bl_idname = "stratiminer.import_em_data"
    bl_label = "Import em_data.xlsx as new graph"
    bl_description = (
        "Action A: parse an em_data.xlsx (5 sheets: Units, Epochs, Claims, "
        "Authors, Documents) via UnifiedXLSXImporter, build an s3dgraphy "
        "graph in memory, and optionally write it out as a GraphML file "
        "ready to open in yEd / reimport with the standard EM flow"
    )
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        em_tools = context.scene.em_tools

        # ── 1. Validate xlsx input ──
        xlsx_path = normalize_path(em_tools.stratiminer_input_xlsx)
        if not xlsx_path or not os.path.exists(xlsx_path):
            self.report({'ERROR'}, f"em_data.xlsx not found: {xlsx_path}")
            return {'CANCELLED'}

        # ── 2. Import + build graph ──
        try:
            from s3dgraphy.importer.unified_xlsx_importer import (
                UnifiedXLSXImporter)
            from s3dgraphy.multigraph.multigraph import multi_graph_manager
        except ImportError as e:
            self.report({'ERROR'}, f"s3dgraphy import failed: {e}")
            return {'CANCELLED'}

        base_name = os.path.splitext(os.path.basename(xlsx_path))[0]
        graph_id = f"stratiminer_{base_name}"
        try:
            importer = UnifiedXLSXImporter(
                filepath=xlsx_path, graph_id=graph_id)
            graph = importer.parse()
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.report({'ERROR'}, f"Failed to parse em_data.xlsx: {e}")
            return {'CANCELLED'}

        # Register in MultiGraphManager so other tools can reach it
        if graph_id in multi_graph_manager.graphs:
            multi_graph_manager.remove_graph(graph_id)
        multi_graph_manager.graphs[graph_id] = graph
        em_tools.stratiminer_active_graph_id = graph_id

        # Collect warnings for the UI
        warnings = list(getattr(graph, 'warnings', []) or [])
        em_tools.xlsx_wizard_warnings = "\n".join(warnings)
        em_tools.xlsx_wizard_show_warnings = bool(warnings)

        # Suggest an output .graphml path if empty. The extension is
        # always appended here; if the user edits the field and omits
        # the extension, the export step below will add it back.
        if not em_tools.stratiminer_output_graphml:
            em_tools.stratiminer_output_graphml = os.path.join(
                os.path.dirname(xlsx_path), f"{base_name}.graphml")

        self.report(
            {'INFO'},
            f"Graph '{graph_id}' built: {importer.stats}"
        )

        # ── 3. Optional export ──
        out_path = normalize_path(em_tools.stratiminer_output_graphml)
        if em_tools.stratiminer_export_on_import and out_path:
            # Force the .graphml extension so yEd / EMtools recognise
            # the file (the Blender file-path field otherwise accepts a
            # bare basename like "TempluMare_ai_v3").
            if not out_path.lower().endswith('.graphml'):
                out_path = out_path.rstrip('.') + '.graphml'
                em_tools.stratiminer_output_graphml = out_path
            # Write-lock pre-flight — abort before rebuilding the graph
            # structure if the target .graphml is held by another process.
            from ..graphml_lock import abort_if_graphml_locked
            if not abort_if_graphml_locked(self, out_path):
                return {'CANCELLED'}
            try:
                from s3dgraphy.exporter.graphml.graphml_exporter import (
                    GraphMLExporter)
                exporter = GraphMLExporter(graph)
                exporter.export(out_path)
                self.report({'INFO'}, f"GraphML exported: {out_path}")
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.report({'ERROR'}, f"GraphML export failed: {e}")
                return {'CANCELLED'}

        return {'FINISHED'}


# ──────────────────────────────────────────────────────────────────────
# Registration
# ──────────────────────────────────────────────────────────────────────

classes = (
    STRATIMINER_OT_copy_prompt,
    STRATIMINER_OT_import_em_data,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass
