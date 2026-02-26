"""
XLSX-to-GraphML Wizard Operators for EM-blender-tools

Panel-based 3-step workflow for creating GraphML from Excel data:

Step 1: Convert Stratigraphy XLSX → s3dgraphy Graph (in-memory only)
Step 2: Enrich with Paradata (optional, QualiaImporter on in-memory graph)
Step 3: Export to GraphML file on disk

The graph lives only in memory until Step 3 exports it. Blender lists are
NOT populated here — that happens when the user imports the exported GraphML
through the standard EM import flow (which handles yEd layout attributes etc.).
"""

import bpy  # type: ignore
import os
import random

from ..functions import normalize_path


def _random_epoch_hex_color():
    """Generate a vivid random hex color for epoch nodes."""
    r = random.randint(50, 230)
    g = random.randint(50, 230)
    b = random.randint(50, 230)
    return f"#{r:02X}{g:02X}{b:02X}"


# ──────────────────────────────────────────────────────────────────────
# STEP 1 — Convert Stratigraphy
# ──────────────────────────────────────────────────────────────────────

class XLSX_WIZARD_OT_convert_stratigraphy(bpy.types.Operator):
    """Parse stratigraphy XLSX and create an s3dgraphy graph in memory"""
    bl_idname = "xlsx_wizard.convert_stratigraphy"
    bl_label = "Convert Stratigraphy to Graph"
    bl_description = (
        "Parse the stratigraphy Excel file using the selected mapping "
        "and create the EM graph in memory (not yet exported to GraphML)"
    )
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        em_tools = context.scene.em_tools

        # ── 1. Validate inputs ──
        strat_file = normalize_path(em_tools.xlsx_wizard_strat_file)
        mapping_name = em_tools.xlsx_wizard_mapping.strip()

        if not strat_file or not os.path.exists(strat_file):
            self.report({'ERROR'}, f"Stratigraphy file not found: {strat_file}")
            return {'CANCELLED'}

        if not mapping_name:
            self.report({'ERROR'}, "No mapping name specified")
            return {'CANCELLED'}

        # ── 2. Import s3dgraphy components ──
        try:
            from s3dgraphy.importer.mapped_xlsx_importer import MappedXLSXImporter
            from s3dgraphy.multigraph.multigraph import multi_graph_manager
            from s3dgraphy.nodes.stratigraphic_node import StratigraphicNode
        except ImportError as e:
            self.report({'ERROR'}, f"Failed to import s3dgraphy: {str(e)}")
            return {'CANCELLED'}

        # ── 3. Parse XLSX → Graph ──
        try:
            importer = MappedXLSXImporter(
                filepath=strat_file,
                mapping_name=mapping_name
            )
            graph = importer.parse()
        except FileNotFoundError as e:
            self.report({'ERROR'}, f"Mapping file not found: {str(e)}")
            return {'CANCELLED'}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to parse Excel: {str(e)}")
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}

        # ── 3b. Assign random colors to all generated epochs ──
        for node in graph.nodes:
            if getattr(node, "node_type", None) == "EpochNode":
                epoch_color = _random_epoch_hex_color()
                if hasattr(node, "color"):
                    node.color = epoch_color
                if hasattr(node, "attributes") and isinstance(node.attributes, dict):
                    node.attributes["fill_color"] = epoch_color

        # ── 4. Assign graph_id and register in MultiGraphManager ──
        base_name = os.path.splitext(os.path.basename(strat_file))[0]
        graph_id = f"xlsx_{base_name}"
        graph.graph_id = graph_id

        # Remove previous wizard graph if it exists
        old_graph_id = em_tools.xlsx_wizard_graph_id
        if old_graph_id and old_graph_id in multi_graph_manager.graphs:
            multi_graph_manager.remove_graph(old_graph_id)

        # Also remove if same new id exists
        if graph_id in multi_graph_manager.graphs:
            multi_graph_manager.remove_graph(graph_id)

        multi_graph_manager.graphs[graph_id] = graph

        # ── 5. Save wizard state ──
        em_tools.xlsx_wizard_graph_id = graph_id

        # Collect warnings from Step 1 (reset: new graph, fresh start)
        step1_warnings = list(getattr(graph, 'warnings', []) or [])
        em_tools.xlsx_wizard_warnings = "\n".join(step1_warnings)
        em_tools.xlsx_wizard_show_warnings = True  # auto-open if warnings present

        # Auto-suggest output path if empty
        if not em_tools.xlsx_wizard_output_path:
            input_dir = os.path.dirname(strat_file)
            em_tools.xlsx_wizard_output_path = os.path.join(input_dir, f"{base_name}.graphml")

        # ── Report ──
        strat_nodes = [n for n in graph.nodes if isinstance(n, StratigraphicNode)]
        self.report(
            {'INFO'},
            f"Graph created in memory: {len(strat_nodes)} stratigraphic units, "
            f"{len(graph.nodes)} total nodes, {len(graph.edges)} edges"
        )

        print(f"✅ Wizard Step 1: Graph '{graph_id}' created")
        print(f"   {len(strat_nodes)} stratigraphic units, {len(graph.nodes)} total nodes, {len(graph.edges)} edges")

        return {'FINISHED'}


