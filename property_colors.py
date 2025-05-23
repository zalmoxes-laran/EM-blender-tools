import bpy # type: ignore
from .s3Dgraphy.nodes.stratigraphic_node import StratigraphicNode
import json
import os
from .functions import hex_to_rgb

DEFAULT_COLOR = (0.5, 0.5, 0.5, 1.0)  # Grigio medio



# Versione ottimizzata di create_property_value_mapping
def create_property_value_mapping_optimized(graph, property_name):
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