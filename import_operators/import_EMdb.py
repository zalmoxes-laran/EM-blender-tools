# import_operators/import_EMdb.py

import bpy # type: ignore
from bpy.props import BoolProperty, StringProperty, IntProperty # type: ignore
import io
import contextlib
from ..populate_lists import populate_blender_lists_from_graph, clear_lists
from .importer_xlsx import GenericXLSXImporter
from s3dgraphy import get_graph, Graph
from s3dgraphy.importer.pyarchinit_importer import PyArchInitImporter
from s3dgraphy.importer.mapped_xlsx_importer import MappedXLSXImporter
from s3dgraphy.multigraph.multigraph import multi_graph_manager


class EM_OT_import_3dgis_database(bpy.types.Operator):
    """Import operator for both 3D GIS mode and advanced EM mode"""
    bl_idname = "em.import_3dgis_database"
    bl_label = "Import Database"
    bl_description = "Import data from selected database format"
    bl_options = {'REGISTER', 'UNDO'}

    # Properties for auxiliary files
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
            # 1. Get import settings
            settings = self.get_import_settings(context)

            # ✅ VALIDAZIONE PREVENTIVA PER AUXILIARY MODE
            if self.auxiliary_mode:
                em_tools = context.scene.em_tools
                graphml = em_tools.graphml_files[self.graphml_index]
                
                # Verifica se il grafo è già caricato
                from s3dgraphy import get_graph
                existing_graph = get_graph(graphml.name)
                
                if not existing_graph:
                    # ✅ POPUP ELEGANTE
                    from ..functions import show_popup_message
                    show_popup_message(
                        context,
                        title="GraphML Not Loaded",
                        message=f"The GraphML file '{graphml.graph_code}' must be loaded first.\n\n"
                                f"Steps:\n"
                                f"1. Go to 'GraphML List' section above\n"
                                f"2. Click the Import button (↓) next to '{graphml.graph_code}'\n"
                                f"3. Then retry importing this auxiliary file",
                        icon='ERROR'
                    )
                    return {'FINISHED'}

            # ✅ VALIDAZIONE: pyArchInit richiede sempre un mapping valido
            if settings['import_type'] == "pyarchinit":
                if not settings.get('mapping') or settings['mapping'] == 'none':
                    self.report({'ERROR'}, "pyArchInit import requires a valid mapping. Please select a mapping from the dropdown.")
                    return {'CANCELLED'}

            # 2. VALIDAZIONE
            if not self._validate_settings(settings):
                return {'CANCELLED'}
            
            # 3. PULIZIA (solo per 3DGIS)
            if settings['mode'] == '3DGIS':
                self._clean_3dgis_state(context)
            
            # 4. PREPARAZIONE GRAFO
            # ✅ Per EM_ADVANCED: ritorna grafo esistente
            # ✅ Per 3DGIS: ritorna None (importer lo creerà)
            graph_to_use = self._prepare_graph(settings)
            if settings['mode'] == 'EM_ADVANCED' and not graph_to_use:
                return {'CANCELLED'}
            
            # 5. CREAZIONE IMPORTER
            importer = self._create_importer(settings, graph_to_use)
            if not importer:
                return {'CANCELLED'}
            
            # 6. IMPORT
            captured_output = io.StringIO()
            with contextlib.redirect_stdout(captured_output), contextlib.redirect_stderr(captured_output):
                graph = importer.parse()
                importer.display_warnings()

            # Filtra log troppo verbosi (es. nodi mancanti in grafo esistente)
            noisy_tokens = [
                "not found in existing graph - SKIPPED",
                "Processing pyArchInit row",
                "Node name from DB:",
                "Enriching existing graph:",
            ]
            for line in captured_output.getvalue().splitlines():
                if any(tok in line for tok in noisy_tokens):
                    continue
                if line.strip():
                    print(line)
            
            # 7. REGISTRAZIONE GRAFO (solo per 3DGIS, dopo l'import)
            if settings['mode'] == '3DGIS':
                graph.graph_id = "3dgis_graph"
                multi_graph_manager.graphs["3dgis_graph"] = graph
                print(f"✅ EM-tools: Registered graph '3dgis_graph' after import")
                print(f"✅ Nodes in graph: {len(graph.nodes)}")
            
            # 8. METADATA
            self._set_graph_metadata(settings, graph)
            
            # 9. POST-PROCESSING
            return self._handle_import_results(context, settings, graph)
            
        except Exception as e:
            self.report({'ERROR'}, f"Import failed: {str(e)}")
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}
    
    def _validate_settings(self, settings):
        """Validate import settings"""
        if settings['import_type'] in ["pyarchinit", "emdb_xlsx"]:
            if not settings.get('mapping') or settings['mapping'] == 'none':
                self.report({'ERROR'}, f"{settings['import_type']} import requires a valid mapping. Please select a mapping from the dropdown.")
                return False
        return True
    
    def _clean_3dgis_state(self, context):
        """Clean existing 3DGIS graph and Blender lists"""
        hardcoded_name = "3dgis_graph"
        
        if hardcoded_name in multi_graph_manager.graphs:
            multi_graph_manager.remove_graph(hardcoded_name)
            print(f"🗑️ EM-tools: Removed existing 3D GIS graph '{hardcoded_name}'")
        
        clear_lists(context)
        print("🧹 EM-tools: Cleared Blender lists for clean 3D GIS import")
    
    def _prepare_graph(self, settings):
        """
        Prepare graph for import based on mode.
        
        Returns:
            - For EM_ADVANCED: existing graph from GraphML
            - For 3DGIS: None (importer will create it)
        """
        if settings['mode'] == 'EM_ADVANCED':
            # EM_ADVANCED: recupera grafo esistente
            graphml = settings['parent_graphml']
            existing_graph = get_graph(graphml.name)
            if not existing_graph:
                self.report({'ERROR'}, f"GraphML graph '{graphml.name}' not found")
                return None
            print(f"✅ EM-tools: Using existing graph '{graphml.name}' for EM_ADVANCED")
            return existing_graph
        else:
            # 3DGIS: ritorna None, l'importer creerà il grafo
            print(f"✅ EM-tools: Importer will create new graph for 3DGIS")
            return None
    
    def _create_importer(self, settings, graph_to_use):
        """
        Create appropriate importer.
        
        Args:
            graph_to_use: Existing graph for EM_ADVANCED, None for 3DGIS
        """
        import_type = settings['import_type']
        
        if import_type == "generic_xlsx":
            # ⚠️ GenericXLSXImporter va refactorato in futuro
            # Per ora manteniamo comportamento attuale
            return GenericXLSXImporter(
                filepath=settings['filepath'],
                sheet_name=settings['sheet_name'],
                id_column=settings['id_column'],
                mode=settings['mode']
            )
        
        elif import_type == "emdb_xlsx":
            mapping_name = settings['mapping'] if settings['mapping'] != 'none' else None
            
            # ✅ Passa graph_to_use: None per 3DGIS, grafo esistente per EM_ADVANCED
            return MappedXLSXImporter(
                filepath=settings['filepath'],
                mapping_name=mapping_name,
                existing_graph=graph_to_use,  # None per 3DGIS, grafo per EM_ADVANCED
                overwrite=True
            )
        
        elif import_type == "pyarchinit":
            mapping_name = settings['mapping'] if settings['mapping'] != 'none' else None
            
            # ✅ Passa graph_to_use: None per 3DGIS, grafo esistente per EM_ADVANCED
            return PyArchInitImporter(
                filepath=settings['filepath'],
                mapping_name=mapping_name,
                existing_graph=graph_to_use,  # None per 3DGIS, grafo per EM_ADVANCED
                overwrite=True
            )
        
        else:
            self.report({'ERROR'}, f"Unknown import type: {import_type}")
            return None
    
    def _set_graph_metadata(self, settings, graph):
        """Set metadata on the graph after import"""
        if not hasattr(graph, 'attributes'):
            graph.attributes = {}
        
        graph.attributes['source_file'] = str(settings['filepath'])
        graph.attributes['import_type'] = settings['import_type']
        
        print(f"✅ EM-tools: Set metadata on graph '{graph.graph_id}'")
    
    def _handle_import_results(self, context, settings, graph):
        """Handle post-import processing"""
        if self.auxiliary_mode:
            # ✅ FIXED: In auxiliary mode NON fare populate_lists qui!
            # Il populate verrà fatto UNA SOLA VOLTA alla fine dell'import del GraphML
            # in importer_graphml.py:126 dopo che tutti i file ausiliari sono stati importati.
            # Questo evita duplicazione delle epoche e altri elementi nelle liste.
            self.report({'INFO'}, "Successfully imported auxiliary data to existing graph")
        else:
            # Normal mode: populate lists
            populate_blender_lists_from_graph(context, graph)
            self.report({'INFO'}, f"Successfully imported {len(graph.nodes)} nodes from {settings['import_type']}")

        return {'FINISHED'}


def register():
    bpy.utils.register_class(EM_OT_import_3dgis_database)


def unregister():
    bpy.utils.unregister_class(EM_OT_import_3dgis_database)
