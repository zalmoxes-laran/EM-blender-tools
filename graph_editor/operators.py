"""
Operators for Graph Editor
Handles loading, clearing, and manipulating graphs in the node editor.
"""

import bpy
from bpy.types import Operator
from bpy.props import EnumProperty, BoolProperty, IntProperty
from s3dgraphy import get_graph

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
            ('STRATIGRAPHIC', "Stratigraphic Only", "Show only stratigraphic nodes"),
            ('TEMPORAL', "Temporal", "Show nodes in time range"),
            ('NEIGHBORHOOD', "Neighborhood", "Show selected node and connected nodes"),
        ],
        default='ALL'
    ) # type: ignore
    
    neighborhood_depth: IntProperty(
        name="Depth",
        description="Number of connection levels to show",
        default=1,
        min=1,
        max=5
    ) # type: ignore
    
    def execute(self, context):
        # Ottieni il grafo da s3dgraphy
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
        print(f"   Nodes: {len(graph.nodes)}")
        print(f"   Edges: {len(graph.edges)}")
        
        # Trova o crea il node tree
        tree_name = f"EMGraph_{graphml.graph_code if hasattr(graphml, 'graph_code') else graphml.name}"
        
        if tree_name in bpy.data.node_groups:
            tree = bpy.data.node_groups[tree_name]
            tree.nodes.clear()
        else:
            tree = bpy.data.node_groups.new(tree_name, 'EMGraphNodeTreeType')
        
        tree.graph_id = graph_id
        tree.graph_name = tree_name
        
        # Filtra i nodi in base al filter_mode
        filtered_nodes = self.filter_nodes(graph, context)
        
        # Popola il grafo
        node_count, edge_count = self.populate_tree(tree, graph, filtered_nodes, context)
        
        tree.node_count = node_count
        tree.edge_count = edge_count
        
        # Apri l'editor
        self.open_graph_editor(context, tree)
        
        self.report({'INFO'}, f"Loaded '{tree_name}': {node_count} nodes, {edge_count} edges")
        return {'FINISHED'}
    
    def filter_nodes(self, graph, context):
        """Filtra i nodi in base al filter_mode"""
        if self.filter_mode == 'ALL':
            return list(graph.nodes)
        
        elif self.filter_mode == 'STRATIGRAPHIC':
            stratigraphic_types = ['US', 'USVs', 'USVn', 'SF', 'VSF', 'USD']
            return [n for n in graph.nodes if n.node_type in stratigraphic_types]
        
        elif self.filter_mode == 'NEIGHBORHOOD':
            return self.get_neighborhood_nodes(graph, context)
        
        else:
            return list(graph.nodes)
    
    def get_neighborhood_nodes(self, graph, context):
        """Ottiene i nodi nel vicinato del nodo selezionato"""
        em_tools = context.scene.em_tools
        
        # Trova il nodo selezionato (da stratigraphy manager o oggetto 3D)
        selected_node_id = self.get_selected_node_id(context)
        
        if not selected_node_id:
            self.report({'WARNING'}, "No node selected for neighborhood filter")
            return list(graph.nodes)
        
        # Trova il nodo nel grafo
        center_node = graph.find_node_by_id(selected_node_id)
        if not center_node:
            return list(graph.nodes)
        
        # Raccogli nodi nel vicinato
        neighborhood = {center_node.node_id: center_node}
        current_level = {center_node.node_id}
        
        for depth in range(self.neighborhood_depth):
            next_level = set()
            
            for node_id in current_level:
                # Trova edges collegati
                for edge in graph.edges:
                    if edge.edge_source == node_id:
                        target_node = graph.find_node_by_id(edge.edge_target)
                        if target_node and target_node.node_id not in neighborhood:
                            neighborhood[target_node.node_id] = target_node
                            next_level.add(target_node.node_id)
                    
                    elif edge.edge_target == node_id:
                        source_node = graph.find_node_by_id(edge.edge_source)
                        if source_node and source_node.node_id not in neighborhood:
                            neighborhood[source_node.node_id] = source_node
                            next_level.add(source_node.node_id)
            
            current_level = next_level
        
        return list(neighborhood.values())
    
    def get_selected_node_id(self, context):
        """Ottiene l'ID del nodo selezionato (da 3D o UI)"""
        # Prova da stratigraphy manager
        em_tools = context.scene.em_tools
        if hasattr(em_tools, 'active_item_index') and em_tools.active_item_index >= 0:
            if em_tools.items:
                item = em_tools.items[em_tools.active_item_index]
                if hasattr(item, 'uuid'):
                    return item.uuid
        
        # Prova da oggetto 3D selezionato
        if context.active_object:
            obj = context.active_object
            if 'node_id' in obj:
                return obj['node_id']
            elif 'uuid' in obj:
                return obj['uuid']
        
        return None
    
    def populate_tree(self, tree, graph, filtered_nodes, context):
        """Popola il node tree con wrapper dei nodi s3dgraphy"""
        node_map = {}
        edge_count = 0
        
        # Crea set di node_id filtrati per lookup veloce
        filtered_node_ids = {node.node_id for node in filtered_nodes}
        
        # Mappa tipi di nodo s3dgraphy -> wrapper Blender
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
        
        # Crea i nodi wrapper
        print(f"\n📊 Creating {len(filtered_nodes)} nodes...")
        for i, s3d_node in enumerate(filtered_nodes):
            # Determina il tipo di wrapper
            node_type_id = node_type_map.get(s3d_node.node_type, 'EMGraphStratigraphicNodeType')
            
            try:
                # Crea il wrapper
                bl_node = tree.nodes.new(node_type_id)
                
                # Imposta solo l'ID di riferimento
                bl_node.node_id = s3d_node.node_id
                bl_node.original_name = s3d_node.name
                bl_node.label = s3d_node.name[:30] if len(s3d_node.name) > 30 else s3d_node.name
                
                # Posiziona il nodo
                if hasattr(s3d_node, 'attributes') and 'y_pos' in s3d_node.attributes:
                    try:
                        y_pos = float(s3d_node.attributes.get('y_pos', 0))
                        x_pos = (i % 10) * 350
                        bl_node.location = (x_pos, -y_pos * 2)
                    except (ValueError, TypeError):
                        bl_node.location = ((i % 10) * 350, -(i // 10) * 200)
                else:
                    bl_node.location = ((i % 10) * 350, -(i // 10) * 200)
                
                # Cache per epoche
                if s3d_node.node_type == 'epoch':
                    if hasattr(s3d_node, 'start_time'):
                        try:
                            bl_node.start_time = float(s3d_node.start_time)
                        except (ValueError, TypeError):
                            pass
                    if hasattr(s3d_node, 'end_time'):
                        try:
                            bl_node.end_time = float(s3d_node.end_time)
                        except (ValueError, TypeError):
                            pass
                
                # Converti colore hex a RGB
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
        
        print(f"✅ Created {len(node_map)} nodes successfully")
        
        # Crea i collegamenti solo tra nodi filtrati
        print(f"\n🔗 Creating edges...")
        for i, edge in enumerate(graph.edges):
            try:
                source_id = edge.edge_source
                target_id = edge.edge_target
                edge_type = edge.edge_type
                
                # Solo se entrambi i nodi sono nel filtro
                if source_id in filtered_node_ids and target_id in filtered_node_ids:
                    if source_id in node_map and target_id in node_map:
                        link_created = self.create_link(tree, node_map, source_id, target_id, edge_type)
                        if link_created:
                            edge_count += 1
                        
            except Exception as e:
                print(f"❌ Error processing edge {i}: {e}")
        
        print(f"✅ Created {edge_count} edges successfully\n")
        
        return len(node_map), edge_count
    
    def create_link(self, tree, node_map, source_id, target_id, edge_type):
        """Crea un collegamento tra nodi wrapper"""
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
            edge_keywords = edge_type_lower.replace('_', ' ').split()
            for output in source_node.outputs:
                if any(kw in output.name.lower() for kw in edge_keywords):
                    source_socket = output
                    break
        
        if not target_socket:
            edge_keywords = edge_type_lower.replace('_', ' ').split()
            for input_socket in target_node.inputs:
                if any(kw in input_socket.name.lower() for kw in edge_keywords):
                    target_socket = input_socket
                    break
        
        # Fallback
        if not source_socket and len(source_node.outputs) > 0:
            source_socket = source_node.outputs[0]
        
        if not target_socket and len(target_node.inputs) > 0:
            target_socket = target_node.inputs[0]
        
        # Crea il link
        if source_socket and target_socket:
            try:
                tree.links.new(source_socket, target_socket)
                return True
            except:
                return False
        
        return False
    
    def hex_to_rgb(self, hex_color):
        """Converti colore hex (#RRGGBB) in RGB (0-1)"""
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
    """Sincronizza selezione tra 3D Viewport, UI e Graph Editor (Alt+F)"""
    bl_idname = "graphedit.sync_selection"
    bl_label = "Sync Selection"
    bl_description = "Synchronize selection between 3D viewport, UI lists, and graph editor (Alt+F)"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        return True
    
    def execute(self, context):
        # Determina il contesto da cui viene chiamato
        if context.space_data.type == 'NODE_EDITOR':
            # Da Graph Editor → 3D + UI
            return self.sync_from_graph_editor(context)
        elif context.space_data.type == 'VIEW_3D':
            # Da 3D → Graph Editor + UI
            return self.sync_from_3d(context)
        else:
            self.report({'WARNING'}, "Use Alt+F in 3D View or Node Editor")
            return {'CANCELLED'}
    
    def sync_from_graph_editor(self, context):
        """Sincronizza selezione dal Graph Editor verso 3D e UI"""
        if not context.active_node:
            self.report({'WARNING'}, "No node selected in graph editor")
            return {'CANCELLED'}
        
        node = context.active_node
        if not hasattr(node, 'node_id') or not node.node_id:
            self.report({'WARNING'}, "Selected node has no ID")
            return {'CANCELLED'}
        
        node_id = node.node_id
        print(f"🔗 Syncing from graph editor: {node_id}")
        
        # Cerca oggetto 3D corrispondente
        obj_found = False
        for obj in bpy.data.objects:
            if obj.get('node_id') == node_id or obj.get('uuid') == node_id:
                # Deseleziona tutto
                bpy.ops.object.select_all(action='DESELECT')
                # Seleziona questo oggetto
                obj.select_set(True)
                context.view_layer.objects.active = obj
                obj_found = True
                print(f"   ✓ Selected 3D object: {obj.name}")
                break
        
        # Sincronizza UI list (stratigraphy manager)
        self.sync_ui_list(context, node_id)
        
        if obj_found:
            self.report({'INFO'}, f"Selected: {node.label}")
        else:
            self.report({'INFO'}, f"Node {node.label} has no 3D object")
        
        return {'FINISHED'}
    
    def sync_from_3d(self, context):
        """Sincronizza selezione dal 3D verso Graph Editor e UI"""
        if not context.active_object:
            self.report({'WARNING'}, "No object selected")
            return {'CANCELLED'}
        
        obj = context.active_object
        node_id = obj.get('node_id') or obj.get('uuid')
        
        if not node_id:
            self.report({'WARNING'}, f"Object {obj.name} has no node_id")
            return {'CANCELLED'}
        
        print(f"🔗 Syncing from 3D: {node_id}")
        
        # Sincronizza Graph Editor
        graph_synced = self.sync_graph_editor(context, node_id)
        
        # Sincronizza UI list
        self.sync_ui_list(context, node_id)
        
        if graph_synced:
            self.report({'INFO'}, f"Synced: {obj.name}")
        else:
            self.report({'INFO'}, f"Synced UI (no graph node for {obj.name})")
        
        return {'FINISHED'}
    
    def sync_graph_editor(self, context, node_id):
        """Seleziona il nodo nel graph editor"""
        # Cerca un'area Node Editor
        for area in context.screen.areas:
            if area.type == 'NODE_EDITOR':
                space = area.spaces[0]
                
                if space.tree_type == 'EMGraphNodeTreeType' and space.node_tree:
                    tree = space.node_tree
                    
                    # Deseleziona tutti i nodi
                    for node in tree.nodes:
                        node.select = False
                    
                    # Cerca e seleziona il nodo corrispondente
                    for node in tree.nodes:
                        if hasattr(node, 'node_id') and node.node_id == node_id:
                            node.select = True
                            tree.nodes.active = node
                            print(f"   ✓ Selected graph node: {node.label}")
                            return True
        
        return False
    
    def sync_ui_list(self, context, node_id):
        """Sincronizza la selezione nella UI list (stratigraphy manager)"""
        em_tools = context.scene.em_tools
        
        if not hasattr(em_tools, 'items'):
            return False
        
        # Cerca l'item nella lista
        for i, item in enumerate(em_tools.items):
            if hasattr(item, 'uuid') and item.uuid == node_id:
                em_tools.active_item_index = i
                print(f"   ✓ Selected UI list item: {item.name}")
                return True
        
        return False


class GRAPHEDIT_OT_draw_neighborhood(Operator):
    """Disegna solo il vicinato del nodo selezionato"""
    bl_idname = "graphedit.draw_neighborhood"
    bl_label = "Draw Neighborhood"
    bl_description = "Draw only the selected node and its connected neighbors"
    bl_options = {'REGISTER', 'UNDO'}
    
    depth: IntProperty(
        name="Depth",
        description="Number of connection levels",
        default=1,
        min=1,
        max=5
    ) # type: ignore
    
    def execute(self, context):
        # Chiama draw_graph con filter_mode NEIGHBORHOOD
        bpy.ops.graphedit.draw_graph(
            filter_mode='NEIGHBORHOOD',
            neighborhood_depth=self.depth
        )
        return {'FINISHED'}


# ... (operatori esistenti: clear_editor, refresh_node, apply_color_scheme rimangono invariati)


class GRAPHEDIT_OT_clear_editor(Operator):
    """Pulisci l'editor EMGraph"""
    bl_idname = "graphedit.clear_editor"
    bl_label = "Clear Graph"
    bl_description = "Clear all nodes from the current EMGraph editor"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        if context.space_data.type == 'NODE_EDITOR':
            tree = context.space_data.node_tree
            if tree and tree.bl_idname == 'EMGraphNodeTreeType':
                tree.nodes.clear()
                tree.node_count = 0
                tree.edge_count = 0
                self.report({'INFO'}, "Graph editor cleared")
                return {'FINISHED'}
        
        self.report({'ERROR'}, "Not in EMGraph editor")
        return {'CANCELLED'}


class GRAPHEDIT_OT_refresh_node(Operator):
    """Aggiorna il nodo selezionato dal grafo s3dgraphy"""
    bl_idname = "graphedit.refresh_node"
    bl_label = "Refresh Node"
    bl_description = "Refresh selected node data from s3dgraphy graph"
    
    def execute(self, context):
        if not context.active_node:
            self.report({'WARNING'}, "No node selected")
            return {'CANCELLED'}
        
        node = context.active_node
        if hasattr(node, 'get_s3d_node'):
            s3d_node = node.get_s3d_node(context)
            if s3d_node:
                node.original_name = s3d_node.name
                node.label = s3d_node.name[:30] if len(s3d_node.name) > 30 else s3d_node.name
                
                self.report({'INFO'}, f"Refreshed node: {s3d_node.name}")
                return {'FINISHED'}
            else:
                self.report({'ERROR'}, "S3D node not found")
                return {'CANCELLED'}
        
        self.report({'ERROR'}, "Not an EMGraph node")
        return {'CANCELLED'}


class GRAPHEDIT_OT_apply_color_scheme(Operator):
    """Applica schema colori ai nodi"""
    bl_idname = "graphedit.apply_color_scheme"
    bl_label = "Apply Color Scheme"
    bl_description = "Apply color scheme to all nodes based on their type"
    
    scheme: EnumProperty(
        name="Scheme",
        items=[
            ('DEFAULT', "Default", "Default EMTools colors"),
            ('PASTEL', "Pastel", "Soft pastel colors"),
            ('VIBRANT', "Vibrant", "Bright vibrant colors"),
            ('GRAYSCALE', "Grayscale", "Shades of gray"),
        ],
        default='DEFAULT'
    ) # type: ignore
    
    def execute(self, context):
        tree = context.space_data.node_tree
        if not tree or tree.bl_idname != 'EMGraphNodeTreeType':
            self.report({'ERROR'}, "Not in EMGraph editor")
            return {'CANCELLED'}
        
        color_schemes = {
            'DEFAULT': {
                'US': (0.608, 0.608, 0.608),
                'USVs': (0.4, 0.6, 0.8),
                'USVn': (0.8, 0.6, 0.4),
                'SF': (0.8, 0.4, 0.4),
                'epoch': (0.3, 0.5, 0.7),
                'document': (0.8, 0.8, 0.4),
                'paradata': (0.6, 0.3, 0.8),
            },
            'PASTEL': {
                'US': (0.8, 0.8, 0.9),
                'USVs': (0.7, 0.8, 0.9),
                'USVn': (0.9, 0.8, 0.7),
                'SF': (0.9, 0.7, 0.7),
                'epoch': (0.7, 0.8, 0.9),
                'document': (0.9, 0.9, 0.7),
                'paradata': (0.8, 0.7, 0.9),
            },
            'VIBRANT': {
                'US': (0.3, 0.3, 0.9),
                'USVs': (0.2, 0.6, 1.0),
                'USVn': (1.0, 0.6, 0.2),
                'SF': (1.0, 0.2, 0.2),
                'epoch': (0.2, 0.4, 0.9),
                'document': (1.0, 1.0, 0.2),
                'paradata': (0.8, 0.2, 1.0),
            },
            'GRAYSCALE': {
                'US': (0.7, 0.7, 0.7),
                'USVs': (0.6, 0.6, 0.6),
                'USVn': (0.5, 0.5, 0.5),
                'SF': (0.4, 0.4, 0.4),
                'epoch': (0.8, 0.8, 0.8),
                'document': (0.3, 0.3, 0.3),
                'paradata': (0.5, 0.5, 0.5),
            }
        }
        
        scheme = color_schemes[self.scheme]
        count = 0
        
        for node in tree.nodes:
            if hasattr(node, 'custom_node_color'):
                if 'US' in node.bl_label:
                    color = scheme.get(node.bl_label, scheme['US'])
                elif 'Epoch' in node.bl_label:
                    color = scheme['epoch']
                elif 'Document' in node.bl_label:
                    color = scheme['document']
                elif 'Paradata' in node.bl_label:
                    color = scheme['paradata']
                else:
                    color = (0.5, 0.5, 0.5)
                
                node.custom_node_color = color
                node.use_custom_node_color = True
                node.use_custom_color = True
                node.color = color
                count += 1
        
        self.report({'INFO'}, f"Applied {self.scheme} color scheme to {count} nodes")
        return {'FINISHED'}


# ============================================================================
# REGISTRATION
# ============================================================================

classes = (
    GRAPHEDIT_OT_draw_graph,
    GRAPHEDIT_OT_sync_selection,
    GRAPHEDIT_OT_draw_neighborhood,
    GRAPHEDIT_OT_clear_editor,
    GRAPHEDIT_OT_refresh_node,
    GRAPHEDIT_OT_apply_color_scheme,
)

def register_operators():
    """Register all operator classes"""
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except ValueError:
            pass

def unregister_operators():
    """Unregister all operator classes"""
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass
        