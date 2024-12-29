# s3Dgraphy/importer/pyarchinit_importer.py

from .base_importer import BaseImporter
import sqlite3
import os
from ..graph import Graph  # Aggiungiamo questo import


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

    def parse(self) -> Graph:
        """Parse pyArchInit database using mapping configuration"""
        try:
            conn = sqlite3.connect(self.filepath)
            cursor = conn.cursor()
            
            # Get table name from mapping
            table_settings = self.mapping.get('table_settings', {})
            table_name = table_settings.get('table_name')
            
            if not table_name:
                raise ValueError("Table name not specified in mapping")
            
            # Get column mappings
            column_maps = self.mapping.get('column_mappings', {})
            if not column_maps:
                raise ValueError("No column mappings found")
            
            columns = list(column_maps.keys())
            query = f'SELECT {",".join(columns)} FROM {table_name}'
            
            total_rows = 0
            successful_rows = 0
            
            for row in cursor.execute(query):
                total_rows += 1
                try:
                    # Convert row to dict with column names
                    row_dict = dict(zip(columns, row))
                    
                    # Process row using parent class method
                    self.process_row(row_dict)
                    successful_rows += 1
                    
                except Exception as e:
                    self.warnings.append(f"Error processing row {total_rows}: {str(e)}")

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