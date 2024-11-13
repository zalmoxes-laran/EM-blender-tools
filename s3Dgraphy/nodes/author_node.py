from .base_node import Node

class AuthorNode(Node):
    """
    Classe per rappresentare un nodo autore all'interno del grafo.

    Attributi:
        orcid (str): Identificativo ORCID dell'autore (opzionale).
        name (str): Nome dell'autore (opzionale).
        surname (str): Cognome dell'autore (opzionale).
    """
    node_type = "author"

    def __init__(self, node_id, orcid="noorcid", name="noname", surname="nosurname"):
        """
        Inizializza una nuova istanza di AuthorNode.

        Args:
            node_id (str): Identificativo univoco del nodo.
            orcid (str, opzionale): Identificativo ORCID. Defaults to "noorcid".
            name (str, opzionale): Nome dell'autore. Defaults to "noname".
            surname (str, opzionale): Cognome dell'autore. Defaults to "nosurname".
        """
        super().__init__(node_id=node_id, name="author")
        
        # Dati dell'autore con valori di fallback
        self.data = {
            "orcid": orcid,
            "name": name,
            "surname": surname
        }
    
    def to_dict(self):
        """
        Converte l'istanza di AuthorNode in un dizionario.

        Returns:
            dict: Rappresentazione del AuthorNode come dizionario.
        """
        return {
            "type": self.node_type,
            "name": self.name,
            "data": self.data
        }

'''
# Esempio di utilizzo per connettere AuthorNode al GraphNode e a nodi specifici
author_node = AuthorNode(node_id="author_1", orcid="noorcid", name="John", surname="Doe")
graph = Graph(graph_id="my_graph")

# Aggiunge l'AuthorNode al grafo
graph.add_node(author_node)

# Connetti l'AuthorNode al GraphNode con edge "generic"
graph.add_edge(edge_id="authorship_1", edge_source=author_node.node_id, edge_target=graph.graph_id, edge_type="generic")

# Connetti l'AuthorNode a un nodo specifico (es. StratigraphicNode) con edge "generic"
stratigraphic_node = StratigraphicNode(node_id="strat_1", name="Stratification A", stratigraphic_type="Layer")
graph.add_node(stratigraphic_node)
graph.add_edge(edge_id="contribution_1", edge_source=author_node.node_id, edge_target=stratigraphic_node.node_id, edge_type="generic")

'''