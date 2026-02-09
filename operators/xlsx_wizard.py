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

from ..functions import normalize_path


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

        # ── Report ──
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

        # ── 1. Locate AI_EXTRACTION_PROMPT.md in s3dgraphy package ──
        try:
            import s3dgraphy
            # s3dgraphy.__file__ = .../src/s3dgraphy/__init__.py
            # We need .../docs/AI_EXTRACTION_PROMPT.md (2 levels up from __file__)
            pkg_dir = os.path.dirname(os.path.dirname(s3dgraphy.__file__))
            prompt_path = os.path.join(pkg_dir, '..', 'docs', 'AI_EXTRACTION_PROMPT.md')
            prompt_path = os.path.normpath(prompt_path)
        except ImportError:
            self.report({'ERROR'}, "s3dgraphy package not found")
            return {'CANCELLED'}

        if not os.path.exists(prompt_path):
            self.report({'ERROR'}, f"AI prompt file not found: {prompt_path}")
            return {'CANCELLED'}

        # ── 2. Read and parse the prompt file ──
        try:
            with open(prompt_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            self.report({'ERROR'}, f"Failed to read prompt file: {str(e)}")
            return {'CANCELLED'}

        # Extract code blocks (text between ``` delimiters)
        blocks = []
        current_block = []
        in_block = False
        for line in content.splitlines():
            if line.strip() == '```':
                if in_block:
                    blocks.append('\n'.join(current_block))
                    current_block = []
                in_block = not in_block
            elif in_block:
                current_block.append(line)

        if len(blocks) < 2:
            self.report({'ERROR'}, "Could not parse prompt blocks from AI_EXTRACTION_PROMPT.md")
            return {'CANCELLED'}

        part_a = blocks[0]  # Core Stratigraphy Extraction
        part_b = blocks[1]  # Paradata Extraction

        # ── 3. Build language instruction ──
        language = em_tools.xlsx_wizard_prompt_language.strip()
        default_lang = "the same as the original document"

        if not language or language.lower() == default_lang.lower():
            lang_instruction = (
                "IMPORTANT: Write all descriptions and properties in the same "
                "language as the original document."
            )
        else:
            lang_instruction = (
                f"IMPORTANT: Write all descriptions and properties in {language}."
            )

        # ── 4. Compose final prompt ──
        full_prompt = (
            f"{lang_instruction}\n\n"
            f"--- PART A: STRATIGRAPHY EXTRACTION ---\n\n"
            f"{part_a}\n\n"
            f"--- PART B: PARADATA EXTRACTION ---\n\n"
            f"{part_b}"
        )

        # ── 5. Copy to clipboard ──
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
