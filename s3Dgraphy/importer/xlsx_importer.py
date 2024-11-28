# s3Dgraphy/importer/xlsx_importer.py

"""
XLSX file importer for s3Dgraphy.
"""

import pandas as pd
from typing import Dict, Any
from .base_importer import BaseImporter
from ..graph import Graph

class XLSXImporter(BaseImporter):
    """
    Importer for Excel (.xlsx) files.
    """
    def __init__(self, filepath: str, mapping_name: str):
        """
        Initialize the XLSX importer.
        
        Args:
            filepath (str): Path to the XLSX file
            mapping_name (str): Name of the mapping configuration to use
        """
        super().__init__(filepath, mapping_name)
        self._validate_mapping()

    def _validate_mapping(self):
        """
        Validate that the mapping configuration has all required fields.
        
        Raises:
            ValueError: If required fields are missing
        """
        required_fields = ['id_column', 'name_column', 'description_column']
        missing_fields = [field for field in required_fields if field not in self.mapping]
        
        if missing_fields:
            raise ValueError(f"Missing required fields in mapping: {', '.join(missing_fields)}")

    def parse(self) -> Graph:
        """
        Parse the XLSX file and create nodes/edges in the graph.
        
        Returns:
            Graph: The populated graph object
            
        Raises:
            ImportError: If there's an error reading or parsing the file
        """
        try:
            # Read Excel file
            sheet_name = self.mapping.get('sheet_name', 0)  # Use first sheet if not specified
            df = pd.read_excel(
                self.filepath,
                sheet_name=sheet_name,
                na_values=['', 'NA', 'N/A'],
                keep_default_na=True
            )
            
            # Convert DataFrame to list of dictionaries
            rows = df.to_dict('records')
            
            # Process each row
            for row in rows:
                try:
                    self.process_row(row)
                except KeyError as e:
                    self.warnings.append(f"Skipping row due to missing required field: {str(e)}")
                except Exception as e:
                    self.warnings.append(f"Error processing row: {str(e)}")

            return self.graph

        except Exception as e:
            raise ImportError(f"Error parsing XLSX file: {str(e)}")

    def _clean_value(self, value: Any) -> str:
        """
        Clean and convert input values to proper format.
        
        Args:
            value: Input value from Excel cell
            
        Returns:
            str: Cleaned value
        """
        if pd.isna(value):
            return ""
        return str(value).strip()

    def process_row(self, row_data: Dict[str, Any]) -> None:
        """
        Override process_row to add Excel-specific cleaning.
        
        Args:
            row_data (dict): Dictionary containing the row data
        """
        # Clean the input data
        cleaned_data = {
            key: self._clean_value(value)
            for key, value in row_data.items()
        }
        
        # Call parent's process_row with cleaned data
        super().process_row(cleaned_data)