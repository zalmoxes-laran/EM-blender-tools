"""
Operators for Graph Editor
Handles loading, clearing, and manipulating graphs in the node editor.
"""

import bpy
from bpy.types import Operator
from bpy.props import EnumProperty, BoolProperty, IntProperty
from s3dgraphy import get_graph
from .utils import (
    find_proxy_by_node_id,
    find_node_id_from_proxy,
    get_em_list_items,
    get_em_list_active_index,
    set_em_list_active_index,
    get_stratigraphic_edge_types,
    get_paradata_edge_types,
    get_model_edge_types
)
from .layout import calculate_hierarchical_layout, apply_layout_to_nodes

class GRAPHEDIT_OT_draw_graph(Operator):
    """Disegna il grafo attivo nell'editor EMGraph"""
    bl_idname = "graphedit.draw_graph"
    bl_label = "Draw Graph"
    bl_description = "Load and draw the active graph from EM Setup into the EMGraph editor"
    bl_options = {'REGISTER', 'UNDO'}

    # Proprietà per specificare quale graphml usare
    graphml_index: IntProperty(
        name="GraphML Index",
        description="Index of the GraphML file to load",
        default=-1
    )

    # Proprietà per filtraggio
    filter_mode: EnumProperty(
        name="Filter Mode",
        items=[
            ('ALL', "All Nodes", "Show all nodes"),
            ('STRATIGRAPHIC', "Stratigraphic Only", "Show only stratigraphic nodes (US, USVs, USVn, SF, VSF, USD)"),
            ('US_ONLY', "US Only", "Show only US nodes"),
            ('FROM_UILIST', "From UI List", "Show only nodes currently in Stratigraphy Manager UI list"),
            ('NEIGHBORHOOD', "Neighborhood", "Show selected node and connected nodes"),
            ('NODE_CONTEXT', "Node + Context", "Show node with stratigraphic neighbors and all paradata"),
            ('EDGE_FILTERED', "By Edge Types", "Filter by selected edge types"),
        ],
        default='ALL'
    )

    neighborhood_depth: IntProperty(
        name="Depth",
        description="Number of connection levels to show",
        default=1,
        min=1,
        max=5
    )

    def execute(self, context):
        from .utils import get_active_graph, get_active_graph_code

        em_tools = context.scene.em_tools

        # Se è stato specificato un graphml_index, aggiorna l'active_file_index (solo EM Advanced)
        if self.graphml_index >= 0 and em_tools.mode_em_advanced:
            em_tools.active_file_index = self.graphml_index
            # Chiama populate_lists per aggiornare le liste
            print(f"✓ Setting active GraphML index to {self.graphml_index}")
            bpy.ops.em_tools.populate_lists(graphml_index=self.graphml_index)

        # ✅ Usa la funzione centralizzata per ottenere il grafo
        graph, graph_id = get_active_graph(context)

        if not graph:
            mode = "3D GIS" if not em_tools.mode_em_advanced else "EM Advanced"
            self.report({'ERROR'}, f"No active graph found in {mode} mode")
            return {'CANCELLED'}
        
        print(f"\n✅ Found graph: {graph_id}")
        print(f"   Total nodes: {len(graph.nodes)}")
        print(f"   Total edges: {len(graph.edges)}")
        print(f"   Filter mode: {self.filter_mode}")

        # ✅ Trova o crea il node tree con nome appropriato
        graph_code = get_active_graph_code(context)
        tree_name = f"EMGraph_{graph_code}" if graph_code else graph_id

        if tree_name in bpy.data.node_groups:
            tree = bpy.data.node_groups[tree_name]
            tree.nodes.clear()
        else:
            tree = bpy.data.node_groups.new(tree_name, 'EMGraphNodeTreeType')

        tree.graph_id = graph_id
        tree.graph_name = tree_name
        
        # Filtra i nodi
        filtered_nodes = self.filter_nodes_optimized(graph, context)
        
        if not filtered_nodes:
            self.report({'WARNING'}, f"No nodes match filter: {self.filter_mode}")
            return {'CANCELLED'}
        
        print(f"   Filtered to {len(filtered_nodes)} nodes")

        # ✅ Validate edges before populating
        from .dynamic_nodes import validate_graph_edges
        from .socket_generator import load_datamodels

        nodes_dm, connections_dm = load_datamodels()
        if nodes_dm and connections_dm:
            validate_graph_edges(graph, connections_dm, nodes_dm)

        # Popola il grafo
        node_count, edge_count = self.populate_tree(tree, graph, filtered_nodes, context)

        tree.node_count = node_count
        tree.edge_count = edge_count

        # Apri l'editor
        self.open_graph_editor(context, tree)

        # Se siamo in modalità NEIGHBORHOOD, seleziona solo il nodo centrale
        if self.filter_mode == 'NEIGHBORHOOD':
            selected_node_id = self.get_selected_node_id(context)
            if selected_node_id:
                # Deseleziona tutto
                for node in tree.nodes:
                    node.select = False
                # Seleziona solo il nodo centrale
                for node in tree.nodes:
                    if node.node_id == selected_node_id:
                        node.select = True
                        tree.nodes.active = node
                        break

        self.report({'INFO'}, f"Loaded: {node_count} nodes, {edge_count} edges")
        return {'FINISHED'}
    
    def filter_nodes_optimized(self, graph, context):
        """Filtra i nodi in base al filter_mode"""
        
        if self.filter_mode == 'ALL':
            return list(graph.nodes)
        
        elif self.filter_mode == 'STRATIGRAPHIC':
            stratigraphic_types = ['US', 'USVs', 'USVn', 'SF', 'VSF', 'USD']
            filtered = []
            for node_type in stratigraphic_types:
                filtered.extend(graph.get_nodes_by_type(node_type))
            return filtered
        
        elif self.filter_mode == 'US_ONLY':
            return graph.get_nodes_by_type('US')
        
        elif self.filter_mode == 'FROM_UILIST':
            return self.filter_from_uilist(graph, context)
        
        elif self.filter_mode == 'NEIGHBORHOOD':
            return self.get_neighborhood_nodes(graph, context)
        
        elif self.filter_mode == 'NODE_CONTEXT':
            return self.get_node_context(graph, context)
        
        elif self.filter_mode == 'EDGE_FILTERED':
            return self.filter_by_edge_types(graph, context)
        
        return list(graph.nodes)
    
    def filter_from_uilist(self, graph, context):
        """Filtra usando solo i nodi presenti nella UIList corrente"""
        em_list = get_em_list_items(context)
        
        if not em_list or len(em_list) == 0:
            print("   ⚠️  UIList is empty")
            return []
        
        # ✅ Raccogli i NOMI (human-readable) dalla UIList
        ui_names = set()
        for item in em_list:
            if hasattr(item, 'name') and item.name:
                ui_names.add(item.name)
        
        print(f"   UIList contains {len(ui_names)} items")
        
        if not ui_names:
            print("   ⚠️  No valid names in UIList")
            return []
        
        # ✅ Filtra il grafo per node.name (non node.node_id!)
        filtered = []
        for node in graph.nodes:
            if node.name in ui_names:
                filtered.append(node)
        
        print(f"   Matched {len(filtered)} nodes from UIList")
        
        return filtered
    
    def get_neighborhood_nodes(self, graph, context):
        """Ottiene i nodi nel vicinato del nodo selezionato (qualsiasi tipo di nodo)"""

        # ✅ PRIMA: Controlla se c'è un node_id temporaneo salvato dall'operatore neighborhood
        selected_node_id = None
        if '_temp_neighborhood_node_id' in context.scene:
            selected_node_id = context.scene['_temp_neighborhood_node_id']
            print(f"   ✅ Using saved node_id from neighborhood operator: {selected_node_id}")
            # Rimuovi dopo l'uso
            del context.scene['_temp_neighborhood_node_id']
        else:
            # Altrimenti usa il metodo normale
            selected_node_id = self.get_selected_node_id(context)

        if not selected_node_id:
            print("   ⚠️  No node selected for neighborhood filter")
            print("   Please select a node in the Graph Editor, 3D view, or UIList")
            return []

        print(f"   Building neighborhood for node: {selected_node_id}")

        center_node = graph.find_node_by_id(selected_node_id)
        if not center_node:
            print(f"   ⚠️  Node not found: {selected_node_id}")
            return []

        # Mostra info sul nodo centrale
        node_type = getattr(center_node, 'node_type', 'unknown')
        node_name = getattr(center_node, 'name', 'unnamed')
        print(f"   Center node: {node_name} (type: {node_type})")
        
        # Usa get_connected_nodes di s3dgraphy
        neighborhood = {center_node.node_id: center_node}
        current_level = {center_node}
        
        for depth in range(self.neighborhood_depth):
            next_level = set()
            
            for node in current_level:
                connected = graph.get_connected_nodes(node.node_id)
                for connected_node in connected:
                    if connected_node.node_id not in neighborhood:
                        neighborhood[connected_node.node_id] = connected_node
                        next_level.add(connected_node)
            
            current_level = next_level
            if not next_level:
                break
        
        print(f"   Neighborhood: {len(neighborhood)} nodes at depth {self.neighborhood_depth}")
        return list(neighborhood.values())
    
    def get_node_context(self, graph, context):
        """
        Ottiene il nodo + contesto completo:
        - Vicinato stratigrafico immediato (is_before, overlies, etc.)
        - Tutti i paradata (has_property, extracted_from, etc.)
        - Modelli 3D (has_representation_model)
        """
        selected_node_id = self.get_selected_node_id(context)
        
        if not selected_node_id:
            if context.space_data.type == 'NODE_EDITOR' and context.active_node:
                selected_node_id = context.active_node.node_id
            
            if not selected_node_id:
                print("   ⚠️  No node selected for context view")
                return []
        
        center_node = graph.find_node_by_id(selected_node_id)
        if not center_node:
            return []
        
        print(f"   Building context for: {selected_node_id}")
        
        context_nodes = {center_node.node_id: center_node}
        
        settings = context.scene.graph_editor_settings
        
        # Definisci i tipi di edge da includere
        stratigraphic_types = [et['type'] for et in get_stratigraphic_edge_types()]
        paradata_types = [et['type'] for et in get_paradata_edge_types()]
        model_types = [et['type'] for et in get_model_edge_types()]
        
        # Raccogli nodi connessi
        for edge in graph.edges:
            include_edge = False
            
            if edge.edge_source == selected_node_id or edge.edge_target == selected_node_id:
                if settings.show_stratigraphic_context and edge.edge_type in stratigraphic_types:
                    include_edge = True
                elif settings.show_paradata_context and edge.edge_type in paradata_types:
                    include_edge = True
                elif settings.show_model_context and edge.edge_type in model_types:
                    include_edge = True
                
                if include_edge:
                    # Aggiungi entrambi i nodi
                    source = graph.find_node_by_id(edge.edge_source)
                    target = graph.find_node_by_id(edge.edge_target)
                    
                    if source:
                        context_nodes[source.node_id] = source
                    if target:
                        context_nodes[target.node_id] = target
        
        print(f"   Context: {len(context_nodes)} nodes")
        return list(context_nodes.values())
    
    def filter_by_edge_types(self, graph, context):
        """Filtra i nodi in base ai tipi di edge selezionati"""
        settings = context.scene.graph_editor_settings
        
        # Raccogli edge types abilitati
        enabled_edge_types = [
            ef.edge_type for ef in settings.edge_filters if ef.enabled
        ]
        
        if not enabled_edge_types:
            print("   ⚠️  No edge types enabled")
            return []
        
        print(f"   Filtering by {len(enabled_edge_types)} edge types")
        
        # Raccogli tutti i nodi connessi da questi edge types
        included_node_ids = set()
        
        for edge in graph.edges:
            if edge.edge_type in enabled_edge_types:
                included_node_ids.add(edge.edge_source)
                included_node_ids.add(edge.edge_target)
        
        filtered = [node for node in graph.nodes if node.node_id in included_node_ids]
        
        print(f"   Found {len(filtered)} nodes connected by selected edge types")
        return filtered
    
    def get_selected_node_id(self, context):
        """Ottiene l'ID del nodo selezionato, con priorità al Graph Editor se siamo lì"""

        # ✅ Se siamo nel Graph Editor, dai priorità al nodo selezionato lì
        if context.space_data and context.space_data.type == 'NODE_EDITOR':
            if context.active_node and hasattr(context.active_node, 'node_id'):
                node_id = context.active_node.node_id
                if node_id:
                    print(f"   Selected from Graph Editor: {node_id}")
                    return node_id

        # Altrimenti, ordine normale: 3D → UIList → Graph Editor

        # 1. Prova da oggetto 3D selezionato
        if context.active_object:
            node_id = find_node_id_from_proxy(context.active_object, context)
            if node_id:
                print(f"   Selected from 3D: {node_id}")
                return node_id

        # 2. Prova da UIList
        em_list = get_em_list_items(context)
        em_list_index = get_em_list_active_index(context)

        if em_list and 0 <= em_list_index < len(em_list):
            item = em_list[em_list_index]
            if hasattr(item, 'node_id') and item.node_id:
                print(f"   Selected from UIList: {item.node_id}")
                return item.node_id

        # 3. Fallback a Graph Editor (se non trovato sopra)
        if context.space_data and context.space_data.type == 'NODE_EDITOR':
            if context.active_node and hasattr(context.active_node, 'node_id'):
                print(f"   Selected from Graph Editor (fallback): {context.active_node.node_id}")
                return context.active_node.node_id

        return None
    
    def populate_tree(self, tree, graph, filtered_nodes, context):
        """Popola il node tree con wrapper dei nodi s3dgraphy"""
        from .dynamic_nodes import _NODE_TYPE_MAP

        node_map = {}
        edge_count = 0

        filtered_node_ids = {node.node_id for node in filtered_nodes}

        # ✅ Build dynamic node type map from registered classes
        node_type_map = {}
        for node_type, node_class in _NODE_TYPE_MAP.items():
            bl_idname = node_class.bl_idname
            node_type_map[node_type] = bl_idname

        print(f"\n📊 Creating {len(filtered_nodes)} nodes...")
        print(f"   Available node types: {len(node_type_map)}")

        for i, s3d_node in enumerate(filtered_nodes):
            # ✅ Use dynamic mapping with fallback to generic node
            node_type_id = node_type_map.get(s3d_node.node_type)

            if not node_type_id:
                print(f"⚠️  Unknown node type '{s3d_node.node_type}' for node {s3d_node.name}, skipping")
                continue

            try:
                bl_node = tree.nodes.new(node_type_id)
                bl_node.node_id = s3d_node.node_id
                bl_node.original_name = s3d_node.name
                bl_node.label = s3d_node.name[:30] if len(s3d_node.name) > 30 else s3d_node.name

                # Posizionamento temporaneo (verrà aggiornato dal layout algorithm)
                bl_node.location = (0, 0)

                # Colore
                if hasattr(s3d_node, 'attributes') and 'fill_color' in s3d_node.attributes:
                    fill_color_hex = s3d_node.attributes.get('fill_color')
                    if fill_color_hex and isinstance(fill_color_hex, str):
                        rgb = self.hex_to_rgb(fill_color_hex)
                        if rgb:
                            bl_node.custom_node_color = rgb
                            bl_node.use_custom_node_color = True

                node_map[s3d_node.node_id] = bl_node

            except Exception as e:
                print(f"❌ Error creating node {s3d_node.node_id}: {e}")

        print(f"✅ Created {len(node_map)} nodes")
        
        # Crea edges
        print(f"\n🔗 Creating edges...")
        for edge in graph.edges:
            try:
                if edge.edge_source in filtered_node_ids and edge.edge_target in filtered_node_ids:
                    if edge.edge_source in node_map and edge.edge_target in node_map:
                        if self.create_link(tree, node_map, edge.edge_source, edge.edge_target, edge.edge_type):
                            edge_count += 1
            except:
                pass

        print(f"✅ Created {edge_count} edges")

        # ✅ Calcola e applica layout gerarchico
        print(f"\n📐 Calculating hierarchical layout...")
        positions = calculate_hierarchical_layout(node_map, graph, filtered_node_ids)
        apply_layout_to_nodes(node_map, positions)
        print(f"✅ Layout applied\n")

        return len(node_map), edge_count
    
    def create_link(self, tree, node_map, source_id, target_id, edge_type):
        """
        Crea un collegamento tra nodi con matching migliorato dei socket.

        Priorità di matching:
        1. Match esatto (edge_type == socket.name)
        2. Match case-insensitive
        3. Match parziale con keywords
        4. Fallback al primo socket disponibile
        """
        source_node = node_map[source_id]
        target_node = node_map[target_id]

        source_socket = None
        target_socket = None

        # ✅ 1. Match ESATTO (priorità massima)
        for output in source_node.outputs:
            if output.name == edge_type:
                source_socket = output
                break

        for input_socket in target_node.inputs:
            if input_socket.name == edge_type:
                target_socket = input_socket
                break

        # ✅ 2. Match case-insensitive
        if not source_socket:
            edge_type_lower = edge_type.lower() if edge_type else 'connection'
            for output in source_node.outputs:
                if output.name.lower() == edge_type_lower:
                    source_socket = output
                    break

        if not target_socket:
            edge_type_lower = edge_type.lower() if edge_type else 'connection'
            for input_socket in target_node.inputs:
                if input_socket.name.lower() == edge_type_lower:
                    target_socket = input_socket
                    break

        # ✅ 3. Match parziale (keywords)
        if not source_socket:
            edge_type_lower = edge_type.lower() if edge_type else 'connection'
            keywords = edge_type_lower.replace('_', ' ').split()
            for output in source_node.outputs:
                if all(kw in output.name.lower() for kw in keywords):
                    source_socket = output
                    break

        if not target_socket:
            edge_type_lower = edge_type.lower() if edge_type else 'connection'
            keywords = edge_type_lower.replace('_', ' ').split()
            for input_socket in target_node.inputs:
                if all(kw in input_socket.name.lower() for kw in keywords):
                    target_socket = input_socket
                    break

        # ✅ 4. Fallback (ultimo resort)
        if not source_socket and len(source_node.outputs) > 0:
            # Debug: stampa warning se dobbiamo usare fallback
            if edge_type:
                print(f"   ⚠️  No matching output socket for '{edge_type}' on {source_node.bl_label}")
                print(f"       Available outputs: {[s.name for s in source_node.outputs]}")
            source_socket = source_node.outputs[0]

        if not target_socket and len(target_node.inputs) > 0:
            if edge_type:
                print(f"   ⚠️  No matching input socket for '{edge_type}' on {target_node.bl_label}")
                print(f"       Available inputs: {[s.name for s in target_node.inputs]}")
            target_socket = target_node.inputs[0]

        # Crea il link
        if source_socket and target_socket:
            try:
                tree.links.new(source_socket, target_socket)
                return True
            except Exception as e:
                print(f"   ❌ Failed to create link: {e}")
                return False

        return False
    
    def hex_to_rgb(self, hex_color):
        """Converti hex a RGB"""
        try:
            hex_color = hex_color.lstrip('#')
            if len(hex_color) == 6:
                r = int(hex_color[0:2], 16) / 255.0
                g = int(hex_color[2:4], 16) / 255.0
                b = int(hex_color[4:6], 16) / 255.0
                return (r, g, b)
        except:
            pass
        return None
    
    def open_graph_editor(self, context, tree):
        """Apri l'editor EMGraph in una nuova finestra se non esiste già"""
        # Prima controlla se esiste già una finestra con EMGraph editor aperto
        for window in context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'NODE_EDITOR':
                    space = area.spaces[0]
                    if hasattr(space, 'tree_type') and space.tree_type == 'EMGraphNodeTreeType':
                        # Finestra già esistente, aggiorna il tree
                        space.node_tree = tree
                        print("✓ Updated existing EMGraph editor window")
                        return

        # Nessuna finestra EMGraph trovata, creane una nuova
        print("✓ Creating new EMGraph editor window")
        bpy.ops.wm.window_new()

        # Ottieni la nuova finestra (è l'ultima creata)
        new_window = context.window_manager.windows[-1]

        # Trova la prima area disponibile e convertila in NODE_EDITOR
        for area in new_window.screen.areas:
            area.type = 'NODE_EDITOR'
            space = area.spaces[0]
            space.tree_type = 'EMGraphNodeTreeType'
            space.node_tree = tree
            print(f"✓ New window created with EMGraph: {tree.name}")
            break


