from .node import Node

class RepresentationModelNode(Node):
    """
    Node to represent 3D representation models associated with EpochNode and StratigraphicNode.

    Attributes:
        model_type (str): Format of the 3D model, default is "gltf".
        data (dict): Specific data for the representation model, including ID, name, description, and link.
    """
    
    def __init__(self, node_id, name="Representation Model", model_type="gltf", description="", url=""):
        """
        Initialize a new instance of RepresentationModelNode.

        Args:
            node_id (str): Unique identifier for the node.
            name (str, optional): Name of the representation model. Defaults to "Representation Model".
            model_type (str, optional): Format of the 3D model (e.g., gltf). Defaults to "gltf".
            description (str, optional): Description of the model. Defaults to an empty string.
            url (str, optional): URL link to the model. Defaults to an empty string.
        """
        super().__init__(node_id=node_id, name=name, node_type="representation_model")
        self.data = {
            "model_type": model_type,
            "description": description,
            "url": url
        }
    
    def to_dict(self):
        """
        Convert the RepresentationModelNode instance to a dictionary.

        Returns:
            dict: Dictionary representation of the node.
        """
        return {
            "type": self.node_type,
            "id": self.node_id,
            "name": self.name,
            "data": self.data
        }

    def link_to_epoch_or_stratigraphic(self, target_node, edge_type="generic_line"):
        """
        Establish a connection from this RepresentationModelNode to an EpochNode or StratigraphicNode.
        
        This connection can be used to apply properties from the representation model to the connected
        stratigraphic elements or epochs during parsing or data processing.

        Args:
            target_node (Node): The target EpochNode or StratigraphicNode to connect to.
            edge_type (str, optional): Type of edge for the connection. Defaults to "generic_line".
        """
        if target_node.node_type in ["epoch", "stratigraphic"]:
            # Assuming add_edge function exists in the Graph class to create edges
            self.graph.add_edge(
                edge_id=f"{self.node_id}_to_{target_node.node_id}",
                edge_source=self.node_id,
                edge_target=target_node.node_id,
                edge_type=edge_type
            )
        else:
            raise ValueError("Target node must be of type 'epoch' or 'stratigraphic'")


'''
# Creazione del grafo
graph = Graph(graph_id="example_graph")

# Creazione dei nodi StratigraphicNode e EpochNode
stratigraphic_node = StratigraphicNode(node_id="SN1", name="Stratigraphic Layer 1", stratigraphic_type="US")
epoch_node = EpochNode(node_id="E1", name="Epoch Example", start_time=-500, end_time=1000)

# Aggiunta dei nodi al grafo
graph.add_node(stratigraphic_node)
graph.add_node(epoch_node)

# Creazione di un RepresentationModelNode
representation_model = RepresentationModelNode(
    node_id="RM1",
    name="House Model",
    model_type="gltf",
    description="3D model of an ancient house",
    url="http://example.com/house_model.gltf"
)

# Aggiunta del RepresentationModelNode al grafo
graph.add_node(representation_model)

# Collegamento del RepresentationModelNode al StratigraphicNode e all'EpochNode
representation_model.link_to_epoch_or_stratigraphic(target_node=stratigraphic_node)
representation_model.link_to_epoch_or_stratigraphic(target_node=epoch_node)

# Visualizzazione del risultato
print("Representation Model Node:", representation_model.to_dict())
print("Stratigraphic Node connections:", graph.get_connected_edges(stratigraphic_node.node_id))
print("Epoch Node connections:", graph.get_connected_edges(epoch_node.node_id))
'''