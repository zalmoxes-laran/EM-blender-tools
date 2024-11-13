from .base_node import Node

class LinkNode(Node):
    """
    Classe per rappresentare un nodo di collegamento (LinkNode) nel grafo.
    
    Attributi:
        url (str): URL del collegamento.
        url_type (str): Tipo di URL (es. "External link", "Image").
        description (str): Descrizione del collegamento.
    """
    node_type="link"
    def __init__(self, node_id, name="Unnamed Link", url="", url_type="External link", description="No description"):
        """
        Inizializza una nuova istanza di LinkNode.

        Args:
            node_id (str): Identificatore univoco del nodo.
            name (str, opzionale): Nome del collegamento. Defaults to "Unnamed Link".
            url (str, opzionale): URL del collegamento. Defaults to "".
            url_type (str, opzionale): Tipo di URL. Defaults to "External link".
            description (str, opzionale): Descrizione del collegamento. Defaults to "No description".
        """
        super().__init__(node_id=node_id, name=name)
        
        # Dati del collegamento
        self.data = {
            "description": description,
            "url": url,
            "url_type": url_type
        }

    def to_dict(self):
        """
        Converte l'istanza di LinkNode in un dizionario.

        Returns:
            dict: Rappresentazione del LinkNode come dizionario.
        """
        return {
            "id": self.node_id,
            "name": self.name,
            "type": self.node_type,
            "data": self.data
        }

'''
# Creazione di un LinkNode per un URL Zenodo
link_node_zenodo = LinkNode(
    node_id="USM04.zenodo",
    name="ZENODO URL",
    url="https://zenodo.org/record/28917",
    url_type="External link",
    description="Zenodo repository entry"
)

# Creazione di un LinkNode per un’immagine a risoluzione completa
link_node_image = LinkNode(
    node_id="USM04.image",
    name="FullRES Image",
    url="http://aton.ispc.it/image.jpeg",
    url_type="Image",
    description="Full resolution image"
)

# Aggiunta dei nodi al grafo e connessione (esempio con edge tipo "generic")
graph = Graph(graph_id="example_graph")
graph.add_node(link_node_zenodo)
graph.add_node(link_node_image)
graph.add_edge(edge_id="link_edge_1", edge_source=link_node_zenodo.node_id, edge_target="some_target_node", edge_type="generic")
graph.add_edge(edge_id="link_edge_2", edge_source=link_node_image.node_id, edge_target="some_target_node", edge_type="generic")

'''