# import_operators/import_EMdb.py

import bpy # type: ignore
from bpy.props import IntProperty # type: ignore
import io
import contextlib
from s3dgraphy import get_graph
from .pyarchinit_geom_importer import import_geometries as _pyarchinit_import_geometries


class _TableImport:
    """What the two gestures share: the pyArchInit connection and filters,
    the importer, the provenance, the geometries (Enzo Cocca's reader,
    `pyarchinit_geom_importer`, called unchanged)."""

    def _resolve_pyarchinit_db_spec(self, em_tools):
        """Resolve the pyArchInit connection spec from the panel.

        Returns ``(db_spec, error)``:

        * ``db_spec`` — a SQLite file path (SQLite mode) or a
          ``postgresql+psycopg2://…`` URL (PostgreSQL mode), suitable
          for both PyArchInitImporter and the geometry reader.
        * ``error`` — None on success, or a user-facing message when the
          chosen mode is missing required fields.

        The password is read from the (SKIP_SAVE) password field if the
        user just typed it, otherwise from the OS keychain — never from
        the .blend (issue #27). Delegates to the shared resolver so the
        import and export paths stay in sync.
        """
        from .pyarchinit_connection import resolve_db_spec
        return resolve_db_spec(em_tools)

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

    def _validate_settings(self, settings):
        """Validate import settings using the centralized validator."""
        from .import_validator import ImportValidator

        is_valid, error_msg = ImportValidator.validate(
            settings['import_type'],
            settings
        )
        if not is_valid:
            self.report({'ERROR'}, error_msg)
            return False
        return True

    def _create_importer(self, settings, graph_to_use):
        """The importer of the registry: the existing graph to enrich, or
        None for a new graph."""
        from .importer_registry import create_importer
        try:
            importer = create_importer(
                import_type=settings['import_type'],
                settings=settings,
                existing_graph=graph_to_use
            )
            # the rule that names the US, for the geometries to find them (N1)
            mapping = getattr(importer, "mapping", None) or {}
            self._name_template = (mapping.get("table_settings") or {}).get("node_name_template")
            return importer
        except ValueError as e:
            self.report({'ERROR'}, str(e))
            return None

    def _parse(self, importer):
        """Run the importer with its chatter filtered."""
        captured_output = io.StringIO()
        with contextlib.redirect_stdout(captured_output), contextlib.redirect_stderr(captured_output):
            graph = importer.parse()
            importer.display_warnings()
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
        return graph

    def _set_graph_metadata(self, settings, graph):
        """Set metadata on the graph after import"""
        if not hasattr(graph, 'attributes'):
            graph.attributes = {}
        # A pyArchInit import may carry a connection_url instead of a
        # filepath; redact credentials before recording provenance so a
        # PostgreSQL password never lands in the graph / .blend (#27).
        source = settings.get('filepath')
        if source is None and settings.get('connection_url'):
            from .pyarchinit_db_reader import redacted_db_spec
            source = redacted_db_spec(settings['connection_url'])
        graph.attributes['source_file'] = str(source or '')
        graph.attributes['import_type'] = settings['import_type']

    def _import_geometries(self, context, db_path, graph, graph_code, force_update, filters):
        from ..functions import show_popup_message

        def show_warning(level, msg):
            icon = 'ERROR' if level == 'ERROR' else 'INFO'
            if bpy.app.background:
                print(f"[geometry import] {level}: {msg}")
                return
            show_popup_message(context, title=f"Geometry import {level}",
                               message=msg, icon=icon)

        # N1 · the US keep the label of the mapping (area.settore.tipoNumero)
        # and the reader finds them through the adapter, its own code unchanged
        from .pyarchinit_us_adapter import resolving_us_by_label
        with resolving_us_by_label(db_path, getattr(self, "_name_template", None),
                                   filters) as resolver:
            report = _pyarchinit_import_geometries(
                context=context,
                db_path=db_path,
                graph=graph,
                graph_code=graph_code,
                force_update=force_update,
                show_warning_callback=show_warning,
                filters=filters,
            )
        if resolver is not None:
            report["matched_by"] = {k: list(resolver.how.values()).count(k)
                                    for k in ("uuid", "label", "bare", "orphan")}
        self._show_geom_summary(context, report)
        return report

    def _show_geom_summary(self, context, report):
        lines = [
            f"Created:               {report['created']}",
            f"Updated:               {report['updated']}",
            f"Skipped (modified):    {report['skipped_user_modified']}",
            f"Marked orphan (obj):   {report['marked_orphan_obj']}",
            f"Polygon orphans:       {report['polygon_orphans']}",
            f"US without geometry:   {len(report['us_without_geometry'])}",
        ]
        if report.get("matched_by"):
            m = report["matched_by"]
            lines.append(f"Matched by UUID/label/number: {m['uuid']}/{m['label']}/{m['bare']} "
                         f"(keys; {m['orphan']} without US)")
        if report["malformed_geometries"]:
            lines.append(
                f"Malformed geometries:  {len(report['malformed_geometries'])}"
            )
        if report["backup_collection"]:
            lines.append(f"Backup collection:     {report['backup_collection']}")
        if bpy.app.background:
            print("[geometry import] " + " · ".join(x.strip() for x in lines))
            return
        from ..functions import show_popup_message
        show_popup_message(
            context,
            title="PyArchInit Geometry Import — Summary",
            message="\n".join(lines),
            icon='INFO',
        )


