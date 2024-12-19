# s3Dgraphy/utils/utils.py
import os
import json

"""
Utilities for the s3Dgraphy library.

This module includes helper functions for node type conversion based on YED node shapes and border styles.
"""

from ..nodes.stratigraphic_node import (
    StratigraphicNode,
    StratigraphicUnit,
    SeriesOfStratigraphicUnit,
    SeriesOfNonStructuralVirtualStratigraphicUnit,
    SeriesOfStructuralVirtualStratigraphicUnit,
    NonStructuralVirtualStratigraphicUnit,
    StructuralVirtualStratigraphicUnit,
    SpecialFindUnit,
    VirtualSpecialFindUnit,
    DocumentaryStratigraphicUnit,
    TransformationStratigraphicUnit,
    StratigraphicEventNode,
    ContinuityNode
)


def convert_shape2type(yedtype, border_style):
    """
    Converts YED node shape and border style to a specific stratigraphic node type.

    Args:
        yedtype (str): The shape type of the node in YED.
        border_style (str): The border color of the node.

    Returns:
        tuple: A tuple with a short code for the node type and an extended description.
    """
    if yedtype == "rectangle":
        nodetype = ("US", "Stratigraphic Unit")
    elif yedtype == "parallelogram":
        nodetype = ("USVs", "Structural Virtual Stratigraphic Units")
    elif yedtype == "ellipse" and border_style == "#31792D":
        nodetype = ("serUSVn", "Series of USVn")
    elif yedtype == "ellipse" and border_style == "#248FE7":
        nodetype = ("serUSVs", "Series of USVs")
    elif yedtype == "ellipse" and border_style == "#9B3333":
        nodetype = ("serSU", "Series of SU")
    elif yedtype == "hexagon":
        nodetype = ("USVn", "Non-Structural Virtual Stratigraphic Units")
    elif yedtype == "octagon" and border_style == "#D8BD30":
        nodetype = ("SF", "Special Find")
    elif yedtype == "octagon" and border_style == "#B19F61":
        nodetype = ("VSF", "Virtual Special Find")
    elif yedtype == "roundrectangle":
        nodetype = ("USD", "Documentary Stratigraphic Unit")
    else:
        print(f"Unrecognized node type and style: yedtype='{yedtype}', border_style='{border_style}'")
        nodetype = ("unknown", "Unrecognized node")
        
    return nodetype


# Mappa dei tipi stratigrafici alle rispettive classi
STRATIGRAPHIC_CLASS_MAP = {
    "US": StratigraphicUnit,
    "USVs": StructuralVirtualStratigraphicUnit,
    "serSU": SeriesOfStratigraphicUnit,
    "serUSVn": SeriesOfNonStructuralVirtualStratigraphicUnit,
    "serUSVs": SeriesOfStructuralVirtualStratigraphicUnit,
    "USVn": NonStructuralVirtualStratigraphicUnit,
    "SF": SpecialFindUnit,
    "VSF": VirtualSpecialFindUnit,
    "USD": DocumentaryStratigraphicUnit,
    "TSU": TransformationStratigraphicUnit,
    "SE": StratigraphicEventNode,
    "BR": ContinuityNode,
    # Aggiungi ulteriori tipi e classi se necessario
}

def get_stratigraphic_node_class(stratigraphic_type):
    """
    Returns the stratigraphic node class corresponding to the specified type.

    Args:
        stratigraphic_type (str): The type of stratigraphic unit.

    Returns:
        class: The corresponding stratigraphic node class.
    """
    # Usa StratigraphicUnit come fallback se il tipo non è nella mappa
    return STRATIGRAPHIC_CLASS_MAP.get(stratigraphic_type, StratigraphicNode)

def get_material_color(matname, rules_path=None):
    """
    Ottiene i valori RGB per un dato tipo di materiale dal file di configurazione.
    
    Args:
        matname (str): Nome del materiale/tipo di unità stratigrafica
        rules_path (str, optional): Percorso al file JSON delle regole. Se None,
            usa il path di default.
            
    Returns:
        tuple: (R, G, B, A) con valori tra 0 e 1 o None se il nodo non prevede
        un materiale
    """
    if rules_path is None:
        rules_path = os.path.join(os.path.dirname(__file__), 
                                "../JSON_config/em_visual_rules.json")
    
    try:
        with open(rules_path, 'r') as f:
            rules = json.load(f)
            node_style = rules["node_styles"].get(matname, {})
            style = node_style.get("style", {})
            
            # Se non c'è la sezione material, restituisce None
            if "material" not in style:
                return None
                
            color = style["material"]["color"]
            return (color["r"], color["g"], color["b"], color.get("a", 1.0))
            
    except (KeyError, FileNotFoundError, json.JSONDecodeError):
        # Fallback solo per i nodi che dovrebbero avere un materiale
        if matname in ['US', 'USVs', 'USVn', 'VSF', 'SF', 'USD']:
            return (0.5, 0.5, 0.5, 1.0)
        return None