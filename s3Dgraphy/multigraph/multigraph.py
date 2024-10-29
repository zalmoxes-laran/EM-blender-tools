import os
from ..graph import Graph
from ..importer.import_graphml import GraphMLImporter

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

    def update_graph_metadata(self, current_graph_id, new_graph_id=None, new_name=None):
        """
        Update the ID and/or name of a graph within the MultiGraphManager.

        Args:
            current_graph_id (str): The current ID of the graph to be updated.
            new_graph_id (str, optional): The new ID for the graph. Defaults to None.
            new_name (str, optional): The new name for the graph. Defaults to None.

        Raises:
            ValueError: If the graph ID to update does not exist or if the new ID is already taken.
        """
        if current_graph_id not in self.graphs:
            raise ValueError(f"Graph with ID '{current_graph_id}' does not exist.")

        graph = self.graphs[current_graph_id]

        # Update graph ID if specified and unique
        if new_graph_id and new_graph_id != current_graph_id:
            if new_graph_id in self.graphs:
                raise ValueError(f"Graph with ID '{new_graph_id}' already exists.")
            # Remove old entry and add new entry with updated ID
            self.graphs[new_graph_id] = self.graphs.pop(current_graph_id)
            graph.graph_id = new_graph_id
            print(f"Graph ID updated from '{current_graph_id}' to '{new_graph_id}'.")

        # Update graph name if specified
        if new_name is not None:
            graph.name = new_name
            print(f"Graph '{new_graph_id or current_graph_id}' name updated to '{new_name}'.")

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
