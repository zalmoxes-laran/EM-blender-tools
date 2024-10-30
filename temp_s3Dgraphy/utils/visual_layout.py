# s3Dgraphy/utils/visual_layout.py

"""
Module for generating visual layouts for s3Dgraphy graphs using NetworkX.

This module provides functionality to generate hierarchical X, Y coordinates for nodes
within a graph using NetworkX. 
"""

# Import NetworkX only if available
try:
    import networkx as nx
except ImportError:
    nx = None  # Handle NetworkX unavailability gracefully

from ..graph import Graph, Node

def generate_layout(graph: Graph):
    """
    Generates X, Y coordinates for nodes in a graph based on a hierarchical layout.

    :param graph: An instance of the Graph class containing nodes and edges.
    :return: A dictionary with node IDs as keys and (x, y) tuples as values representing node coordinates.
    :raises ImportError: If NetworkX is not installed.
    """
    if nx is None:
        raise ImportError("NetworkX library is required for layout generation but is not installed.")

    # Initialize a NetworkX directed graph
    G = nx.DiGraph()

    # Add nodes to the NetworkX graph
    for node in graph.nodes:
        G.add_node(node.node_id)

    # Add edges to the NetworkX graph
    for edge in graph.edges:
        G.add_edge(edge.edge_source, edge.edge_target)

    # Generate layout using a spring layout or graphviz-based layout
    pos = nx.spring_layout(G)  # Alternative layout can be used based on requirements
    
    # Create dictionary for node positions
    node_positions = {node_id: (x, y) for node_id, (x, y) in pos.items()}

    return node_positions

if __name__ == "__main__":
    # Example usage
    # Create a sample graph
    example_graph = Graph("example")
    example_graph.add_node(Node("1", "Node 1", "type1"))
    example_graph.add_node(Node("2", "Node 2", "type2"))
    example_graph.add_node(Node("3", "Node 3", "type3"))
    example_graph.add_edge("e1", "1", "2", "is_connected_to")
    example_graph.add_edge("e2", "2", "3", "is_connected_to")

    # Generate layout
    layout = generate_layout(example_graph)

    # Print node positions
    for node_id, coordinates in layout.items():
        print(f"Node {node_id}: {coordinates}")