class GRAPHEDIT_OT_sync_selection(Operator):
    """Sincronizza selezione tra 3D, UIList e Graph Editor (Shift+Alt+F)"""
    bl_idname = "graphedit.sync_selection"
    bl_label = "Sync Selection"
    bl_description = "Synchronize selection between 3D viewport, UI lists, and graph editor"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        return True
    
    def execute(self, context):
        if context.space_data.type == 'NODE_EDITOR':
            return self.sync_from_graph_editor(context)
        elif context.space_data.type == 'VIEW_3D':
            return self.sync_from_3d(context)
        else:
            self.report({'WARNING'}, "Use Shift+Alt+F in 3D View or Node Editor")
            return {'CANCELLED'}
        
    def sync_from_graph_editor(self, context):
        """Sincronizza dal Graph Editor verso 3D + UIList"""
        if not context.active_node:
            self.report({'WARNING'}, "No node selected")
            return {'CANCELLED'}
        
        node = context.active_node
        
        # ✅ Usa il LABEL come human name
        if not hasattr(node, 'label') or not node.label:
            self.report({'WARNING'}, "Node has no label")
            return {'CANCELLED'}
        
        human_name = node.label
        print(f"🔗 Syncing from graph editor: label='{human_name}'")
        
        # ✅ Cerca proxy usando human name + prefisso
        from .utils import add_graph_prefix
        prefixed_name = add_graph_prefix(human_name, context)
        
        proxy = None
        for obj in bpy.data.objects:
            if obj.name == prefixed_name:
                proxy = obj
                break
        
        if proxy:
            bpy.ops.object.select_all(action='DESELECT')
            proxy.select_set(True)
            context.view_layer.objects.active = proxy
            print(f"   ✓ Selected 3D proxy: {proxy.name}")
        else:
            print(f"   ✗ Proxy not found: '{prefixed_name}'")
        
        # ✅ Sincronizza UIList usando human name
        from .utils import sync_ui_list
        sync_ui_list(context, human_name)
        
        self.report({'INFO'}, f"Synced: {human_name}")
        return {'FINISHED'}
        
    def sync_from_3d(self, context):
        """Sincronizza dal 3D verso Graph Editor + UIList"""
        if not context.active_object:
            self.report({'WARNING'}, "No object selected")
            return {'CANCELLED'}
        
        obj = context.active_object
        
        # ✅ Estrai human name dal proxy
        from .utils import remove_graph_prefix
        human_name = remove_graph_prefix(obj.name, context)
        
        print(f"🔗 Syncing from 3D: '{obj.name}' → human name: '{human_name}'")
        
        # ✅ Sincronizza Graph Editor - cerca per LABEL
        graph_synced = False

        # ✅ Determina quale tree usare in base alla modalità
        em_tools = context.scene.em_tools
        expected_tree_name = "3dgis_graph" if not em_tools.mode_em_advanced else None

        for window in bpy.data.window_managers[0].windows:
            for area in window.screen.areas:
                if area.type == 'NODE_EDITOR':
                    space = area.spaces[0]

                    if space.tree_type == 'EMGraphNodeTreeType' and space.node_tree:
                        tree = space.node_tree

                        # ✅ In 3D GIS mode, cerca solo nel tree "3dgis_graph"
                        if expected_tree_name and tree.name != expected_tree_name:
                            continue

                        print(f"   Searching in tree: {tree.name}")
                        
                        # Deseleziona tutto
                        for n in tree.nodes:
                            n.select = False
                        
                        # ✅ CERCA PER LABEL (contiene human name)
                        for n in tree.nodes:
                            if hasattr(n, 'label') and n.label == human_name:
                                n.select = True
                                tree.nodes.active = n
                                graph_synced = True
                                print(f"   ✓ Selected graph node by label: '{n.label}'")
                                break
                        
                        if graph_synced:
                            break
            
            if graph_synced:
                break
        
        if not graph_synced:
            print(f"   ⚠️  Node '{human_name}' not found in Graph Editor")
            print(f"      (may be filtered out or not loaded)")
        
        # ✅ Sincronizza UIList usando human name
        from .utils import sync_ui_list
        sync_ui_list(context, human_name)
        
        self.report({'INFO'}, f"Synced: {human_name}")
        return {'FINISHED'}
    
    def sync_graph_editor(self, context, node_id):
        """Seleziona nodo nel graph editor"""
        for area in context.screen.areas:
            if area.type == 'NODE_EDITOR':
                space = area.spaces[0]
                
                if space.tree_type == 'EMGraphNodeTreeType' and space.node_tree:
                    tree = space.node_tree
                    
                    for node in tree.nodes:
                        node.select = False
                    
                    for node in tree.nodes:
                        if hasattr(node, 'node_id') and node.node_id == node_id:
                            node.select = True
                            tree.nodes.active = node
                            print(f"   ✓ Selected graph node: {node.label}")
                            return True
        
        return False
    

