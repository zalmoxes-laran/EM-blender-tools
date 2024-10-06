# s3Dgraphy/visual_layout.py
import networkx as nx
from .graph import Graph, Node  # Cambiato import per evitare errore di importazione relativa

def generate_layout(graph: Graph):
    """
    Genera le coordinate X, Y per tutti i nodi di un grafo basato su una disposizione gerarchica.
    
    :param graph: Un'istanza della classe Graph contenente nodi e archi.
    :return: Un dizionario con gli ID dei nodi come chiavi e tuple (x, y) come valori per le coordinate dei nodi.
    """
    # Crea un grafo di NetworkX a partire dal grafo esistente
    G = nx.DiGraph()
    
    # Aggiungi i nodi al grafo di NetworkX
    for node in graph.nodes:
        G.add_node(node.node_id)
    
    # Aggiungi gli archi al grafo di NetworkX
    for edge in graph.edges:
        G.add_edge(edge.edge_source, edge.edge_target)
    
    # Genera il layout usando un algoritmo di layout gerarchico alternativo
    pos = nx.drawing.layout.spring_layout(G)
    #pos = nx.drawing.nx_agraph.graphviz_layout(G, prog="dot")

    
    # Crea un dizionario delle posizioni per i nodi
    node_positions = {}
    for node_id, (x, y) in pos.items():
        node_positions[node_id] = (x, y)
    
    return node_positions

if __name__ == "__main__":
    # Esempio di utilizzo
    # Crea un grafo di esempio
    example_graph = Graph()
    example_graph.add_node(Node("1", "Nodo 1", "type1"))
    example_graph.add_node(Node("2", "Nodo 2", "type2"))
    example_graph.add_node(Node("3", "Nodo 3", "type3"))
    example_graph.add_edge("e1", "1", "2", "link")
    example_graph.add_edge("e2", "2", "3", "link")
    
    # Genera il layout
    layout = generate_layout(example_graph)
    
    # Stampa le posizioni dei nodi
    for node_id, coordinates in layout.items():
        print(f"Nodo {node_id}: {coordinates}")