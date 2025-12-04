"""
Utility functions for the Visual Manager
This module contains helper functions for property mapping, color application,
and other visual management utilities.
"""

import bpy
import json
import os
import time
from s3dgraphy.nodes.stratigraphic_node import StratigraphicNode
from s3dgraphy import get_graph, get_all_graph_ids

DEFAULT_COLOR = (0.5, 0.5, 0.5, 1.0)  # Grigio medio

# Cache variables per get_available_properties
CACHE_DURATION = 5.0  # Cache duration in seconds
_cached_properties = []
_last_cache_time = 0


def create_property_value_mapping(graph, property_name):
    """
    Complete optimized version using graph indices for property mapping.
    Creates mapping from node names to property values, INCLUDING special cases.
    
    Args:
        graph: The s3dgraphy graph object
        property_name: Name of the property to map
        
    Returns:
        dict: mapping from stratigraphic node names to property values
    """
    print(f"\n=== Creating Property Value Mapping for '{property_name}' ===")
    
    mapping = {}
    
    try:
        # APPROCCIO DIRETTO: usa la stessa logica dell'operatore per consistenza
        return create_property_value_mapping_direct(graph, property_name)
        
    except Exception as e:
        print(f"Warning: Direct method failed ({e}), falling back to legacy method")
        return create_property_value_mapping_legacy(graph, property_name)


def create_property_value_mapping_direct(graph, property_name):
    """
    Direct implementation that matches the operator logic exactly.
    This ensures consistency between update_property_values and apply_colors.
    """
    print(f"Using direct mapping method for '{property_name}'")
    
    mapping = {}
    
    # 1. Find ALL property nodes with this name
    property_nodes = [node for node in graph.nodes 
                    if hasattr(node, 'node_type') and node.node_type == "property" 
                    and hasattr(node, 'name') and node.name == property_name]
    
    print(f"Found {len(property_nodes)} property nodes for '{property_name}'")
    
    # 2. Track stratigraphic nodes that have this property
    connected_strat_nodes = set()
    
    # 3. Process each property node and find connected US
    for prop_node in property_nodes:
        value = getattr(prop_node, 'description', '')
        is_empty = not (value and value.strip())
        
        print(f"Processing property node {prop_node.node_id}: empty={is_empty}, value='{value}'")
        
        # Find all US connected to this property node
        connected_us = []
        for edge in graph.edges:
            if (hasattr(edge, 'edge_type') and 
                edge.edge_type == "has_property" and 
                hasattr(edge, 'edge_target') and
                edge.edge_target == prop_node.node_id):
                
                strat_node = graph.find_node_by_id(edge.edge_source)
                if strat_node and hasattr(strat_node, 'name'):
                    connected_us.append(strat_node)
                    connected_strat_nodes.add(strat_node.node_id)
        
        print(f"  Connected to {len(connected_us)} US: {[us.name for us in connected_us]}")
        
        # Assign appropriate value
        for us_node in connected_us:
            if is_empty:
                mapping[us_node.name] = f"empty property {property_name} node"
                print(f"  -> {us_node.name}: EMPTY PROPERTY")
            else:
                mapping[us_node.name] = value
                print(f"  -> {us_node.name}: '{value}'")
    
    # 4. Find all US that DON'T have this property
    no_property_count = 0
    for node in graph.nodes:
        if (hasattr(node, 'node_type') and 
            isinstance(node, StratigraphicNode) and 
            hasattr(node, 'node_id') and
            node.node_id not in connected_strat_nodes):
            
            if hasattr(node, 'name'):
                mapping[node.name] = f"no property {property_name} node"
                no_property_count += 1
    
    print(f"Direct mapping created with {len(mapping)} entries")
    print(f"  - With property: {len(connected_strat_nodes)}")  
    print(f"  - Without property: {no_property_count}")
    
    return mapping


