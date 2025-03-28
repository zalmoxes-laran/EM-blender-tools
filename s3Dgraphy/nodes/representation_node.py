from .base_node import Node
from typing import Dict, Any, List, Optional, Union

class RepresentationNode(Node):
    """
    Base class for all representation nodes in 3D space.
    
    This class provides common functionality for RepresentationModelNode,
    RepresentationModelDocNode, and RepresentationModelSpecialFindNode.
    
    Attributes:
        node_type (str): Type of node, set by child classes
        type (str): The type of representation (e.g. "RM", "spatialized_image", "generic")
        transform (dict): Transformation data for positioning in 3D space
    """
    
    node_type = "representation_node"
    
    def __init__(self, 
                 node_id: str,
                 name: str,
                 type: str = "generic",
                 transform: Optional[Dict[str, List[str]]] = None,
                 description: str = ""):
        """
        Initialize a new RepresentationNode.
        
        Args:
            node_id (str): Unique identifier for the node
            name (str): Name of the representation
            type (str): Type of representation
            transform (Dict[str, List[str]], optional): Transformation data with position, rotation, and scale
            description (str): Description of the representation
        """
        super().__init__(node_id=node_id, name=name, description=description)
        
        self.type = type
        
        # Initialize transform with default values if not provided
        if transform is None:
            self.transform = {
                "position": ["0.0", "0.0", "0.0"],
                "rotation": ["0.0", "0.0", "0.0"],
                "scale": ["1.0", "1.0", "1.0"]
            }
        else:
            self.transform = transform
        
        # Structure data for serialization
        self.data = {
            "transform": self.transform
        }
    
    def set_transform(self, 
                     position: Optional[List[str]] = None, 
                     rotation: Optional[List[str]] = None, 
                     scale: Optional[List[str]] = None) -> None:
        """
        Set the transformation parameters.
        
        Args:
            position (List[str], optional): Position [x, y, z] as strings
            rotation (List[str], optional): Rotation [x, y, z] in radians as strings
            scale (List[str], optional): Scale [x, y, z] as strings
        """
        if position:
            self.transform["position"] = position
        if rotation:
            self.transform["rotation"] = rotation
        if scale:
            self.transform["scale"] = scale
            
        self.data["transform"] = self.transform
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the node to a dictionary for JSON serialization.
        
        Returns:
            Dict[str, Any]: Dictionary representation of the node
        """
        return {
            self.node_id: {
                "type": self.type,
                "name": self.name,
                "description": self.description,
                "data": self.data
            }
        }


class RepresentationModelNode(RepresentationNode):
    """
    Node representing a 3D model or spatialized image.
    
    This class is used for general 3D models associated with stratigraphic units.
    
    Attributes:
        node_type (str): Type of node, set to "representation_model"
    """
    
    node_type = "representation_model"
    
    # Valid types of representation
    VALID_TYPES = {
        "RM": "Representation Model - 3D Model",
        "spatialized_image": "Spatialized Image",
        "generic": "Generic Representation"
    }
    
    def __init__(self, 
                 node_id: str,
                 name: str,
                 type: str = "RM",
                 transform: Optional[Dict[str, List[str]]] = None,
                 description: str = ""):
        """
        Initialize a new RepresentationModelNode.
        
        Args:
            node_id (str): Unique identifier for the node
            name (str): Name of the model
            type (str): Type of representation ("RM", "spatialized_image", or "generic")
            transform (Dict[str, List[str]], optional): Transformation data
            description (str): Description of the model
            
        Raises:
            ValueError: If the type is not valid
        """
        if type not in self.VALID_TYPES:
            raise ValueError(f"type must be one of: {list(self.VALID_TYPES.keys())}")
        
        super().__init__(
            node_id=node_id, 
            name=name, 
            type=type, 
            transform=transform,
            description=description
        )


class RepresentationModelDocNode(RepresentationNode):
    """
    Node representing a 3D model or spatialized image for documents.
    
    This class is used to instantiate documents, extractors or combiner nodes
    within the scene. An example is a historical photo positioned in its original position.
    
    Attributes:
        node_type (str): Type of node, set to "representation_model_doc"
    """
    
    node_type = "representation_model_doc"
    
    # Valid types of representation
    VALID_TYPES = {
        "RM": "Representation Model - 3D Model",
        "spatialized_image": "Spatialized Image",
        "generic": "Generic Representation"
    }
    
    def __init__(self, 
                 node_id: str,
                 name: str,
                 type: str = "spatialized_image",
                 transform: Optional[Dict[str, List[str]]] = None,
                 description: str = ""):
        """
        Initialize a new RepresentationModelDocNode.
        
        Args:
            node_id (str): Unique identifier for the node
            name (str): Name of the model
            type (str): Type of representation ("RM", "spatialized_image", or "generic")
            transform (Dict[str, List[str]], optional): Transformation data
            description (str): Description of the model
            
        Raises:
            ValueError: If the type is not valid
        """
        if type not in self.VALID_TYPES:
            raise ValueError(f"type must be one of: {list(self.VALID_TYPES.keys())}")
        
        super().__init__(
            node_id=node_id, 
            name=name, 
            type=type, 
            transform=transform,
            description=description
        )


class RepresentationModelSpecialFindNode(RepresentationNode):
    """
    Node representing a 3D model for special finds.
    
    This class is used to instantiate special finds in the scene. An example is
    a scanned 3D model of a capital repositioned in its original position
    according to an anastylosis hypothesis.
    
    Attributes:
        node_type (str): Type of node, set to "representation_model_sf"
    """
    
    node_type = "representation_model_sf"
    
    # Valid types of representation
    VALID_TYPES = {
        "RM": "Representation Model - 3D Model",
        "spatialized_image": "Spatialized Image",
        "generic": "Generic Representation"
    }
    
    def __init__(self, 
                 node_id: str,
                 name: str,
                 type: str = "RM",
                 transform: Optional[Dict[str, List[str]]] = None,
                 description: str = ""):
        """
        Initialize a new RepresentationModelSpecialFindNode.
        
        Args:
            node_id (str): Unique identifier for the node
            name (str): Name of the model
            type (str): Type of representation ("RM", "spatialized_image", or "generic")
            transform (Dict[str, List[str]], optional): Transformation data
            description (str): Description of the model
            
        Raises:
            ValueError: If the type is not valid
        """
        if type not in self.VALID_TYPES:
            raise ValueError(f"type must be one of: {list(self.VALID_TYPES.keys())}")
        
        super().__init__(
            node_id=node_id, 
            name=name, 
            type=type, 
            transform=transform,
            description=description
        )
