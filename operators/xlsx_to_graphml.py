"""
XLSX to GraphML Converter Operator for EM-blender-tools

Converts AI-extracted stratigraphic data from Excel to Extended Matrix GraphML format.
Uses s3dgraphy MappedXLSXImporter + GraphMLExporter pipeline.
"""

import bpy  # type: ignore
from bpy_extras.io_utils import ImportHelper  # type: ignore
import os


class XLSX_OT_to_graphml(bpy.types.Operator, ImportHelper):
    """Convert Excel file with AI-extracted stratigraphic data to GraphML"""
    bl_idname = "xlsx.to_graphml"
    bl_label = "XLSX → GraphML Converter"
    bl_description = "Convert AI-extracted stratigraphic data from Excel to Extended Matrix GraphML format"
    bl_options = {'REGISTER', 'UNDO'}

    # File browser properties
    filename_ext = ".xlsx"
    filter_glob: bpy.props.StringProperty(
        default="*.xlsx",
        options={'HIDDEN'},
        maxlen=255,
    )  # type: ignore

    # Mapping selection
    mapping_name: bpy.props.StringProperty(
        name="Mapping Name",
        description="Name of the mapping configuration (without .json extension)",
        default="excel_to_graphml_mapping"
    )  # type: ignore

    # Output path
    output_name: bpy.props.StringProperty(
        name="Output Filename",
        description="Name for the output GraphML file (without extension)",
        default="output"
    )  # type: ignore

    # Paradata enrichment (optional)
    paradata_filepath: bpy.props.StringProperty(
        name="Paradata File (optional)",
        description="Path to em_paradata.xlsx. Leave empty to skip paradata enrichment",
        default="",
        subtype='FILE_PATH'
    )  # type: ignore

    overwrite_properties: bpy.props.BoolProperty(
        name="Overwrite Existing Properties",
        description="If ON: update duplicate properties. If OFF: skip duplicates with warning",
        default=False
    )  # type: ignore

    def execute(self, context):
        """Execute the XLSX → GraphML conversion."""
        try:
            # Import s3dgraphy components
            from s3dgraphy.importer.mapped_xlsx_importer import MappedXLSXImporter
            from s3dgraphy.exporter.graphml import GraphMLExporter
            from s3dgraphy.nodes.stratigraphic_node import StratigraphicNode
        except ImportError as e:
            self.report({'ERROR'}, f"Failed to import s3dgraphy: {str(e)}")
            return {'CANCELLED'}

        # Get input Excel path
        xlsx_path = self.filepath
        if not os.path.exists(xlsx_path):
            self.report({'ERROR'}, f"Excel file not found: {xlsx_path}")
            return {'CANCELLED'}

        # Determine output path
        input_dir = os.path.dirname(xlsx_path)
        if self.output_name:
            output_filename = f"{self.output_name}.graphml"
        else:
            # Use input filename with .graphml extension
            base_name = os.path.splitext(os.path.basename(xlsx_path))[0]
            output_filename = f"{base_name}.graphml"

        output_path = os.path.join(input_dir, output_filename)

        # Step 1: Load Excel using MappedXLSXImporter
        self.report({'INFO'}, f"Loading Excel: {os.path.basename(xlsx_path)}")

        try:
            importer = MappedXLSXImporter(
                filepath=xlsx_path,
                mapping_name=self.mapping_name
            )
        except Exception as e:
            self.report({'ERROR'}, f"Failed to initialize importer: {str(e)}")
            return {'CANCELLED'}

        # Step 2: Parse Excel → Graph
        self.report({'INFO'}, f"Parsing Excel with mapping: {self.mapping_name}")

        try:
            graph = importer.parse()
        except FileNotFoundError as e:
            self.report({'ERROR'}, f"Mapping file not found: {str(e)}")
            self.report({'INFO'}, "Available mappings: excel_to_graphml_mapping, usm_mapping, pyarchinit_us_mapping")
            return {'CANCELLED'}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to parse Excel: {str(e)}")
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}

        # Count nodes
        strat_nodes = [n for n in graph.nodes if isinstance(n, StratigraphicNode)]
        total_nodes = len(graph.nodes)
        total_edges = len(graph.edges)

        self.report({'INFO'}, f"Graph created: {len(strat_nodes)} stratigraphic units, {total_nodes} total nodes, {total_edges} edges")

        # Step 2b: Optionally enrich with qualia paradata
        if self.paradata_filepath and self.paradata_filepath.strip():
            paradata_path = bpy.path.abspath(self.paradata_filepath)
            if not os.path.exists(paradata_path):
                self.report({'ERROR'}, f"Paradata file not found: {paradata_path}")
                return {'CANCELLED'}

            self.report({'INFO'}, f"Enriching with paradata: {os.path.basename(paradata_path)}")

            try:
                from s3dgraphy.importer.qualia_importer import QualiaImporter
                qualia = QualiaImporter(
                    filepath=paradata_path,
                    existing_graph=graph,
                    overwrite=self.overwrite_properties
                )
                graph = qualia.parse()

                # Update counts after enrichment
                total_nodes = len(graph.nodes)
                total_edges = len(graph.edges)
                self.report({'INFO'}, f"Paradata enriched: {total_nodes} total nodes, {total_edges} edges")

            except Exception as e:
                self.report({'ERROR'}, f"Failed to import paradata: {str(e)}")
                import traceback
                traceback.print_exc()
                return {'CANCELLED'}

        # Step 3: Export Graph → GraphML
        self.report({'INFO'}, f"Exporting to GraphML: {output_filename}")

        try:
            exporter = GraphMLExporter(graph)
            exporter.export(output_path)
        except Exception as e:
            self.report({'ERROR'}, f"Failed to export GraphML: {str(e)}")
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}

        # Success!
        self.report({'INFO'}, f"✓ GraphML exported successfully: {output_path}")

        # Show summary in console
        print("="*70)
        print("XLSX → GraphML Conversion Complete")
        print("="*70)
        print(f"Input:  {xlsx_path}")
        print(f"Output: {output_path}")
        print(f"Stats:  {len(strat_nodes)} stratigraphic units")
        print(f"        {total_nodes} total nodes")
        print(f"        {total_edges} edges")
        print("="*70)

        return {'FINISHED'}

    def draw(self, context):
        """Draw the sidebar panel in the file browser."""
        layout = self.layout
        layout.prop(self, "mapping_name")
        layout.prop(self, "output_name")
        layout.separator()
        layout.label(text="Paradata Enrichment (optional):")
        layout.prop(self, "paradata_filepath")
        layout.prop(self, "overwrite_properties")

    def invoke(self, context, event):
        """Open file browser when operator is invoked."""
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


def register():
    """Register the operator."""
    bpy.utils.register_class(XLSX_OT_to_graphml)


def unregister():
    """Unregister the operator."""
    bpy.utils.unregister_class(XLSX_OT_to_graphml)


if __name__ == "__main__":
    register()
