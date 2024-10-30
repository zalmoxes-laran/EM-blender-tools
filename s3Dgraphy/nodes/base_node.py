# 3dgraphy/nodes/base_node.py

import json
import os

def load_json_mapping(filename):
    """
    Load JSON mapping data from a specified file.

    Args:
        filename (str): Name of the JSON file containing mapping data.

    Returns:
        dict: Mapping data loaded from the JSON file.
    """
    # Construct the absolute path
    mapping_path = os.path.join(os.path.dirname(__file__), '..', 'JSON_config', filename)
    mapping_path = os.path.abspath(mapping_path)

    try:
        with open(mapping_path, 'r') as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading mapping file: {e}")
        return {}

class Node:
    """
    Base class to represent a node in the graph with CIDOC mapping.

    Attributes:
        node_id (str): Unique identifier for the node.
        name (str): Name of the node.
        node_type (str): Type of the node.
        description (str): Description of the node.
        attributes (dict): Dictionary for additional attributes.
        mapping (dict): CIDOC mapping data specific to the node type.
    """

    def __init__(self, node_id, name, node_type, description=""):
        self.node_id = node_id
        self.name = name
        self.node_type = node_type
        self.description = description
        self.attributes = {}
        self.mapping = self.load_mapping()

    def add_attribute(self, key, value):
        self.attributes[key] = value

    def load_mapping(self):
        """
        Loads the CIDOC mapping specific to the node type.

        Returns:
            dict: CIDOC mapping data if found, else an empty dictionary.
        """
        mappings = load_json_mapping('em_cidoc_mapping.json')
        return mappings.get(self.node_type, {})
