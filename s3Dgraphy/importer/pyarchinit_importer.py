# s3Dgraphy/importer/pyarchinit_importer.py

from typing import Dict, Any
from .base_importer import BaseImporter
import sqlite3
import os
from ..graph import Graph  
from ..nodes.base_node import Node
from ..nodes.stratigraphic_node import StratigraphicNode
from ..utils.utils import get_stratigraphic_node_class


class PyArchInitImporter(BaseImporter):
    """
    Importer for pyArchInit SQLite databases using JSON mapping configuration.
    """
    
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

        self.graph = Graph(graph_id="pyarchinit_graph")
        self.validate_mapping()

    def process_row(self, row_dict: Dict[str, Any]) -> Node:
        """Process a row from pyArchInit database"""
        # Add type conversion for numeric ID
        id_column = self._get_id_column()
        if isinstance(row_dict.get(id_column), (int, float)):
            row_dict[id_column] = str(row_dict[id_column])
        return super().process_row(row_dict)

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
            id_column = None
            for col, config in column_maps.items():
                if config.get('is_id', False):
                    id_column = col
                    break
                    
            print(f"\nID column identified: {id_column}")
            
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