def create_property_value_mapping_legacy(graph, property_name):
    """
    Legacy fallback function for when direct method fails.
    """
    print(f"Using legacy mapping method for '{property_name}'")
    
    mapping = {}
    
    # Find all property nodes with the given name
    property_nodes = []
    for node in graph.nodes:
        if (hasattr(node, 'node_type') and 
            node.node_type == "property" and 
            hasattr(node, 'name') and 
            node.name == property_name):
            property_nodes.append(node)
    
    print(f"Found {len(property_nodes)} property nodes with name '{property_name}'")
    
    # Track stratigraphic nodes that have this property
    connected_strat_nodes = set()
    
    # Process normal property values
    for prop_node in property_nodes:
        # Get the property value (description)
        value = getattr(prop_node, 'description', '')
        
        # Find all stratigraphic nodes connected to this property
        for edge in graph.edges:
            if (hasattr(edge, 'edge_type') and 
                edge.edge_type == "has_property" and 
                hasattr(edge, 'edge_target') and
                edge.edge_target == prop_node.node_id):
                
                strat_node_id = edge.edge_source
                connected_strat_nodes.add(strat_node_id)
                strat_node = graph.find_node_by_id(strat_node_id)
                
                if strat_node and hasattr(strat_node, 'name'):
                    # Use actual value or special tag for empty values
                    if value and value.strip():
                        mapping[strat_node.name] = value
                    else:
                        mapping[strat_node.name] = f"empty property {property_name} node"
    
    # Handle "no property" case
    no_property_count = 0
    for node in graph.nodes:
        if (hasattr(node, 'node_type') and 
            isinstance(node, StratigraphicNode) and 
            hasattr(node, 'node_id') and
            node.node_id not in connected_strat_nodes):
            
            if hasattr(node, 'name'):
                mapping[node.name] = f"no property {property_name} node"
                no_property_count += 1
    
    print(f"Legacy mapping created with {len(mapping)} entries")
    print(f"  - With property: {len(connected_strat_nodes)}")  
    print(f"  - Without property: {no_property_count}")
    
    return mapping