class EM_OT_import_auxiliary_table(_TableImport, bpy.types.Operator):
    """Enrich a graph already loaded with a table (EMdb Excel or pyArchInit)
    attached to it as an auxiliary file"""
    bl_idname = "em.import_auxiliary_table"
    bl_label = "Import the auxiliary table"
    bl_description = "Enrich the graph it is attached to with this table"
    bl_options = {'REGISTER', 'UNDO'}

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
        """The auxiliary file's settings."""
        em_tools = context.scene.em_tools
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
        }

    def execute(self, context):
        try:
            settings = self.get_import_settings(context)
            em_tools = context.scene.em_tools
            graphml = em_tools.graphml_files[self.graphml_index]
            existing_graph = get_graph(graphml.name)
            if not existing_graph:
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
            if settings['import_type'] == "pyarchinit":
                if not settings.get('mapping_name') or settings['mapping_name'] == 'none':
                    self.report({'ERROR'}, "pyArchInit import requires a valid mapping. Please select a mapping from the dropdown.")
                    return {'CANCELLED'}
            if not self._validate_settings(settings):
                return {'CANCELLED'}
            importer = self._create_importer(settings, existing_graph)
            if not importer:
                return {'CANCELLED'}
            graph = self._parse(importer)
            self._set_graph_metadata(settings, graph)
            # the lists are populated ONCE, at the end of the graph's import
            # (importer_graphml), after every auxiliary file
            self.report({'INFO'}, "Successfully imported auxiliary data to existing graph")
            if settings["import_type"] == "pyarchinit":
                aux_file = graphml.auxiliary_files[self.auxiliary_index]
                if aux_file.pyarchinit_import_geometries:
                    self._import_geometries(context, aux_file.filepath, graph, graphml.graph_code,
                                            aux_file.pyarchinit_geom_force_update, settings.get('filters'))
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Import failed: {str(e)}")
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}



def _random_epoch_hex_color():
    """A vivid colour for an epoch the table gave none (the xlsx wizard's)."""
    import random
    return "#{:02X}{:02X}{:02X}".format(*(random.randint(50, 230) for _ in range(3)))


class _TableFromPanel(_TableImport):
    """The table as the panel describes it (Import from tables and Re-import
    a table share the same fields)."""

    def settings(self, context):
        em_tools = context.scene.em_tools
        kind = em_tools.table_import_type
        if kind == "pyarchinit":
            from .pyarchinit_db_reader import is_postgres_spec
            db_spec, err = self._resolve_pyarchinit_db_spec(em_tools)
            if err:
                self.report({'ERROR'}, err)
                return None
            out = {'import_type': kind, 'mapping_name': em_tools.pyarchinit_mapping, 'db_spec': db_spec}
            if is_postgres_spec(db_spec):
                out['connection_url'] = db_spec
            else:
                out['filepath'] = db_spec
            filters = self._collect_pyarchinit_filters(em_tools)
            if filters is None:
                return None
            if filters:
                out['filters'] = filters
            return out
        if kind == "generic_xlsx":
            return {'import_type': kind, 'filepath': bpy.path.abspath(em_tools.generic_xlsx_file),
                    'sheet_name': em_tools.generic_xlsx_sheet, 'id_column': em_tools.xlsx_id_column,
                    'desc_column': em_tools.generic_xlsx_desc_column
                    if em_tools.generic_xlsx_desc_column != "none" else None}
        return {'import_type': "emdb_xlsx", 'filepath': bpy.path.abspath(em_tools.emdb_xlsx_file),
                'mapping_name': em_tools.emdb_mapping}


