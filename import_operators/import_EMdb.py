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

            if aux_file.file_type == "emdb_xlsx":
                mapping = aux_file.emdb_mapping
            elif aux_file.file_type == "pyarchinit":
                mapping = aux_file.pyarchinit_mapping
            else:
                mapping = None

            return {
                'import_type': aux_file.file_type,
                'filepath': aux_file.filepath,
                'mapping': mapping,
                'sheet_name': em_tools.xlsx_sheet_name,
                'id_column': em_tools.xlsx_id_column,
                'parent_graphml': graphml,
                'resource_folder': aux_file.resource_folder,
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

            # ✅ VALIDAZIONE: pyArchInit richiede sempre un mapping valido
            if settings['import_type'] == "pyarchinit":
                if not settings.get('mapping') or settings['mapping'] == 'none':
                    self.report({'ERROR'}, "pyArchInit import requires a valid mapping. Please select a mapping from the dropdown.")
                    return {'CANCELLED'}
            
            # ✅ VALIDAZIONE: emdb_xlsx richiede sempre un mapping valido
            if settings['import_type'] == "emdb_xlsx":
                if not settings.get('mapping') or settings['mapping'] == 'none':
                    self.report({'ERROR'}, "EMdb Excel import requires a valid mapping. Please select a format from the dropdown.")
                    return {'CANCELLED'}

            # *** PULIZIA AUTOMATICA 3D GIS - SOLO IN EM-TOOLS ***
            if settings['mode'] == '3DGIS':
                from s3dgraphy.multigraph.multigraph import multi_graph_manager
                from ..populate_lists import clear_lists
                
                hardcoded_name = "3dgis_graph"
                
                # Rimuovi il grafo esistente se presente
                if hardcoded_name in multi_graph_manager.graphs:
                    multi_graph_manager.remove_graph(hardcoded_name)
                    print(f"🗑️ EM-tools: Automatically removed existing 3D GIS graph '{hardcoded_name}'")
                
                # Pulisci le liste di Blender
                clear_lists(context)
                print("🧹 EM-tools: Cleared Blender lists for clean 3D GIS import")
            
            # Create appropriate importer based on type
            if settings['import_type'] == "generic_xlsx":
                importer = GenericXLSXImporter(
                    filepath=settings['filepath'],
                    sheet_name=settings['sheet_name'],
                    id_column=settings['id_column']
                )
                            
            elif settings['import_type'] == "emdb_xlsx":
                mapping_name = settings['mapping'] if settings['mapping'] != 'none' else None
                
                # EMtools logic: get existing graph for EM_ADVANCED mode
                existing_graph = None
                if settings['mode'] == 'EM_ADVANCED':
                    # EM_ADVANCED mode: get existing GraphML graph
                    graphml = settings['parent_graphml'] 
                    existing_graph = get_graph(graphml.name)
                    if not existing_graph:
                        self.report({'ERROR'}, f"GraphML graph '{graphml.name}' not found")
                        return {'CANCELLED'}
                    print(f"EMtools: Using existing graph for EM_ADVANCED mode")
                else:
                    print(f"EMtools: Creating new graph for 3DGIS mode")
                
                # s3dgraphy doesn't know about modes, just existing_graph or not
                importer = MappedXLSXImporter(
                    filepath=settings['filepath'], 
                    mapping_name=mapping_name,
                    existing_graph=existing_graph,  # ✅ Generic parameter
                    overwrite=True
                )

            elif settings['import_type'] == "pyarchinit":
                # Stessa logica di emdb_xlsx
                mapping_name = settings['mapping'] if settings['mapping'] != 'none' else None
                
                # Get existing graph for EM_ADVANCED mode
                existing_graph = None
                if settings['mode'] == 'EM_ADVANCED':
                    # EM_ADVANCED mode: get existing GraphML graph
                    graphml = settings['parent_graphml']
                    existing_graph = get_graph(graphml.name)
                    if not existing_graph:
                        self.report({'ERROR'}, f"GraphML graph '{graphml.name}' not found")
                        return {'CANCELLED'}
                    print(f"EMtools: Using existing graph for EM_ADVANCED mode (pyarchinit)")
                else:
                    print(f"EMtools: Creating new graph for 3DGIS mode (pyarchinit)")
                
                # s3dgraphy doesn't know about modes, just existing_graph or not
                importer = PyArchInitImporter(
                    filepath=settings['filepath'],
                    mapping_name=mapping_name,
                    existing_graph=existing_graph,
                    overwrite=True
                )
            else:
                self.report({'ERROR'}, f"Unknown import type: {settings['import_type']}")
                return {'CANCELLED'}


            # Execute import
            graph = importer.parse()
            importer.display_warnings()

            # Se auxiliary mode, aggiorna anche le liste Blender
            if self.auxiliary_mode:
                from ..populate_lists import clear_lists
                clear_lists(context)  # Clear prima del refresh
                populate_blender_lists_from_graph(context, graph)
                self.report({'INFO'}, f"Successfully imported auxiliary data to existing graph")
                return {'FINISHED'}

            # *** REGISTRA IL GRAFO NEL SISTEMA S3DGRAPHY ***
            from s3dgraphy.multigraph.multigraph import multi_graph_manager
            from pathlib import Path
            
            filepath = Path(settings['filepath'])
            
            # Usa nome hardcodato per 3D GIS, altrimenti nome dinamico
            if settings['mode'] == '3DGIS':
                graph_name = "3dgis_graph"
                print(f"EM-tools: Using hardcoded graph name for 3D GIS: '{graph_name}'")
            else:
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
                # Populate Blender lists from the imported graph
                populate_blender_lists_from_graph(context, graph)  # ← ORDINE CORRETTO

            self.report({'INFO'}, f"Successfully imported {len(graph.nodes)} nodes from {settings['import_type']}")
            return {'FINISHED'}

        except Exception as e:
            self.report({'ERROR'}, f"Import failed: {str(e)}")
            return {'CANCELLED'}

    def _clean_3dgis_graph(self, context):
        """Pulisce completamente il grafo 3D GIS esistente - SOLO EM-TOOLS"""
        from s3dgraphy.multigraph.multigraph import multi_graph_manager
        from ..populate_lists import clear_lists
        
        hardcoded_name = "3dgis_graph"
        
        if hardcoded_name in multi_graph_manager.graphs:
            # Rimuovi il grafo esistente
            multi_graph_manager.remove_graph(hardcoded_name)
            print(f"🗑️ EM-tools: Removed existing 3D GIS graph '{hardcoded_name}'")
            
            # Pulisci le liste di Blender - PASSA CONTEXT
            clear_lists(context)
            print("🧹 EM-tools: Cleared Blender lists for clean 3D GIS import")
        else:
            print(f"ℹ️ EM-tools: No existing 3D GIS graph to clean")

def register():
    bpy.utils.register_class(EM_OT_import_3dgis_database)

def unregister():
    bpy.utils.unregister_class(EM_OT_import_3dgis_database)