import bpy
from bpy.types import Operator
from bpy.props import StringProperty, BoolProperty
from ..s3Dgraphy.importer.xlsx_importer import XLSXImporter
from ..s3Dgraphy.graph import Graph

class EM_OT_Import3DGISDatabase(Operator):
    """Import 3D GIS database into Extended Matrix"""
    bl_idname = "em.import_3dgis_database"
    bl_label = "Import 3D GIS Database"
    bl_description = "Import stratigraphic units and special finds from 3D GIS database"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        em_tools = scene.em_tools

        if not em_tools.xlsx_3DGIS_database_file:
            self.report({'ERROR'}, "No 3D GIS database file specified")
            return {'CANCELLED'}

        try:
            # Create importer with automatic property creation mode
            importer = XLSXImporter(
                filepath=em_tools.xlsx_3DGIS_database_file,
                id_column="ID",  # Assuming 'ID' is the primary key column
                overwrite=True
            )

            # Parse the file and get the graph
            graph = importer.parse()

            # Display any warnings from the import process
            if importer.warnings:
                for warning in importer.warnings:
                    self.report({'WARNING'}, warning)

            # Store the graph in the scene for later use
            context.scene.em_graph = graph

            # Update UI lists
            bpy.ops.em_tools.populate_lists(graphml_index=em_tools.active_file_index)

            self.report({'INFO'}, f"Successfully imported {len(graph.nodes)} nodes and {len(graph.edges)} edges")
            return {'FINISHED'}

        except Exception as e:
            self.report({'ERROR'}, f"Error importing database: {str(e)}")
            return {'CANCELLED'}

def register():
    bpy.utils.register_class(EM_OT_Import3DGISDatabase)

def unregister():
    bpy.utils.unregister_class(EM_OT_Import3DGISDatabase)