class GRAPHEDIT_OT_draw_neighborhood(Operator):
    """Disegna vicinato del nodo selezionato (context-aware: Graph Editor o 3D)"""
    bl_idname = "graphedit.draw_neighborhood"
    bl_label = "Draw Neighborhood"
    bl_description = "Draw neighborhood of selected node from current context"
    bl_options = {'REGISTER', 'UNDO'}

    depth: IntProperty(
        name="Depth",
        default=1,
        min=1,
        max=5
    )

    def execute(self, context):
        # ✅ PRIMA cattura il nodo selezionato dal contesto corrente
        selected_node_id = self._get_selected_node_from_context(context)

        if not selected_node_id:
            self.report({'WARNING'}, "No node selected. Select a node in Graph Editor, 3D view, or UIList")
            return {'CANCELLED'}

        print(f"\n🎯 Neighborhood request for node: {selected_node_id}")

        # Salva temporaneamente il node_id in una proprietà di scena
        context.scene['_temp_neighborhood_node_id'] = selected_node_id

        bpy.ops.graphedit.draw_graph(
            'INVOKE_DEFAULT',
            filter_mode='NEIGHBORHOOD',
            neighborhood_depth=self.depth
        )
        return {'FINISHED'}

    def _get_selected_node_from_context(self, context):
        """Ottiene il nodo selezionato dando priorità al contesto corrente"""

        # ✅ PRIORITÀ 1: Se siamo nel Graph Editor (NODE_EDITOR)
        if context.area and context.area.type == 'NODE_EDITOR':
            if context.active_node and hasattr(context.active_node, 'node_id'):
                node_id = context.active_node.node_id
                if node_id:
                    print(f"   📍 Selected from Graph Editor: {node_id}")
                    return node_id

        # ✅ PRIORITÀ 2: Se siamo nella 3D View
        if context.area and context.area.type == 'VIEW_3D':
            if context.active_object:
                node_id = find_node_id_from_proxy(context.active_object, context)
                if node_id:
                    print(f"   📍 Selected from 3D View: {node_id}")
                    return node_id

        # ✅ PRIORITÀ 3: UIList (sempre disponibile)
        em_list = get_em_list_items(context)
        em_list_index = get_em_list_active_index(context)

        if em_list and 0 <= em_list_index < len(em_list):
            item = em_list[em_list_index]
            if hasattr(item, 'node_id') and item.node_id:
                print(f"   📍 Selected from UIList: {item.node_id}")
                return item.node_id

        return None