class EM_OT_import_from_table(_TableFromPanel, bpy.types.Operator):
    """A new graph from a table — an Excel read through a mapping, an Excel
    sheet, a pyArchInit database (SQLite or PostgreSQL, with its filters) —
    saved as em.json and listed with the other graphs; for pyArchInit, the
    US geometries too when asked"""
    bl_idname = "em.import_from_table"
    bl_label = "Import from tables"
    bl_description = ("A new graph from a table (Excel with a mapping, an Excel sheet, pyArchInit), "
                      "saved as em.json beside the table and listed with the other graphs")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        import os
        import uuid
        from .table_naming import emjson_path_for, graph_code_for
        em_tools = context.scene.em_tools
        try:
            settings = self.settings(context)
            if settings is None:
                return {'CANCELLED'}
            if settings['import_type'] == "pyarchinit" and settings.get('mapping_name') in (None, "", "none"):
                self.report({'ERROR'}, "pyArchInit needs a mapping: choose one")
                return {'CANCELLED'}
            if not self._validate_settings(settings):
                return {'CANCELLED'}
            source = settings.get('filepath') or settings.get('connection_url') or ""
            code = graph_code_for(settings['import_type'], source, settings.get('filters'),
                                  typed=em_tools.table_graph_code)
            if settings.get('filepath'):
                folder = os.path.dirname(settings['filepath'])
            elif bpy.data.filepath:
                folder = os.path.dirname(bpy.data.filepath)
            else:
                folder = ""
            typed_out = bpy.path.abspath(em_tools.table_output_path) if em_tools.table_output_path else ""
            if not folder and not typed_out:
                self.report({'ERROR'}, "where to save the new graph? A PostgreSQL table has no folder: "
                                       "save the .blend first, or give the em.json path")
                return {'CANCELLED'}
            path = emjson_path_for(code, folder, typed=typed_out)

            importer = self._create_importer(settings, None)
            if not importer:
                return {'CANCELLED'}
            graph = self._parse(importer)
            if graph is None or not getattr(graph, "nodes", None):
                self.report({'ERROR'}, "the table gave no node: nothing to save (check the mapping and the filters)")
                return {'CANCELLED'}
            # a graph of its own, like any other: its id, its code, its name
            graph.graph_id = str(uuid.uuid4())
            self._set_graph_metadata(settings, graph)
            graph.attributes['graph_code'] = code
            # graph.data is what em.json carries (attributes stay in memory)
            if isinstance(getattr(graph, "data", None), dict):
                graph.data['graph_code'] = code
            if hasattr(graph, "name") and not getattr(graph, "name", None):
                try:
                    graph.name = {"default": code}
                except Exception:  # noqa: BLE001
                    pass
            for node in graph.nodes:
                if getattr(node, "node_type", None) == "EpochNode" and not getattr(node, "color", None):
                    node.color = _random_epoch_hex_color()

            from ..emjson_support import export_graph_to_emjson
            export_graph_to_emjson(graph, path)
            # loaded as every em.json is: a row in the list, its origin, the lists
            r = getattr(bpy.ops, "import").em_emjson(filepath=path)
            if r != {'FINISHED'}:
                self.report({'ERROR'}, f"saved {path} but it could not be loaded back")
                return {'CANCELLED'}
            loaded = get_graph(graph.graph_id)
            row = next((f for f in em_tools.graphml_files if f.name == graph.graph_id), None)
            if row is not None and not row.graph_code:
                row.graph_code = code
            n_units = len([n for n in loaded.nodes if hasattr(n, "node_type")]) if loaded else 0
            said = f"new graph {code} from the table: {n_units} nodes, saved in {path}"

            if settings['import_type'] == "pyarchinit" and em_tools.pyarchinit_import_geometries and loaded:
                report = self._import_geometries(context, settings['db_spec'], loaded,
                                                 row.graph_code if row is not None and row.graph_code else code,
                                                 em_tools.pyarchinit_geom_force_update, settings.get('filters'))
                said += f"; geometries: {report['created']} created, {report['updated']} updated"
            self.report({'INFO'}, said)
            return {'FINISHED'}
        except Exception as e:  # noqa: BLE001
            self.report({'ERROR'}, f"Import failed: {e}")
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}


