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

        # Create all standard collections
        standard_collections = ["Proxy", "RM", "CAMS"]

        for collection_name in standard_collections:
            if not bpy.data.collections.get(collection_name):
                self.create_collection(collection_name)
                collections_created.append(collection_name)

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
    bl_label = "Add GraphML File"
    bl_description = "Add a new GraphML file to the list"

    def execute(self, context):

        em_tools = context.scene.em_tools
        new_file = em_tools.graphml_files.add()
        new_file.name = "New GraphML File"
        # Aggiungi un graph_code predefinito
        if hasattr(new_file, 'graph_code'):
            new_file.graph_code = "empty slot"
        em_tools.active_file_index = len(em_tools.graphml_files) - 1
        return {'FINISHED'}


class EMToolsRemoveFile(Operator):
    bl_idname = "em_tools.remove_file"
    bl_label = "Remove GraphML File"
    bl_description = "Remove the selected GraphML file from the list"

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

            # ✅ NON ripopolare le liste qui!
            # Le liste verranno popolate automaticamente dopo l'auto-import
            # dalla funzione chiamante (import.em_graphml) per evitare duplicazioni

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
        """Process Source List Excel file to update source descriptions"""
        from .resource_utils import resolve_resource_path

        # Validate filepath
        if not aux_file.filepath:
            self.report({'ERROR'}, "Source List file path not specified")
            return {'CANCELLED'}

        # Resolve filepath
        try:
            filepath = resolve_resource_path(aux_file.filepath)
        except ValueError as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}

        # Check file exists
        if not os.path.exists(filepath):
            self.report({'ERROR'}, f"Source List file not found: {filepath}")
            return {'CANCELLED'}

        try:
            import pandas
            import openpyxl

            # Read Excel file - sheet name 'sources'
            data = pandas.read_excel(filepath, sheet_name='sources')
            df = pandas.DataFrame(data, columns=['Name', 'Description'])

            updated_count = 0
            em_tools = context.scene.em_tools

            # Update em_sources_list
            for index, row in df.iterrows():
                for source_item in em_tools.em_sources_list:
                    if source_item.name == row['Name']:
                        source_item.description = row['Description']
                        updated_count += 1

                # Update em_v_sources_list (virtual sources)
                for source_v_item in em_tools.em_v_sources_list:
                    if source_v_item.name == row['Name']:
                        source_v_item.description = row['Description']
                        updated_count += 1

            self.report({'INFO'}, f"Source List imported: {updated_count} descriptions updated")
            return {'FINISHED'}

        except ImportError:
            self.report({'ERROR'}, "pandas and openpyxl required. Install dependencies first.")
            return {'CANCELLED'}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to import Source List: {str(e)}")
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}


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
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
