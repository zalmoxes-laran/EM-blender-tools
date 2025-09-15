import bpy # type: ignore
from bpy.props import BoolProperty, StringProperty, IntProperty # type: ignore
from ..populate_lists import populate_blender_lists_from_graph, clear_lists
from .importer_xlsx import GenericXLSXImporter
from s3dgraphy import get_graph
from s3dgraphy.importer.pyarchinit_importer import PyArchInitImporter
from s3dgraphy.importer.mapped_xlsx_importer import MappedXLSXImporter

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
            import_type = em_tools.mode_3dgis_import_type
            
            if import_type == "pyarchinit":
                return {
                    'import_type': import_type,
                    'filepath': em_tools.pyarchinit_db_path,
                    'mapping': em_tools.pyarchinit_mapping,
                    'table_name': em_tools.pyarchinit_table,
                    'mode': '3DGIS'
                }
            elif import_type == "generic_xlsx":
                return {
                    'import_type': import_type,
                    'filepath': em_tools.generic_xlsx_file,
                    'sheet_name': em_tools.xlsx_sheet_name,
                    'id_column': em_tools.xlsx_id_column,
                    'mode': '3DGIS'
                }
            elif import_type == "emdb_xlsx":
                return {
                    'import_type': import_type,
                    'filepath': em_tools.emdb_xlsx_file,
                    'mapping': em_tools.emdb_mapping,
                    'mode': '3DGIS'
                }

    def execute(self, context):
        try:
            # Get import settings
            settings = self.get_import_settings(context)
            
            # Create appropriate importer based on type
            if settings['import_type'] == "generic_xlsx":
                importer = GenericXLSXImporter(
                    filepath=settings['filepath'],
                    sheet_name=settings['sheet_name'],
                    id_column=settings['id_column']
                )
                
            elif settings['import_type'] == "emdb_xlsx":
                mapping_name = settings['mapping'] if settings['mapping'] != 'none' else None
                importer = MappedXLSXImporter(
                    filepath=settings['filepath'], 
                    mapping_name=mapping_name,
                    overwrite=True
                )

            elif settings['import_type'] == "pyarchinit":
                mapping_name = f"{settings['mapping']}.json" if settings['mapping'] != 'none' else None
                importer = PyArchInitImporter(
                    filepath=settings['filepath'],
                    mapping_name=mapping_name
                )
            else:
                self.report({'ERROR'}, f"Unknown import type: {settings['import_type']}")
                return {'CANCELLED'}

            # Execute import
            graph = importer.parse()
            importer.display_warnings()

            # *** REGISTRA IL GRAFO NEL SISTEMA S3DGRAPHY ***
            from s3dgraphy.multigraph.multigraph import multi_graph_manager
            from pathlib import Path
            
            filepath = Path(settings['filepath'])
            graph_name = f"{filepath.stem}_{settings['import_type']}"
            
            if not hasattr(graph, 'attributes'):
                graph.attributes = {}
            graph.attributes['graph_code'] = graph_name
            graph.attributes['source_file'] = str(filepath)
            graph.attributes['import_type'] = settings['import_type']
            
            graph.graph_id = graph_name
            multi_graph_manager.graphs[graph_name] = graph
            
            print(f"✅ Grafo '{graph_name}' registrato nel sistema s3dgraphy")
            print(f"✅ Nodi nel grafo: {len(graph.nodes)}")
            print(f"✅ Archi nel grafo: {len(graph.edges)}")
            # *** FINE REGISTRAZIONE ***

            # Handle results based on mode
            if self.auxiliary_mode and settings['parent_graphml']:
                pass
            else:
                clear_lists(context)
                populate_blender_lists_from_graph(context, graph)

            # *** AGGIORNAMENTO VISUAL MANAGER ***
            try:
                if hasattr(bpy.ops, 'visual') and hasattr(bpy.ops.visual, 'update_property_values'):
                    bpy.ops.visual.update_property_values()
                    print("✅ Visual Manager aggiornato")
            except Exception as e:
                print(f"⚠️  Errore aggiornamento Visual Manager: {e}")

            # *** RESET PROPRIETÀ VISUAL MANAGER ***
            try:
                context.scene.selected_property = ""
                # Ottieni le proprietà dal grafo registrato
                from s3dgraphy import get_graph
                registered_graph = get_graph(graph_name)
                if registered_graph and hasattr(registered_graph, 'indices'):
                    available_props = list(registered_graph.indices.get_property_names())
                    if available_props:
                        first_property = sorted(available_props)[0]
                        context.scene.selected_property = first_property
                        print(f"✅ Proprietà Visual Manager impostata su: {first_property}")
                        bpy.ops.visual.update_property_values()
            except Exception as e:
                print(f"⚠️  Errore reset proprietà: {e}")

            # Display warnings
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