# ──────────────────────────────────────────────────────────────────────
# STEP 2 — Enrich with Paradata
# ──────────────────────────────────────────────────────────────────────

class XLSX_WIZARD_OT_enrich_paradata(bpy.types.Operator):
    """Enrich the in-memory graph with paradata provenance from em_paradata.xlsx"""
    bl_idname = "xlsx_wizard.enrich_paradata"
    bl_label = "Enrich Graph with Paradata"
    bl_description = (
        "Run QualiaImporter on the in-memory graph to add property nodes "
        "with provenance chains (extractor → document)"
    )
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        em_tools = context.scene.em_tools

        # ── 1. Validate ──
        graph_id = em_tools.xlsx_wizard_graph_id
        if not graph_id:
            self.report({'ERROR'}, "No graph to enrich. Run Step 1 first.")
            return {'CANCELLED'}

        paradata_file = normalize_path(em_tools.xlsx_wizard_paradata_file)
        if not paradata_file or not os.path.exists(paradata_file):
            self.report({'ERROR'}, f"Paradata file not found: {paradata_file}")
            return {'CANCELLED'}

        # ── 2. Get existing graph from memory ──
        try:
            from s3dgraphy import get_graph
        except ImportError as e:
            self.report({'ERROR'}, f"Failed to import s3dgraphy: {str(e)}")
            return {'CANCELLED'}

        graph = get_graph(graph_id)
        if not graph:
            self.report({'ERROR'}, f"Graph '{graph_id}' not found in memory. Re-run Step 1.")
            return {'CANCELLED'}

        nodes_before = len(graph.nodes)

        # ── 3. Run QualiaImporter ──
        try:
            from s3dgraphy.importer.qualia_importer import QualiaImporter
            qualia = QualiaImporter(
                filepath=paradata_file,
                existing_graph=graph,
                overwrite=em_tools.xlsx_wizard_overwrite_properties
            )
            graph = qualia.parse()
        except Exception as e:
            self.report({'ERROR'}, f"Failed to import paradata: {str(e)}")
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}

        # Collect accumulated warnings (Step 1 + Step 2)
        all_warnings = list(getattr(graph, 'warnings', []) or [])
        em_tools.xlsx_wizard_warnings = "\n".join(all_warnings)

        # ── Report ──
        nodes_added = len(graph.nodes) - nodes_before
        self.report(
            {'INFO'},
            f"Paradata enriched: +{nodes_added} nodes added "
            f"({len(graph.nodes)} total nodes, {len(graph.edges)} edges)"
        )

        print(f"✅ Wizard Step 2: Paradata enriched graph '{graph_id}'")
        print(f"   +{nodes_added} nodes added, {len(graph.nodes)} total nodes, {len(graph.edges)} edges")

        return {'FINISHED'}


# ──────────────────────────────────────────────────────────────────────
# STEP 3 — Export GraphML
# ──────────────────────────────────────────────────────────────────────

