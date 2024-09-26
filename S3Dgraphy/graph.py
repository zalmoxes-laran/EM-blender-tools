# 3dgraphy/graph.py
from .node import *
from .edge import *

class Graph:
    def __init__(self):
        self.nodes = []
        self.edges = []

    def add_node(self, node):
        # Verifica se il nodo esiste già
        if self.find_node_by_id(node.node_id):
            raise ValueError(f"Un nodo con ID '{node.node_id}' esiste già.")
        # Aggiungi il nuovo nodo
        self.nodes.append(node)
        return node

    def add_edge(self, edge_id, start_node_id, end_node_id, edge_type):
        # Verifica se i nodi di sorgente e destinazione esistono
        source_node = self.find_node_by_id(start_node_id)
        target_node = self.find_node_by_id(end_node_id)
        if not source_node or not target_node:
            raise ValueError(f"Entrambi i nodi con ID '{start_node_id}' e '{end_node_id}' devono esistere.")

        # Verifica se un arco identico esiste già
        if self.find_edge_by_nodes(start_node_id, end_node_id):
            raise ValueError(f"Un arco tra '{start_node_id}' e '{end_node_id}' esiste già.")

        # Verifica se un arco con stesso id esiste già
        if self.find_edge_by_id(edge_id):
            raise ValueError(f"Un arco tra con id '{edge_id}' esiste già.")

        # Aggiungi il nuovo arco
        edge = Edge(edge_id, start_node_id, end_node_id, edge_type)
        self.edges.append(edge)
        return edge

    def find_node_by_id(self, node_id):
        # Ricerca un nodo per ID
        for node in self.nodes:
            if node.node_id == node_id:
                return node
        return None

    def find_edge_by_nodes(self, start_node_id, end_node_id):
        # Ricerca un arco per i nodi di sorgente e destinazione
        for edge in self.edges:
            if edge.edge_source == start_node_id and edge.edge_target == end_node_id:
                return edge
        return None

    def find_edge_by_id(self, edge_id):
        # Ricerca un arco per i nodi di sorgente e destinazione
        for edge in self.edges:
            if edge.edge_source == edge_id:
                return edge
        return None

    def filter_nodes_by_connection_to_type(self, target_node_type, connected=True):
        """
        Filtra i nodi in base al fatto che siano collegati o meno ad almeno un nodo di un tipo specifico.

        :param target_node_type: Il tipo di nodo a cui verificare la connessione.
        :param connected: Se True, restituisce nodi collegati ad almeno un nodo del tipo specificato.
                          Se False, restituisce nodi non collegati a nodi del tipo specificato.
        :return: Una lista di oggetti Node.
        """
        # Ottieni l'insieme degli ID dei nodi del tipo target
        target_node_ids = set(node.node_id for node in self.nodes if node.node_type == target_node_type)

        # Crea una mappatura dei nodi alle loro connessioni
        node_connections = {node.node_id: set() for node in self.nodes}
        for edge in self.edges:
            # Considera sia sorgente che destinazione per grafi non diretti
            node_connections[edge.edge_source].add(edge.edge_target)
            node_connections[edge.edge_target].add(edge.edge_source)

        # Filtra i nodi in base alle connessioni
        filtered_nodes = []
        for node in self.nodes:
            connections = node_connections[node.node_id]
            # Verifica se il nodo è collegato ad almeno un nodo del tipo target
            is_connected = any(conn_node_id in target_node_ids for conn_node_id in connections)
            if connected and is_connected:
                filtered_nodes.append(node)
            elif not connected and not is_connected:
                filtered_nodes.append(node)

        return filtered_nodes

    # Qui puoi aggiungere ulteriori metodi per gestire ricerche, rimozioni e manipolazioni

'''
class MultiGraph:
    def __init__(self):
        self.graphs = []

    def add_graph(self, graph):
        self.graphs.append(graph)

    def import_graphml(self, filepaths):
        # Importa più grafi da una lista di file GraphML
        for filepath in filepaths:
            graph = import_graphml(filepath)
            self.add_graph(graph)

            
COME SI USA:

from s3Dgraphy import MultiGraph

multi_graph = MultiGraph()
multi_graph.import_graphml(['file1.graphml', 'file2.graphml'])

LA STRUTTURA A CUI VOGLIO ARRIVARE E' QUESTA, la sviluppo appena ho finito il porting di tutto il parser
s3Dgraphy/
│
├── __init__.py          # Importazioni principali
├── graph.py             # Classi Graph e MultiGraph
├── node.py              # Classe Node e sottoclassi
├── edge.py              # Classe Edge e sottoclassi
├── import_graphml.py    # Funzioni per l'importazione del GraphML
└── utils.py             # Funzioni di supporto comuni (opzionale)


'''