class GRAPHEDIT_OT_initialize_edge_filters(Operator):
    """Inizializza filtri edge dalla configurazione s3dgraphy"""
    bl_idname = "graphedit.initialize_edge_filters"
    bl_label = "Initialize Edge Filters"
    bl_description = "Load edge types from s3dgraphy configuration"
    
    def execute(self, context):
        from .properties import initialize_edge_filters
        initialize_edge_filters(context)
        self.report({'INFO'}, "Edge filters initialized")
        return {'FINISHED'}


# ... (altri operatori: clear_editor, refresh_node, apply_color_scheme rimangono invariati)

class GRAPHEDIT_OT_clear_editor(Operator):
    """Pulisci editor"""
    bl_idname = "graphedit.clear_editor"
    bl_label = "Clear Graph"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        if context.space_data.type == 'NODE_EDITOR':
            tree = context.space_data.node_tree
            if tree and tree.bl_idname == 'EMGraphNodeTreeType':
                tree.nodes.clear()
                tree.node_count = 0
                tree.edge_count = 0
                self.report({'INFO'}, "Graph cleared")
                return {'FINISHED'}
        
        self.report({'ERROR'}, "Not in EMGraph editor")
        return {'CANCELLED'}


classes = (
    GRAPHEDIT_OT_draw_graph,
    GRAPHEDIT_OT_sync_selection,
    GRAPHEDIT_OT_draw_neighborhood,
    GRAPHEDIT_OT_initialize_edge_filters,
    GRAPHEDIT_OT_clear_editor,
)

def register_operators():
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except ValueError:
            pass

def unregister_operators():
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass