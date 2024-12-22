import bpy # type: ignore
from .s3Dgraphy.nodes.stratigraphic_node import StratigraphicNode
import json
import os
from .functions import hex_to_rgb

DEFAULT_COLOR = (0.5, 0.5, 0.5, 1.0)  # Grigio medio



def create_property_value_mapping(graph, property_name):
    """
    Creates a mapping of unique values for a given property.
    """
    print(f"\n=== Creating Property Value Mapping for '{property_name}' ===")
    
    mapping = {}
    has_empty = False
    
    # Raccogli tutti i valori unici per quella proprietà
    property_nodes = [node for node in graph.nodes 
                     if node.node_type == "property" 
                     and node.name == property_name]
    
    print(f"Found {len(property_nodes)} nodes for property {property_name}")
    
    # Set per tenere traccia dei nodi stratigrafici connessi
    connected_strat_nodes = set()
    
    for node in property_nodes:
        if node.description:  # Se ha un valore
            value = node.description
            mapping[node.node_id] = value
            print(f"Found value: {value}")
            
            # Aggiungi i nodi stratigrafici connessi al set
            for edge in graph.edges:
                if edge.edge_type == "has_data_provenance" and edge.edge_target == node.node_id:
                    connected_strat_nodes.add(edge.edge_source)
        else:
            has_empty = True

    # Aggiungi empty property se necessario
    if has_empty:
        mapping['empty'] = f"empty property {property_name} node"
        print(f"Found nodes with empty {property_name} property")

    # Verifica se ci sono nodi stratigrafici senza questa proprietà
    strat_nodes_without_prop = any(
        isinstance(node, StratigraphicNode) and node.node_id not in connected_strat_nodes 
        for node in graph.nodes
    )
    if strat_nodes_without_prop:
        mapping['no_prop'] = f"no property {property_name} node"
        print(f"Found nodes without {property_name} property")

    print(f"\nMapping results:")
    for node_id, value in mapping.items():
        print(f"  {value}")
    
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