# em_setup/operators.py

import bpy
import os
import json
from bpy.types import Operator
from bpy.props import EnumProperty, IntProperty, StringProperty

from s3dgraphy import get_graph, remove_graph, get_all_graph_ids

# Import from parent package
from ..populate_lists import clear_lists, populate_blender_lists_from_graph
from ..import_operators.importer_graphml import EM_import_GraphML


def get_em_tools_version():
    """Legge la versione corrente dal manifest o da version.json come fallback"""
    try:
        # Prima prova a leggere dal manifest (che sarà sempre presente nel .blext)
        addon_dir = os.path.dirname(os.path.dirname(__file__))
        manifest_file = os.path.join(addon_dir, "blender_manifest.toml")

        if os.path.exists(manifest_file):
            with open(manifest_file, 'r') as f:
                manifest_content = f.read()

            # Cerca la versione principale nel manifest (non blender_version_min o altre versioni)
            # Pattern migliorato per catturare solo la versione principale
            import re
            version_match = re.search(r'^version\s*=\s*"([^"]+)"', manifest_content, re.MULTILINE)
            if version_match:
                return version_match.group(1)

        # Fallback su version.json (solo durante lo sviluppo)
        version_file = os.path.join(addon_dir, "version.json")

        if os.path.exists(version_file):
            with open(version_file, 'r') as f:
                config = json.load(f)

            # Genera la stringa di versione basata sul mode
            major = config.get('major', 1)
            minor = config.get('minor', 5)
            patch = config.get('patch', 0)
            mode = config.get('mode', 'dev')

            base = f"{major}.{minor}.{patch}"

            if mode == 'dev':
                dev_build = config.get('dev_build', 0)
                return f"{base}-dev.{dev_build}"
            elif mode == 'rc':
                rc_build = config.get('rc_build', 1)
                return f"{base}-rc.{rc_build}"
            else:  # stable
                return base

    except Exception as e:
        print(f"Error reading version information: {e}")

    # Fallback statico se non riesce a leggere
    return "unknown"


class EM_create_collection(Operator):
    bl_idname = "create.collection"
    bl_label = "Create Standard Collections"
    bl_description = "Create all standard EM collections"
    bl_options = {'REGISTER', 'UNDO'}

    @staticmethod
    def create_collection(target_collection):
        """Create a collection if it doesn't exist"""
        context = bpy.context
        if bpy.data.collections.get(target_collection) is None:
            currentCol = bpy.context.blend_data.collections.new(name=target_collection)
            bpy.context.scene.collection.children.link(currentCol)
            return currentCol
        else:
            currentCol = bpy.data.collections.get(target_collection)
            return currentCol

    def execute(self, context):
        collections_created = []

        # Top-level standard collections.
        #
        # "Layouts" replaces the legacy "CAMS" name. The CAMS label
        # was a Blender-ism (cameras for renders) that confused
        # archaeologists; "Layouts" reflects what this collection
        # actually holds — 2D viewpoint setups (camera + labels)
        # used to author derivative plates and publication figures.
        # Lookups across the addon prefer "Layouts" and fall back
        # to "CAMS" so projects authored against earlier 1.6 dev
        # builds keep working without a migration step.
        standard_collections = ["Proxy", "RM", "Layouts"]

        for collection_name in standard_collections:
            if not bpy.data.collections.get(collection_name):
                self.create_collection(collection_name)
                collections_created.append(collection_name)

        # RM sub-collections — split Representation Models by
        # source type so the user can browse them at a glance:
        #   - RB = reality-based   (photogrammetry, laser scan, ...)
        #   - SB = source-based    (hand-modelled from sources)
        # Routing is left to the user (drag the mesh into the
        # appropriate sub-collection); a future patch may
        # auto-route on promote_to_rm. We never re-parent meshes
        # that already live elsewhere — the sub-collections are
        # added as empty children of RM and the user moves
        # content into them as needed.
        rm_collection = bpy.data.collections.get("RM")
        if rm_collection is not None:
            existing_children = {c.name for c in rm_collection.children}
            for sub_name in ("RB", "SB"):
                if sub_name in existing_children:
                    continue
                sub = bpy.data.collections.get(sub_name)
                if sub is None:
                    sub = bpy.data.collections.new(name=sub_name)
                    rm_collection.children.link(sub)
                    collections_created.append(f"RM/{sub_name}")
                else:
                    # Top-level collection with the same name exists
                    # (probably created by hand in an earlier
                    # session) — link it as an RM child instead of
                    # creating a duplicate.
                    try:
                        rm_collection.children.link(sub)
                        collections_created.append(
                            f"RM/{sub_name} (re-linked under RM)")
                    except RuntimeError:
                        # Already a child of another collection;
                        # leave it alone, the user can re-parent
                        # manually if they want.
                        pass

        if collections_created:
            self.report({'INFO'}, f"Created collections: {', '.join(collections_created)}")
        else:
            self.report({'INFO'}, "All standard collections already exist")

        return {'FINISHED'}


