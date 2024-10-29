# 3dgraphy/nodes/base_node.py
class Node:
    """
    Classe base per rappresentare un nodo nel grafo.

    Attributes:
        node_id (str): Identificatore univoco del nodo.
        name (str): Nome del nodo.
        node_type (str): Tipo di nodo.
        description (str): Descrizione del nodo.
        attributes (dict): Dizionario per attributi aggiuntivi.
    """

    def __init__(self, node_id, name, node_type, description=""):
        self.node_id = node_id
        self.name = name
        self.node_type = node_type
        self.description = description
        self.attributes = {}

    def add_attribute(self, key, value):
        self.attributes[key] = value

