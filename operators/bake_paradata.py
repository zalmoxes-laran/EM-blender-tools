"""
Bake Paradata into GraphML Operator for EM-blender-tools

Loads an existing GraphML file, enriches it with qualia paradata from
em_paradata.xlsx, and re-exports the GraphML with embedded provenance chains.

Flow:
    [user selects .graphml] -> GraphMLImporter -> Graph in memory
                             -> QualiaImporter(em_paradata.xlsx) -> enriches Graph
                             -> GraphMLExporter -> overwrites .graphml
"""

import bpy  # type: ignore
from bpy_extras.io_utils import ImportHelper  # type: ignore
import os


class PARADATA_OT_bake(bpy.types.Operator, ImportHelper):
    """Bake qualia paradata into an existing GraphML file"""
    bl_idname = "paradata.bake_to_graphml"
    bl_label = "Bake Paradata into GraphML"
    bl_description = (
        "Load an existing GraphML, enrich it with paradata from em_paradata.xlsx, "
        "and re-export the GraphML with embedded provenance chains"
    )
    bl_options = {'REGISTER', 'UNDO'}

    # File browser opens .graphml files
    filename_ext = ".graphml"
    filter_glob: bpy.props.StringProperty(
        default="*.graphml",
        options={'HIDDEN'},
        maxlen=255,
    )  # type: ignore

    # Paradata file path
    paradata_filepath: bpy.props.StringProperty(
        name="Paradata File",
        description="Path to em_paradata.xlsx with qualia provenance data",
        default="",
        subtype='FILE_PATH'
    )  # type: ignore

    # Overwrite toggle
    overwrite_properties: bpy.props.BoolProperty(
        name="Overwrite Existing Properties",
        description="If ON: update duplicate properties. If OFF: skip duplicates with warning",
        default=False
    )  # type: ignore

    def execute(self, context):
        """Execute the Bake Paradata pipeline."""
        # Validate inputs
        graphml_path = self.filepath
        if not os.path.exists(graphml_path):
            self.report({'ERROR'}, f"GraphML file not found: {graphml_path}")
            return {'CANCELLED'}

        if not self.paradata_filepath or not self.paradata_filepath.strip():
            self.report({'ERROR'}, "No paradata file specified. Please select an em_paradata.xlsx file.")
            return {'CANCELLED'}

        paradata_path = bpy.path.abspath(self.paradata_filepath)
        if not os.path.exists(paradata_path):
            self.report({'ERROR'}, f"Paradata file not found: {paradata_path}")
            return {'CANCELLED'}

        # Step 1: Import existing GraphML -> Graph
        self.report({'INFO'}, f"Loading GraphML: {os.path.basename(graphml_path)}")

        try:
            from s3dgraphy.importer.import_graphml import GraphMLImporter
            graphml_importer = GraphMLImporter(graphml_path)
            graph = graphml_importer.parse()
        except ImportError as e:
            self.report({'ERROR'}, f"Failed to import s3dgraphy: {str(e)}")
            return {'CANCELLED'}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to load GraphML: {str(e)}")
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}

        nodes_before = len(graph.nodes)
        edges_before = len(graph.edges)
        self.report({'INFO'}, f"GraphML loaded: {nodes_before} nodes, {edges_before} edges")

        # Step 2: Enrich with qualia paradata
        self.report({'INFO'}, f"Enriching with paradata: {os.path.basename(paradata_path)}")

        try:
            from s3dgraphy.importer.qualia_importer import QualiaImporter
            qualia = QualiaImporter(
                filepath=paradata_path,
                existing_graph=graph,
                overwrite=self.overwrite_properties
            )
            graph = qualia.parse()
        except Exception as e:
            self.report({'ERROR'}, f"Failed to import paradata: {str(e)}")
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}

        nodes_after = len(graph.nodes)
        edges_after = len(graph.edges)
        self.report({'INFO'},
            f"Paradata enriched: +{nodes_after - nodes_before} nodes, "
            f"+{edges_after - edges_before} edges"
        )

        # Step 3: Re-export GraphML (overwrites original)
        self.report({'INFO'}, f"Re-exporting GraphML: {os.path.basename(graphml_path)}")

        try:
            from s3dgraphy.exporter.graphml import GraphMLExporter
            exporter = GraphMLExporter(graph)
            exporter.export(graphml_path)
        except Exception as e:
            self.report({'ERROR'}, f"Failed to export GraphML: {str(e)}")
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}

        # Success!
        self.report({'INFO'}, f"Paradata baked successfully into: {graphml_path}")

        # Show summary in console
        print("="*70)
        print("Bake Paradata into GraphML - Complete")
        print("="*70)
        print(f"GraphML: {graphml_path}")
        print(f"Paradata: {paradata_path}")
        print(f"Before:  {nodes_before} nodes, {edges_before} edges")
        print(f"After:   {nodes_after} nodes, {edges_after} edges")
        print(f"Added:   +{nodes_after - nodes_before} nodes, +{edges_after - edges_before} edges")
        print(f"Mode:    {'overwrite' if self.overwrite_properties else 'skip duplicates'}")
        print("="*70)

        return {'FINISHED'}

    def draw(self, context):
        """Draw the sidebar panel in the file browser."""
        layout = self.layout
        layout.label(text="Paradata Source:")
        layout.prop(self, "paradata_filepath")
        layout.separator()
        layout.label(text="Options:")
        layout.prop(self, "overwrite_properties")

    def invoke(self, context, event):
        """Open file browser when operator is invoked."""
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


def register():
    """Register the operator."""
    bpy.utils.register_class(PARADATA_OT_bake)


def unregister():
    """Unregister the operator."""
    bpy.utils.unregister_class(PARADATA_OT_bake)


if __name__ == "__main__":
    register()
