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
from .indices import GraphIndices


# Load the connection rules JSON
rules_path = os.path.join(os.path.dirname(__file__), "./JSON_config/em_connection_rules.json")
with open(rules_path) as f:
    connection_rules = json.load(f)["rules"]
    print('s3Dgraphy rules are correctly loaded.')

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
        self.attributes = {}

        # Initialize graph indices
        self._indices = None
        self._indices_dirty = True

        # Initialize and add geo_position node if not already present
        if not any(node.node_type == "geo_position" for node in self.nodes):
            geo_node = GeoPositionNode(node_id=f"geo_{graph_id}")
            self.add_node(geo_node, overwrite=True)

    @property
    def indices(self):
        """Lazy loading degli indici con rebuild automatico se necessario"""
        if self._indices is None:
            self._indices = GraphIndices()
        if self._indices_dirty:
            self._rebuild_indices()
        return self._indices
    
    def _rebuild_indices(self):
        """Ricostruisce gli indici del grafo"""
        if self._indices is None:
            self._indices = GraphIndices()
        
        self._indices.clear()
        
        # Indicizza nodi per tipo
        for node in self.nodes:
            node_type = getattr(node, 'node_type', 'unknown')
            self._indices.add_node_by_type(node_type, node)
            
            # Indicizzazione speciale per property nodes
            if node_type == 'property' and hasattr(node, 'name'):
                self._indices.add_property_node(node.name, node)
        
        # Indicizza edges
        for edge in self.edges:
            self._indices.add_edge(edge)
            
            # Indicizzazione speciale per has_property edges
            if edge.edge_type == 'has_property':
                source_node = self.find_node_by_id(edge.edge_source)
                target_node = self.find_node_by_id(edge.edge_target)
                if source_node and target_node and hasattr(target_node, 'name'):
                    prop_value = getattr(target_node, 'description', 'empty')
                    self._indices.add_property_relation(
                        target_node.name, 
                        edge.edge_source, 
                        prop_value
                    )
        
        self._indices_dirty = False


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

        source_class = Node.node_type_map.get(source_node_type)
        target_class = Node.node_type_map.get(target_node_type)

        if source_class is None or target_class is None:
            return False  # O gestisci l'errore come preferisci

        for rule in connection_rules:
            if rule["type"] == edge_type:
                allowed_sources = rule["allowed_connections"]["source"]
                allowed_targets = rule["allowed_connections"]["target"]

                
                source_allowed = any(
                    issubclass(source_class, Node.node_type_map.get(allowed_source, object))
                    for allowed_source in allowed_sources
                )

                target_allowed = any(
                    issubclass(target_class, Node.node_type_map.get(allowed_target, object))
                    for allowed_target in allowed_targets
                )

                return source_allowed and target_allowed    

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
        self._indices_dirty = True  # ← Aggiunto per invalidare gli indici
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

        # Validate connection using connection rules
        if not self.validate_connection(source_node.node_type, target_node.node_type, edge_type):
            self.add_warning(f"Connection '{edge_type}' not allowed between '{source_node.node_type}' (name:{source_node.name}) and '{target_node.node_type}' (name:'{target_node.name}'). Using 'generic_connection' instead.")
            edge_type = "generic_connection"

        if self.find_edge_by_id(edge_id):
            raise ValueError(f"An edge with ID '{edge_id}' already exists.")

        edge = Edge(edge_id, edge_source, edge_target, edge_type)
        self.edges.append(edge)
        self._indices_dirty = True  # ← Aggiunto per invalidare gli indici
        return edge

    def connect_paradatagroup_propertynode_to_stratigraphic(self, verbose=True):
        """
        Identifica le relazioni tra unità stratigrafiche e ParadataNodeGroup,
        poi collega direttamente le unità stratigrafiche ai PropertyNode 
        contenuti nel ParadataNodeGroup.
        
        Questa funzione permette due modalità di collegamento:
        1. Collegamento diretto: Unità Stratigrafica -> PropertyNode
        (modalità già supportata nel codice esistente)
        2. Collegamento indiretto: Unità Stratigrafica -> ParadataNodeGroup -> PropertyNode
        In questo caso, crea anche collegamenti diretti tra Unità Stratigrafica e PropertyNode
        
        Il risultato è una rete semantica più ricca, dove ogni unità stratigrafica
        può accedere direttamente alle sue proprietà, indipendentemente dalla
        struttura organizzativa scelta dall'utente (collegamento diretto o tramite gruppo).
        
        Args:
            verbose (bool): Se True, stampa messaggi dettagliati durante l'esecuzione.
                        Utile per debug. Default: True
        
        Returns:
            dict: Statistiche sulle operazioni eseguite (gruppi analizzati, collegamenti creati, ecc.)
        """
        if verbose:
            print("\n=== Connessione PropertyNode dai ParadataNodeGroup alle Unità Stratigrafiche ===")
        
        # Inizializza statistiche
        stats = {
            "paradata_groups_found": 0,
            "property_nodes_found": 0,
            "stratigraphic_nodes_found": 0,
            "connections_created": 0,
            "connections_already_existing": 0,
            "errors": 0
        }
        
        # Definisci i tipi di unità stratigrafiche riconosciuti
        stratigraphic_types = ['US', 'USVs', 'SF', 'USVn', 'USD', 'VSF', 'serSU', 
                            'serUSVn', 'serUSVs', 'TSU', 'SE', 'BR', 'unknown']
        
        # Identifica tutti i nodi ParadataNodeGroup
        paradata_groups = [node for node in self.nodes 
                        if hasattr(node, 'node_type') and node.node_type == "ParadataNodeGroup"]
        stats["paradata_groups_found"] = len(paradata_groups)
        
        if verbose:
            print(f"Trovati {stats['paradata_groups_found']} gruppi ParadataNodeGroup")
        
        # Per ogni ParadataNodeGroup, trova le property contenute e le unità stratigrafiche collegate
        for group in paradata_groups:
            if verbose:
                print(f"\nAnalisi del gruppo: {group.name} (ID: {group.node_id})")
            
            # Trova i PropertyNode contenuti nel gruppo
            property_nodes = []
            for edge in self.edges:
                if edge.edge_target == group.node_id and edge.edge_type == "is_in_paradata_nodegroup":
                    source_node = self.find_node_by_id(edge.edge_source)
                    if source_node and hasattr(source_node, 'node_type') and source_node.node_type == "property":
                        property_nodes.append(source_node)
                        if verbose:
                            print(f"  - PropertyNode {source_node.name} trovato nel gruppo (ID: {group.name})")
            
            stats["property_nodes_found"] += len(property_nodes)
            
            # Se non ci sono PropertyNode nel gruppo, passa al prossimo
            if not property_nodes:
                if verbose:
                    print(f"  Nessun PropertyNode trovato nel gruppo {group.name}")
                continue
            
            # Trova le unità stratigrafiche collegate al ParadataNodeGroup
            stratigraphic_nodes = []
            
            # Cerchiamo prima con edge_type "has_paradata_nodegroup"
            for edge in self.edges:
                if edge.edge_target == group.node_id and edge.edge_type == "has_paradata_nodegroup":
                    source_node = self.find_node_by_id(edge.edge_source)
                    #print(f"  - Trovato stronzo edge {edge.edge_id} con source {edge.edge_source} e target {edge.edge_target}")
                    if source_node and hasattr(source_node, 'node_type'):
                        if source_node.node_type in stratigraphic_types:
                            stratigraphic_nodes.append(source_node)
                            if verbose:
                                print(f"  - Unità stratigrafica collegata al gruppo: {source_node.name} (Tipo: {source_node.node_type})")
            
            # Se non troviamo nulla, proviamo con edge_type "generic_connection"
            if not stratigraphic_nodes:
                for edge in self.edges:
                    if edge.edge_target == group.node_id and edge.edge_type == "generic_connection":
                        source_node = self.find_node_by_id(edge.edge_source)
                        if source_node and hasattr(source_node, 'node_type'):
                            if source_node.node_type in stratigraphic_types:
                                stratigraphic_nodes.append(source_node)
                                if verbose:
                                    print(f"  - Unità stratigrafica collegata al gruppo (generic_connection): {source_node.name} (Tipo: {source_node.node_type})")
            
            stats["stratigraphic_nodes_found"] += len(stratigraphic_nodes)
            
            # Se non ci sono unità stratigrafiche collegate al gruppo, passa al prossimo
            if not stratigraphic_nodes:
                if verbose:
                    print(f"  Nessuna unità stratigrafica collegata al gruppo {group.name}")
                continue
            
            # Crea collegamenti diretti tra le unità stratigrafiche e i PropertyNode
            for strat_node in stratigraphic_nodes:
                for prop_node in property_nodes:
                    # Verifica se esiste già un collegamento diretto
                    existing_edge = None
                    for edge in self.edges:
                        if (edge.edge_source == strat_node.node_id and 
                            edge.edge_target == prop_node.node_id and 
                            edge.edge_type == "has_property"):
                            existing_edge = edge
                            break
                    
                    if existing_edge:
                        stats["connections_already_existing"] += 1
                        if verbose:
                            print(f"  Collegamento già esistente: {strat_node.name} -> {prop_node.name}")
                    else:
                        # Crea un nuovo edge per collegare direttamente
                        edge_id = f"{strat_node.node_id}_has_property_{prop_node.node_id}"
                        try:
                            new_edge = self.add_edge(edge_id, strat_node.node_id, prop_node.node_id, "has_property")
                            stats["connections_created"] += 1
                            if verbose:
                                print(f"  ✅ Nuovo collegamento creato: {strat_node.name} -> {prop_node.name}")
                        except Exception as e:
                            stats["errors"] += 1
                            if verbose:
                                print(f"  ❌ Errore nella creazione del collegamento: {str(e)}")
        
        if verbose:
            print("\n=== Statistiche dell'operazione ===")
            print(f"Gruppi ParadataNodeGroup trovati: {stats['paradata_groups_found']}")
            print(f"PropertyNode trovati nei gruppi: {stats['property_nodes_found']}")
            print(f"Unità stratigrafiche collegate ai gruppi: {stats['stratigraphic_nodes_found']}")
            print(f"Nuovi collegamenti creati: {stats['connections_created']}")
            print(f"Collegamenti già esistenti: {stats['connections_already_existing']}")
            print(f"Errori: {stats['errors']}")
            print("=== Completata la connessione PropertyNode dai ParadataNodeGroup ===")
        
        return stats



    def display_warnings(self):
        """Displays all accumulated warning messages."""
        for warning in self.warnings:
            #print("Warning:", warning)
            pass

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
                #print("Ho trovato un edge corretto per il mio nodo")
                target_node = self.find_node_by_id(edge.edge_target)
                if target_node and target_node.node_type == "epoch":
                    #print(f"Found connected EpochNode '{target_node.node_id}' via edge type '{edge_type}'.")
                    return target_node
                else:
                    print(f"NOT found any epochnode for {node.name} con id {node.node_id}")
            elif (edge.edge_target == node.node_id and edge.edge_type == edge_type):
                source_node = self.find_node_by_id(edge.edge_source)
                if source_node and source_node.node_type == "epoch":
                    #print(f"Found connected EpochNode '{source_node.node_id}' via edge type '{edge_type}'.")
                    return source_node
                else:
                    print(f"NOT found any epochnode for {node.name} con id {node.id}")
            
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

    def print_node_connections(self, node):

        print(f"Node: {node.name}, Type: {node.node_type}")
        print("Connections:")

        for edge in self.edges:
            if edge.edge_source == node.node_id:
                target_node = self.find_node_by_id(edge.edge_target)
                if target_node:
                    print(f"  Connection Type: {edge.edge_type} ({edge.label})")
                    print(f"    - Target Node: {target_node.name}, Type: {target_node.node_type}")
            elif edge.edge_target == node.node_id:
                source_node = self.find_node_by_id(edge.edge_source)
                if source_node:
                    print(f"  Connection Type: {edge.edge_type} ({edge.label})")
                    print(f"    - Source Node: {source_node.name}, Type: {source_node.node_type}")


    def get_connected_nodes_by_filters(self, node, target_node_type="all", edge_type="all"):
        """
        Ottiene una lista di nodi collegati in base ai filtri specificati su target_node_type ed edge_type.

        Args:
            node (Node): Nodo di partenza.
            target_node_type (str): Tipo di nodo target da cercare ("all" per nessun filtro).
            edge_type (str): Tipo di edge da cercare ("all" per nessun filtro).

        Returns:
            list[Node]: Lista di nodi collegati che soddisfano i criteri specificati.
        """
        connected_nodes = []

        for edge in self.edges:
            # Filtra per edge_type se specificato
            if edge_type != "all" and edge.edge_type != edge_type:
                continue

            # Verifica se il nodo di partenza è source o target dell'edge
            if edge.edge_source == node.node_id:
                target_node = self.find_node_by_id(edge.edge_target)
                # Filtra per target_node_type se specificato
                if target_node and (target_node_type == "all" or target_node.node_type == target_node_type):
                    connected_nodes.append(target_node)
            elif edge.edge_target == node.node_id:
                source_node = self.find_node_by_id(edge.edge_source)
                # Filtra per target_node_type se specificato
                if source_node and (target_node_type == "all" or source_node.node_type == target_node_type):
                    connected_nodes.append(source_node)

        return connected_nodes


    def get_connected_nodes_by_edge_type(self, node_id, edge_type):
        """
        Ottiene tutti i nodi connessi a un nodo specifico tramite un tipo di edge.
        
        Args:
            node_id (str): ID del nodo di partenza
            edge_type (str): Tipo di edge da filtrare
            
        Returns:
            list: Lista di nodi connessi attraverso il tipo di edge specificato
        """
        connected_nodes = []
        
        for edge in self.edges:
            if edge.edge_type == edge_type:
                if edge.edge_source == node_id:
                    target_node = self.find_node_by_id(edge.edge_target)
                    if target_node:
                        connected_nodes.append(target_node)
                elif edge.edge_target == node_id:
                    source_node = self.find_node_by_id(edge.edge_source)
                    if source_node:
                        connected_nodes.append(source_node)
        
        return connected_nodes

    def get_property_nodes_for_node(self, node_id):
        """
        Ottiene tutti i nodi proprietà connessi a un nodo specifico.
        
        Args:
            node_id (str): ID del nodo di partenza
            
        Returns:
            list: Lista di nodi proprietà connessi
        """
        #return [node for node in self.get_connected_nodes_by_edge_type(node_id, "has_property") 
        #        if node.node_type == "property"]

        return [node for node in self.get_connected_nodes_by_edge_type(node_id, "has_property") 
                if node.node_type == "property"]


    def get_combiner_nodes_for_property(self, property_node_id):
        """
        Ottiene tutti i nodi combiner connessi a un nodo proprietà.
        
        Args:
            property_node_id (str): ID del nodo proprietà
            
        Returns:
            list: Lista di nodi combiner connessi
        """
        combiners = []
        
        for edge in self.edges:
            if edge.edge_source == property_node_id:
                target_node = self.find_node_by_id(edge.edge_target)
                if target_node and target_node.node_type == "combiner":
                    combiners.append(target_node)
        
        return combiners

    def get_extractor_nodes_for_node(self, node_id):
        """
        Ottiene tutti i nodi extractor connessi a un nodo (proprietà o combiner).
        
        Args:
            node_id (str): ID del nodo di partenza
            
        Returns:
            list: Lista di nodi extractor connessi
        """
        extractors = []
        node = self.find_node_by_id(node_id)
        print(f"\nCercando estrattori per nodo: {node_id} (tipo: {node.node_type if node else 'sconosciuto'})")
        
        # Lista di edge types da considerare
        edge_types = ["has_data_provenance", "extracted_from", "combines", "generic_connection"]
        
        # Check per estrattori che sono source delle relazioni (estrattore -> nodo)
        for edge in self.edges:
            if edge.edge_source in edge_types and edge.edge_target == node_id:
                source_node = self.find_node_by_id(edge.edge_source)
                if source_node and source_node.node_type == "extractor":
                    extractors.append(source_node)
                    print(f"  Trovato estrattore (source): {source_node.name} (edge: {edge.edge_type})")
        
        # Check per estrattori che sono target delle relazioni (nodo -> estrattore)
        for edge in self.edges:
            if edge.edge_type in edge_types and edge.edge_source == node_id:
                target_node = self.find_node_by_id(edge.edge_target)
                if target_node and target_node.node_type == "extractor":
                    extractors.append(target_node)
                    print(f"  Trovato estrattore (target): {target_node.name} (edge: {edge.edge_type})")
        
        # Verifica le relazioni inverse (estrattore è source e questo nodo è target)
        for edge in self.edges:
            if edge.edge_target == node_id:
                source_node = self.find_node_by_id(edge.edge_source)
                if source_node and source_node.node_type == "extractor":
                    extractors.append(source_node)
                    print(f"  Trovato estrattore (rel inverse): {source_node.name} (edge: {edge.edge_type})")
        
        # Nel caso specifico dei combiner, verifica anche relazioni di tipo "combines"
        node = self.find_node_by_id(node_id)
        if node and node.node_type == "combiner":
            # Se questo è un combiner, cerca estrattori che ha combinato
            print(f"  Verifico relazioni speciali per combiner: {node.name}")
            
            # Verifica attributo sources se il nodo è un combiner
            if hasattr(node, 'sources'):
                for source_id in node.sources:
                    source_node = self.find_node_by_id(source_id)
                    if source_node and source_node.node_type == "extractor":
                        extractors.append(source_node)
                        print(f"  Trovato estrattore da sources: {source_node.name}")
        
        # Rimuovi duplicati
        unique_extractors = []
        seen = set()
        for extractor in extractors:
            if extractor.node_id not in seen:
                seen.add(extractor.node_id)
                unique_extractors.append(extractor)
        
        print(f"  Totale estrattori trovati: {len(unique_extractors)}")
        return unique_extractors
    
    def get_document_nodes_for_extractor(self, extractor_node_id):
        """
        Ottiene tutti i nodi documento connessi a un nodo extractor.
        
        Args:
            extractor_node_id (str): ID del nodo extractor
            
        Returns:
            list: Lista di nodi documento connessi
        """
        documents = []
        
        extractor = self.find_node_by_id(extractor_node_id)
        print(f"Cercando documenti per estrattore: {extractor_node_id} (tipo: {extractor.node_type if extractor else 'sconosciuto'})")
        print(f"Numero totale di edges: {len(self.edges)}")
        
        # Verifica tutti i tipi di edge possibili
        edge_types = ["extracted_from", "has_data_provenance", "generic_connection"]
        
        # Cerca relazioni (estrattore -> documento)
        for edge in self.edges:
            if edge.edge_type in edge_types and edge.edge_source == extractor_node_id:
                target_node = self.find_node_by_id(edge.edge_target)
                if target_node and target_node.node_type == "document":
                    documents.append(target_node)
                    print(f"  Trovato documento (target): {target_node.name} (edge: {edge.edge_type})")
        
        # Cerca relazioni (documento -> estrattore)
        for edge in self.edges:
            if edge.edge_type in edge_types and edge.edge_target == extractor_node_id:
                source_node = self.find_node_by_id(edge.edge_source)
                if source_node and source_node.node_type == "document":
                    documents.append(source_node)
                    print(f"  Trovato documento (source): {source_node.name} (edge: {edge.edge_type})")
        
        # Rimuovi duplicati
        unique_documents = []
        seen = set()
        for doc in documents:
            if doc.node_id not in seen:
                seen.add(doc.node_id)
                unique_documents.append(doc)
        
        print(f"  Totale documenti trovati: {len(unique_documents)}")
        return unique_documents

    def get_paradata_chain(self, strat_node_id):
        """
        Ottiene la catena completa di paradata per un nodo stratigrafico.
        
        Args:
            strat_node_id (str): ID del nodo stratigrafico
            
        Returns:
            dict: Dizionario con le catene di paradata strutturate
        """
        result = {
            "properties": [],
            "combiners": [],
            "extractors": [],
            "documents": []
        }
        
        # Ottieni le proprietà
        properties = self.get_property_nodes_for_node(strat_node_id)
        result["properties"] = properties
        
        # Per ogni proprietà, ottieni combiners ed extractors
        for prop in properties:
            combiners = self.get_combiner_nodes_for_property(prop.node_id)
            extractors = self.get_extractor_nodes_for_node(prop.node_id)
            
            result["combiners"].extend(combiners)
            result["extractors"].extend(extractors)
            
            # Per ogni combiner, ottieni extractors
            for combiner in combiners:
                comb_extractors = self.get_extractor_nodes_for_node(combiner.node_id)
                result["extractors"].extend(comb_extractors)
            
            # Per ogni extractor, ottieni documents
            for extractor in extractors + [ext for comb in combiners for ext in self.get_extractor_nodes_for_node(comb.node_id)]:
                documents = self.get_document_nodes_for_extractor(extractor.node_id)
                result["documents"].extend(documents)
        
        # Rimuovi duplicati (preservando l'ordine)
        for key in result:
            seen = set()
            result[key] = [x for x in result[key] if not (x.node_id in seen or seen.add(x.node_id))]
        
        return result


'''
Esempio di utilizzo:
graph = get_graph()  # Ottieni il grafo caricato
graph.calculate_chronology()  # Calcola la cronologia

# Filtra i nodi in un intervallo di tempo specifico
filtered_nodes = graph.filter_nodes_by_time_range(50, 100)
for node in filtered_nodes:
    print(f"Node {node.node_id}: Start = {node.attributes.get('CALCUL_START_T')}, End = {node.attributes.get('CALCUL_END_T')}")
'''