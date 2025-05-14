EDGE_TYPES = {
    "is_before": {
        "label": "Chronological Sequence",
        "description": "Indicates a temporal sequence where one item occurs before another."
    },
    "has_linked_resource": {
        "label": "Has Link",
        "description": "Connects a node to its linked resource(s)"
    },
    "has_same_time": {
        "label": "Contemporaneous Elements",
        "description": "Indicates that two elements are contemporaneous."
    },
    "changed_from": {
        "label": "Temporal Transformation",
        "description": "Represents an object that changes over time."
    },
    "has_data_provenance": {
        "label": "Data Provenance",
        "description": "Indicates the provenance of data, often linking to source nodes."
    },
    "contrasts_with": {
        "label": "Contrasting Properties",
        "description": "Represents contrasting or mutually exclusive properties."
    },
    "has_first_epoch": {
        "label": "Has First Epoch",
        "description": "Indicates the initial epoch associated with a node."
    },
    "survive_in_epoch": {
        "label": "Survives In Epoch",
        "description": "Indicates that a node continues to exist in a given epoch."
    },
    "is_in_activity": {
        "label": "Part of Activity",
        "description": "Indicates that a node is part of a specific activity."
    },
    "has_property": {
        "label": "Has Property",
        "description": "Connects a node to one of its properties."
    },
    "extracted_from": {
        "label": "Extracted From",
        "description": "Indicates that information is derived from a particular source."
    },
    "combines": {
        "label": "Combines",
        "description": "Indicates that a node combines information from various sources."
    },
    "has_timebranch": {
        "label": "Connected to a Timebranch",
        "description": "Indicates that a node is connected to a specific time branch."
    },
    "is_in_timebranch": {
        "label": "Included in Timebranch",
        "description": "Indicates that a node belongs to a specific time branch."
    },    
    "generic_connection": {
        "label": "Generic Connection",
        "description": "Represents a non-specific connection between two nodes."
    },
    "has_semantic_shape": {
        "label": "Has Semantic Shape",
        "description": "Connects any node to its semantic shape representation in 3D space."
    },
    "has_representation_model": {
        "label": "Has Representation Model",
        "description": "Connects any node to its representation model in 3D space."
    },

    "is_in_paradata_nodegroup": {
        "label": "Belongs to a Paradata Node Group",
        "description": "Indicates that a node is included into a paradata node group."
    },
    "has_paradata_nodegroup": {
        "label": "Is connected to a Paradata Node Group",
        "description": "Indicates that a node belongs to a paradata node group."
    },
    "has_license": {
        "label": "Has License",
        "description": "Indicates that a resource is subject to a specific licence."
    },

    "has_embargo": {
        "label": "Has Embargo",
        "description": "Indicates that a licence has an associated time embargo."
    }
}

class Edge:
    """
    Represents an edge in the graph, connecting two nodes with a specific relationship type.
    
    Attributes:
        edge_id (str): Unique identifier for the edge.
        edge_source (str): ID of the source node.
        edge_target (str): ID of the target node.
        edge_type (str): Semantic type of the relationship.
        label (str): A descriptive label for the relationship type.
        description (str): A detailed description of the relationship type.
    """

    def __init__(self, edge_id, edge_source, edge_target, edge_type):
        if edge_type not in EDGE_TYPES:
            raise ValueError(f"Edge type '{edge_type}' is not a recognized relationship type.")
        
        self.edge_id = edge_id
        self.edge_source = edge_source
        self.edge_target = edge_target
        self.edge_type = edge_type
        self.label = EDGE_TYPES[edge_type]["label"]
        self.description = EDGE_TYPES[edge_type]["description"]

        self.attributes = {}


    def to_dict(self):
        """
        Converts the Edge instance to a dictionary format.

        Returns:
            dict: A dictionary representation of the edge, including its attributes.
        """
        return {
            "edge_id": self.edge_id,
            "source": self.edge_source,
            "target": self.edge_target,
            "type": self.edge_type,
            "label": self.label,
            "description": self.description
        }

    def __repr__(self):
        """
        Returns a string representation of the Edge instance.

        Returns:
            str: A string representation of the edge, showing its source, target, and type.
        """
        return f"Edge({self.edge_id}, {self.edge_source} -> {self.edge_target}, {self.edge_type})"
