# s3Dgraphy/importer/xlsx_importer.py

import pandas as pd
from typing import Dict, Any
from .base_importer import BaseImporter
from ..graph import Graph

class XLSXImporter(BaseImporter):
    """
    Importer for Excel (.xlsx) files.
    Supports both mapped and automatic property creation modes.
    """
    
    def __init__(self, filepath: str, mapping_name: str = None, id_column: str = None, overwrite: bool = False):
        """
        Initialize the XLSX importer.
        
        Args:
            filepath (str): Path to the XLSX file
            mapping_name (str, optional): Name of the mapping configuration to use
            id_column (str, optional): Name of the ID column when not using mapping
            overwrite (bool, optional): If True, overwrites existing values
        """
        super().__init__(filepath, mapping_name, id_column, overwrite)
        self._validate_settings()

    def _validate_settings(self):
        """
        Validate importer settings based on mode (mapped or automatic).
        
        Raises:
            ValueError: If required settings are missing or invalid
        """
        if self.mapping:
            self._validate_mapping()
        else:
            if not self.id_column:
                raise ValueError("id_column must be provided when not using mapping")

    def _validate_mapping(self):
        """
        Validate that the mapping configuration has all required fields.
        
        Raises:
            ValueError: If required fields are missing from mapping
        """
        required_fields = ['id_column', 'name_column']
        missing_fields = [field for field in required_fields if field not in self.mapping]
        
        if missing_fields:
            raise ValueError(f"Missing required fields in mapping: {', '.join(missing_fields)}")

    def _read_excel_file(self):
        """
        Read the Excel file using pandas.
        
        Returns:
            pd.DataFrame: The loaded DataFrame
            
        Raises:
            ImportError: If there's an error reading the file
        """
        try:
            # Determine sheet name or index
            sheet_name = self.mapping.get('sheet_name', 0) if self.mapping else 0
            
            # Read Excel with proper settings
            df = pd.read_excel(
                self.filepath,
                sheet_name=sheet_name,
                na_values=['', 'NA', 'N/A'],
                keep_default_na=True
            )
            
            # Basic validation
            if df.empty:
                raise ValueError("Excel file is empty")
                
            return df
            
        except Exception as e:
            raise ImportError(f"Error reading Excel file: {str(e)}")

    def _validate_dataframe(self, df: pd.DataFrame):
        """
        Validate the loaded DataFrame has required columns.
        
        Args:
            df (pd.DataFrame): The DataFrame to validate
            
        Raises:
            ValueError: If required columns are missing
        """
        # Check ID column exists
        id_column = self.mapping['id_column'] if self.mapping else self.id_column
        if id_column not in df.columns:
            raise ValueError(f"ID column '{id_column}' not found in Excel file")
            
        # If using mapping, check other required columns
        if self.mapping:
            required_columns = [self.mapping['id_column'], self.mapping['name_column']]
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                raise ValueError(f"Required columns missing: {', '.join(missing_columns)}")

    def _clean_row_data(self, row: pd.Series) -> Dict[str, Any]:
        """
        Clean and prepare row data for processing.
        
        Args:
            row (pd.Series): The row from DataFrame
            
        Returns:
            dict: Cleaned row data
        """
        # Convert row to dictionary
        row_dict = row.to_dict()
        
        # Clean values
        cleaned_data = {}
        for key, value in row_dict.items():
            # Handle various types of null values
            if pd.isna(value):
                continue
                
            # Convert numbers to appropriate type
            if isinstance(value, (int, float)):
                cleaned_data[key] = value
            else:
                # Clean strings
                cleaned_value = str(value).strip()
                if cleaned_value:  # Only include non-empty strings
                    cleaned_data[key] = cleaned_value
                    
        return cleaned_data

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
            df = self._read_excel_file()
            
            # Validate DataFrame
            self._validate_dataframe(df)
            
            # Track statistics
            total_rows = 0
            successful_rows = 0
            
            # Process each row
            for idx, row in df.iterrows():
                total_rows += 1
                try:
                    # Clean row data
                    row_dict = self._clean_row_data(row)
                    
                    # Process row if it has valid data
                    if row_dict:
                        self.process_row(row_dict)
                        successful_rows += 1
                    else:
                        self.warnings.append(f"Skipping row {idx+1}: No valid data")
                        
                except KeyError as e:
                    self.warnings.append(f"Skipping row {idx+1} due to missing required field: {str(e)}")
                except Exception as e:
                    self.warnings.append(f"Error processing row {idx+1}: {str(e)}")

            # Add summary to warnings
            self.warnings.append(f"\nImport summary:")
            self.warnings.append(f"Total rows processed: {total_rows}")
            self.warnings.append(f"Successful rows: {successful_rows}")
            self.warnings.append(f"Failed/skipped rows: {total_rows - successful_rows}")

            return self.graph

        except Exception as e:
            raise ImportError(f"Error parsing XLSX file: {str(e)}")

    def _get_sheet_names(self) -> list:
        """
        Get list of sheet names from Excel file.
        
        Returns:
            list: List of sheet names
        """
        try:
            return pd.ExcelFile(self.filepath).sheet_names
        except Exception as e:
            self.warnings.append(f"Error reading sheet names: {str(e)}")
            return []