def create_property_materials_for_scene_values(context):
    """
    Create materials for all property values currently in scene.property_values.
    This reads directly from the scene's property values list with their assigned colors.
    
    Args:
        context: Blender context
        
    Returns:
        dict: mapping from property values to Blender material objects
    """
    scene = context.scene
    # Get alpha from em_tools, not directly from scene
    alpha_value = getattr(scene.em_tools, 'proxy_display_alpha', 1.0)
    selected_property = getattr(scene, 'selected_property', 'unknown')
    
    materials_by_value = {}
    
    print(f"\nCreating materials for {len(scene.property_values)} property values")
    
    for item in scene.property_values:
        property_value = item.value
        
        # Create unique material name using property name to avoid conflicts
        # Replace problematic characters for material naming
        safe_property = selected_property.replace(" ", "_").replace(".", "_")
        safe_value = property_value.replace(" ", "_").replace(".", "_")
        mat_name = f"prop_{safe_property}_{safe_value}"
        
        # Create or get existing material
        if mat_name in bpy.data.materials:
            mat = bpy.data.materials[mat_name]
            # Update existing material with current color from scene.property_values
            if mat.node_tree:
                principled = None
                for node in mat.node_tree.nodes:
                    if node.type == 'BSDF_PRINCIPLED':
                        principled = node
                        break
                if principled and hasattr(item, 'color') and len(item.color) >= 3:
                    rgba_color = (*item.color[:3], alpha_value)
                    principled.inputs['Base Color'].default_value = rgba_color
                    principled.inputs['Alpha'].default_value = alpha_value
                    print(f"  Updated material '{mat_name}': color = {rgba_color}")

                    mat.diffuse_color[0] = item.color[0]
                    mat.diffuse_color[1] = item.color[1]
                    mat.diffuse_color[2] = item.color[2]
                    mat.diffuse_color[3] = alpha_value

        else:
            # Create new material
            mat = bpy.data.materials.new(name=mat_name)
            mat.use_nodes = True
            mat.node_tree.nodes.clear()
            
            # Set blend method based on alpha
            if alpha_value < 1.0:
                mat.blend_method = 'BLEND'
            else:
                mat.blend_method = 'OPAQUE'

            mat.show_transparent_back = False
            mat.use_backface_culling = False

            # Create shader nodes
            output = mat.node_tree.nodes.new('ShaderNodeOutputMaterial')
            output.location = (0, 0)
            principled = mat.node_tree.nodes.new('ShaderNodeBsdfPrincipled')
            principled.location = (-200, 0)
            
            # Connect nodes
            mat.node_tree.links.new(principled.outputs['BSDF'], output.inputs['Surface'])
            
            # Set material properties from scene.property_values color
            if hasattr(item, 'color') and len(item.color) >= 3:
                rgba_color = (*item.color[:3], alpha_value)
                principled.inputs['Base Color'].default_value = rgba_color
                print(f"  Created material '{mat_name}': color = {rgba_color}")

                mat.diffuse_color[0] = item.color[0]
                mat.diffuse_color[1] = item.color[1]
                mat.diffuse_color[2] = item.color[2]
                mat.diffuse_color[3] = alpha_value

            else:
                # Default gray color
                rgba_color = (*DEFAULT_COLOR[:3], alpha_value)
                principled.inputs['Base Color'].default_value = rgba_color
                print(f"  Created material '{mat_name}': using default color = {rgba_color}")

                mat.diffuse_color[0] = DEFAULT_COLOR[0]
                mat.diffuse_color[1] = DEFAULT_COLOR[1]
                mat.diffuse_color[2] = DEFAULT_COLOR[2]
                mat.diffuse_color[3] = alpha_value

            principled.inputs['Alpha'].default_value = alpha_value
        
        materials_by_value[property_value] = mat
    
    print(f"Created/updated {len(materials_by_value)} materials")
    return materials_by_value


def apply_materials_to_objects(context, property_mapping, materials_by_value):
    """
    Apply the created materials to objects based on their property values.
    
    Args:
        context: Blender context
        property_mapping: dict mapping object names to property values
        materials_by_value: dict mapping property values to materials
        
    Returns:
        int: number of objects that were colored
    """

    from ..operators.addon_prefix_helpers import proxy_name_to_node_name
    from ..functions import is_graph_available as check_graph

    scene = context.scene
    colored_count = 0
    total_objects = 0

    #  Ottieni il grafo attivo
    graph_exists, graph = check_graph(context)
    active_graph = graph if graph_exists else None

    print(f"\nApplying materials to objects:")
    print(f"  Property mapping: {len(property_mapping)} entries")
    print(f"  Available materials: {len(materials_by_value)} materials")
    
    for obj in scene.objects:
        if obj.type == 'MESH':
            total_objects += 1

            node_name = proxy_name_to_node_name(obj.name, context=context, graph=active_graph)
            
            if node_name in property_mapping:
                property_value = str(property_mapping[node_name])
                
                if property_value in materials_by_value:
                    mat = materials_by_value[property_value]
                    
                    # Apply material to object
                    if obj.data.materials:
                        obj.data.materials[0] = mat
                    else:
                        obj.data.materials.append(mat)
                    
                    colored_count += 1
                    print(f"  ✓ Applied material '{mat.name}' to object '{obj.name}' (value: '{property_value}')")
                    
                else:
                    print(f"  ⚠ Warning: No material found for value '{property_value}' on object '{node_name}'")
            else:
                # Oggetto non ha questa proprietà
                pass  # Non loggare per evitare spam, ma potremmo volerlo colorare diversamente
    
    print(f"\n✅ Applied materials to {colored_count} of {total_objects} mesh objects")
    return colored_count


