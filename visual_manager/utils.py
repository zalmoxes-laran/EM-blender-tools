"""
Utility functions for the Visual Manager
This module contains helper functions for property mapping, color application,
and other visual management utilities.
"""

import bpy
import json
import os
from ..s3Dgraphy.nodes.stratigraphic_node import StratigraphicNode
from ..s3Dgraphy import get_graph, get_all_graph_ids
from ..s3Dgraphy.multigraph.multigraph import multi_graph_manager

DEFAULT_COLOR = (0.5, 0.5, 0.5, 1.0)  # Grigio medio

# Variabili per il caching delle proprietà disponibili
_cached_properties = None
_last_cache_time = 0
_cache_lifetime = 5.0  # 5 secondi di vita per la cache

def create_property_value_mapping_old(graph, property_name):
    """
    Legacy function to create a mapping of nodes to property values.
    Kept for backward compatibility - use create_property_value_mapping instead.
    """
    print(f"\n=== Creating Property Value Mapping for '{property_name}' (Legacy) ===")
    



    mapping = {}
    
    # Find all property nodes with the given name
    property_nodes = [node for node in graph.nodes 
                    if hasattr(node, 'node_type') and node.node_type == "property" 
                    and node.name == property_name]
    
    # Track stratigraphic nodes that have this property
    connected_strat_nodes = set()
    
    # Process normal property values
    for prop_node in property_nodes:
        value = getattr(prop_node, 'description', '')
        
        # Find all stratigraphic nodes connected to this property
        for edge in graph.edges:
            if edge.edge_type == "has_property" and edge.edge_target == prop_node.node_id:
                strat_node_id = edge.edge_source
                connected_strat_nodes.add(strat_node_id)
                strat_node = graph.find_node_by_id(strat_node_id)
                
                if strat_node:
                    # Use actual value or special tag for empty values
                    if value:
                        mapping[strat_node.name] = value
                    else:
                        mapping[strat_node.name] = f"empty property {property_name} node"
    
    # Handle "no property" case
    for node in graph.nodes:
        if hasattr(node, 'node_type') and isinstance(node, StratigraphicNode) and node.node_id not in connected_strat_nodes:
            mapping[node.name] = f"no property {property_name} node"
    
    print(f"Legacy mapping created with {len(mapping)} entries")
    return mapping

def create_property_value_mapping(context):
    """Create materials for property values"""
    scene = context.scene
    materials = {}
    
    alpha_value = scene.proxy_display_alpha
    
    for item in scene.property_values:
        material_name = f"prop_{item.value}"
        
        # Crea o ottieni il materiale
        if material_name in bpy.data.materials:
            mat = bpy.data.materials[material_name]
        else:
            mat = bpy.data.materials.new(name=material_name)
        
        # Configura il materiale
        mat.use_nodes = True
        mat.node_tree.nodes.clear()
        
        if alpha_value < 1.0:
            mat.blend_method = 'BLEND'
        else:
            mat.blend_method = scene.proxy_blend_mode
        
        # Crea i nodi
        output = mat.node_tree.nodes.new('ShaderNodeOutputMaterial')
        principled = mat.node_tree.nodes.new('ShaderNodeBsdfPrincipled')
        
        # Collega i nodi
        mat.node_tree.links.new(principled.outputs['BSDF'], output.inputs['Surface'])
        
        # Imposta il colore e l'alpha
        principled.inputs['Base Color'].default_value = (*item.color[:3], 1.0)
        
        if 'Alpha' in principled.inputs:
            principled.inputs['Alpha'].default_value = alpha_value
        
        materials[item.value] = mat
    
    return materials

def apply_property_colors(context, property_mapping, color_scheme):
    """Applies colors to mesh objects based on property values."""
    scene = context.scene
    
    for obj in scene.objects:
        if obj.type == 'MESH':
            if obj.name in property_mapping:
                value = property_mapping[obj.name]
                color = color_scheme.get(value, color_scheme.get("nodata", DEFAULT_COLOR))
                
                mat_name = f"prop_{value}"
                if mat_name not in bpy.data.materials:
                    mat = bpy.data.materials.new(name=mat_name)
                    mat.use_nodes = True
                    mat.node_tree.nodes["Principled BSDF"].inputs[0].default_value = hex_to_rgb(color) if isinstance(color, str) else color
                else:
                    mat = bpy.data.materials[mat_name]
                
                if obj.data.materials:
                    obj.data.materials[0] = mat
                else:
                    obj.data.materials.append(mat)

