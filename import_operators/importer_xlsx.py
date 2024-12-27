import bpy # type: ignore
import pandas as pd
from typing import Dict, Any, Optional
from ..s3Dgraphy.importer.base_importer import BaseImporter
from ..s3Dgraphy.graph import Graph
from ..s3Dgraphy.multigraph import load_graph, get_graph
import os

from ..s3Dgraphy.multigraph.multigraph import multi_graph_manager  # Aggiungi questa importazione


class GenericXLSXImporter(BaseImporter):
    """
    A generic XLSX importer for EM-tools that can import Excel files with flexible structures.
    This importer is specific to EM-tools and handles basic Excel file parsing with minimal assumptions
    about the file structure.
    """
    
    def __init__(self, filepath: str, sheet_name: str = "Sheet1", id_column: str = "ID", 
                 overwrite: bool = False, mode: str = "3DGIS"):
        """
        Initialize the generic XLSX importer.
        
        Args:
            filepath: Path to the XLSX file
            sheet_name: Name of the sheet to import
            id_column: Name of the column containing unique identifiers
            overwrite: If True, overwrites existing nodes
            mode: Either "3DGIS" or "EM_ADVANCED"
        """
        
        super().__init__(filepath=filepath, id_column=id_column, overwrite=overwrite, mode=mode)
        
        self.sheet_name = sheet_name
        self.mode = mode  # Lo salviamo come attributo della classe figlia

        # Inizializzazione del grafo
        if mode == "3DGIS":
            self.graph_id = "3dgis_graph"
        else:
            self.graph_id = f"imported_{os.path.splitext(os.path.basename(filepath))[0]}"
            
        # Crea il grafo
        self.graph = Graph(graph_id=self.graph_id)


        # Debug print
        print(f"\nDebug - Graph Initialization:")
        print(f"Creating graph with ID: {self.graph_id}")

        # Registra il grafo nel MultiGraphManager
        multi_graph_manager.graphs[self.graph_id] = self.graph
        print(f"\nDebug - Graph Registration:")
        print(f"Registering graph with ID: {self.graph_id}")
        print(f"Current registered graphs: {list(multi_graph_manager.graphs.keys())}")


    def _read_excel_file(self) -> pd.DataFrame:
        """
        Read the Excel file using pandas.
        """
        try:
            # Debug prints
            print(f"\nDebug Excel file path:")
            print(f"Original filepath: {self.filepath}")
            abs_filepath = bpy.path.abspath(self.filepath)
            print(f"Absolute filepath: {abs_filepath}")
            
            # Verifica del file
            if not os.path.exists(abs_filepath):
                print(f"File does not exist at: {abs_filepath}")
                print(f"Current working directory: {os.getcwd()}")
                raise ImportError(f"File not found: {abs_filepath}")
            
            print(f"File exists and has size: {os.path.getsize(abs_filepath)} bytes")
            
            # Verifica del file Excel
            try:
                xl = pd.ExcelFile(abs_filepath)
                print(f"Available sheets: {xl.sheet_names}")
            except Exception as e:
                print(f"Error reading Excel file structure: {str(e)}")
                raise ImportError(f"Invalid Excel file: {str(e)}")
                
            # Lettura del file
            try:
                df = pd.read_excel(
                    abs_filepath,
                    sheet_name=self.sheet_name,
                    na_values=['', 'NA', 'N/A'],
                    keep_default_na=True,
                    engine='openpyxl'
                )
                print(f"Successfully read DataFrame with shape: {df.shape}")
                print(f"Columns found: {list(df.columns)}")
                
            except Exception as e:
                print(f"Error during pandas read_excel: {str(e)}")
                raise ImportError(f"Error reading Excel sheet: {str(e)}")

            if df.empty:
                raise ImportError("Excel file is empty")
                
            if self.id_column not in df.columns:
                raise ImportError(f"ID column '{self.id_column}' not found. Available columns: {', '.join(df.columns)}")
                
            return df
            
        except Exception as e:
            raise ImportError(f"Error reading Excel file: {str(e)}")
    
    def _clean_row_data(self, row: pd.Series) -> Dict[str, Any]:
        """Clean and prepare row data for processing."""
        row_dict = row.to_dict()
        cleaned_data = {}
        
        for key, value in row_dict.items():
            # Skip null values
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
        """
        try:

            # Verifica che il grafo esista
            if self.graph is None:
                print("Graph is None, creating new graph")
                self.graph = Graph(graph_id=self.graph_id)
            
            print(f"\nStarting parse with graph ID: {self.graph_id}")


            df = self._read_excel_file()
            total_rows = 0
            successful_rows = 0
            
            for idx, row in df.iterrows():
                total_rows += 1
                try:
                    row_dict = self._clean_row_data(row)
                    if row_dict:
                        # Process row using automatic mode (no mapping)
                        self.process_row(row_dict)
                        successful_rows += 1
                    else:
                        self.warnings.append(f"Skipping row {idx+1}: No valid data")
                        
                except Exception as e:
                    self.warnings.append(f"Error processing row {idx+1}: {str(e)}")

            # Add import summary
            self.warnings.append(f"\nImport summary:")
            self.warnings.append(f"Total rows processed: {total_rows}")
            self.warnings.append(f"Successful rows: {successful_rows}")
            self.warnings.append(f"Failed/skipped rows: {total_rows - successful_rows}")


            # Dopo aver popolato il grafo, lo registriamo nel MultiGraphManager
            print(f"\nDebug - Registering graph:")
            print(f"Graph ID: {self.graph_id}")
            print(f"Number of nodes: {len(self.graph.nodes)}")
            #load_graph(self.filepath, graph_id=self.graph_id, overwrite=True)


            return self.graph
            
        except Exception as e:
            raise ImportError(f"Error parsing XLSX file: {str(e)}")

    def get_available_sheets(self) -> list:
        """Get list of available sheets in the Excel file."""
        try:
            return pd.ExcelFile(self.filepath).sheet_names
        except Exception as e:
            self.warnings.append(f"Error reading sheet names: {str(e)}")
            return []