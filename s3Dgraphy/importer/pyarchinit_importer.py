# s3Dgraphy/importer/pyarchinit_importer.py

from typing import Dict, Any, Optional
from .base_importer import BaseImporter
import sqlite3
import os
from ..graph import Graph  
from ..nodes.base_node import Node
from ..nodes.property_node import PropertyNode
from ..nodes.stratigraphic_node import StratigraphicNode
from ..utils.utils import get_stratigraphic_node_class
from ..multigraph.multigraph import multi_graph_manager  

class PyArchInitImporter(BaseImporter):
    def __init__(self, filepath: str, mapping_name: str, overwrite: bool = False):
        """
        Initialize pyArchInit importer with mapping configuration.
        
        Args:
            filepath: Path to the SQLite database
            mapping_name: Name of the JSON mapping file to use
            overwrite: If True, overwrites existing nodes
        """
        super().__init__(
            filepath=filepath, 
            mapping_name=mapping_name,
            overwrite=overwrite,
            mode="3DGIS"
        )

        # Inizializzazione del grafo per modalità 3DGIS
        self.graph_id = "3dgis_graph"
        self.graph = Graph(graph_id=self.graph_id)

        # Debug print
        print(f"\nDebug - Graph Initialization:")
        print(f"Creating graph with ID: {self.graph_id}")

        # Registra il grafo nel MultiGraphManager
        multi_graph_manager.graphs[self.graph_id] = self.graph
        print(f"\nDebug - Graph Registration:")
        print(f"Registering graph with ID: {self.graph_id}")
        print(f"Current registered graphs: {list(multi_graph_manager.graphs.keys())}")

        self.validate_mapping()

    def process_row(self, row_dict: Dict[str, Any]) -> Node:
        """Process a row from pyArchInit database"""
        try:
            # Get ID column and convert if numeric
            id_column = self._get_id_column()
            if isinstance(row_dict.get(id_column), (int, float)):
                row_dict[id_column] = str(row_dict[id_column])
                
            node_id = str(row_dict[id_column])
            
            # Get description from mapping or default
            desc_column = self._get_description_column()
            description = row_dict.get(desc_column) if desc_column else "pyarchinit element"

            # Create or update stratigraphic node
            base_attrs = {
                'node_id': f"pyarchinit_{node_id}",
                'name': str(row_dict[id_column]),
                'description': str(description)
            }

            # Get node type from id column mapping
            id_col_config = self.mapping['column_mappings'][id_column]
            strat_type = id_col_config.get('node_type', 'US')
            node_class = get_stratigraphic_node_class(strat_type)
            
            print(f"\nProcessing stratigraphic node:")
            print(f"ID: {base_attrs['node_id']}")
            print(f"Name: {base_attrs['name']}")
            print(f"Description: {base_attrs['description']}")
            print(f"Type: {strat_type}")

            # Create or update stratigraphic node            
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

            # Process other columns as properties
            print("\nProcessing property nodes:")
            for col_name, col_config in self.mapping.get('column_mappings', {}).items():
                # Skip ID and description columns
                if col_config.get('is_id', False) or col_config.get('is_description', False):
                    continue
                    
                print(f"\nChecking column: {col_name}")
                print(f"Column config: {col_config}")
                
                if col_config.get('property_name'):
                    # Create property node
                    value = row_dict.get(col_name, '')
                    print(f"Property value: {value}")
                    
                    if value:  # Only create property if value exists
                        property_id = f"{base_attrs['node_id']}_{col_config['property_name']}"
                        print(f"Creating property node: {property_id}")
                        
                        property_node = PropertyNode(
                            node_id=property_id,
                            name=col_config['property_name'],
                            description=str(value),
                            value=str(value),
                            property_type=col_config['property_name']
                        )
                        self.graph.add_node(property_node)
                        
                        # Create edge between stratigraphic node and property
                        edge_id = f"{base_attrs['node_id']}_has_property_{property_id}"
                        if not self.graph.find_edge_by_id(edge_id):
                            print(f"Creating property edge: {edge_id}")
                            self.graph.add_edge(
                                edge_id=edge_id,
                                edge_source=base_attrs['node_id'],
                                edge_target=property_id,
                                edge_type="has_property"
                            )

            return strat_node

        except KeyError as e:
            self.warnings.append(f"Missing required column: {str(e)}")
            raise

    def _get_description_column(self) -> Optional[str]:
        """Get description column from mapping"""
        for col_name, col_config in self.mapping.get('column_mappings', {}).items():
            if col_config.get('is_description', False):
                return col_name
        return None

    def parse(self) -> Graph:
        """Parse pyArchInit database using mapping configuration"""
        try:
            print("\n=== Starting PyArchInit Import ===")
            conn = sqlite3.connect(self.filepath)
            cursor = conn.cursor()
            
            # Debug del mapping
            print(f"\nMapping configuration:")
            print(f"Filepath: {self.filepath}")
            print(f"Table settings: {self.mapping.get('table_settings', {})}")
            print(f"Column mappings: {self.mapping.get('column_mappings', {})}")
            
            # Get table name from mapping
            table_settings = self.mapping.get('table_settings', {})
            table_name = table_settings.get('table_name')
            
            if not table_name:
                raise ValueError("Table name not specified in mapping")
            
            # Get column mappings
            column_maps = self.mapping.get('column_mappings', {})
            if not column_maps:
                raise ValueError("No column mappings found")
                
            # Find ID column
            id_column = self._get_id_column()
            desc_column = self._get_description_column()
                    
            print(f"\nID column identified: {id_column}")
            print(f"Description column identified: {desc_column or 'None'}")
            
            columns = list(column_maps.keys())
            print(f"Columns to query: {columns}")
            query = f'SELECT {",".join(columns)} FROM {table_name}'
            print(f"Query: {query}")
            
            total_rows = 0
            successful_rows = 0
            
            for row in cursor.execute(query):
                total_rows += 1
                try:
                    # Convert row to dict with column names
                    row_dict = dict(zip(columns, row))
                    print(f"\nProcessing row {total_rows}:")
                    print(f"Row data: {row_dict}")
                    
                    # Process row using this class's method
                    self.process_row(row_dict)
                    successful_rows += 1
                    
                except Exception as e:
                    self.warnings.append(f"Error processing row {total_rows}: {str(e)}")
                    print(f"Error processing row {total_rows}: {str(e)}")

            # Add import summary
            self.warnings.append(f"\nImport summary:")
            self.warnings.append(f"Total rows processed: {total_rows}")
            self.warnings.append(f"Successful rows: {successful_rows}")
            self.warnings.append(f"Failed rows: {total_rows - successful_rows}")
                
            conn.close()
            return self.graph
            
        except Exception as e:
            raise ImportError(f"Error parsing pyArchInit database: {str(e)}")

    def validate_mapping(self):
        """Validate the mapping configuration."""
        if not self.mapping:
            raise ValueError("No mapping configuration provided")
            
        required_sections = ['table_settings', 'column_mappings']
        missing = [s for s in required_sections if s not in self.mapping]
        if missing:
            raise ValueError(f"Missing required sections in mapping: {', '.join(missing)}")
            
        table_settings = self.mapping.get('table_settings', {})
        if not table_settings.get('table_name'):
            raise ValueError("Table name not specified in mapping")
            
        column_maps = self.mapping.get('column_mappings', {})
        if not any(cm.get('is_id', False) for cm in column_maps.values()):
            raise ValueError("No ID column specified in mapping")