class EM_OT_benchmark_property_functions(Operator):
    bl_idname = "em.benchmark_property_functions"
    bl_label = "Benchmark Property Functions"
    bl_description = "Compare performance between legacy and optimized property mapping functions"

    def execute(self, context):
        from ..visual_manager.utils import test_optimization_performance
        test_optimization_performance(context)
        self.report({'INFO'}, "Benchmark completed. Check console for results.")
        return {'FINISHED'}


class EM_OT_rebuild_graph_indices(Operator):
    bl_idname = "em.rebuild_graph_indices"
    bl_label = "Rebuild Graph Indices"
    bl_description = "Force rebuild of graph indices for better performance"

    def execute(self, context):
        rebuilt = 0
        for graph_id in get_all_graph_ids():
            graph = get_graph(graph_id)
            if graph:
                graph._indices_dirty = True
                _ = graph.indices  # Forza il rebuild
                rebuilt += 1

        self.report({'INFO'}, f"Rebuilt indices for {rebuilt} graphs")
        return {'FINISHED'}


class EM_OT_manage_object_prefixes(Operator):
    bl_idname = "em.manage_object_prefixes"
    bl_label = "Manage Object Prefixes"
    bl_description = "Add or remove graph code prefixes to/from selected objects"
    bl_options = {'REGISTER', 'UNDO'}

    action: EnumProperty(
        name="Action",
        description="Whether to add or remove prefixes",
        items=[
            ('ADD', "Add Prefixes", "Add graph code prefixes to selected objects"),
            ('REMOVE', "Remove Prefixes", "Remove existing prefixes from selected objects")
        ],
        default='ADD'
    )  # type: ignore

    def invoke(self, context, event):
        # Check if at least one object is selected
        if not context.selected_objects:
            self.report({'WARNING'}, "No objects selected")
            return {'CANCELLED'}

        # Show a confirmation dialog
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "action", expand=True)

        # Get current graph code
        em_tools = context.scene.em_tools
        if em_tools.active_file_index >= 0 and em_tools.graphml_files:
            graphml = em_tools.graphml_files[em_tools.active_file_index]
            graph_code = graphml.graph_code if hasattr(graphml, 'graph_code') and graphml.graph_code not in ["site_id"] else None

            if self.action == 'ADD' and graph_code:
                layout.label(text=f"Will add prefix: {graph_code}.")
                layout.label(text=f"Example: SU001 → {graph_code}.SU001")
            elif self.action == 'ADD' and not graph_code:
                layout.label(text="Warning: No valid graph code available", icon='ERROR')
                layout.label(text="Please set a valid graph code first")
            else:  # REMOVE
                layout.label(text="Will remove existing prefixes")
                layout.label(text="Example: GT16.SU001 → SU001")

    def execute(self, context):
        em_tools = context.scene.em_tools

        # Get the active graph code
        graph_code = None
        if em_tools.active_file_index >= 0 and em_tools.graphml_files:
            graphml = em_tools.graphml_files[em_tools.active_file_index]
            if hasattr(graphml, 'graph_code') and graphml.graph_code not in ["site_ID"]:
                graph_code = graphml.graph_code

        # Check if we have a valid graph code when adding prefixes
        if self.action == 'ADD' and not graph_code:
            self.report({'ERROR'}, "No valid graph code available. Please set a valid graph code first.")
            return {'CANCELLED'}

        # Process selected objects
        processed_count = 0
        for obj in context.selected_objects:
            if obj.type == 'MESH':  # Only process mesh objects
                if self.action == 'ADD':
                    # Check if object already has a prefix
                    if '.' in obj.name:
                        prefix, base_name = obj.name.split('.', 1)
                        # If prefix is not the current graph code, replace it
                        if prefix != graph_code:
                            obj.name = f"{graph_code}.{base_name}"
                            processed_count += 1
                    else:
                        # No prefix, add one
                        obj.name = f"{graph_code}.{obj.name}"
                        processed_count += 1
                else:  # REMOVE
                    # Check if object has a prefix
                    if '.' in obj.name:
                        prefix, base_name = obj.name.split('.', 1)
                        obj.name = base_name
                        processed_count += 1

        # Report results
        action_str = "added to" if self.action == 'ADD' else "removed from"
        self.report({'INFO'}, f"Prefixes {action_str} {processed_count} objects")

        # Update the em_list to reflect the name changes
        if processed_count > 0:
            bpy.ops.list_icon.update(list_type="all")

        return {'FINISHED'}


