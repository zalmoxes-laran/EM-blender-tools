# ParadataNode Class - Subclass of Node
from .base_node import Node

class ParadataNode(Node):
    """
    Classe base per i nodi che rappresentano metadati o informazioni su come i dati sono stati generati.

    Attributes:
        url (str): URL associato al nodo.
    """
    node_type = "ParadataNode"
    
    def __init__(self, node_id, name, description="", url=None):
        super().__init__(node_id, name, description)
        self.url = url  # Aggiunge l'attributo url
        self.data = {}  # Dizionario per dati aggiuntivi

