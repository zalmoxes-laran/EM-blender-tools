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


    def find_node_by_name(self, name):
        """
        Cerca un nodo per nome.

        Args:
            name (str): Nome del nodo da cercare.

        Returns:
            Node: Il nodo trovato, o None se non esiste.
        """
        for node in self.nodes:
            if node.name == name:
                return node
        return None
    
    def find_edge_by_nodes(self, source_id, target_id):
        """
        Cerca un arco basato sugli ID dei nodi sorgente e destinazione.

        Args:
            source_id (str): ID del nodo sorgente.
            target_id (str): ID del nodo destinazione.

        Returns:
            Edge: L'arco trovato, o None se non esiste.
        """
        for edge in self.edges:
            if edge.edge_source == source_id and edge.edge_target == target_id:
                return edge
        return None

    def get_connected_node_by_type(self, node, node_type):
        """
        Ottiene un nodo collegato di un determinato tipo.

        Args:
            node (Node): Nodo di partenza.
            node_type (str): Tipo di nodo da cercare.

        Returns:
            Node: Il nodo collegato del tipo specificato, o None se non trovato.
        """
        for edge in self.edges:
            if edge.edge_source == node.node_id:
                target_node = self.find_node_by_id(edge.edge_target)
                if target_node and target_node.node_type == node_type:
                    return target_node
            elif edge.edge_target == node.node_id:
                source_node = self.find_node_by_id(edge.edge_source)
                if source_node and source_node.node_type == node_type:
                    return source_node
        return None


    def get_connected_epoch_node_by_edge_type(self, node, edge_type: str):
        """
        Ottiene il nodo EpochNode connesso tramite un arco di tipo specifico.

        Args:
            node (Node): Il nodo da cui partire.
            edge_type (str): Il tipo di arco da filtrare.

        Returns:
            EpochNode | None: Il nodo EpochNode connesso, oppure None se non trovato.
        """
        for edge in self.edges:
            if (edge.edge_source == node.node_id and edge.edge_type == edge_type):
                target_node = self.find_node_by_id(edge.edge_target)
                if target_node and target_node.node_type == "EpochNode":
                    print(f"Found connected EpochNode '{target_node.node_id}' via edge type '{edge_type}'.")
                    return target_node
            elif (edge.edge_target == node.node_id and edge.edge_type == edge_type):
                source_node = self.find_node_by_id(edge.edge_source)
                if source_node and source_node.node_type == "EpochNode":
                    print(f"Found connected EpochNode '{source_node.node_id}' via edge type '{edge_type}'.")
                    return source_node
        return None


    def get_connected_epoch_nodes_list_by_edge_type(self, node, edge_type: str):
        """
        Ottiene una lista di nodi EpochNode connessi tramite un arco di tipo specifico.

        Args:
            node (Node): Il nodo da cui partire.
            edge_type (str): Il tipo di arco da filtrare.

        Returns:
            List[EpochNode]: Lista di nodi EpochNode connessi.
        """
        connected_epoch_nodes = []
        for edge in self.edges:
            if (edge.edge_source == node.node_id and edge.edge_type == edge_type):
                target_node = self.find_node_by_id(edge.edge_target)
                if target_node and target_node.node_type == "EpochNode":
                    print(f"Found connected EpochNode '{target_node.node_id}' via edge type '{edge_type}'.")
                    connected_epoch_nodes.append(target_node)
            elif (edge.edge_target == node.node_id and edge.edge_type == edge_type):
                source_node = self.find_node_by_id(edge.edge_source)
                if source_node and source_node.node_type == "EpochNode":
                    print(f"Found connected EpochNode '{source_node.node_id}' via edge type '{edge_type}'.")
                    connected_epoch_nodes.append(source_node)
        return connected_epoch_nodes


    def calculate_chronology(self, graph):
        """
        Calculate the chronology for all stratigraphic nodes in the graph.

        This method implements the chronology calculation protocol, considering
        the hierarchy of data: specific > local > general. It propagates temporal
        information through the stratigraphic relationships and epoch associations.

        Args:
            graph (Graph): The graph containing stratigraphic nodes and their relationships.

        Returns:
            None: The method updates the nodes in place.
        """
        stratigraphic_nodes = self.get_nodes_of_type(graph, "StratigraphicNode")

        for node in stratigraphic_nodes:
            self.propagate_chronology(graph, node)


    def propagate_chronology(self, graph, node):
        """
        Propagate chronological information for a single stratigraphic node.

        This method applies the chronology calculation protocol to a specific node,
        considering its properties, associated epochs, and stratigraphic relationships.

        Args:
            graph (Graph): The graph containing the node and its relationships.
            node (StratigraphicNode): The node for which to calculate chronology.

        Returns:
            None: The method updates the node in place.
        """
        start_time_prop = self.find_property_node(graph, node, "Start_time")
        end_time_prop = self.find_property_node(graph, node, "End_time")

        epochs = self.get_connected_epoch_nodes(graph, node)

        delta_start = min(epoch.start_time for epoch in epochs) if epochs else None
        delta_end = max(epoch.end_time for epoch in epochs) if epochs else None

        start_time = float(start_time_prop.value) if start_time_prop else delta_start
        end_time = float(end_time_prop.value) if end_time_prop else delta_end
        self.set_calculated_times(node, start_time, end_time)
        self.propagate_to_connected_nodes(graph, node, start_time, end_time)


    def find_property_node(self, graph, node, property_type):
        """
        Find a specific property node connected to a stratigraphic node.

        This method searches for a property node of a given type that is connected
        to the stratigraphic node via a 'dashed' edge type.

        Args:
            graph (Graph): The graph containing the nodes and their relationships.
            node (StratigraphicNode): The stratigraphic node to search from.
            property_type (str): The type of property to find (e.g., "Start_time", "End_time").

        Returns:
            PropertyNode or None: The found property node, or None if not found.
        """
        for edge in self.get_connected_edges(graph, node):
            if edge.type == "dashed":
                prop_node = self.find_node_by_id(graph, edge.target)
                if self.is_property_node(prop_node) and prop_node.property_type == property_type:
                    return prop_node
        return None


    def set_calculated_times(self, node, start_time, end_time):
        """
        Set the calculated start and end times as attributes of a stratigraphic node.

        Args:
            node (StratigraphicNode): The node to update.
            start_time (float or None): The calculated start time.
            end_time (float or None): The calculated end time.
        """
        if start_time is not None:
            node.attributes["CALCUL_START_T"] = start_time
        if end_time is not None:
            node.attributes["CALCUL_END_T"] = end_time


    def filter_nodes_by_time_range(self, graph, start_time, end_time):
        """
        Filter stratigraphic nodes based on a given time range.

        Args:
            graph (Graph): The graph containing the nodes to filter.
            start_time (float): The start of the time range to filter by.
            end_time (float): The end of the time range to filter by.

        Returns:
            list: A list of StratigraphicNodes that fall within the specified time range.
        """
        filtered_nodes = []
        for node in self.get_nodes_of_type(graph, "StratigraphicNode"):
            node_start = node.attributes.get("CALCUL_START_T")
            node_end = node.attributes.get("CALCUL_END_T")
            if node_start is not None and node_end is not None:
                if start_time <= node_end and end_time >= node_start:
                    filtered_nodes.append(node)
        return filtered_nodes


'''
Esempio di utilizzo:
graph = get_graph()  # Ottieni il grafo caricato
graph.calculate_chronology()  # Calcola la cronologia

# Filtra i nodi in un intervallo di tempo specifico
filtered_nodes = graph.filter_nodes_by_time_range(50, 100)
for node in filtered_nodes:
    print(f"Node {node.node_id}: Start = {node.attributes.get('CALCUL_START_T')}, End = {node.attributes.get('CALCUL_END_T')}")
'''