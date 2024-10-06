# graph_manager.py

class GraphManager:
    def __init__(self):
        self.graph = None

    def load_graph(self, filepath):
        from .S3Dgraphy.graph import Graph
        from .S3Dgraphy.import_graphml import GraphMLImporter

        # Crea un'istanza del grafo
        graph = Graph()
        importer = GraphMLImporter(filepath, graph)
        self.graph = importer.parse()

    def get_graph(self):
        return self.graph

# Creare un'istanza di GraphManager
#graph_manager = GraphManager()

'''
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
'''