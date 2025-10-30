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

class GRAPHEDIT_OT_draw_graph(Operator):
    """Disegna il grafo attivo nell'editor EMGraph"""
    bl_idname = "graphedit.draw_graph"
    bl_label = "Draw Graph"
    bl_description = "Load and draw the active graph from EM Setup into the EMGraph editor"
    bl_options = {'REGISTER', 'UNDO'}
    
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
        em_tools = context.scene.em_tools
        
        if em_tools.active_file_index < 0 or not em_tools.graphml_files:
            self.report({'ERROR'}, "No active GraphML file in EM Setup")
            return {'CANCELLED'}
        
        graphml = em_tools.graphml_files[em_tools.active_file_index]
        graph_id = graphml.name
        graph = get_graph(graph_id)
        
        if not graph:
            self.report({'ERROR'}, f"Graph '{graph_id}' not found in s3dgraphy")
            return {'CANCELLED'}
        
        print(f"\n✅ Found graph: {graph_id}")
        print(f"   Total nodes: {len(graph.nodes)}")
        print(f"   Total edges: {len(graph.edges)}")
        print(f"   Filter mode: {self.filter_mode}")
        
        # Trova o crea il node tree
        tree_name = f"EMGraph_{graphml.graph_code if hasattr(graphml, 'graph_code') else graphml.name}"
        
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
        
        # Popola il grafo
        node_count, edge_count = self.populate_tree(tree, graph, filtered_nodes, context)
        
        tree.node_count = node_count
        tree.edge_count = edge_count
        
        # Apri l'editor
        self.open_graph_editor(context, tree)
        
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
        
        # Raccogli i node_id dalla UIList
        ui_node_ids = set()
        for item in em_list:
            if hasattr(item, 'node_id') and item.node_id:
                ui_node_ids.add(item.node_id)
        
        print(f"   UIList contains {len(ui_node_ids)} node IDs")
        
        # Filtra il grafo
        filtered = [node for node in graph.nodes if node.node_id in ui_node_ids]
        
        return filtered
    
    def get_neighborhood_nodes(self, graph, context):
        """Ottiene i nodi nel vicinato del nodo selezionato"""
        selected_node_id = self.get_selected_node_id(context)
        
        if not selected_node_id:
            if context.space_data.type == 'NODE_EDITOR' and context.active_node:
                selected_node_id = context.active_node.node_id
            
            if not selected_node_id:
                print("   ⚠️  No node selected for neighborhood filter")
                return []
        
        print(f"   Building neighborhood for: {selected_node_id}")
        
        center_node = graph.find_node_by_id(selected_node_id)
        if not center_node:
            print(f"   ⚠️  Node not found: {selected_node_id}")
            return []
        
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
        """Ottiene l'ID del nodo selezionato (da 3D, UIList o Graph Editor)"""
        
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
        
        # 3. Prova da Graph Editor
        if context.space_data.type == 'NODE_EDITOR' and context.active_node:
            if hasattr(context.active_node, 'node_id'):
                print(f"   Selected from Graph Editor: {context.active_node.node_id}")
                return context.active_node.node_id
        
        return None
    
    def populate_tree(self, tree, graph, filtered_nodes, context):
        """Popola il node tree con wrapper dei nodi s3dgraphy"""
        node_map = {}
        edge_count = 0
        
        filtered_node_ids = {node.node_id for node in filtered_nodes}
        
        # Mappa tipi
        node_type_map = {
            'US': 'EMGraphUSNodeType',
            'USVs': 'EMGraphUSVsNodeType',
            'USVn': 'EMGraphUSVnNodeType',
            'SF': 'EMGraphSFNodeType',
            'VSF': 'EMGraphVSFNodeType',
            'USD': 'EMGraphUSDNodeType',
            'epoch': 'EMGraphEpochNodeType',
            'property': 'EMGraphParadataNodeType',
            'extractor': 'EMGraphParadataNodeType',
            'combiner': 'EMGraphParadataNodeType',
            'document': 'EMGraphDocumentNodeType',
            'activity_group': 'EMGraphGroupNodeType',
            'paradata_group': 'EMGraphGroupNodeType',
            'time_branch_group': 'EMGraphGroupNodeType',
            'representation_model': 'EMGraphRepresentationNodeType',
            'representation_model_doc': 'EMGraphRepresentationNodeType',
            'representation_model_sf': 'EMGraphRepresentationNodeType',
            'semantic_shape': 'EMGraphRepresentationNodeType',
            'link': 'EMGraphLinkNodeType',
        }
        
        print(f"\n📊 Creating {len(filtered_nodes)} nodes...")
        for i, s3d_node in enumerate(filtered_nodes):
            node_type_id = node_type_map.get(s3d_node.node_type, 'EMGraphUSNodeType')
            
            try:
                bl_node = tree.nodes.new(node_type_id)
                bl_node.node_id = s3d_node.node_id
                bl_node.original_name = s3d_node.name
                bl_node.label = s3d_node.name[:30] if len(s3d_node.name) > 30 else s3d_node.name
                
                # Posizionamento
                if hasattr(s3d_node, 'attributes') and 'y_pos' in s3d_node.attributes:
                    try:
                        y_pos = float(s3d_node.attributes.get('y_pos', 0))
                        x_pos = (i % 10) * 350
                        bl_node.location = (x_pos, -y_pos * 2)
                    except:
                        bl_node.location = ((i % 10) * 350, -(i // 10) * 200)
                else:
                    bl_node.location = ((i % 10) * 350, -(i // 10) * 200)
                
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
        
        print(f"✅ Created {edge_count} edges\n")
        
        return len(node_map), edge_count
    
    def create_link(self, tree, node_map, source_id, target_id, edge_type):
        """Crea un collegamento tra nodi"""
        source_node = node_map[source_id]
        target_node = node_map[target_id]
        
        edge_type_lower = edge_type.lower() if edge_type else 'connection'
        
        source_socket = None
        target_socket = None
        
        # Match esatto
        for output in source_node.outputs:
            if edge_type_lower in output.name.lower():
                source_socket = output
                break
        
        for input_socket in target_node.inputs:
            if edge_type_lower in input_socket.name.lower():
                target_socket = input_socket
                break
        
        # Match parziale
        if not source_socket:
            keywords = edge_type_lower.replace('_', ' ').split()
            for output in source_node.outputs:
                if any(kw in output.name.lower() for kw in keywords):
                    source_socket = output
                    break
        
        if not target_socket:
            keywords = edge_type_lower.replace('_', ' ').split()
            for input_socket in target_node.inputs:
                if any(kw in input_socket.name.lower() for kw in keywords):
                    target_socket = input_socket
                    break
        
        # Fallback
        if not source_socket and len(source_node.outputs) > 0:
            source_socket = source_node.outputs[0]
        
        if not target_socket and len(target_node.inputs) > 0:
            target_socket = target_node.inputs[0]
        
        if source_socket and target_socket:
            try:
                tree.links.new(source_socket, target_socket)
                return True
            except:
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
        """Apri l'editor EMGraph"""
        for area in context.screen.areas:
            if area.type == 'NODE_EDITOR':
                space = area.spaces[0]
                space.tree_type = 'EMGraphNodeTreeType'
                space.node_tree = tree
                return


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
        """Dal Graph Editor → 3D + UIList"""
        if not context.active_node:
            self.report({'WARNING'}, "No node selected")
            return {'CANCELLED'}
        
        node = context.active_node
        if not hasattr(node, 'node_id') or not node.node_id:
            self.report({'WARNING'}, "Node has no ID")
            return {'CANCELLED'}
        
        node_id = node.node_id
        print(f"🔗 Syncing from graph: {node_id}")
        
        # Cerca proxy 3D
        proxy = find_proxy_by_node_id(node_id, context)
        if proxy:
            bpy.ops.object.select_all(action='DESELECT')
            proxy.select_set(True)
            context.view_layer.objects.active = proxy
            print(f"   ✓ Selected 3D proxy: {proxy.name}")
        
        # Sincronizza UIList
        self.sync_ui_list(context, node_id)
        
        self.report({'INFO'}, f"Synced: {node.label}")
        return {'FINISHED'}
    
    def sync_from_3d(self, context):
        """Dal 3D → Graph Editor + UIList"""
        if not context.active_object:
            self.report({'WARNING'}, "No object selected")
            return {'CANCELLED'}
        
        node_id = find_node_id_from_proxy(context.active_object, context)
        
        if not node_id:
            self.report({'WARNING'}, "Object has no node_id")
            return {'CANCELLED'}
        
        print(f"🔗 Syncing from 3D: {node_id}")
        
        # Sincronizza Graph Editor
        self.sync_graph_editor(context, node_id)
        
        # Sincronizza UIList
        self.sync_ui_list(context, node_id)
        
        self.report({'INFO'}, f"Synced: {context.active_object.name}")
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
    
    def sync_ui_list(self, context, node_id):
        """Sincronizza UIList"""
        em_list = get_em_list_items(context)
        
        if not em_list:
            return False
        
        for i, item in enumerate(em_list):
            if hasattr(item, 'node_id') and item.node_id == node_id:
                set_em_list_active_index(context, i)
                print(f"   ✓ Selected UIList item: {item.name}")
                return True
        
        return False


class GRAPHEDIT_OT_draw_neighborhood(Operator):
    """Disegna vicinato del nodo selezionato"""
    bl_idname = "graphedit.draw_neighborhood"
    bl_label = "Draw Neighborhood"
    bl_description = "Draw neighborhood of selected node"
    bl_options = {'REGISTER', 'UNDO'}
    
    depth: IntProperty(
        name="Depth",
        default=1,
        min=1,
        max=5
    )
    
    def execute(self, context):
        bpy.ops.graphedit.draw_graph(
            'INVOKE_DEFAULT',
            filter_mode='NEIGHBORHOOD',
            neighborhood_depth=self.depth
        )
        return {'FINISHED'}


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