class EMToolsSwitchModeOperator(Operator):
    bl_idname = "emtools.switch_mode"
    bl_label = "Switch Mode"

    def execute(self, context):
        em_tools = context.scene.em_tools

        # Alterna tra le due modalità
        em_tools.mode_em_advanced = not em_tools.mode_em_advanced

        # Messaggio per informare l'utente
        if em_tools.mode_em_advanced:
            self.report({'INFO'}, "Switched to EM Mode")
        else:
            self.report({'INFO'}, "Switched to 3D GIS Mode")

        return {'FINISHED'}


class EMToolsAddFile(Operator):
    bl_idname = "em_tools.add_file"
    bl_label = "Add graph"
    bl_description = "Add a new EM graph slot (set its Path to a .graphml or .em.json)"

    def execute(self, context):

        em_tools = context.scene.em_tools
        new_file = em_tools.graphml_files.add()
        new_file.name = "New Graph"
        # Aggiungi un graph_code predefinito
        if hasattr(new_file, 'graph_code'):
            new_file.graph_code = "empty slot"
        em_tools.active_file_index = len(em_tools.graphml_files) - 1
        return {'FINISHED'}


class EMToolsRemoveFile(Operator):
    bl_idname = "em_tools.remove_file"
    bl_label = "Remove graph"
    bl_description = "Remove the selected EM graph from the list"

    def execute(self, context):
        em_tools = context.scene.em_tools
        if em_tools.active_file_index >= 0:
            graphml = em_tools.graphml_files[em_tools.active_file_index]
            remove_graph(graphml.name)

            em_tools.graphml_files.remove(em_tools.active_file_index)
            em_tools.active_file_index = min(max(0, em_tools.active_file_index - 1), len(em_tools.graphml_files) - 1)

        return {'FINISHED'}


class EM_InvokePopulateLists(Operator):
    bl_idname = "em_tools.populate_lists"
    bl_label = "Activate EM"
    bl_description = "Activate and show this EM in the lists below"
    bl_options = {"REGISTER", "UNDO"}

    # Aggiungiamo una proprietà per passare l'indice del file GraphML selezionato
    graphml_index: IntProperty()  # type: ignore

    def execute(self, context):
        # Ottieni il GraphML attivo dal contesto
        scene = context.scene
        em_tools = scene.em_tools

        if self.graphml_index >= 0 and self.graphml_index < len(em_tools.graphml_files):
            # Ottieni il file GraphML selezionato
            graphml_file = em_tools.graphml_files[self.graphml_index]

            # Recupero il grafo
            graph_instance = get_graph(graphml_file.name)

            # Verifica che il grafo sia caricato (luce verde)
            if not graph_instance or not hasattr(graph_instance, 'nodes') or len(graph_instance.nodes) == 0:
                self.report({'ERROR'}, "Graph not loaded. Please import the GraphML file first.")
                return {'CANCELLED'}

            if getattr(scene, 'landscape_mode_active', False):
                from ..landscape_system.populate_functions import populate_lists_landscape_mode
                populate_lists_landscape_mode(context)
            else:
                # Clear Blender Lists
                clear_lists(context)
                populate_blender_lists_from_graph(context, graph_instance)

            # ✅ Aggiorna le statistiche del grafo
            from ..populate_lists import update_graph_statistics
            update_graph_statistics(context, graph_instance, graphml_file)

            self.report({'INFO'}, "Populated Blender lists from GraphML")
            return {'FINISHED'}
        else:
            self.report({'ERROR'}, "No valid GraphML file selected")
            return {'CANCELLED'}


class AUXILIARY_OT_add_file(Operator):
    bl_idname = "auxiliary.add_file"
    bl_label = "Add Auxiliary File"
    bl_description = "Add a new auxiliary file to the selected GraphML"

    def execute(self, context):
        em_tools = context.scene.em_tools
        if em_tools.active_file_index >= 0:
            graphml = em_tools.graphml_files[em_tools.active_file_index]
            new_file = graphml.auxiliary_files.add()
            new_file.name = "Rename me"
            graphml.active_auxiliary_index = len(graphml.auxiliary_files) - 1
            return {'FINISHED'}
        return {'CANCELLED'}


class AUXILIARY_OT_remove_file(Operator):
    bl_idname = "auxiliary.remove_file"
    bl_label = "Remove Auxiliary File"
    bl_description = "Remove selected auxiliary file"

    def execute(self, context):
        em_tools = context.scene.em_tools
        if em_tools.active_file_index >= 0:
            graphml = em_tools.graphml_files[em_tools.active_file_index]
            if graphml.active_auxiliary_index >= 0:
                graphml.auxiliary_files.remove(graphml.active_auxiliary_index)
                graphml.active_auxiliary_index = min(max(0, graphml.active_auxiliary_index - 1),
                                                   len(graphml.auxiliary_files) - 1)
            return {'FINISHED'}
        return {'CANCELLED'}


class AUXILIARY_OT_context_menu_invoke(Operator):
    bl_idname = "auxiliary.context_menu"
    bl_label = "Auxiliary File Context Menu"

    def execute(self, context):
        bpy.ops.wm.call_menu(name="AUXILIARY_MT_context_menu")
        return {'FINISHED'}


class AUXILIARY_OT_reload_file(Operator):
    bl_idname = "auxiliary.reload"
    bl_label = "Reload Auxiliary File"
    bl_description = "Reload the auxiliary file data"

    file_index: IntProperty()  # type: ignore

    def execute(self, context):
        em_tools = context.scene.em_tools
        graphml = em_tools.graphml_files[em_tools.active_file_index]
        aux_file = graphml.auxiliary_files[self.file_index]

        # Qui andrà la logica di ricaricamento del file
        # che riutilizzerà gli importers esistenti
        self.report({'INFO'}, f"Reloading {aux_file.name}")
        return {'FINISHED'}


class AUXILIARY_OT_import_now(Operator):
    bl_idname = "auxiliary.import_now"
    bl_label = "Import Auxiliary File"
    bl_description = "Import the auxiliary file data now"

    def execute(self, context):
        em_tools = context.scene.em_tools
        graphml = em_tools.graphml_files[em_tools.active_file_index]
        aux_file = graphml.auxiliary_files[graphml.active_auxiliary_index]

        # Handle DosCo type differently - no database import, just harvesting
        if aux_file.file_type == "dosco":
            return self._process_dosco(context, graphml, aux_file)

        # Handle Source List type - updates source descriptions
        if aux_file.file_type == "source_list":
            return self._process_source_list(context, graphml, aux_file)

        # Handle Resource Collection type - standalone folder scanning
        if aux_file.file_type == "resource_collection":
            return self._process_resource_collection(context, graphml, aux_file)

        # ✅ 1. Importa file xlsx (aggiunge proprietà ai nodi esistenti)
        result = bpy.ops.em.import_3dgis_database(
            auxiliary_mode=True,
            graphml_index=em_tools.active_file_index,
            auxiliary_index=graphml.active_auxiliary_index
        )

        if result != {'FINISHED'}:
            self.report({'ERROR'}, "Failed to import auxiliary file")
            return {'CANCELLED'}

        # ✅ 2. Processa cartella risorse (se specificata)
        if aux_file.resource_folder:
            try:
                self._process_resource_folder(context, graphml, aux_file)
                self.report({'INFO'}, f"Imported {aux_file.name} with resources")
            except Exception as e:
                self.report({'WARNING'}, f"Imported {aux_file.name} but resource processing failed: {str(e)}")
        else:
            self.report({'INFO'}, f"Imported {aux_file.name}")

        return {'FINISHED'}

    def _process_resource_folder(self, context, graphml, aux_file):
        """Process resource folder - delegates to shared resource_utils."""
        from .resource_utils import process_resource_folder
        allowed_formats = self._get_allowed_formats_from_mapping(aux_file)
        process_resource_folder(
            get_graph(graphml.name),
            aux_file.resource_folder,
            aux_file,
            graphml.name,
            allowed_formats=allowed_formats
        )

    def _process_resource_collection(self, context, graphml, aux_file):
        """Process a standalone resource collection (scan folder, link to graph nodes)."""
        from .resource_utils import (
            resolve_resource_path, process_resource_folder,
            process_resource_folder_by_prefix, get_target_types_from_enum
        )

        if not aux_file.resource_folder:
            self.report({'ERROR'}, "Resource folder not configured")
            return {'CANCELLED'}

        try:
            resolved = resolve_resource_path(aux_file.resource_folder)
        except ValueError as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}

        import os
        if not os.path.exists(resolved):
            self.report({'ERROR'}, f"Resource folder not found: {resolved}")
            return {'CANCELLED'}

        graph = get_graph(graphml.name)
        if not graph:
            self.report({'ERROR'}, f"Graph '{graphml.name}' not loaded. Import the GraphML first.")
            return {'CANCELLED'}

        target_types = get_target_types_from_enum(aux_file.target_node_types)

        try:
            if aux_file.scan_mode == 'FOLDER_NAME':
                process_resource_folder(
                    graph=graph,
                    resource_folder_raw=aux_file.resource_folder,
                    source_item=aux_file,
                    graph_name=graphml.name,
                    target_types=target_types
                )
            elif aux_file.scan_mode == 'FILENAME_PREFIX':
                process_resource_folder_by_prefix(
                    graph=graph,
                    resource_folder_raw=aux_file.resource_folder,
                    target_types=target_types
                )

            # Invalidate graph index so new edges are picked up
            graph._indices_dirty = True

            self.report({'INFO'}, f"Resources scanned and linked from '{aux_file.name}'")
            return {'FINISHED'}

        except Exception as e:
            self.report({'ERROR'}, f"Resource scanning failed: {str(e)}")
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}

    def _get_allowed_formats_from_mapping(self, aux_file):
        """Get allowed_formats from the mapping JSON specific to this aux file type."""
        if aux_file.file_type == "emdb_xlsx" and aux_file.emdb_mapping != "none":
            try:
                from s3dgraphy.mappings import mapping_registry
                mapping_data = mapping_registry.load_mapping(aux_file.emdb_mapping, "emdb")
                return mapping_data.get('allowed_formats', None)
            except Exception as e:
                print(f"Error loading mapping: {e}")
                return None
        elif aux_file.file_type == "pyarchinit" and aux_file.pyarchinit_mapping != "none":
            try:
                from s3dgraphy.mappings import mapping_registry
                mapping_data = mapping_registry.load_mapping(aux_file.pyarchinit_mapping, "pyarchinit")
                return mapping_data.get('allowed_formats', None)
            except Exception as e:
                print(f"Error loading mapping: {e}")
                return None
        return None

    def _process_dosco(self, context, graphml, aux_file):
        """Process DosCo folder harvesting"""
        from ..functions import inspect_load_dosco_files_on_graph
        from s3dgraphy import get_graph
        from .resource_utils import resolve_resource_path

        # Validate DosCo folder path
        if not aux_file.dosco_folder:
            self.report({'ERROR'}, "DosCo folder path not specified")
            return {'CANCELLED'}

        # Resolve DosCo folder path
        try:
            dosco_folder = resolve_resource_path(aux_file.dosco_folder)
        except ValueError as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}

        # Check folder exists
        if not os.path.exists(dosco_folder):
            self.report({'ERROR'}, f"DosCo folder not found: {dosco_folder}")
            return {'CANCELLED'}

        # Get graph instance
        graph = get_graph(graphml.name)
        if not graph:
            self.report({'ERROR'}, f"Graph {graphml.name} not found. Load the GraphML first.")
            return {'CANCELLED'}

        # Temporarily set global settings for DosCo harvesting
        em_settings = context.window_manager.em_addon_settings
        old_overwrite = em_settings.overwrite_url_with_dosco_filepath
        old_preserve = em_settings.preserve_web_url

        try:
            # Apply DosCo-specific settings from auxiliary file
            em_settings.overwrite_url_with_dosco_filepath = aux_file.dosco_overwrite_paths
            em_settings.preserve_web_url = aux_file.dosco_preserve_web_urls

            # Execute DosCo harvesting
            inspect_load_dosco_files_on_graph(graph, dosco_folder)

            # During the initial GraphML auto-import flow, the caller
            # repopulates all lists from scratch so we don't have to.
            # When the user triggers DosCo manually on an already-loaded
            # graph, however, we must propagate the fresh URLs to the UI
            # lists ourselves — populate_document_node skips existing
            # items and would leave em_sources_list with stale URLs,
            # breaking the "open file" button in Paradata Manager.
            try:
                from ..populate_lists import refresh_paradata_urls_from_graph
                refresh_paradata_urls_from_graph(context.scene, graph)
            except Exception as exc:
                print(f"Warning: could not refresh paradata URLs after DosCo: {exc}")

            try:
                from ..document_manager.data import sync_doc_list
                sync_doc_list(context.scene)
            except Exception as exc:
                print(f"Warning: could not sync doc_list after DosCo: {exc}")

            if context.scene.em_tools.paradata_streaming_mode:
                try:
                    bpy.ops.em.update_paradata_lists()
                except Exception as exc:
                    print(f"Warning: streaming paradata refresh failed after DosCo: {exc}")

            self.report({'INFO'}, f"DosCo harvesting completed from {os.path.basename(dosco_folder)}")
            return {'FINISHED'}

        except Exception as e:
            self.report({'ERROR'}, f"DosCo harvesting failed: {str(e)}")
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}

        finally:
            # Restore original settings
            em_settings.overwrite_url_with_dosco_filepath = old_overwrite
            em_settings.preserve_web_url = old_preserve

    def _process_source_list(self, context, graphml, aux_file):
        """Process Source List Excel file to update source descriptions
        on document / extractor / combiner nodes in the active graph.

        The previous implementation had two compounding bugs that
        produced "0 descriptions updated" on every real source-list
        file we ship:

          1. ``pandas.read_excel(...)`` used the default ``header=0``
             but our xlsx convention puts a single-row title above
             the headers (``San Pietro`` etc.), so the header row was
             read as data and the actual headers were skipped.
          2. The code then reindexed to ``['Name', 'Description']``,
             but our files carry Italian column names
             (``Nome`` / ``Descrizione``). The reindex produced an
             all-NaN frame and the equality test ``source_item.name
             == row['Name']`` never fired.

        Additionally, the old code only mutated the Blender UI
        collection (``em_sources_list[].description``), not the
        underlying graph node. Even when matching worked, the change
        was lost on the next GraphML save because the exporter reads
        from the graph, not the UI list.

        This rewrite:

          - auto-detects the header row (scans the first 5 rows for a
            row exposing both a name-like and a description-like
            column), and tolerates both Italian and English column
            names;
          - resolves matches against graph nodes (document / extractor
            / combiner), honouring the optional ``graph_code`` prefix
            so a row keyed ``D.02`` matches a node named ``GT26.D.02``;
          - writes the description on the graph node with Hybrid-C
            bookkeeping (``record_attribute_override`` +
            ``freeze_aux_value``) so a volatile save can revert it;
          - clears previously-filed orphans for this injector before
            the scan so reloading doesn't double the orphan list;
          - files unmatched rows as orphans so they appear in the
            Lifecycle panel with a "Create host node" action;
          - syncs the matched UI rows so the user sees the new
            descriptions immediately, without a full populate.
        """
        from .resource_utils import resolve_resource_path
        from s3dgraphy import get_graph

        if not aux_file.filepath:
            self.report({'ERROR'}, "Source List file path not specified")
            return {'CANCELLED'}
        try:
            filepath = resolve_resource_path(aux_file.filepath)
        except ValueError as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
        if not os.path.exists(filepath):
            self.report({'ERROR'}, f"Source List file not found: {filepath}")
            return {'CANCELLED'}

        graph = get_graph(graphml.name)
        if graph is None:
            self.report(
                {'ERROR'},
                f"Graph '{graphml.name}' not loaded — import the "
                f"GraphML first.")
            return {'CANCELLED'}

        try:
            import pandas
        except ImportError:
            self.report({'ERROR'},
                        "pandas and openpyxl required. Install "
                        "dependencies first.")
            return {'CANCELLED'}

        try:
            raw = pandas.read_excel(filepath, sheet_name='sources',
                                    header=None)
        except Exception as e:
            self.report({'ERROR'},
                        f"Cannot read 'sources' sheet from {filepath}: {e}")
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}

        NAME_KEYS = {"name", "nome", "id", "id node", "node id"}
        DESC_KEYS = {"description", "descrizione"}

        def _cell_str(v):
            if v is None:
                return ""
            if isinstance(v, float) and pandas.isna(v):
                return ""
            return str(v).strip()

        # ---- locate the header row ------------------------------------
        header_row_idx = None
        name_col_idx = None
        desc_col_idx = None
        scan_limit = min(5, len(raw))
        for i in range(scan_limit):
            cells = [_cell_str(v).lower() for v in raw.iloc[i].tolist()]
            cand_name = next(
                (j for j, v in enumerate(cells) if v in NAME_KEYS), None)
            cand_desc = next(
                (j for j, v in enumerate(cells) if v in DESC_KEYS), None)
            if cand_name is not None and cand_desc is not None:
                header_row_idx = i
                name_col_idx = cand_name
                desc_col_idx = cand_desc
                break

        if header_row_idx is None:
            self.report(
                {'ERROR'},
                "Source List: could not locate a header row with "
                "Name/Nome AND Description/Descrizione columns in "
                "the first 5 rows of the 'sources' sheet.")
            return {'CANCELLED'}

        data_rows = raw.iloc[header_row_idx + 1:]

        # ---- Hybrid-C primitives (best-effort) ------------------------
        try:
            from s3dgraphy.transforms import (
                record_attribute_override, freeze_aux_value,
                push_orphan, clear_orphans)
            _AUX_AVAILABLE = True
            _INJECTOR_ID = f"sources_list:{filepath}"
            # Reload semantics: drop previous orphans from this
            # injector so the list doesn't accumulate duplicates on
            # repeated imports of the same xlsx.
            clear_orphans(graph, injector_id=_INJECTOR_ID)
        except ImportError:
            _AUX_AVAILABLE = False
            _INJECTOR_ID = None

        # ---- build a name -> node lookup (with graph_code support) ----
        graph_code = None
        if (hasattr(graph, 'attributes')
                and graph.attributes
                and 'graph_code' in graph.attributes):
            graph_code = graph.attributes['graph_code']

        nodes_by_name = {}
        for n in graph.nodes:
            nt = getattr(n, 'node_type', None)
            if nt not in ('document', 'extractor', 'combiner'):
                continue
            nm = getattr(n, 'name', '') or ''
            if not nm:
                continue
            nodes_by_name.setdefault(nm, n)
            if graph_code:
                for sep in (f"{graph_code}.", f"{graph_code}_"):
                    if nm.startswith(sep):
                        nodes_by_name.setdefault(
                            nm.split(sep, 1)[1], n)
                        break

        # ---- per-row apply -------------------------------------------
        desc_updated = 0
        matched_node_ids = set()
        unmatched = []

        for _i, row in data_rows.iterrows():
            name_raw = (row.iloc[name_col_idx]
                        if name_col_idx < len(row) else None)
            name = _cell_str(name_raw)
            if not name:
                continue
            desc = _cell_str(row.iloc[desc_col_idx]
                             if desc_col_idx < len(row) else None)

            node = nodes_by_name.get(name)
            if node is None and graph_code:
                node = nodes_by_name.get(f"{graph_code}.{name}")
            if node is None:
                unmatched.append((name, desc))
                continue

            if not desc:
                # Match but no description to apply — still count as
                # touched (the row exists in the xlsx) and remember
                # the node so the UI sync below doesn't blank it.
                matched_node_ids.add(getattr(node, 'node_id', None))
                continue

            if _AUX_AVAILABLE:
                record_attribute_override(
                    node, "description",
                    injector_id=_INJECTOR_ID,
                    original_value=getattr(node, "description", None))
            node.description = desc
            if _AUX_AVAILABLE:
                freeze_aux_value(node, "description")
            desc_updated += 1
            matched_node_ids.add(getattr(node, 'node_id', None))

        # ---- file unmatched rows as orphans --------------------------
        if _AUX_AVAILABLE and unmatched:
            for name, desc in unmatched:
                push_orphan(
                    graph,
                    injector_id=_INJECTOR_ID,
                    key_id=name,
                    payload={"description": desc},
                )

        # ---- mirror description into the UI lists --------------------
        em_tools = context.scene.em_tools
        for collection_name in ("em_sources_list", "em_v_sources_list",
                                "em_extractors_list", "em_combiners_list"):
            collection = getattr(em_tools, collection_name, None)
            if not collection:
                continue
            for item in collection:
                if (item.id_node
                        and item.id_node in matched_node_ids):
                    node = next(
                        (n for n in graph.nodes
                         if getattr(n, 'node_id', None) == item.id_node),
                        None)
                    if node is not None:
                        item.description = (
                            getattr(node, "description", "") or "")

        tail = (f", {len(unmatched)} unmatched rows filed as orphans"
                if unmatched else "")
        self.report({'INFO'},
                    f"Source List imported: {desc_updated} descriptions "
                    f"updated{tail}")
        return {'FINISHED'}


