import bpy # type: ignore
from .s3Dgraphy.nodes.stratigraphic_node import StratigraphicNode
import json
import os
from .functions import hex_to_rgb



DEFAULT_COLOR = (0.5, 0.5, 0.5, 1.0)  # Grigio medio

def create_property_value_mapping_old(graph, property_name):
    """
    Legacy function to create a mapping of nodes to property values.
    Kept for backward compatibility - use create_property_value_mapping_optimized instead.
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

# Versione ottimizzata di create_property_value_mapping
def create_property_value_mapping(graph, property_name):
    """Optimised version using graph indices"""
    print(f"\n=== Creating Property Value Mapping for '{property_name}' (Optimized) ===")
    
    # Usa gli indici del grafo
    indices = graph.indices
    
    # Ottieni tutti i valori per questa proprietà
    values = indices.get_property_values(property_name)
    
    # Crea il mapping
    mapping = {}
    for value in values:
        # I valori speciali hanno già il formato corretto
        if value.startswith("empty property") or value.startswith("no property"):
            mapping[value] = value
        else:
            # Per i valori normali, trova un nodo rappresentativo
            strat_ids = indices.get_strat_nodes_by_property_value(property_name, value)
            if strat_ids:
                # Usa il primo ID come chiave
                mapping[strat_ids[0]] = value
    
    print(f"Mapping results: {len(mapping)} values found")
    return mapping

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