def save_color_scheme(filepath, property_name, color_mapping):
    """Saves color mapping to .emc file."""
    data = {
        "metadata": {
            "property_name": property_name,
            "created": bpy.data.filepath,
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
    """Convert hex color to RGB with gamma correction"""
    gamma = 2.2
    value = value.lstrip('#')
    lv = len(value)
    fin = list(int(value[i:i + lv // 3], 16) for i in range(0, lv, lv // 3))
    r = pow(fin[0] / 255, gamma)
    g = pow(fin[1] / 255, gamma)
    b = pow(fin[2] / 255, gamma)
    return (r, g, b)


def get_available_properties(context):
    """
    Get list of available property names using optimized indices.
    Supporta modalità 3D GIS (grafo hardcodato) e Advanced EM (grafo attivo/multigrafo).
    """
    scene = context.scene
    em_tools = scene.em_tools
    properties = set()
    
    # Cache check
    global _cached_properties, _last_cache_time
    current_time = time.time()
    if _cached_properties and (current_time - _last_cache_time) < CACHE_DURATION:
        return _cached_properties

    if not em_tools.mode_em_advanced:  # Modalità 3D GIS
        # Nome hardcodato per modalità 3D GIS
        graph = get_graph("3dgis_graph")
        if graph and hasattr(graph, 'indices'):
            properties.update(graph.indices.get_property_names())
            print(f"3D GIS mode: found {len(properties)} properties from hardcoded graph")
        else:
            print("3D GIS mode: hardcoded graph '3dgis_graph' not found")
    else:  # Modalità Advanced EM
        if hasattr(scene, 'show_all_graphs') and scene.show_all_graphs:  # Modalità multigrafo
            graph_ids = get_all_graph_ids()
            print(f"Advanced EM multigrafo mode: processing {len(graph_ids)} graphs")
            for graph_id in graph_ids:
                graph = get_graph(graph_id)
                if graph and hasattr(graph, 'indices'):
                    properties.update(graph.indices.get_property_names())
        else:  # Solo grafo attivo
            if em_tools.active_file_index >= 0:
                active_file = em_tools.graphml_files[em_tools.active_file_index]
                graph = get_graph(active_file.name)
                if graph and hasattr(graph, 'indices'):
                    properties.update(graph.indices.get_property_names())
                    print(f"Advanced EM mode: found {len(properties)} properties from active graph '{active_file.name}'")
            else:
                print("Advanced EM mode: no active GraphML file selected")

    result = sorted(list(properties))
    print(f"Total: {len(result)} properties found")

    # Update cache
    _cached_properties = result
    _last_cache_time = current_time

    return result


def get_enum_items(self, context):
    """Funzione getter per gli items dell'enum property"""
    try:
        props = get_available_properties(context)
        return [(p, p, f"Select {p} property") for p in props]
    except Exception as e:
        print(f"Error getting enum items: {e}")
        return [("none", "No properties available", "No properties found")]


def print_graph_info():
    """Debug function to print graph information"""
    print("\n=== Graph Debug Info ===")
    try:
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
    except Exception as e:
        print(f"Error in print_graph_info: {e}")


def test_optimization_performance(context):
    """Test function to compare performance"""
    scene = context.scene
    if not scene.selected_property:
        print("ERROR: Please select a property first")
        return
        
    graph = None
    try:
        graph = get_graph("3dgis_graph")
        if not graph and hasattr(scene.em_tools, 'graphml_files') and len(scene.em_tools.graphml_files) > 0:
            graph = get_graph(scene.em_tools.graphml_files[0].name)
    except Exception as e:
        print(f"Error getting graph: {e}")
        
    if not graph:
        print("ERROR: No graph available")
        return
    
    # Test mapping method
    start = time.time()
    mapping = create_property_value_mapping(graph, scene.selected_property)
    mapping_time = time.time() - start
    
    print(f"Performance test for property '{scene.selected_property}':")
    print(f"Mapping creation: {mapping_time:.4f}s, {len(mapping)} items")