# graph_registry.py

from .graph_manager import GraphManager

# Crea un'unica istanza di GraphManager
graph_manager = GraphManager()

# Funzione per caricare un grafo
def load_graph(filepath):
    graph_manager.load_graph(filepath)

# Funzione per ottenere l'istanza del grafo
def get_graph():
    return graph_manager.get_graph()