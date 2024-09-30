# graph_manager.py

graph_instance = None  # Variabile globale per il grafo

def load_graph(filepath):
    from .S3Dgraphy.graph import Graph
    from .S3Dgraphy.import_graphml import GraphMLImporter

    # Crea un'istanza del grafo
    graph = Graph()
    importer = GraphMLImporter(filepath, graph)
    graph = importer.parse()

    global graph_instance
    graph_instance = graph
