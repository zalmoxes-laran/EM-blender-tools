# s3Dgraphy/graph.py

"""
Graph module for s3Dgraphy, responsible for managing nodes and edges in the knowledge graph.
"""

import json
import os
from .nodes.base_node import Node
from .nodes.epoch_node import EpochNode
from .nodes.stratigraphic_node import StratigraphicNode
from .nodes.property_node import PropertyNode
from .nodes.geo_position_node import GeoPositionNode
from .edges import Edge
from typing import List

# Load the connection rules JSON
rules_path = os.path.join(os.path.dirname(__file__), "./JSON_config/em_connection_rules.json")
with open(rules_path) as f:
    connection_rules = json.load(f)["rules"]

class Graph:
    """
    Class representing a graph containing nodes and edges.

    Attributes:
        graph_id (str): Unique identifier for the graph.
        name (dict): Dictionary of graph name translations.
        description (dict): Dictionary of graph description translations.
        audio (dict): Dictionary of audio file lists by language.
        video (dict): Dictionary of video file lists by language.
        data (dict): Additional metadata like geographical position.
        nodes (List[Node]): List of nodes in the graph.
        edges (List[Edge]): List of edges in the graph.
        warnings (List[str]): List to accumulate warning messages during operations.
    """

    def __init__(self, graph_id, name=None, description=None, audio=None, video=None, data=None):
        self.graph_id = graph_id
        self.name = name if name is not None else {}
        self.description = description if description is not None else {}
        self.audio = audio if audio is not None else {}
        self.video = video if video is not None else {}
        self.data = data if data is not None else {}
        self.nodes = []
        self.edges = []
        self.warnings = []

        # Initialize and add geo_position node if not already present
        if not any(node.node_type == "geo_position" for node in self.nodes):
            geo_node = GeoPositionNode(node_id=f"geo_{graph_id}")
            self.add_node(geo_node, overwrite=True)

    @staticmethod
    def validate_connection(source_node_type, target_node_type, edge_type):
        """
        Validates if a connection type between two nodes is allowed by the rules.

        Args:
            source_node_type (str): The type of the source node.
            target_node_type (str): The type of the target node.
            edge_type (str): The type of edge connecting the nodes.

        Returns:
            bool: True if the connection is allowed, False otherwise.
        """
        for rule in connection_rules:
            if rule["type"] == edge_type:
                allowed_sources = rule["allowed_connections"]["source"]
                allowed_targets = rule["allowed_connections"]["target"]
                return source_node_type in allowed_sources and target_node_type in allowed_targets
        return False

    def add_warning(self, message):
        """Adds a warning message to the warnings list."""
        self.warnings.append(message)

    def add_node(self, node: Node, overwrite=False) -> Node:
        """Adds a node to the graph."""
        existing_node = self.find_node_by_id(node.node_id)
        if existing_node:
            if overwrite:
                self.nodes.remove(existing_node)
                self.add_warning(f"Node '{node.node_id}' overwritten.")
            else:
                return existing_node
        self.nodes.append(node)
        return node

    def add_edge(self, edge_id: str, edge_source: str, edge_target: str, edge_type: str) -> Edge:
        """
        Adds an edge to the graph with connection validation.

        Args:
            edge_id (str): Unique ID of the edge.
            edge_source (str): Source node ID.
            edge_target (str): Target node ID.
            edge_type (str): Type of edge, must be defined in the connection rules.

        Returns:
            Edge: The added edge.

        Raises:
            ValueError: If the source or target node does not exist or if the edge is a duplicate.
        """
        source_node = self.find_node_by_id(edge_source)
        target_node = self.find_node_by_id(edge_target)
        
        if not source_node or not target_node:
            raise ValueError(f"Both nodes with IDs '{edge_source}' and '{edge_target}' must exist.")

        # Validate the connection using connection rules
        if not self.validate_connection(source_node.node_type, target_node.node_type, edge_type):
            self.add_warning(f"Connection '{edge_type}' not allowed between '{source_node.node_type}' and '{target_node.node_type}'. Using 'generic_connection' instead.")
            edge_type = "generic_connection"

        if self.find_edge_by_id(edge_id):
            raise ValueError(f"An edge with ID '{edge_id}' already exists.")

        edge = Edge(edge_id, edge_source, edge_target, edge_type)
        self.edges.append(edge)
        return edge

    def display_warnings(self):
        """Displays all accumulated warning messages."""
        for warning in self.warnings:
            print("Warning:", warning)

    def find_node_by_id(self, node_id):
        """Finds a node by ID."""
        for node in self.nodes:
            if node.node_id == node_id:
                return node
        return None

    def find_edge_by_id(self, edge_id):
        """Finds an edge by ID."""
        for edge in self.edges:
            if edge.edge_id == edge_id:
                return edge
        return None

    def get_connected_nodes(self, node_id):
        """Gets all nodes connected to a given node."""
        connected_nodes = []
        for edge in self.edges:
            if edge.edge_source == node_id:
                target_node = self.find_node_by_id(edge.edge_target)
                if target_node:
                    connected_nodes.append(target_node)
            elif edge.edge_target == node_id:
                source_node = self.find_node_by_id(edge.edge_source)
                if source_node:
                    connected_nodes.append(source_node)
        return connected_nodes

    def get_connected_edges(self, node_id):
        """Gets all edges connected to a given node."""
        return [edge for edge in self.edges if edge.edge_source == node_id or edge.edge_target == node_id]

    def filter_nodes_by_connection_to_type(self, node_id, node_type):
        """Filters nodes connected to a given node by node type."""
        connected_nodes = self.get_connected_nodes(node_id)
        return [node for node in connected_nodes if node.node_type == node_type]

    def get_nodes_by_type(self, node_type):
        """Gets all nodes of a given type."""
        return [node for node in self.nodes if node.node_type == node_type]

    def remove_node(self, node_id):
        """Removes a node and all edges connected to it."""
        self.nodes = [node for node in self.nodes if node.node_id != node_id]
        self.edges = [edge for edge in self.edges if edge.edge_source != node_id and edge.edge_target != node_id]
        print(f"Node '{node_id}' and its edges removed successfully.")

    def remove_edge(self, edge_id):
        """Removes an edge from the graph."""
        self.edges = [edge for edge in self.edges if edge.edge_id != edge_id]
        print(f"Edge '{edge_id}' removed successfully.")

    def update_node(self, node_id, **kwargs):
        """Updates attributes of an existing node."""
        node = self.find_node_by_id(node_id)
        if not node:
            raise ValueError(f"Node with ID '{node_id}' not found.")
        for key, value in kwargs.items():
            setattr(node, key, value)
        print(f"Node '{node_id}' updated successfully.")

    def update_edge(self, edge_id, **kwargs):
        """Updates attributes of an existing edge."""
        edge = self.find_edge_by_id(edge_id)
        if not edge:
            raise ValueError(f"Edge with ID '{edge_id}' not found.")
        for key, value in kwargs.items():
            setattr(edge, key, value)
        print(f"Edge '{edge_id}' updated successfully.")

'''
Esempio di utilizzo:
graph = get_graph()  # Ottieni il grafo caricato
graph.calculate_chronology()  # Calcola la cronologia

# Filtra i nodi in un intervallo di tempo specifico
filtered_nodes = graph.filter_nodes_by_time_range(50, 100)
for node in filtered_nodes:
    print(f"Node {node.node_id}: Start = {node.attributes.get('CALCUL_START_T')}, End = {node.attributes.get('CALCUL_END_T')}")
'''