class EM_OT_reimport_table(_TableFromPanel, bpy.types.Operator):
    """E2 · «Re-import a table» (E.D., 4 Oct 2026): the newer version of the
    table a graph was made from, read with the same settings as Import from
    tables, updates the ACTIVE graph, which already has work on it. Every
    difference is shown field by field in Conflict Resolution, the epochs of
    the new units are checked first, and what is applied is written to the
    graph's em.json. Not an auxiliary file: an auxiliary is not saved into
    the graph, it is grafted on top of it each time the graph is loaded."""
    bl_idname = "em.reimport_table"
    bl_label = "Re-import a table"
    bl_description = ("Update the active graph with a newer version of its table: each difference "
                      "field by field, the epochs of the new units checked, the result written to "
                      "the graph's em.json")
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        em_tools = context.scene.em_tools
        if not (0 <= em_tools.active_file_index < len(em_tools.graphml_files)):
            cls.poll_message_set("Load the graph to update first")
            return False
        if not get_graph(em_tools.graphml_files[em_tools.active_file_index].name):
            cls.poll_message_set("Load the graph to update first")
            return False
        return True

    def _incoming(self, settings):
        """The table read into a graph of its own, never listed: the unified
        em_data.xlsx (five sheets) is read by its own importer, as before."""
        if settings['import_type'] == "emdb_xlsx":
            try:
                import pandas as _pd
                with _pd.ExcelFile(settings['filepath'], engine='openpyxl') as xl:
                    sheets = set(xl.sheet_names)
            except Exception:  # noqa: BLE001
                sheets = set()
            if {'Units', 'Epochs', 'Claims', 'Authors', 'Documents'}.issubset(sheets):
                from s3dgraphy.importer.unified_xlsx_importer import UnifiedXLSXImporter
                return UnifiedXLSXImporter(
                    filepath=settings['filepath'],
                    graph_id="incoming_reimport").parse()
        importer = self._create_importer(settings, None)
        if not importer:
            return None
        return self._parse(importer)

    def execute(self, context):
        import os
        from .. import graph_origins
        from ..operators.merge_conflict_ui import begin_merge, is_merge_active
        em_tools = context.scene.em_tools
        row = em_tools.graphml_files[em_tools.active_file_index]
        origin = graph_origins.origin_of(row, abspath=bpy.path.abspath)
        if origin.is_room:
            self.report({'ERROR'}, "this graph lives in a room, where a re-import would not reach the "
                                   "others: re-import the table into its em.json, then put that in the room")
            return {'CANCELLED'}
        if em_tools.merge_active or is_merge_active():
            self.report({'ERROR'}, "a re-import is waiting for its choices in Conflict Resolution: "
                                   "apply it or cancel it first")
            return {'CANCELLED'}
        try:
            settings = self.settings(context)
            if settings is None:
                return {'CANCELLED'}
            if settings['import_type'] == "pyarchinit" and (
                    not settings.get('mapping_name') or settings['mapping_name'] == 'none'):
                self.report({'ERROR'}, "choose the mapping the graph was made with")
                return {'CANCELLED'}
            if not self._validate_settings(settings):
                return {'CANCELLED'}
            incoming = self._incoming(settings)
            if incoming is None or not getattr(incoming, "nodes", None):
                self.report({'ERROR'}, "the table gave no node: nothing to compare (check the mapping and the filters)")
                return {'CANCELLED'}
            # the epoch report goes beside the table, or beside the graph's
            # em.json when the table is a PostgreSQL database
            source = settings.get('filepath') or ""
            if not source or not os.path.isfile(source):
                base = origin.path if origin.is_file else (bpy.data.filepath or os.path.join(
                    bpy.app.tempdir, "reimport"))
                stem = base[:-len(".em.json")] if base.endswith(".em.json") else os.path.splitext(base)[0]
                source = stem + "_reimport"
            return begin_merge(self, context, incoming, source)
        except Exception as e:  # noqa: BLE001
            self.report({'ERROR'}, f"Re-import failed: {e}")
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}


def register():
    bpy.utils.register_class(EM_OT_import_auxiliary_table)
    bpy.utils.register_class(EM_OT_import_from_table)
    bpy.utils.register_class(EM_OT_reimport_table)


def unregister():
    bpy.utils.unregister_class(EM_OT_reimport_table)
    bpy.utils.unregister_class(EM_OT_import_from_table)
    bpy.utils.unregister_class(EM_OT_import_auxiliary_table)
