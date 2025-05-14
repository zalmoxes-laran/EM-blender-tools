# graph_node.py
from .base_node import Node

class GraphNode(Node):
    """
    It represents the node of the graph itself within the system.
    It allows the graph itself to be linked to other nodes, such as authors and licences.
    """
    node_type = "graph"
    
    def __init__(self, node_id, name="Graph", description=""):
        super().__init__(node_id=node_id, name=name, description=description)