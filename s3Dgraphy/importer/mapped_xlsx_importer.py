from .base_importer import BaseImporter
import pandas as pd
from ..graph import Graph
import os
import json

class MappedXLSXImporter(BaseImporter):
    def __init__(self, filepath: str, mapping_name: str, overwrite: bool = False):
        #if mapping_name and not mapping_name.endswith('.json'):
        #    mapping_name = f"{mapping_name}.json"
            
        super().__init__(
            filepath=filepath, 
            mapping_name=mapping_name,
            overwrite=overwrite,
            mode="3DGIS"
        )
        self.mapping = self._load_mapping(mapping_name)
        self.graph = Graph(graph_id=f"{os.path.splitext(mapping_name)[0]}_graph")

    def parse(self) -> Graph:
        try:
            table_settings = self.mapping.get('table_settings', {})
            start_row = table_settings.get('start_row', 0)
            sheet_name = table_settings.get('sheet_name', 0)
            
            df = pd.read_excel(
                self.filepath,
                sheet_name=sheet_name,
                skiprows=start_row - 1 if start_row > 0 else 0,
                na_values=['', 'NA', 'N/A'],
                keep_default_na=True
            )
            
            if df.empty:
                raise ValueError("Excel file is empty")
            
            column_maps = self.mapping.get('column_mappings', {})
            if not column_maps:
                raise ValueError("No column mappings found")
            
            columns = list(column_maps.keys())
            total_rows = successful_rows = 0
            
            for _, row in df.iterrows():
                total_rows += 1
                try:
                    row_dict = dict(zip(columns, row))
                    self.process_row(row_dict)
                    successful_rows += 1
                except Exception as e:
                    self.warnings.append(f"Error processing row {total_rows}: {str(e)}")

            self.warnings.extend([
                f"\nImport summary:",
                f"Total rows processed: {total_rows}",
                f"Successful rows: {successful_rows}",
                f"Failed rows: {total_rows - successful_rows}"
            ])
                
            return self.graph
            
        except Exception as e:
            raise ImportError(f"Error parsing mapped Excel file: {str(e)}")

    def validate_mapping(self):

        if not self.mapping:
            raise ValueError("No mapping configuration provided")
            
        required_sections = ['table_settings', 'column_mappings']
        missing = [s for s in required_sections if s not in self.mapping]
        if missing:
            raise ValueError(f"Missing required sections in mapping: {', '.join(missing)}")
            
        table_settings = self.mapping.get('table_settings', {})
        if not table_settings.get('sheet_name'):
            raise ValueError("Sheet name not specified in mapping")
            
        column_maps = self.mapping.get('column_mappings', {})
        if not any(cm.get('is_id', False) for cm in column_maps.values()):
            raise ValueError("No ID column specified in mapping")

    def _load_mapping(self, mapping_name):
        """Load the JSON mapping file from emdbjson directory."""
        if not mapping_name:
            return None
            
        mapping_path = os.path.join(
            os.path.dirname(__file__), 
            '..', 'emdbjson',
            mapping_name
        )
        
        try:
            with open(mapping_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            raise ValueError(f"Mapping file {mapping_name} not found")