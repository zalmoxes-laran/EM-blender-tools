"""
Utility functions for the Visual Manager
This module contains helper functions for property mapping, color application,
and other visual management utilities.
"""

import bpy
import json
import os
from s3dgraphy.nodes.stratigraphic_node import StratigraphicNode
from s3dgraphy import get_graph, get_all_graph_ids
from s3dgraphy.multigraph.multigraph import multi_graph_manager

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

def create_property_value_mapping(graph, property_name):
    """
    Complete optimized version using graph indices for property mapping.
    Creates both the node->value mapping and materials for visualization.
    """
    print(f"\n=== Creating Property Value Mapping for '{property_name}' (Optimized) ===")
    
    mapping = {}
    
    try:
        # Usa gli indici ottimizzati del grafo
        indices = graph.indices
        
        # Ottieni tutti i valori per questa proprietà usando gli indici
        property_values = indices.get_property_values(property_name)
        print(f"Found {len(property_values)} unique property values using indices")
        
        # Track stratigraphic nodes that have this property
        connected_strat_nodes = set()
        
        # Process each property value using optimized lookup
        for value in property_values:
            # Skip special values for now
            if not (value.startswith("empty property") or value.startswith("no property")):
                # Get stratigraphic nodes with this property value - O(1) lookup
                strat_node_ids = indices.get_strat_nodes_by_property_value(property_name, value)
                
                for strat_node_id in strat_node_ids:
                    connected_strat_nodes.add(strat_node_id)
                    strat_node = graph.find_node_by_id(strat_node_id)
                    
                    if strat_node:
                        # Use actual value or special tag for empty values
                        if value and value.strip():
                            mapping[strat_node.name] = value
                        else:
                            mapping[strat_node.name] = f"empty property {property_name} node"
        
        # Handle "no property" case using optimized node type lookup
        if hasattr(indices, 'nodes_by_type'):
            strat_nodes = indices.nodes_by_type.get('stratigraphic', [])
            # Also check for 'US' type nodes (common stratigraphic type)
            strat_nodes.extend(indices.nodes_by_type.get('US', []))
        else:
            # Fallback to manual iteration if indices don't have node type lookup
            strat_nodes = [node for node in graph.nodes 
                          if hasattr(node, 'node_type') and 
                          node.node_type in ['stratigraphic', 'US']]
        
        # Add nodes without this property
        for strat_node in strat_nodes:
            node_id = getattr(strat_node, 'node_id', None)
            if node_id and node_id not in connected_strat_nodes:
                mapping[strat_node.name] = f"no property {property_name} node"
        
        print(f"Optimized mapping created with {len(mapping)} entries")
        
    except Exception as e:
        print(f"Warning: Optimized method failed ({e}), falling back to legacy method")
        # Fallback to legacy implementation
        return create_property_value_mapping_old(graph, property_name)
    
    return mapping


def create_property_materials(context, property_values_list=None):
    """
    Create Blender materials for property values.
    Separated from mapping function for better modularity.
    """
    scene = context.scene
    materials = {}
    
    alpha_value = scene.proxy_display_alpha
    
    # Use provided list or scene property_values
    values_to_process = property_values_list or scene.property_values
    
    for item in values_to_process:
        material_name = f"prop_{item.value if hasattr(item, 'value') else item}"
        
        # Create or get existing material
        if material_name in bpy.data.materials:
            mat = bpy.data.materials[material_name]
        else:
            mat = bpy.data.materials.new(name=material_name)
            mat.use_nodes = True
            mat.node_tree.nodes.clear()
            
            # Set blend method based on alpha
            if alpha_value < 1.0:
                mat.blend_method = 'BLEND'
            else:
                mat.blend_method = scene.proxy_blend_mode if hasattr(scene, 'proxy_blend_mode') else 'OPAQUE'
            
            # Create shader nodes
            output = mat.node_tree.nodes.new('ShaderNodeOutputMaterial')
            output.location = (0, 0)
            principled = mat.node_tree.nodes.new('ShaderNodeBsdfPrincipled')
            principled.location = (-200, 0)
            
            # Connect nodes
            mat.node_tree.links.new(principled.outputs['BSDF'], output.inputs['Surface'])
            
            # Set material properties
            if hasattr(item, 'color') and len(item.color) >= 3:
                principled.inputs['Base Color'].default_value = (*item.color[:3], alpha_value)
            else:
                # Default gray color
                principled.inputs['Base Color'].default_value = (0.5, 0.5, 0.5, alpha_value)
            
            principled.inputs['Alpha'].default_value = alpha_value
        
        materials[material_name] = mat
    
    print(f"Created/updated {len(materials)} materials")
    return materials


def create_property_value_mapping_with_materials(graph, property_name, context=None):
    """
    Combined function that creates both mapping and materials.
    Use this when you need both functionality.
    """
    # Create the optimized mapping
    mapping = create_property_value_mapping(graph, property_name)
    
    # Create materials if context is provided
    materials = {}
    if context:
        # Extract unique values from mapping
        unique_values = list(set(mapping.values()))
        
        # Create simple objects with value attribute for material creation
        class ValueItem:
            def __init__(self, value, color=(0.5, 0.5, 0.5, 1.0)):
                self.value = value
                self.color = color
        
        value_items = [ValueItem(value) for value in unique_values]
        materials = create_property_materials(context, value_items)
    
    return mapping, materials

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