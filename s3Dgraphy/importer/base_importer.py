# s3Dgraphy/importer/base_importer.py

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
    Supports both mapped and automatic property creation modes.
    """
    def __init__(self, filepath: str, mapping_name: str = None, id_column: str = None, overwrite: bool = False):
        """
        Initialize the importer.
        
        Args:
            filepath (str): Path to the file to import
            mapping_name (str, optional): Name of the mapping configuration to use
            id_column (str, optional): Name of the ID column when not using mapping
            overwrite (bool, optional): If True, overwrites existing property values
            
        Raises:
            ValueError: If neither mapping_name nor id_column is provided
        """
        if mapping_name is None and id_column is None:
            raise ValueError("Either mapping_name or id_column must be provided")
            
        self.filepath = filepath
        self.id_column = id_column
        self.mapping = self._load_mapping(mapping_name) if mapping_name else None
        self.graph = Graph(graph_id=f"imported_{os.path.splitext(os.path.basename(filepath))[0]}")
        self.warnings = []
        self.overwrite = overwrite
        self.automatic_mode = mapping_name is None

    def _load_mapping(self, mapping_name: str) -> Dict[str, Any]:
        """Load the JSON mapping file from the JSONmappings directory."""
        if mapping_name is None:
            return None
            
        mapping_path = os.path.join(
            os.path.dirname(__file__), 
            'JSONmappings', 
            f'{mapping_name}.json'
        )
        try:
            with open(mapping_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"Mapping file {mapping_name}.json not found")
        except json.JSONDecodeError as e:
            raise ValueError(f"Error parsing mapping file: {str(e)}")

    @abstractmethod
    def parse(self) -> Graph:
        """Parse the input file and create nodes/edges in the graph."""
        pass

    def process_row(self, row_data: Dict[str, Any]) -> Node:
        """Process a row using either mapping or automatic mode."""
        try:
            if self.mapping:
                return self._process_row_with_mapping(row_data)
            else:
                return self._process_row_automatic(row_data)
        except KeyError as e:
            self.warnings.append(f"Missing required column: {str(e)}")
            raise

    def _process_row_with_mapping(self, row_data: Dict[str, Any]) -> Node:
        """Process a row using the mapping configuration."""
        base_attrs = {
            'node_id': str(row_data[self.mapping['id_column']]),
            'name': str(row_data[self.mapping['name_column']]),
            'description': str(row_data.get(self.mapping['description_column'], ''))
        }

        strat_type = self.mapping.get('stratigraphic_type', 'US')
        node_class = get_stratigraphic_node_class(strat_type)
        
        existing_node = self.graph.find_node_by_id(base_attrs['node_id'])
        
        if existing_node:
            if self.overwrite:
                existing_node.name = base_attrs['name']
                existing_node.description = base_attrs['description']
                self.warnings.append(f"Updated existing node: {base_attrs['node_id']}")
            strat_node = existing_node
        else:
            strat_node = node_class(
                node_id=base_attrs['node_id'],
                name=base_attrs['name'],
                description=base_attrs['description']
            )
            self.graph.add_node(strat_node)

        if 'property_columns' in self.mapping:
            self._process_properties(row_data, base_attrs['node_id'], strat_node)

        return strat_node

    def _process_row_automatic(self, row_data: Dict[str, Any]) -> Node:
        """Process a row creating properties for all non-ID columns."""
        try:
            node_id = str(row_data[self.id_column])
        except KeyError:
            raise KeyError(f"ID column '{self.id_column}' not found in data")

        # Get basic node attributes from data or use defaults
        name = str(row_data.get('name', node_id))
        description = str(row_data.get('description', ''))

        existing_node = self.graph.find_node_by_id(node_id)
        
        if existing_node:
            if self.overwrite:
                existing_node.name = name
                existing_node.description = description
                self.warnings.append(f"Updated existing node: {node_id}")
            strat_node = existing_node
        else:
            # Create new node (default to US type in automatic mode)
            strat_node = get_stratigraphic_node_class('US')(
                node_id=node_id,
                name=name,
                description=description
            )
            self.graph.add_node(strat_node)

        # Process all columns except ID, name, and description as properties
        skip_columns = {self.id_column, 'name', 'description'}
        for col_name, value in row_data.items():
            if col_name not in skip_columns and value is not None and str(value).strip():
                self._create_or_update_property(
                    node_id=node_id,
                    strat_node=strat_node,
                    prop_name=col_name,
                    prop_value=value
                )

        return strat_node

    def _create_or_update_property(self, node_id: str, strat_node: Node, prop_name: str, prop_value: Any):
        """Create or update a property node."""
        prop_id = f"{node_id}_{prop_name}"
        existing_prop = self.graph.find_node_by_id(prop_id)
        
        if existing_prop:
            if self.overwrite:
                existing_prop.value = prop_value
                self.warnings.append(f"Updated existing property: {prop_id}")
        else:
            # Create new property
            prop_node = PropertyNode(
                node_id=prop_id,
                name=prop_name,
                value=prop_value,
                property_type=self._guess_property_type(prop_name, prop_value)
            )
            self.graph.add_node(prop_node)

            # Create edge to connect property to stratigraphic node
            edge = Edge(
                edge_id=f"{node_id}_{prop_name}_edge",
                edge_source=strat_node.node_id,
                edge_target=prop_node.node_id,
                edge_type="has_property"
            )
            self.graph.add_edge(edge)

    def _guess_property_type(self, prop_name: str, value: Any) -> str:
        """
        Guess property type based on column name and value.
        Uses the predefined PropertyNode.PROPERTY_TYPES for validation.
        """
        name_lower = prop_name.lower()
        
        # Check dimension-related properties
        if any(dim in name_lower for dim in ['height', 'altezza']):
            return 'Height'
        if any(dim in name_lower for dim in ['width', 'larghezza']):
            return 'Width'
        if any(dim in name_lower for dim in ['length', 'lunghezza']):
            return 'Length'
        if any(dim in name_lower for dim in ['diameter', 'diametro']):
            return 'Diameter'
        if any(dim in name_lower for dim in ['depth', 'profondità']):
            return 'Depth'
            
        # Check material-related properties
        if any(mat in name_lower for mat in ['material', 'materiale']):
            return 'Material'
            
        # Check morphology-related properties
        if any(morph in name_lower for morph in ['shape', 'form', 'morphology', 'forma']):
            return 'Morphology'
            
        # Check style-related properties
        if any(style in name_lower for style in ['style', 'stile']):
            return 'Style'
            
        # Check location-related properties
        if any(loc in name_lower for loc in ['location', 'position', 'posizione']):
            return 'Location'
            
        # Check restoration-related properties
        if any(rest in name_lower for rest in ['restoration', 'restauro']):
            return 'Restoration'
            
        # Default to string if no specific type is identified
        return 'string'

    def display_warnings(self):
        """Display all accumulated warnings."""
        if self.warnings:
            print("\nWarnings during import:")
            for warning in self.warnings:
                print(f"- {warning}")