"""
Operators for Graph Editor
Handles loading, clearing, and manipulating graphs in the node editor.
"""

import bpy
from bpy.types import Operator
from s3dgraphy import get_graph

class GRAPHEDIT_OT_draw_graph(Operator):
    """Disegna il grafo attivo nell'editor EMGraph"""
    bl_idname = "graphedit.draw_graph"
    bl_label = "Draw Graph"
    bl_description = "Load and draw the active graph from EM Setup into the EMGraph editor"
    bl_options = {'REGISTER', 'UNDO'}
    
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
        
        # Popola il grafo
        node_count, edge_count = self.populate_tree(tree, graph, context)
        
        tree.node_count = node_count
        tree.edge_count = edge_count
        
        # Apri l'editor
        self.open_graph_editor(context, tree)
        
        self.report({'INFO'}, f"Loaded '{tree_name}': {node_count} nodes, {edge_count} edges")
        return {'FINISHED'}
    
    def populate_tree(self, tree, graph, context):
        """Popola il node tree con wrapper dei nodi s3dgraphy"""
        node_map = {}
        edge_count = 0
        
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
        print(f"\n📊 Creating {len(graph.nodes)} nodes...")
        for i, s3d_node in enumerate(graph.nodes):
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
                
                # Cache per epoche (per visualizzazione veloce)
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
                
                # Converti colore hex a RGB se presente
                if hasattr(s3d_node, 'attributes') and 'fill_color' in s3d_node.attributes:
                    fill_color_hex = s3d_node.attributes.get('fill_color')
                    if fill_color_hex and isinstance(fill_color_hex, str):
                        rgb = self.hex_to_rgb(fill_color_hex)
                        if rgb:
                            bl_node.custom_node_color = rgb
                            bl_node.use_custom_node_color = True
                
                node_map[s3d_node.node_id] = bl_node
                
                if (i + 1) % 10 == 0:
                    print(f"   Created {i + 1} nodes...")
                
            except Exception as e:
                print(f"❌ Error creating node {s3d_node.node_id} ({s3d_node.node_type}): {e}")
        
        print(f"✅ Created {len(node_map)} nodes successfully")
        
        # Crea i collegamenti usando edge_source e edge_target
        print(f"\n🔗 Creating {len(graph.edges)} edges...")
        for i, edge in enumerate(graph.edges):
            try:
                # Gli attributi corretti sono edge_source e edge_target
                source_id = edge.edge_source
                target_id = edge.edge_target
                edge_type = edge.edge_type
                
                if source_id in node_map and target_id in node_map:
                    link_created = self.create_link(tree, node_map, source_id, target_id, edge_type)
                    if link_created:
                        edge_count += 1
                    
                    if (i + 1) % 50 == 0:
                        print(f"   Processed {i + 1}/{len(graph.edges)} edges, created {edge_count} links...")
                else:
                    if source_id not in node_map:
                        print(f"⚠️  Edge {i}: Source node not in map: {source_id}")
                    if target_id not in node_map:
                        print(f"⚠️  Edge {i}: Target node not in map: {target_id}")
                        
            except AttributeError as e:
                print(f"❌ Edge {i} missing attributes: {e}")
                print(f"   Edge: {edge}")
            except Exception as e:
                print(f"❌ Error processing edge {i}: {e}")
                import traceback
                traceback.print_exc()
        
        print(f"✅ Created {edge_count} edges successfully\n")
        
        return len(node_map), edge_count
    
    def create_link(self, tree, node_map, source_id, target_id, edge_type):
        """
        Crea un collegamento tra nodi wrapper.
        """
        source_node = node_map[source_id]
        target_node = node_map[target_id]
        
        # Normalizza edge_type
        edge_type_lower = edge_type.lower() if edge_type else 'connection'
        
        source_socket = None
        target_socket = None
        
        # ============================================
        # STRATEGIA 1: Match esatto con edge_type
        # ============================================
        for output in source_node.outputs:
            if edge_type_lower in output.name.lower():
                source_socket = output
                break
        
        for input_socket in target_node.inputs:
            if edge_type_lower in input_socket.name.lower():
                target_socket = input_socket
                break
        
        # ============================================
        # STRATEGIA 2: Match parziale intelligente
        # ============================================
        if not source_socket:
            edge_keywords = edge_type_lower.replace('_', ' ').split()
            for output in source_node.outputs:
                output_lower = output.name.lower()
                if any(kw in output_lower for kw in edge_keywords):
                    source_socket = output
                    break
        
        if not target_socket:
            edge_keywords = edge_type_lower.replace('_', ' ').split()
            for input_socket in target_node.inputs:
                input_lower = input_socket.name.lower()
                if any(kw in input_lower for kw in edge_keywords):
                    target_socket = input_socket
                    break
        
        # ============================================
        # STRATEGIA 3: Usa socket generici
        # ============================================
        if not source_socket and len(source_node.outputs) == 1:
            source_socket = source_node.outputs[0]
        
        if not target_socket and len(target_node.inputs) == 1:
            target_socket = target_node.inputs[0]
        
        # ============================================
        # STRATEGIA 4: Fallback - primo socket disponibile
        # ============================================
        if not source_socket and len(source_node.outputs) > 0:
            for output in source_node.outputs:
                if not output.is_linked:
                    source_socket = output
                    break
            if not source_socket:
                source_socket = source_node.outputs[0]
        
        if not target_socket and len(target_node.inputs) > 0:
            for input_s in target_node.inputs:
                if not input_s.is_linked:
                    target_socket = input_s
                    break
            if not target_socket:
                target_socket = target_node.inputs[0]
        
        # ============================================
        # CREA IL LINK
        # ============================================
        if source_socket and target_socket:
            try:
                if hasattr(source_socket, 'edge_type'):
                    source_socket.edge_type = edge_type
                if hasattr(target_socket, 'edge_type'):
                    target_socket.edge_type = edge_type
                
                tree.links.new(source_socket, target_socket)
                return True
            except Exception as e:
                print(f"     ❌ Error creating link {source_node.label} -> {target_node.label}: {e}")
                return False
        else:
            # Debug solo per edge problematici
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
                # Aggiorna cache
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
    
    scheme: bpy.props.EnumProperty(
        name="Scheme",
        items=[
            ('DEFAULT', "Default", "Default EMTools colors"),
            ('PASTEL', "Pastel", "Soft pastel colors"),
            ('VIBRANT', "Vibrant", "Bright vibrant colors"),
            ('GRAYSCALE', "Grayscale", "Shades of gray"),
        ],
        default='DEFAULT'
    )
    
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
                # Determina il tipo base
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