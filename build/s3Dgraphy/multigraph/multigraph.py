# s3Dgraphy/multigraph/multigraph.py

import os
from ..graph import Graph
from ..importer.import_graphml import GraphMLImporter
import xml.etree.ElementTree as ET

class MultiGraphManager:
    def __init__(self):
        self.graphs = {}

    def load_graph(self, filepath, graph_id=None, overwrite=False):
        """
        Carica un grafo da un file GraphML.
        
        Args:
            filepath (str): Percorso del file GraphML
            graph_id (str, optional): ID da assegnare al grafo. Se None, verrà estratto dal file.
            overwrite (bool): Se sovrascrivere un grafo esistente con lo stesso ID
        
        Returns:
            str: L'ID del grafo caricato
        """
        print(f"Loading graph: {filepath}, graph_id: {graph_id}, overwrite: {overwrite}")
        
        # ID temporaneo basato sul file se non specificato
        original_id = graph_id if graph_id else os.path.splitext(os.path.basename(filepath))[0]
        
        # Crea un grafo temporaneo con ID originale
        graph = Graph(graph_id=original_id)
        
        # Carica il grafo con il parser
        importer = GraphMLImporter(filepath, graph)
        graph = importer.parse()
        
        # Controlla se l'ID è cambiato durante il parsing
        final_id = graph.graph_id
        
        # IMPORTANTE: Aggiungi il grafo sia con l'ID originale che con quello nuovo
        # Questo crea una "mappa di alias" senza duplicare i grafi
        if final_id != original_id:
            print(f"INFO: Graph ID changed during parsing: {original_id} -> {final_id}")
            
            # Aggiungi il grafo con l'ID finale
            self.graphs[final_id] = graph
            
            # Mantieni anche un riferimento con l'ID originale se necessario per retrocompatibilità
            if overwrite or original_id not in self.graphs:
                self.graphs[original_id] = graph
        else:
            # Se l'ID non è cambiato, aggiungi normalmente
            self.graphs[original_id] = graph
        
        # Restituisci l'ID finale
        return final_id

    def get_graph(self, graph_id=None):
        """
        Ottiene un grafo dal MultiGraphManager.
        
        Args:
            graph_id (str, optional): ID del grafo da recuperare.
                Se None e c'è un solo grafo, restituisce quel grafo.
                Se None e ci sono più grafi, restituisce None invece di generare errore.
        
        Returns:
            Graph: L'istanza del grafo richiesto, o None se non trovato.
        """
        if graph_id is None:
            if len(self.graphs) == 1:
                return next(iter(self.graphs.values()))
            else:
                # Invece di lanciare un errore, restituisci None o un valore di default
                print("Attenzione: Più grafi caricati, specificare un 'graph_id'.")
                return None  # Opzione 1: Restituisci None
                # return list(self.graphs.values())[0]  # Opzione 2: Restituisci il primo grafo
        
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

def load_graph_from_file(filepath, graph_id=None, overwrite=False):
    print(f"Loading graph: {filepath}, graph_id: {graph_id}, overwrite: {overwrite}")
    return multi_graph_manager.load_graph(filepath, graph_id, overwrite)

def get_graph(graph_id=None):
    return multi_graph_manager.get_graph(graph_id)

def get_all_graph_ids():
    return multi_graph_manager.get_all_graph_ids()

def remove_graph(graph_id):
    multi_graph_manager.remove_graph(graph_id)