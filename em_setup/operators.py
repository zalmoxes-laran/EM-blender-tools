# em_setup/operators.py

import bpy
import os
import json
import uuid
from bpy.types import Operator
from bpy.props import EnumProperty, IntProperty

from s3dgraphy import get_graph, remove_graph, get_all_graph_ids
from s3dgraphy.nodes.document_node import DocumentNode
from s3dgraphy.nodes.link_node import LinkNode

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
            self.report({'INFO'}, "Switched to Advanced EM Mode")
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

        if self.graphml_index >= 0 and em_tools.graphml_files[self.graphml_index]:
            # Ottieni il file GraphML selezionato
            graphml_file = em_tools.graphml_files[self.graphml_index]

            # Recupero il grafo
            graph_instance = get_graph(graphml_file.name)

            # Clear Blender Lists
            clear_lists(context)

            # Istanzia l'operatore `EM_import_GraphML`
            populate_blender_lists_from_graph(context, graph_instance)

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
            new_file.name = "New Auxiliary File"
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
        """Processa cartella risorse con ricerca ricorsiva"""
        # ✅ RISOLVI il path della resource_folder PRIMA di usarlo
        resource_folder_raw = aux_file.resource_folder

        # Risolvi con la stessa logica di resolve_resource_folder
        if os.path.isabs(resource_folder_raw) and not resource_folder_raw.startswith("//"):
            base_resource_folder = os.path.normpath(resource_folder_raw)
        elif resource_folder_raw.startswith("//"):
            base_resource_folder = os.path.normpath(bpy.path.abspath(resource_folder_raw))
        else:
            blend_path = bpy.data.filepath
            if blend_path:
                blend_dir = os.path.dirname(blend_path)
                base_resource_folder = os.path.normpath(os.path.join(blend_dir, resource_folder_raw))
            else:
                raise Exception("File .blend non salvato, impossibile usare path relativi senza //")

        print(f"✓ Resource folder risolta per import: {base_resource_folder}")

        if not os.path.exists(base_resource_folder):
            raise Exception(f"Resource folder non trovata: {base_resource_folder}")

        graph = get_graph(graphml.name)
        if not graph:
            raise Exception(f"Graph {graphml.name} not found")

        allowed_formats = self._get_allowed_formats_from_mapping(aux_file)

        print(f"Processing resource folder: {base_resource_folder}")
        print(f"Allowed formats: {allowed_formats if allowed_formats else 'ALL FORMATS'}")

        # ✅ Ottieni tutti gli ID dalla colonna xlsx (già importati come proprietà)
        imported_ids = self._get_imported_node_ids(graph)

        # ✅ Per ogni ID, ricerca ricorsiva della cartella
        for node_id in imported_ids:
            # ✅ USA base_resource_folder invece di aux_file.resource_folder
            matching_folders = self._find_folders_by_name(base_resource_folder, node_id)

            if matching_folders:
                print(f"Found {len(matching_folders)} folder(s) for ID {node_id}:")
                for folder_path in matching_folders:
                    print(f"  - {folder_path}")
                    # ✅ PASSA base_resource_folder come ultimo parametro
                    self._process_node_resource_folder(graph, node_id, folder_path, allowed_formats, base_resource_folder)
            else:
                print(f"No folder found for ID {node_id}")

    def _get_allowed_formats_from_mapping(self, aux_file):
        """Ottieni allowed_formats dal mapping JSON specifico"""
        if aux_file.file_type == "emdb_xlsx" and aux_file.emdb_mapping != "none":
            try:
                from s3dgraphy.mappings import mapping_registry
                mapping_data = mapping_registry.load_mapping(aux_file.emdb_mapping, "emdb")
                return mapping_data.get('allowed_formats', None)
            except Exception as e:
                print(f"Error loading mapping: {e}")
                return None
        return None  # No restrictions = tutti i formati

    def _get_imported_node_ids(self, graph):
        """Ottieni tutti gli ID dei nodi che sono stati importati dall'xlsx"""
        node_ids = []
        for node in graph.nodes:
            # Cerca nei nodi che hanno nome senza prefisso grafo
            original_name = getattr(node, 'attributes', {}).get('original_name', node.name)
            # Se è un nome che potrebbe avere una cartella corrispondente
            if original_name and not original_name.startswith(('D.', 'DOC.', 'PROP.')):
                node_ids.append(original_name)
        return node_ids

    def _find_folders_by_name(self, root_folder, target_name):
        """Trova ricorsivamente tutte le cartelle con nome specifico"""
        matching_folders = []

        try:
            for root, dirs, files in os.walk(root_folder):
                # ✅ Controlla se una delle sottocartelle ha il nome cercato
                if target_name in dirs:
                    match_path = os.path.join(root, target_name)
                    matching_folders.append(match_path)
                    print(f"Found matching folder: {match_path}")

        except Exception as e:
            print(f"Error scanning {root_folder}: {e}")

        return matching_folders

    def _process_node_resource_folder(self, graph, node_id, folder_path, allowed_formats, base_resource_folder):
        """Processa tutti i file nella cartella di un nodo specifico"""
        target_node = self._find_node_by_name(graph, node_id)
        if not target_node:
            print(f"Warning: Node {node_id} not found in graph")
            return

        # ✅ Include il percorso relativo nel nome del documento per disambiguare
        folder_suffix = self._get_folder_suffix(folder_path, base_resource_folder)

        # Scansiona tutti i file nella cartella
        for filename in os.listdir(folder_path):
            file_path = os.path.join(folder_path, filename)
            if os.path.isfile(file_path):
                if self._is_allowed_format(filename, allowed_formats):
                    print(f"Creating DocumentNode for: {folder_suffix}/{filename}")
                    self._create_document_for_resource(
                        graph, target_node, file_path, filename, folder_suffix, base_resource_folder
                    )
                else:
                    print(f"Skipping {filename} (format not allowed)")

    def _find_node_by_name(self, graph, target_name):
        """Trova nodo per nome"""
        for node in graph.nodes:
            original_name = getattr(node, 'attributes', {}).get('original_name', node.name)
            if node.name == target_name or original_name == target_name:
                return node
        return None

    def _get_folder_suffix(self, folder_path, base_resource_folder):
        """Ottieni suffisso identificativo per cartelle multiple"""
        relative_path = os.path.relpath(folder_path, base_resource_folder)
        parts = relative_path.split(os.sep)
        if len(parts) > 1:
            return "_".join(parts[:-1])  # Tutto tranne l'ultima parte (nome cartella target)
        return "main"

    def _is_allowed_format(self, filename, allowed_formats):
        """Controlla se il file ha formato consentito"""
        if allowed_formats is None:
            return True  # Nessuna restrizione = tutti i formati OK

        ext = filename.lower().split('.')[-1]
        return ext in [fmt.lower() for fmt in allowed_formats]

    def _create_document_for_resource(self, graph, target_node, file_path, filename, folder_suffix, base_resource_folder):
        """Crea DocumentNode → LinkNode per la risorsa (con controllo duplicati)"""
        # ✅ Calcola path relativo alla base_resource_folder
        try:
            relative_path = os.path.relpath(file_path, base_resource_folder)
            # Normalizza gli slash per essere cross-platform (sempre /)
            relative_path = relative_path.replace("\\", "/")
        except ValueError:
            # Se file_path e base_resource_folder sono su drive diversi (Windows)
            print(f"⚠️ Impossibile calcolare path relativo per {filename}, uso assoluto")
            relative_path = file_path

        # ✅ FIX DUPLICATI: Prima controlla se esiste già un documento per questo file
        existing_doc = None
        for node in graph.nodes:
            if (hasattr(node, 'node_type') and node.node_type == 'document' and
                hasattr(node, 'url') and node.url == relative_path):
                # Trovato documento esistente con lo stesso URL
                existing_doc = node
                print(f"✅ Found existing DocumentNode for file: {filename}")
                break

        if existing_doc:
            # ✅ Verifica che sia collegato al nodo target
            edge_exists = False
            edge_id = f"{target_node.node_id}_generic_connection_{existing_doc.node_id}"

            for edge in graph.edges:
                if (edge.edge_source == target_node.node_id and
                    edge.edge_target == existing_doc.node_id and
                    edge.edge_type == "generic_connection"):
                    edge_exists = True
                    break

            if not edge_exists:
                # Crea edge se non esiste
                graph.add_edge(
                    edge_id=edge_id,
                    edge_source=target_node.node_id,
                    edge_target=existing_doc.node_id,
                    edge_type="generic_connection"
                )
                print(f"✅ Added edge to existing DocumentNode")
            else:
                print(f"✅ Edge already exists to DocumentNode")

            return existing_doc

        # ✅ Se non esiste, crea nuovo documento
        # Conta documenti esistenti per calcolare l'indice progressivo
        existing_docs = [n for n in graph.nodes
                        if hasattr(n, 'name') and n.name.startswith(f"DOC.{target_node.name}")]
        doc_index = len(existing_docs) + 1

        # Include folder_suffix nel nome se presente
        if folder_suffix and folder_suffix != "main":
            doc_id = f"DOC.{target_node.name}.{folder_suffix}.{doc_index:03d}"
        else:
            doc_id = f"DOC.{target_node.name}.{doc_index:03d}"

        print(f"Creating NEW DocumentNode: {doc_id}")
        print(f"  File path: {file_path}")
        print(f"  Relative path: {relative_path}")

        # Crea DocumentNode
        doc_node = DocumentNode(
            node_id=str(uuid.uuid4()),
            name=doc_id,
            url=relative_path  # ✅ Path relativo
        )
        doc_node.attributes = getattr(doc_node, 'attributes', {})
        doc_node.attributes['resource_type'] = filename.split('.')[-1].lower()

        graph.add_node(doc_node)

        # Crea edge verso il nodo target
        edge_id = f"{target_node.node_id}_generic_connection_{doc_node.node_id}"
        graph.add_edge(
            edge_id=edge_id,
            edge_source=target_node.node_id,
            edge_target=doc_node.node_id,
            edge_type="generic_connection"
        )

        # Crea LinkNode per il file
        link_id = f"LINK.{doc_id}"
        link_node = LinkNode(
            node_id=str(uuid.uuid4()),
            name=link_id,
            url=relative_path
        )
        link_node.data = {'url': relative_path, 'filename': filename}

        graph.add_node(link_node)

        # Crea edge tra DocumentNode e LinkNode
        link_edge_id = f"{doc_node.node_id}_has_linked_resource_{link_node.node_id}"
        graph.add_edge(
            edge_id=link_edge_id,
            edge_source=doc_node.node_id,
            edge_target=link_node.node_id,
            edge_type="has_linked_resource"
        )

        print(f"✅ Created DocumentNode and LinkNode for: {filename}")
        return doc_node


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
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