def save_color_scheme(filepath, property_name, color_mapping):
    """Saves color mapping to .emc file."""
    data = {
        "metadata": {
            "property_name": property_name,
            "created": bpy.data.filepath,  # Usiamo direttamente il filepath del blend
            "description": f"Color mapping for {property_name} values"
        },
        "color_mapping": color_mapping
    }
    
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)

def load_color_scheme(filepath):
    """Loads color mapping from .emc file."""
    with open(filepath, 'r') as f:
        data = json.load(f)
    return data["metadata"]["property_name"], data["color_mapping"]

def hex_to_rgb(value):
    """Convert hex color to RGB"""
    gamma = 2.2
    value = value.lstrip('#')
    lv = len(value)
    fin = list(int(value[i:i + lv // 3], 16) for i in range(0, lv, lv // 3))
    r = pow(fin[0] / 255, gamma)
    g = pow(fin[1] / 255, gamma)
    b = pow(fin[2] / 255, gamma)
    fin.clear()
    fin.append(r)
    fin.append(g)
    fin.append(b)
    return tuple(fin)

def get_available_properties(context):
    """
    Get list of available property names using optimized indices.
    """
    global _cached_properties, _last_cache_time
    import time
    
    # Usa la cache se disponibile e non è scaduta
    current_time = time.time()
    if (_cached_properties is not None and 
            current_time - _last_cache_time < _cache_lifetime):
        return _cached_properties
    
    print(f"\n=== Getting Available Properties (OPTIMIZED) ===")
    scene = context.scene
    em_tools = scene.em_tools
    properties = set()

    if not em_tools.mode_switch:  # Modalità 3D GIS
        mgr = multi_graph_manager
        graph = mgr.graphs.get("3dgis_graph")
        if graph:
            # USA GLI INDICI OTTIMIZZATI! 🚀
            properties.update(graph.indices.get_property_names())
    else:  # Modalità EM Advanced
        if scene.show_all_graphs:
            graph_ids = get_all_graph_ids()
        else:
            if em_tools.active_file_index >= 0:
                active_file = em_tools.graphml_files[em_tools.active_file_index]
                graph_ids = [active_file.name]
            else:
                return []

        for graph_id in graph_ids:
            graph = get_graph(graph_id)
            if graph:
                # USA GLI INDICI OTTIMIZZATI! 🚀
                properties.update(graph.indices.get_property_names())

    result = sorted(list(properties))
    print(f"Found {len(result)} properties using optimized indices")

    # Aggiorna la cache
    _cached_properties = result
    _last_cache_time = current_time

    return result

def get_enum_items(self, context):
    """Funzione getter per gli items dell'enum property"""
    props = get_available_properties(context)
    return [(p, p, f"Select {p} property") for p in props]

def print_graph_info():
    """Debug function to print graph information"""
    print("\n=== Graph Debug Info ===")
    graph_ids = get_all_graph_ids()
    print(f"Available graph IDs: {graph_ids}")
    
    for graph_id in graph_ids:
        graph = get_graph(graph_id)
        if graph:
            print(f"\nGraph {graph_id}:")
            print(f"Number of nodes: {len(graph.nodes)}")
            print("Node types:")
            type_count = {}
            for node in graph.nodes:
                node_type = getattr(node, 'node_type', 'unknown')
                type_count[node_type] = type_count.get(node_type, 0) + 1
            for node_type, count in type_count.items():
                print(f"  {node_type}: {count}")

def test_optimization_performance(context):
    """Test function to compare old vs new performance"""
    import time
    
    scene = context.scene
    if not scene.selected_property:
        print("ERROR: Please select a property first")
        return
        
    graph = get_graph("3dgis_graph") or get_graph(scene.em_tools.graphml_files[0].name)
    if not graph:
        print("ERROR: No graph available")
        return
    
    # Test old method
    start = time.time()
    old_mapping = create_property_value_mapping_old(graph, scene.selected_property)
    old_time = time.time() - start
    
    # Test new method
    start = time.time()
    new_mapping = create_property_value_mapping(graph, scene.selected_property)
    new_time = time.time() - start
    
    print(f"Performance comparison for property '{scene.selected_property}':")
    print(f"Old method: {old_time:.4f}s, {len(old_mapping)} items")
    print(f"New method: {new_time:.4f}s, {len(new_mapping)} items")
    print(f"Speedup: {old_time/new_time:.2f}x")