class EM_OT_open_author_url(Operator):
    """Open the author's ORCID page in the system browser"""
    bl_idname = "em.open_author_url"
    bl_label = "Open Author ORCID"

    url: StringProperty()  # type: ignore

    def execute(self, context):
        import webbrowser
        webbrowser.open(self.url)
        return {'FINISHED'}


class EM_OT_open_license_url(Operator):
    """Open the license page in the system browser"""
    bl_idname = "em.open_license_url"
    bl_label = "Open License Page"

    url: StringProperty()  # type: ignore

    def execute(self, context):
        import webbrowser
        webbrowser.open(self.url)
        return {'FINISHED'}


class EM_OT_pyarchinit_pg_save_password(Operator):
    """Store the PostgreSQL password in the OS keychain.

    The password is never written into the .blend: it is saved in the
    operating-system keychain (or, if that is unavailable, kept in
    memory for this Blender session only). Issue #27, Sub-2.
    """
    bl_idname = "emtools.pyarchinit_pg_save_password"
    bl_label = "Save PostgreSQL password to keychain"

    def execute(self, context):
        em_tools = context.scene.em_tools
        host = (em_tools.pyarchinit_pg_host or "").strip()
        dbname = (em_tools.pyarchinit_pg_dbname or "").strip()
        user = (em_tools.pyarchinit_pg_user or "").strip()
        port = em_tools.pyarchinit_pg_port
        password = em_tools.pyarchinit_pg_password
        if not (host and dbname and user):
            self.report({'ERROR'}, "Fill host, database and user first.")
            return {'CANCELLED'}
        if not password:
            self.report({'ERROR'}, "Type a password to save.")
            return {'CANCELLED'}
        from ..import_operators.pyarchinit_connection import set_password
        tier = set_password(host, port, dbname, user, password)
        if tier == "keychain":
            self.report({'INFO'}, "Password saved to the OS keychain.")
        else:
            self.report(
                {'WARNING'},
                "OS keychain unavailable — password kept in memory for "
                "this session only (still never written to the .blend).",
            )
        return {'FINISHED'}


