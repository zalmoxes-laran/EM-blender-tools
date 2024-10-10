# s3Dgraphy/multigraph.py

import os
from .graph import Graph
from .import_graphml import GraphMLImporter

class MultiGraphManager:
    def __init__(self):
        self.graphs = {}

    def load_graph(self, filepath, graph_id=None, overwrite=False):
        print(f"MultiGraphManager: load_graph called with graph_id={graph_id}, overwrite={overwrite}")
        if graph_id is None:
            graph_id = os.path.splitext(os.path.basename(filepath))[0]

        if graph_id in self.graphs and not overwrite:
            raise ValueError(f"Un grafo con ID '{graph_id}' esiste già. Usa overwrite=True per sovrascriverlo.")

        graph = Graph(graph_id=graph_id)
        importer = GraphMLImporter(filepath, graph)
        graph = importer.parse()

        self.graphs[graph_id] = graph
        print(f"Graph '{graph_id}' loaded successfully with overwrite={overwrite}.")

    def get_graph(self, graph_id):
        return self.graphs.get(graph_id)

    def get_all_graph_ids(self):
        return list(self.graphs.keys())

    def remove_graph(self, graph_id):
        if graph_id in self.graphs:
            del self.graphs[graph_id]
            print(f"Graph '{graph_id}' removed successfully.")

multi_graph_manager = MultiGraphManager()

def load_graph(filepath, graph_id=None, overwrite=False):
    print(f"Loading graph: {filepath}, graph_id: {graph_id}, overwrite: {overwrite}")
    multi_graph_manager.load_graph(filepath, graph_id, overwrite)

def get_graph(graph_id=None):
    if graph_id is None:
        if len(multi_graph_manager.graphs) == 1:
            return next(iter(multi_graph_manager.graphs.values()))
        else:
            raise ValueError("Più grafi caricati, specifica un 'graph_id'.")
    return multi_graph_manager.get_graph(graph_id)

def get_all_graph_ids():
    return multi_graph_manager.get_all_graph_ids()

def remove_graph(graph_id):
    multi_graph_manager.remove_graph(graph_id)
