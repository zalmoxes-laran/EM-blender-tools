import bpy # type: ignore
import pandas as pd
from typing import Dict, Any, Optional
from s3dgraphy.importer.base_importer import BaseImporter
from s3dgraphy.graph import Graph
from s3dgraphy.multigraph import load_graph_from_file, get_graph
import os

from s3dgraphy.multigraph.multigraph import multi_graph_manager  

class GenericXLSXImporter(BaseImporter):
    """
    A generic XLSX importer for EM-tools that can import Excel files with flexible structures.
    This importer is specific to EM-tools and handles basic Excel file parsing with minimal assumptions
    about the file structure.
    """
        
    def __init__(self, filepath: str, sheet_name: str = "Sheet1", id_column: str = "ID",
                desc_column: str = None, overwrite: bool = False, mode: str = "3DGIS"):
        """
        Initialize the generic XLSX importer.

        Args:
            filepath: Path to the XLSX file
            sheet_name: Name of the sheet to import
            id_column: Name of the column containing unique identifiers
            desc_column: Optional column name for descriptions
            overwrite: If True, overwrites existing nodes
            mode: Either "3DGIS" or "EM_ADVANCED"
        """

        super().__init__(filepath=filepath, id_column=id_column, overwrite=overwrite)

        self.sheet_name = sheet_name
        self.desc_column = desc_column
        self.mode = mode

        # Inizializzazione del grafo con nome specifico per modalità
        if mode == "3DGIS":
            self.graph_id = "3dgis_graph"
        else:
            self.graph_id = f"imported_{os.path.splitext(os.path.basename(filepath))[0]}"
            
        # Crea il grafo
        self.graph = Graph(graph_id=self.graph_id)

        # Debug print
        print(f"\nEM-tools Debug - Graph Initialization:")
        print(f"Creating graph with ID: {self.graph_id}")

        # Registra il grafo nel MultiGraphManager
        multi_graph_manager.graphs[self.graph_id] = self.graph
        print(f"\nEM-tools Debug - Graph Registration:")
        print(f"Registering graph with ID: {self.graph_id}")
        print(f"Current registered graphs: {list(multi_graph_manager.graphs.keys())}")

    def _read_excel_file(self) -> pd.DataFrame:
        """
        Read the Excel file using pandas, compatibile con file aperti su Windows.
        Su Windows, copia il file in temp prima di leggerlo per evitare lock.
        """
        file_content = None
        xl = None
        temp_file_path = None
        
        try:
            import io
            import tempfile
            import shutil
            import platform
            
            # Debug prints
            print(f"\nDebug Excel file path:")
            print(f"Original filepath: {self.filepath}")
            abs_filepath = bpy.path.abspath(self.filepath)
            print(f"Absolute filepath: {abs_filepath}")
            print(f"Platform: {platform.system()}")
            
            # ✅ STRATEGIA DOPPIA: Buffer su macOS/Linux, copia temp su Windows
            is_windows = platform.system() == "Windows"
            
            if is_windows:
                # ✅ WINDOWS: Copia il file in una location temporanea
                print(f"Windows detected - using temporary file copy strategy...")
                
                try:
                    # Crea file temporaneo con stesso nome per debug
                    temp_dir = tempfile.gettempdir()
                    temp_filename = f"em_import_{os.path.basename(abs_filepath)}"
                    temp_file_path = os.path.join(temp_dir, temp_filename)
                    
                    # Copia il file
                    print(f"Copying to temp: {temp_file_path}")
                    shutil.copy2(abs_filepath, temp_file_path)
                    print(f"File copied successfully")
                    
                    # Usa il file temporaneo
                    working_path = temp_file_path
                    
                except FileNotFoundError:
                    raise ImportError(f"File not found: {abs_filepath}")
                except PermissionError:
                    # Se anche la copia fallisce, prova copyfile (senza metadata)
                    try:
                        print(f"copy2 failed, trying copyfile...")
                        shutil.copyfile(abs_filepath, temp_file_path)
                        working_path = temp_file_path
                    except Exception as e:
                        raise ImportError(f"Cannot access file (locked or no permissions): {abs_filepath}. Error: {str(e)}")
                except Exception as e:
                    raise ImportError(f"Error copying file: {str(e)}")
                    
            else:
                # ✅ macOS/Linux: Usa buffer in memoria (più veloce)
                print(f"macOS/Linux detected - using memory buffer strategy...")
                
                try:
                    with open(abs_filepath, 'rb') as f:
                        file_content = io.BytesIO(f.read())
                    print(f"File loaded in memory ({len(file_content.getvalue())} bytes)")
                    working_path = file_content
                    
                except FileNotFoundError:
                    raise ImportError(f"File not found: {abs_filepath}")
                except PermissionError:
                    raise ImportError(f"Permission denied: {abs_filepath}")
                except Exception as e:
                    raise ImportError(f"Error reading file: {str(e)}")
            
            # Verifica gli sheet disponibili
            try:
                if is_windows:
                    # Su Windows usa il file temporaneo
                    xl = pd.ExcelFile(working_path, engine='openpyxl')
                else:
                    # Su macOS/Linux usa il buffer
                    xl = pd.ExcelFile(working_path, engine='openpyxl')
                    
                sheet_names = xl.sheet_names
                print(f"Available sheets: {sheet_names}")
                
            except Exception as e:
                print(f"Error reading Excel file structure: {str(e)}")
                raise ImportError(f"Invalid Excel file: {str(e)}")
            finally:
                if xl is not None:
                    xl.close()
                    print("ExcelFile closed")
            
            # Riporta il puntatore all'inizio se è un buffer
            if not is_windows and file_content:
                file_content.seek(0)
            
            # Lettura del DataFrame
            try:
                df = pd.read_excel(
                    working_path,  # File temp su Windows, buffer su macOS/Linux
                    sheet_name=self.sheet_name,
                    na_values=['', 'NA', 'N/A'],
                    keep_default_na=True,
                    engine='openpyxl'
                )
                print(f"Successfully read DataFrame with shape: {df.shape}")
            # Verbose column dump removed to keep import output clean
                
            except Exception as e:
                print(f"Error during pandas read_excel: {str(e)}")
                raise ImportError(f"Error reading Excel sheet: {str(e)}")

            if df.empty:
                raise ImportError("Excel file is empty")
                
            if self.id_column not in df.columns:
                raise ImportError(f"ID column '{self.id_column}' not found. Available columns: {', '.join(df.columns)}")
                
            return df
            
        except ImportError:
            raise
        except Exception as e:
            raise ImportError(f"Error reading Excel file: {str(e)}")
        
        finally:
            # ✅ PULIZIA: Libera risorse
            if file_content is not None:
                try:
                    file_content.close()
                    print("Memory buffer closed")
                except:
                    pass
            
            # ✅ WINDOWS: Rimuovi file temporaneo
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                    print(f"Temporary file removed: {temp_file_path}")
                except Exception as e:
                    print(f"Warning: Could not remove temp file: {e}")
            
            # Garbage collection
            import gc
            gc.collect()
            print("Resources released")

    
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

            # ✅ RINOMINA colonna descrizione se specificata dall'utente
            if self.desc_column and self.desc_column in df.columns:
                # Rinomina la colonna scelta in "Description" (standard BaseImporter)
                df = df.rename(columns={self.desc_column: 'Description'})
                print(f"✓ Renamed column '{self.desc_column}' to 'Description' for import")

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