class XLSX_WIZARD_OT_export_graphml(bpy.types.Operator):
    """Export the in-memory graph to a GraphML file on disk"""
    bl_idname = "xlsx_wizard.export_graphml"
    bl_label = "Export GraphML"
    bl_description = (
        "Save the current graph (with optional paradata) as a GraphML file. "
        "Import the exported file through the standard EM import to populate Blender lists."
    )
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        em_tools = context.scene.em_tools

        # ── 1. Validate ──
        graph_id = em_tools.xlsx_wizard_graph_id
        if not graph_id:
            self.report({'ERROR'}, "No graph to export. Run Step 1 first.")
            return {'CANCELLED'}

        output_path = normalize_path(em_tools.xlsx_wizard_output_path)
        if not output_path:
            self.report({'ERROR'}, "No output path specified")
            return {'CANCELLED'}

        # Ensure .graphml extension
        if not output_path.endswith('.graphml'):
            output_path += '.graphml'

        # Ensure output directory exists
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            self.report({'ERROR'}, f"Output directory not found: {output_dir}")
            return {'CANCELLED'}

        # ── 2. Get graph from memory ──
        try:
            from s3dgraphy import get_graph
            from s3dgraphy.exporter.graphml import GraphMLExporter
        except ImportError as e:
            self.report({'ERROR'}, f"Failed to import s3dgraphy: {str(e)}")
            return {'CANCELLED'}

        graph = get_graph(graph_id)
        if not graph:
            self.report({'ERROR'}, f"Graph '{graph_id}' not found in memory. Re-run Step 1.")
            return {'CANCELLED'}

        # ── 3. Export ──
        try:
            exporter = GraphMLExporter(graph)
            exporter.export(output_path)
        except Exception as e:
            self.report({'ERROR'}, f"Failed to export GraphML: {str(e)}")
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}

        # Collect accumulated warnings (Step 1 + Step 2 + Step 3 — e.g. temporal cycles)
        all_warnings = list(getattr(graph, 'warnings', []) or [])
        em_tools.xlsx_wizard_warnings = "\n".join(all_warnings)

        # ── Report ──
        if all_warnings:
            self.report({'WARNING'}, f"GraphML exported with {len(all_warnings)} warning(s). See Wizard Warnings panel.")
        else:
            self.report({'INFO'}, f"GraphML exported: {output_path}")

        print("=" * 70)
        print("XLSX Wizard — GraphML Export Complete")
        print("=" * 70)
        print(f"  Graph:  {graph_id}")
        print(f"  Output: {output_path}")
        print(f"  Nodes:  {len(graph.nodes)}")
        print(f"  Edges:  {len(graph.edges)}")
        print("=" * 70)
        print("  Import this GraphML through the standard EM import to populate Blender lists.")

        return {'FINISHED'}


# ──────────────────────────────────────────────────────────────────────
# COPY AI PROMPT — Copy extraction prompt to clipboard
# ──────────────────────────────────────────────────────────────────────

class XLSX_WIZARD_OT_copy_ai_prompt(bpy.types.Operator):
    """Copy the AI extraction prompt (Part A + Part B) to clipboard"""
    bl_idname = "xlsx_wizard.copy_ai_prompt"
    bl_label = "Copy AI Prompt to Clipboard"
    bl_description = (
        "Copy the full AI extraction prompt to clipboard, ready to paste "
        "into Claude, ChatGPT, or Gemini alongside your documents"
    )
    bl_options = {'REGISTER'}

    def execute(self, context):
        em_tools = context.scene.em_tools

        # ── 1. Build the prompt via s3dgraphy ──
        try:
            from s3dgraphy import get_ai_prompt
        except ImportError:
            self.report({'ERROR'}, "s3dgraphy package not found or outdated (missing get_ai_prompt)")
            return {'CANCELLED'}

        language = em_tools.xlsx_wizard_prompt_language.strip()

        try:
            full_prompt = get_ai_prompt(language=language if language else None)
        except FileNotFoundError as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
        except ValueError as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to build AI prompt: {str(e)}")
            return {'CANCELLED'}

        # ── 2. Copy to clipboard ──
        bpy.context.window_manager.clipboard = full_prompt

        # ── Report ──
        char_count = len(full_prompt)
        self.report({'INFO'}, f"AI prompt copied to clipboard ({char_count} characters)")
        print(f"✅ AI extraction prompt copied to clipboard ({char_count} chars)")

        return {'FINISHED'}


# ──────────────────────────────────────────────────────────────────────
# Registration
# ──────────────────────────────────────────────────────────────────────

classes = (
    XLSX_WIZARD_OT_convert_stratigraphy,
    XLSX_WIZARD_OT_enrich_paradata,
    XLSX_WIZARD_OT_export_graphml,
    XLSX_WIZARD_OT_copy_ai_prompt,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
