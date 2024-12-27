import bpy # type: ignore
from bpy.props import BoolProperty, StringProperty, IntProperty # type: ignore
from ..populate_lists import populate_blender_lists_from_graph, clear_lists
from .importer_xlsx import GenericXLSXImporter
from ..s3Dgraphy import get_graph

class EM_OT_import_3dgis_database(bpy.types.Operator):
    """Import operator for both 3D GIS mode and advanced EM mode"""
    bl_idname = "em.import_3dgis_database"
    bl_label = "Import Database"
    bl_description = "Import data from selected database format"
    bl_options = {'REGISTER', 'UNDO'}

    # Per gestire import da auxiliary files
    auxiliary_mode: BoolProperty(
        name="Auxiliary Mode",
        description="Whether this is an auxiliary file import",
        default=False
    ) # type: ignore
    graphml_index: IntProperty(
        name="GraphML Index",
        description="Index of the parent GraphML file",
        default=-1
    ) # type: ignore
    auxiliary_index: IntProperty(
        name="Auxiliary Index", 
        description="Index of the auxiliary file",
        default=-1
    ) # type: ignore

    def get_import_settings(self, context):
        """Get import settings based on mode"""
        em_tools = context.scene.em_tools

        if self.auxiliary_mode:
            # EM Advanced mode - auxiliary file
            graphml = em_tools.graphml_files[self.graphml_index]
            aux_file = graphml.auxiliary_files[self.auxiliary_index]
            return {
                'import_type': aux_file.file_type,
                'filepath': aux_file.filepath,
                'mapping': aux_file.emdb_mapping if aux_file.file_type == "emdb_xlsx" else None,
                'sheet_name': em_tools.xlsx_sheet_name,
                'id_column': em_tools.xlsx_id_column,
                'parent_graphml': graphml,
                'mode': 'EM_ADVANCED'
            }
        else:
            # 3D GIS mode
            return {
                'import_type': em_tools.mode_3dgis_import_type,
                'filepath': em_tools.generic_xlsx_file,
                'mapping': em_tools.emdb_mapping if em_tools.mode_3dgis_import_type == "emdb_xlsx" else None,
                'sheet_name': em_tools.xlsx_sheet_name,
                'id_column': em_tools.xlsx_id_column,
                'parent_graphml': None,
                'mode': '3DGIS'
            }

    def execute(self, context):
        try:
            settings = self.get_import_settings(context)
            
            # Validate filepath
            if not settings['filepath']:
                self.report({'ERROR'}, "No file path specified")
                return {'CANCELLED'}

            # Create appropriate importer based on type
            if settings['import_type'] == "generic_xlsx":
                importer = GenericXLSXImporter(
                    filepath=settings['filepath'],
                    sheet_name=settings['sheet_name'],
                    id_column=settings['id_column'],
                    mode=settings['mode']
                )
            elif settings['import_type'] == "emdb_xlsx":
                # TODO: Add EMdb XLSX importer
                self.report({'ERROR'}, "EMdb XLSX import not yet implemented")
                return {'CANCELLED'}
            elif settings['import_type'] == "pyarchinit":
                # TODO: Add PyArchInit importer
                self.report({'ERROR'}, "PyArchInit import not yet implemented")
                return {'CANCELLED'}
            else:
                self.report({'ERROR'}, f"Unknown import type: {settings['import_type']}")
                return {'CANCELLED'}

            # Execute import
            graph = importer.parse()
            importer.display_warnings()

            # Handle results based on mode
            if self.auxiliary_mode and settings['parent_graphml']:
                # TODO: Link data to parent GraphML
                pass
            else:
                # Clear and populate Blender lists
                clear_lists(context)
                populate_blender_lists_from_graph(context, graph)

            # Display any warnings
            for warning in importer.warnings:
                self.report({'WARNING'}, warning)

            self.report({'INFO'}, "Import completed successfully")
            return {'FINISHED'}

        except Exception as e:
            self.report({'ERROR'}, f"Import failed: {str(e)}")
            return {'CANCELLED'}

def register():
    bpy.utils.register_class(EM_OT_import_3dgis_database)

def unregister():
    bpy.utils.unregister_class(EM_OT_import_3dgis_database)