class EM_OT_pyarchinit_pg_forget_password(Operator):
    """Remove the stored PostgreSQL password from keychain and memory."""
    bl_idname = "emtools.pyarchinit_pg_forget_password"
    bl_label = "Forget PostgreSQL password"

    def execute(self, context):
        em_tools = context.scene.em_tools
        host = (em_tools.pyarchinit_pg_host or "").strip()
        dbname = (em_tools.pyarchinit_pg_dbname or "").strip()
        user = (em_tools.pyarchinit_pg_user or "").strip()
        port = em_tools.pyarchinit_pg_port
        from ..import_operators.pyarchinit_connection import forget_password
        forget_password(host, port, dbname, user)
        em_tools.pyarchinit_pg_password = ""
        self.report({'INFO'}, "Password removed from keychain and memory.")
        return {'FINISHED'}


# Registration
classes = (
    EM_create_collection,
    EM_OT_benchmark_property_functions,
    EM_OT_rebuild_graph_indices,
    EM_OT_manage_object_prefixes,
    EMToolsSwitchModeOperator,
    EMToolsAddFile,
    EMToolsRemoveFile,
    EM_InvokePopulateLists,
    AUXILIARY_OT_add_file,
    AUXILIARY_OT_remove_file,
    AUXILIARY_OT_context_menu_invoke,
    AUXILIARY_OT_reload_file,
    AUXILIARY_OT_import_now,
    EM_OT_open_author_url,
    EM_OT_open_license_url,
    EM_OT_pyarchinit_pg_save_password,
    EM_OT_pyarchinit_pg_forget_password,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
