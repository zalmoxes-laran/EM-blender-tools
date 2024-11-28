# s3Dgraphy/importer/base_importer.py

"""
Base class for all data importers in s3Dgraphy.
"""

from abc import ABC, abstractmethod
import json
import os
from typing import Dict, Any
from ..graph import Graph
from ..nodes.base_node import Node
from ..nodes.property_node import PropertyNode
from ..edges import Edge
from ..utils.utils import get_stratigraphic_node_class

class BaseImporter(ABC):
    """
    Abstract base class for all importers.
    Provides common functionality for loading mappings and processing data.
    """
    def __init__(self, filepath: str, mapping_name: str = None, overwrite: bool = False):
        """
        Initialize the importer.
        
        Args:
            filepath (str): Path to the file to import
            mapping_name (str, optional): Name of the mapping configuration to use
            overwrite (bool, optional): If True, overwrites existing property values.
                                      If False, skips existing properties. Defaults to False.
        """
        self.filepath = filepath
        self.mapping = self._load_mapping(mapping_name) if mapping_name else None
        self.graph = Graph(graph_id=f"imported_{os.path.splitext(os.path.basename(filepath))[0]}")
        self.warnings = []
        self.overwrite = overwrite

    def _load_mapping(self, mapping_name: str) -> Dict[str, Any]:
        """
        Load the JSON mapping file from the JSONmappings directory.
        
        Args:
            mapping_name (str): Name of the mapping file (without .json extension)
            
        Returns:
            dict: The mapping configuration
            
        Raises:
            FileNotFoundError: If the mapping file doesn't exist
        """
        mapping_path = os.path.join(
            os.path.dirname(__file__), 
            'JSONmappings', 
            f'{mapping_name}.json'
        )
        try:
            with open(mapping_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"Mapping file {mapping_name}.json not found in JSONmappings directory")
        except json.JSONDecodeError as e:
            raise ValueError(f"Error parsing mapping file: {str(e)}")

    @abstractmethod
    def parse(self) -> Graph:
        """
        Parse the input file and create nodes/edges in the graph.
        Must be implemented by each specific importer.
        
        Returns:
            Graph: The populated graph object
        """
        pass

    def process_row(self, row_data: Dict[str, Any]) -> Node:
        """
        Process a single row of data using the mapping configuration.
        
        Args:
            row_data (dict): Dictionary containing the row data
            
        Returns:
            Node: The created or updated stratigraphic node
            
        Raises:
            KeyError: If required columns are missing
        """
        try:
            # Extract base attributes using mapping
            base_attrs = {
                'node_id': str(row_data[self.mapping['id_column']]),
                'name': str(row_data[self.mapping['name_column']]),
                'description': str(row_data.get(self.mapping['description_column'], ''))
            }

            # Get the stratigraphic type from mapping
            strat_type = self.mapping.get('stratigraphic_type', 'US')

            # Get the appropriate node class based on stratigraphic type
            node_class = get_stratigraphic_node_class(strat_type)

            # Check if node already exists
            existing_node = self.graph.find_node_by_id(base_attrs['node_id'])
            
            if existing_node:
                # Update existing node if overwrite is True
                if self.overwrite:
                    existing_node.name = base_attrs['name']
                    existing_node.description = base_attrs['description']
                    self.warnings.append(f"Updated existing node: {base_attrs['node_id']}")
                strat_node = existing_node
            else:
                # Create new stratigraphic node using appropriate class
                strat_node = node_class(
                    node_id=base_attrs['node_id'],
                    name=base_attrs['name'],
                    description=base_attrs['description']
                )
                self.graph.add_node(strat_node)

            # Process property columns
            if 'property_columns' in self.mapping:
                self._process_properties(row_data, base_attrs['node_id'], strat_node)

            return strat_node

        except KeyError as e:
            self.warnings.append(f"Missing required column: {str(e)}")
            raise

    def _process_properties(self, row_data: Dict[str, Any], base_id: str, strat_node: Node):
        """
        Process property columns and create or update property nodes.
        
        Args:
            row_data (dict): Dictionary containing the row data
            base_id (str): ID of the stratigraphic node
            strat_node (Node): The stratigraphic node to connect properties to
        """
        for col_name, prop_config in self.mapping['property_columns'].items():
            if col_name in row_data and row_data[col_name]:
                prop_id = f"{base_id}_{col_name}"
                
                # Check if property already exists
                existing_prop = self.graph.find_node_by_id(prop_id)
                
                if existing_prop:
                    if self.overwrite:
                        # Update existing property
                        existing_prop.value = row_data[col_name]
                        existing_prop.name = prop_config.get('display_name', col_name)
                        existing_prop.property_type = prop_config.get('property_type', 'string')
                        existing_prop.description = prop_config.get('description', '')
                        self.warnings.append(f"Updated existing property: {prop_id}")
                else:
                    # Create new property node
                    prop_node = PropertyNode(
                        node_id=prop_id,
                        name=prop_config.get('display_name', col_name),
                        property_type=prop_config.get('property_type', 'string'),
                        description=prop_config.get('description', ''),
                        value=row_data[col_name]
                    )
                    self.graph.add_node(prop_node)

                    # Create edge between stratigraphic node and property node
                    edge = Edge(
                        edge_id=f"{base_id}_{col_name}_edge",
                        edge_source=strat_node.node_id,
                        edge_target=prop_node.node_id,
                        edge_type="has_property"
                    )
                    self.graph.add_edge(edge)

    def display_warnings(self):
        """Display all accumulated warnings."""
        if self.warnings:
            print("\nWarnings during import:")
            for warning in self.warnings:
                print(f"- {warning}")