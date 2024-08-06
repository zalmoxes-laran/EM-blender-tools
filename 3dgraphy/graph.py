# 3dgraphy/graph.py
from .node import Node
from .edge import Edge

class Graph:
    def __init__(self):
        self.nodes = []
        self.edges = []

    def add_node(self, id, name):
        node = Node(id, name)
        self.nodes.append(node)

    def add_edge(self, start_node_id, end_node_id, edge_type):
        edge = Edge(start_node_id, end_node_id, edge_type)
        self.edges.append(edge)

    # Qui puoi aggiungere metodi per la ricerca di nodi, la ricerca di percorsi, ecc.
