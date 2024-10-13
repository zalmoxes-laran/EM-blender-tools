# s3Dgraphy/graph.py

from .node import Node, EpochNode, StratigraphicNode, PropertyNode
from .edge import Edge
from typing import List
from .geo_position_node import GeoPositionNode


class Graph:
    """
    Classe per rappresentare un grafo contenente nodi ed archi.

    Attributes:
        graph_id (str): Identificatore univoco del grafo.
        name (dict): Dizionario delle traduzioni del nome del grafo.
        description (dict): Dizionario delle traduzioni della descrizione del grafo.
        audio (dict): Dizionario delle liste di file audio per lingua.
        video (dict): Dizionario delle liste di file video per lingua.
        data (dict): Metadati aggiuntivi come la posizione geografica.
        nodes (List[Node]): Lista dei nodi nel grafo.
        edges (List[Edge]): Lista degli archi nel grafo.
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

        # Inizializza e aggiungi il nodo geo_position se non è già presente
        if not any(node.node_type == "geo_position" for node in self.nodes):
            geo_node = GeoPositionNode(node_id=f"geo_{graph_id}")
            self.add_node(geo_node, overwrite=True)


    def add_node(self, node: Node, overwrite=False) -> Node:
        """
        Aggiunge un nodo al grafo.

        Args:
            node (Node): Il nodo da aggiungere.
            overwrite (bool): Se True, sovrascrive il nodo esistente con lo stesso ID.

        Returns:
            Node: Il nodo aggiunto.

        Raises:
            ValueError: Se un nodo con lo stesso ID esiste già e overwrite è False.
        """
        print(f"Attempting to add node: {node.node_id}, overwrite: {overwrite}")
        existing_node = self.find_node_by_id(node.node_id)
        if existing_node:
            if overwrite:
                self.nodes.remove(existing_node)
                print(f"Node '{node.node_id}' overwritten.")
            else:
                print(f"Node '{node.node_id}' already exists. Skipping addition.")
                return existing_node  # Restituisce il nodo esistente senza aggiungerlo nuovamente
        self.nodes.append(node)
        print(f"Node '{node.node_id}' added successfully.")
        return node


    def add_edge(self, edge_id: str, edge_source: str, edge_target: str, edge_type: str) -> Edge:
        """
        Aggiunge un arco al grafo.

        Args:
            edge_id (str): ID univoco dell'arco.
            edge_source (str): ID del nodo sorgente.
            edge_target (str): ID del nodo destinazione.
            edge_type (str): Tipo di arco, deve essere uno dei tipi definiti in Edge.EDGE_TYPES.

        Returns:
            Edge: L'arco aggiunto.

        Raises:
            ValueError: Se i nodi sorgente o destinazione non esistono, o se l'arco è duplicato.
        """
        source_node = self.find_node_by_id(edge_source)
        target_node = self.find_node_by_id(edge_target)
        if not source_node or not target_node:
            raise ValueError(f"Entrambi i nodi con ID '{edge_source}' e '{edge_target}' devono esistere.")

        if self.find_edge_by_id(edge_id):
            raise ValueError(f"Un arco con id '{edge_id}' esiste già.")

        edge = Edge(edge_id, edge_source, edge_target, edge_type)
        self.edges.append(edge)
        return edge

    def find_node_by_id(self, node_id):
        """
        Cerca un nodo per ID.

        Args:
            node_id (str): ID del nodo da cercare.

        Returns:
            Node: Il nodo trovato, o None se non esiste.
        """
        for node in self.nodes:
            if node.node_id == node_id:
                return node
        return None

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

    def find_edge_by_id(self, edge_id):
        """
        Cerca un arco per ID.

        Args:
            edge_id (str): ID dell'arco da cercare.

        Returns:
            Edge: L'arco trovato, o None se non esiste.
        """
        for edge in self.edges:
            if edge.edge_id == edge_id:
                return edge
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

    def get_connected_nodes(self, node_id):
        """
        Ottiene tutti i nodi collegati a un dato nodo.

        Args:
            node_id (str): ID del nodo per il quale trovare i nodi collegati.

        Returns:
            List[Node]: Lista dei nodi collegati.
        """
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
        """
        Ottiene tutti gli archi collegati a un dato nodo.

        Args:
            node_id (str): ID del nodo per il quale trovare gli archi collegati.

        Returns:
            List[Edge]: Lista degli archi collegati.
        """
        connected_edges = []
        for edge in self.edges:
            if edge.edge_source == node_id or edge.edge_target == node_id:
                connected_edges.append(edge)
        return connected_edges

    def filter_nodes_by_connection_to_type(self, node_id, node_type):
        """
        Filtra i nodi collegati a un dato nodo per tipo di nodo.

        Args:
            node_id (str): ID del nodo per il quale trovare i nodi collegati.
            node_type (str): Tipo di nodo da filtrare.

        Returns:
            List[Node]: Lista dei nodi collegati che corrispondono al tipo specificato.
        """
        connected_nodes = self.get_connected_nodes(node_id)
        filtered_nodes = [node for node in connected_nodes if node.node_type == node_type]
        return filtered_nodes

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

    # Puoi aggiungere qui altri metodi necessari per il tuo progetto.

    def get_nodes_by_type(self, node_type):
        """
        Ottiene tutti i nodi di un determinato tipo.

        Args:
            node_type (str): Tipo di nodo da cercare.

        Returns:
            List[Node]: Lista dei nodi che corrispondono al tipo specificato.
        """
        return [node for node in self.nodes if node.node_type == node_type]

    def remove_node(self, node_id):
        """
        Rimuove un nodo e tutti gli archi ad esso collegati.

        Args:
            node_id (str): ID del nodo da rimuovere.
        """
        self.nodes = [node for node in self.nodes if node.node_id != node_id]
        self.edges = [edge for edge in self.edges if edge.edge_source != node_id and edge.edge_target != node_id]

    def remove_edge(self, edge_id):
        """
        Rimuove un arco dal grafo.

        Args:
            edge_id (str): ID dell'arco da rimuovere.
        """
        self.edges = [edge for edge in self.edges if edge.edge_id != edge_id]

    def update_node(self, node_id, **kwargs):
        """
        Aggiorna gli attributi di un nodo esistente.

        Args:
            node_id (str): ID del nodo da aggiornare.
            **kwargs: Attributi da aggiornare.
        """
        node = self.find_node_by_id(node_id)
        if not node:
            raise ValueError(f"Nodo con ID '{node_id}' non trovato.")
        for key, value in kwargs.items():
            setattr(node, key, value)

    def update_edge(self, edge_id, **kwargs):
        """
        Aggiorna gli attributi di un arco esistente.

        Args:
            edge_id (str): ID dell'arco da aggiornare.
            **kwargs: Attributi da aggiornare.
        """
        edge = self.find_edge_by_id(edge_id)
        if not edge:
            raise ValueError(f"Arco con ID '{edge_id}' non trovato.")
        for key, value in kwargs.items():
            setattr(edge, key, value)


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
        print(f"No connected EpochNode found for node '{node.node_id}' via edge type '{edge_type}'.")
        return None

    def get_nodes_by_type(self, node_type):
        return [node for node in self.nodes if node.node_type == node_type]

    def remove_node(self, node_id):
        self.nodes = [node for node in self.nodes if node.node_id != node_id]
        self.edges = [edge for edge in self.edges if edge.edge_source != node_id and edge.edge_target != node_id]
        print(f"Node '{node_id}' and its edges removed successfully.")

    def remove_edge(self, edge_id):
        self.edges = [edge for edge in self.edges if edge.edge_id != edge_id]
        print(f"Edge '{edge_id}' removed successfully.")

    def update_node(self, node_id, **kwargs):
        node = self.find_node_by_id(node_id)
        if not node:
            raise ValueError(f"Nodo con ID '{node_id}' non trovato.")
        for key, value in kwargs.items():
            setattr(node, key, value)
        print(f"Node '{node_id}' updated successfully.")

    def update_edge(self, edge_id, **kwargs):
        edge = self.find_edge_by_id(edge_id)
        if not edge:
            raise ValueError(f"Arco con ID '{edge_id}' non trovato.")
        for key, value in kwargs.items():
            setattr(edge, key, value)
        print(f"Edge '{edge_id}' updated successfully.")

    def print_all_nodes(self):
        print("Current nodes in the graph:")
        for node in self.nodes:
            print(f" - {node.node_id}")


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
        if connected_epoch_nodes:
            print(f"Found {len(connected_epoch_nodes)} connected EpochNode(s) via edge type '{edge_type}'.")
        else:
            print(f"No connected EpochNodes found for node '{node.node_id}' via edge type '{edge_type}'.")
        return connected_epoch_nodes
    

    # Algoritmo per il calcolo della cronologia basato sull'architettura dati di EM

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
        # Get all stratigraphic nodes in the graph
        stratigraphic_nodes = self.get_nodes_of_type(graph, "StratigraphicNode")

        # Process each stratigraphic node
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
        # Find specific Start_time and End_time property nodes
        start_time_prop = self.find_property_node(graph, node, "Start_time")
        end_time_prop = self.find_property_node(graph, node, "End_time")

        # Get all associated epoch nodes
        epochs = self.get_connected_epoch_nodes(graph, node)

        # Calculate temporal delta from epochs
        delta_start = min(epoch.start_time for epoch in epochs) if epochs else None
        delta_end = max(epoch.end_time for epoch in epochs) if epochs else None

        # Apply data hierarchy: specific > local > general
        if start_time_prop:
            start_time = float(start_time_prop.value)
        elif delta_start is not None:
            start_time = delta_start
        else:
            start_time = None

        if end_time_prop:
            end_time = float(end_time_prop.value)
        elif delta_end is not None:
            end_time = delta_end
        else:
            end_time = self.find_end_time_from_superior_nodes(graph, node)

        # Set calculated times as attributes of the stratigraphic node
        self.set_calculated_times(node, start_time, end_time)

        # Propagate temporal information to connected nodes
        self.propagate_to_connected_nodes(graph, node, start_time, end_time)

    def find_end_time_from_superior_nodes(self, graph, node):
        """
        Search for End_time in superior stratigraphic nodes.

        This method looks for an End_time property in nodes that are stratigraphically
        above the current node, following the 'line' edge type.

        Args:
            graph (Graph): The graph containing the nodes and their relationships.
            node (StratigraphicNode): The starting node for the search.

        Returns:
            float or None: The End_time value found, or None if not found.
        """
        # Iterate through connected edges
        for edge in self.get_connected_edges(graph, node):
            if edge.type == "line" and edge.source == node.id:
                superior_node = self.find_node_by_id(graph, edge.target)
                if self.is_stratigraphic_node(superior_node):
                    end_time_prop = self.find_property_node(graph, superior_node, "End_time")
                    if end_time_prop:
                        return float(end_time_prop.value)
        return None

    def set_calculated_times(self, node, start_time, end_time):
        """
        Set the calculated start and end times as attributes of a stratigraphic node.

        This method updates the node's attributes with the calculated chronological information.

        Args:
            node (StratigraphicNode): The node to update.
            start_time (float or None): The calculated start time.
            end_time (float or None): The calculated end time.

        Returns:
            None: The method updates the node in place.
        """
        if start_time is not None:
            node.attributes["CALCUL_START_T"] = start_time
        if end_time is not None:
            node.attributes["CALCUL_END_T"] = end_time

    def propagate_to_connected_nodes(self, graph, node, start_time, end_time):
        """
        Propagate temporal information to connected stratigraphic nodes.

        This method spreads the calculated chronological information to nodes that are
        stratigraphically related to the current node, following the 'line' edge type.

        Args:
            graph (Graph): The graph containing the nodes and their relationships.
            node (StratigraphicNode): The node from which to propagate information.
            start_time (float or None): The start time to propagate.
            end_time (float or None): The end time to propagate.

        Returns:
            None: The method updates connected nodes in place.
        """
        for edge in self.get_connected_edges(graph, node):
            if edge.type == "line":
                if edge.source == node.id:
                    target_node = self.find_node_by_id(graph, edge.target)
                    if self.is_stratigraphic_node(target_node):
                        if start_time is not None and not self.find_property_node(graph, target_node, "Start_time"):
                            self.set_calculated_times(target_node, start_time, None)
                elif edge.target == node.id:
                    source_node = self.find_node_by_id(graph, edge.source)
                    if self.is_stratigraphic_node(source_node):
                        if end_time is not None and not self.find_property_node(graph, source_node, "End_time"):
                            self.set_calculated_times(source_node, None, end_time)

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

    def filter_nodes_by_time_range(self, graph, start_time, end_time):
        """
        Filter stratigraphic nodes based on a given time range.

        This method selects nodes whose calculated time range overlaps with the specified interval.

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