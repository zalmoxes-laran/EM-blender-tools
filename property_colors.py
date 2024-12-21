import bpy # type: ignore
from .s3Dgraphy.nodes.stratigraphic_node import StratigraphicNode
import json
import os
from .functions import hex_to_rgb

DEFAULT_COLOR = (0.5, 0.5, 0.5, 1.0)  # Grigio medio

def create_property_value_mapping(graph, property_name):
    """
    Creates a mapping of stratigraphic nodes to their property values.
    
    Args:
        graph: Graph instance
        property_name: Name of the property to map
        
    Returns:
        dict: Mapping of node names to property values
    """
    print(f"\n=== Creating Property Value Mapping for '{property_name}' ===")
    
    mapping = {}
    
    # Get all edges of type "has_property"
    property_edges = [
        edge for edge in graph.edges
        if edge.edge_type == "has_property"
    ]
    
    print(f"Found {len(property_edges)} property edges")
    
    for edge in property_edges:
        # Get the property node
        prop_node = graph.find_node_by_id(edge.edge_target)
        
        if prop_node and prop_node.node_type == "property" and prop_node.name == property_name:
            # Get the stratigraphic node
            strat_node = graph.find_node_by_id(edge.edge_source)
            
            if strat_node:
                # Use description as value since that's where the data is stored
                value = prop_node.description
                if value:
                    print(f"Node '{strat_node.name}' has {property_name}: {value}")
                    mapping[strat_node.name] = value
                else:
                    print(f"Warning: Node '{strat_node.name}' has empty {property_name}")
                    mapping[strat_node.name] = "nodata"
    
    if not mapping:
        print(f"No values found for property '{property_name}'")
    else:
        print(f"\nFound {len(mapping)} nodes with {property_name} values")
        
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
            "created": bpy.utils.blend_paths(0),
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