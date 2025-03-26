from .base_node import Node

class LicenseNode(Node):
    """
    Classe per rappresentare un nodo di licenza nel grafo.
    
    Attributi:
        license_type (str): Tipo di licenza (es. "CC-BY", "CC-BY-NC", etc.).
        url (str): URL che punta alla descrizione completa della licenza.
    """
    node_type = "license"
    
    def __init__(self, node_id, name="Unnamed License", license_type="CC-BY-NC-ND", description="", url=""):
        """
        Inizializza una nuova istanza di LicenseNode.
        
        Args:
            node_id (str): Identificatore univoco del nodo.
            name (str, opzionale): Nome della licenza. Default a "Unnamed License".
            license_type (str, opzionale): Tipo di licenza. Default a "CC-BY-NC-ND".
            description (str, opzionale): Descrizione della licenza. Default a stringa vuota.
            url (str, opzionale): URL della licenza. Default a stringa vuota.
        """
        super().__init__(node_id=node_id, name=name, description=description)
        
        self.data = {
            "license_type": license_type,
            "url": url
        }
        
    def to_dict(self):
        """
        Converte l'istanza di LicenseNode in un dizionario.
        
        Returns:
            dict: Rappresentazione del LicenseNode come dizionario.
        """
        return {
            "id": self.node_id,
            "type": self.node_type,
            "name": self.name,
            "description": self.description,
            "data": self.data
        }
        
"""
Esempio di utilizzo:

license_node = LicenseNode(
    node_id="license_cc_by",
    name="Creative Commons Attribution",
    license_type="CC-BY-4.0",
    description="Permette di condividere e adattare il materiale per qualsiasi scopo, anche commerciale.",
    url="https://creativecommons.org/licenses/by/4.0/"
)

graph = Graph(graph_id="my_graph")
graph.add_node(license_node)

# Connetti la licenza a un nodo
res_node = StratigraphicNode(node_id="my_resource", name="My Resource")
graph.add_node(res_node)
graph.add_edge(
    edge_id="resource_license", 
    edge_source=res_node.node_id,
    edge_target=license_node.node_id,
    edge_type="has_license"
)
"""