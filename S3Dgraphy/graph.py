# 3dgraphy/graph.py
from .node import *
from .edge import *
from typing import List


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
            return None
            raise ValueError(f"Entrambi i nodi con ID '{start_node_id}' e '{end_node_id}' devono esistere.")

        # Verifica se un arco identico esiste già
        if self.find_edge_by_nodes(start_node_id, end_node_id):
            return None

            raise ValueError(f"Un arco tra '{start_node_id}' e '{end_node_id}' esiste già.")

        # Verifica se un arco con stesso id esiste già
        if self.find_edge_by_id(edge_id):
            return None

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

    def get_connected_node_by_type(self, node, target_node_type):
        """
        Verifica se il nodo dato è collegato ad almeno un nodo con una data proprietà node_type.
        Se sì, restituisce il primo nodo trovato con il node_type specificato.
        Altrimenti, restituisce None.P

        :param node: Istanza di Node da verificare.
        :param target_node_type: Il valore di node_type da cercare nei nodi collegati.
        :return: Istanza di Node con node_type corrispondente, o None se non esiste.
        """
        # Ottieni tutti gli archi in cui il nodo è coinvolto
        connected_edges = [edge for edge in self.edges if edge.edge_source == node.node_id or edge.edge_target == node.node_id]

        # Itera attraverso gli archi per trovare nodi collegati con il node_type specificato
        for edge in connected_edges:
            # Trova l'ID dell'altro nodo connesso
            if edge.edge_source == node.node_id:
                other_node_id = edge.edge_target
            else:
                other_node_id = edge.edge_source

            # Trova l'oggetto Node corrispondente
            other_node = self.find_node_by_id(other_node_id)

            # Verifica se l'altro nodo esiste e ha il node_type specificato
            if other_node and other_node.node_type == target_node_type:
                #print("Ho trovato un nodo continuity")
                return other_node  # Restituisce il primo nodo trovato con il node_type specificato
        #print("Non ho trovato nodi continuity !!!!")
        # Se nessun nodo con il node_type specificato è trovato
        return None

    def get_epochs_list_for_stratigraphicnode(self, node_id: str) -> List[str]:
        if node_id not in self.nodes or not isinstance(self.nodes[node_id], StratigraphicNode):
            return []

        epoch_names = []
        if node_id in self.edges:
            for to_node_id, edge_type in self.edges[node_id].items():
                if edge_type == "has_epoch" and isinstance(self.nodes[to_node_id], EpochNode):
                    epoch_names.append(self.nodes[to_node_id].name)

        return epoch_names

    def get_connected_epoch_node_by_edge_type(self, node, edge_type):
        """
        Restituisce il primo nodo di tipo EpochNode collegato al nodo dato attraverso un arco del tipo specificato.

        :param node: Istanza di Node da cui partire la ricerca.
        :param edge_type: Il tipo di arco da considerare nella ricerca.
        :return: Istanza di EpochNode se trovato, altrimenti None.
        """
        # Ottieni tutti gli archi collegati al nodo dato che hanno il tipo specificato
        connected_edges = [
            edge for edge in self.edges
            if edge.edge_type == edge_type and (edge.edge_source == node.node_id or edge.edge_target == node.node_id)
        ]

        #print("ciao")
        # Itera attraverso questi archi per trovare nodi EpochNode collegati
        for edge in connected_edges:
            # Determina l'ID dell'altro nodo collegato dall'arco
            if edge.edge_source == node.node_id:
                other_node_id = edge.edge_target
            else:
                other_node_id = edge.edge_source

            # Recupera l'altro nodo
            other_node = self.find_node_by_id(other_node_id)

            # Verifica se l'altro nodo è un'istanza di EpochNode
            if isinstance(other_node, EpochNode):
                return other_node  # Restituisce il primo EpochNode trovato

        # Se nessun EpochNode collegato è trovato, restituisce None
        return None

    def print_connected_epoch_nodes_and_edge_types(self, node):
        """
        Stampa tutti i nodi EpochNode connessi al nodo dato e il tipo di edge che li collega.

        :param node: Istanza di Node da cui partire la ricerca.
        """
        # Ottieni tutti gli archi collegati al nodo dato
        connected_edges = [
            edge for edge in self.edges
            if edge.edge_source == node.node_id or edge.edge_target == node.node_id
        ]

        # Flag per verificare se sono stati trovati EpochNode collegati
        found_epoch_nodes = False

        # Itera attraverso gli archi collegati
        for edge in connected_edges:
            # Determina l'ID dell'altro nodo collegato dall'arco
            if edge.edge_source == node.node_id:
                other_node_id = edge.edge_target
            else:
                other_node_id = edge.edge_source

            # Recupera l'altro nodo
            other_node = self.find_node_by_id(other_node_id)

            # Verifica se l'altro nodo è un'istanza di EpochNode
            if isinstance(other_node, EpochNode):
                found_epoch_nodes = True
                print(f"Nodo {node.name} (ID {node.node_id} e tipo {node.node_type}) ho trovato un EpochNode: ID={other_node.node_id}, Nome={other_node.name}, Tipo={other_node.node_type} Edge Type={edge.edge_type}")
        
        if not found_epoch_nodes:
            print("Nessun EpochNode collegato trovato per il nodo specificato.")

    def find_node_by_name(self, node_name):
        """
        Cerca un nodo per nome.

        :param node_name: Il nome del nodo da cercare.
        :return: Istanza di Node se trovato, altrimenti None.
        """
        for node in self.nodes:
            if node.name == node_name:
                return node
        return None

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