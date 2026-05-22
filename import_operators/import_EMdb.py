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
from .pyarchinit_geom_importer import import_geometries as _pyarchinit_import_geometries


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
                mapping_name = aux_file.emdb_mapping
            elif aux_file.file_type == "pyarchinit":
                mapping_name = aux_file.pyarchinit_mapping
            else:
                mapping_name = None

            return {
                'import_type': aux_file.file_type,
                'filepath': aux_file.filepath,
                'mapping_name': mapping_name,
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
                settings = {
                    'import_type': import_type,
                    'filepath': em_tools.pyarchinit_db_path,
                    'mapping_name': em_tools.pyarchinit_mapping,
                    'mode': '3DGIS'
                }
                filters = self._collect_pyarchinit_filters(em_tools)
                if filters is None:
                    # Required filter left at "(All values)" — abort
                    # gracefully; the user-facing error has already
                    # been reported.
                    return None
                if filters:
                    settings['filters'] = filters
                return settings
            elif import_type == "generic_xlsx":
                return {
                    'import_type': import_type,
                    'filepath': em_tools.generic_xlsx_file,
                    'sheet_name': em_tools.generic_xlsx_sheet,
                    'id_column': em_tools.xlsx_id_column,
                    'desc_column': em_tools.generic_xlsx_desc_column if em_tools.generic_xlsx_desc_column != "none" else None,
                    'mode': '3DGIS'
                }
            elif import_type == "emdb_xlsx":
                return {
                    'import_type': import_type,
                    'filepath': em_tools.emdb_xlsx_file,
                    'mapping_name': em_tools.emdb_mapping,
                    'mode': '3DGIS'
                }

    def _collect_pyarchinit_filters(self, em_tools):
        """Collect the user-selected filter values into a dict.

        Returns:
            * ``dict`` mapping column -> value for each active slot whose
              user picked a real value (skipped if "(All values)" is
              left and the slot isn't required);
            * ``{}`` if no slot has a value to apply;
            * ``None`` if a required filter was left unselected — in
              that case the operator must abort (an ERROR has been
              reported to the user already).
        """
        filters = {}
        for i in range(1, 6):
            column = em_tools.get(f"pyarchinit_filter_{i}_column", "")
            if not column:
                continue
            value = getattr(em_tools, f"pyarchinit_filter_{i}", '__ALL__')
            required = em_tools.get(
                f"pyarchinit_filter_{i}_required", False
            )
            if value in ('__ALL__', 'NONE', ''):
                if required:
                    label = em_tools.get(
                        f"pyarchinit_filter_{i}_label", column
                    )
                    self.report(
                        {'ERROR'},
                        f"Filter '{label}' is required. Please choose a value.",
                    )
                    return None
                continue
            filters[column] = value
        return filters

    def execute(self, context):
        try:
            # 1. Get import settings
            settings = self.get_import_settings(context)
            if settings is None:
                # Filter validation failed (e.g. required filter empty).
                return {'CANCELLED'}

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
                if not settings.get('mapping_name') or settings['mapping_name'] == 'none':
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
                print(f"EM-tools: Registered graph '3dgis_graph' after import")
                print(f"Nodes in graph: {len(graph.nodes)}")
            
            # 8. METADATA
            self._set_graph_metadata(settings, graph)
            
            # 9. POST-PROCESSING
            result = self._handle_import_results(context, settings, graph)

            if settings.get("import_type") == "pyarchinit" \
               and result == {'FINISHED'}:
                self._maybe_import_pyarchinit_geometries(context, settings, graph)

            return result
            
        except Exception as e:
            self.report({'ERROR'}, f"Import failed: {str(e)}")
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}
    
    def _validate_settings(self, settings):
        """
        Validate import settings using centralized validator.

        Uses the ImportValidator class for consistent, comprehensive validation.
        """
        from .import_validator import ImportValidator

        is_valid, error_msg = ImportValidator.validate(
            settings['import_type'],
            settings
        )

        if not is_valid:
            self.report({'ERROR'}, error_msg)
            return False

        return True
    
    def _clean_3dgis_state(self, context):
        """Clean existing 3DGIS graph and Blender lists"""
        hardcoded_name = "3dgis_graph"
        
        if hardcoded_name in multi_graph_manager.graphs:
            multi_graph_manager.remove_graph(hardcoded_name)
            print(f"EM-tools: Removed existing 3D GIS graph '{hardcoded_name}'")
        
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
            print(f"EM-tools: Using existing graph '{graphml.name}' for EM_ADVANCED")
            return existing_graph
        else:
            # 3DGIS: ritorna None, l'importer creerà il grafo
            print(f"EM-tools: Importer will create new graph for 3DGIS")
            return None
    
    def _create_importer(self, settings, graph_to_use):
        """
        Create appropriate importer using registry pattern.

        This method uses the centralized importer registry, which provides
        automatic parameter validation and importer instantiation.

        Args:
            graph_to_use: Existing graph for EM_ADVANCED, None for 3DGIS

        Returns:
            Configured importer instance, or None on error
        """
        from .importer_registry import create_importer

        try:
            # ✅ ARCHITECTURE: Registry pattern handles all importer creation
            # No need for if/elif chains - registry is self-documenting
            return create_importer(
                import_type=settings['import_type'],
                settings=settings,
                existing_graph=graph_to_use
            )
        except ValueError as e:
            self.report({'ERROR'}, str(e))
            return None
    
    def _set_graph_metadata(self, settings, graph):
        """Set metadata on the graph after import"""
        if not hasattr(graph, 'attributes'):
            graph.attributes = {}
        
        graph.attributes['source_file'] = str(settings['filepath'])
        graph.attributes['import_type'] = settings['import_type']
        
        print(f"EM-tools: Set metadata on graph '{graph.graph_id}'")
    
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

    def _maybe_import_pyarchinit_geometries(self, context, settings, graph):
        em_tools = context.scene.em_tools
        if settings["mode"] == "EM_ADVANCED":
            graphml = em_tools.graphml_files[self.graphml_index]
            aux_file = graphml.auxiliary_files[self.auxiliary_index]
            if not aux_file.pyarchinit_import_geometries:
                return
            db_path = aux_file.filepath
            force_update = aux_file.pyarchinit_geom_force_update
            graph_code = graphml.graph_code
        else:
            if not em_tools.pyarchinit_import_geometries:
                return
            db_path = em_tools.pyarchinit_db_path
            force_update = em_tools.pyarchinit_geom_force_update
            graph_code = "GraphMain"

        from ..functions import show_popup_message

        def show_warning(level, msg):
            icon = 'ERROR' if level == 'ERROR' else 'INFO'
            show_popup_message(context, title=f"Geometry import {level}",
                               message=msg, icon=icon)

        def ask_user(state, centroid, db_srid):
            return self._popup_georef_choice(state, centroid, db_srid)

        report = _pyarchinit_import_geometries(
            context=context,
            db_path=db_path,
            graph=graph,
            graph_code=graph_code,
            force_update=force_update,
            ask_user_callback=ask_user,
            show_warning_callback=show_warning,
            filters=settings.get('filters'),
        )
        self._show_geom_summary(context, report)

    def _popup_georef_choice(self, state, centroid, db_srid):
        """Modal popup. Returns 'AUTO' or 'CANCEL'.

        Stub returning 'AUTO' is acceptable for the first iteration —
        auto-anchor is the recommended path and the user can pre-configure
        em_georef manually if they want to skip. A proper modal dialog can
        land in a follow-up.
        """
        return 'AUTO'

    def _show_geom_summary(self, context, report):
        lines = [
            f"Created:               {report['created']}",
            f"Updated:               {report['updated']}",
            f"Skipped (modified):    {report['skipped_user_modified']}",
            f"Marked orphan (obj):   {report['marked_orphan_obj']}",
            f"Polygon orphans:       {report['polygon_orphans']}",
            f"US without geometry:   {len(report['us_without_geometry'])}",
        ]
        if report["malformed_geometries"]:
            lines.append(
                f"Malformed geometries:  {len(report['malformed_geometries'])}"
            )
        if report["backup_collection"]:
            lines.append(f"Backup collection:     {report['backup_collection']}")

        from ..functions import show_popup_message
        show_popup_message(
            context,
            title="PyArchInit Geometry Import — Summary",
            message="\n".join(lines),
            icon='INFO',
        )


def register():
    bpy.utils.register_class(EM_OT_import_3dgis_database)


def unregister():
    bpy.utils.unregister_class(EM_OT_import_3dgis_database)
