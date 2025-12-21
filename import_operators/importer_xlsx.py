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

    REFACTORED: Now follows the same pattern as MappedXLSXImporter and PyArchInitImporter.
    """

    def __init__(self, filepath: str, sheet_name: str = "Sheet1", id_column: str = "ID",
                desc_column: str = None, overwrite: bool = False, existing_graph=None):
        """
        Initialize the generic XLSX importer.

        Args:
            filepath: Path to the XLSX file
            sheet_name: Name of the sheet to import
            id_column: Name of the column containing unique identifiers
            desc_column: Optional column name for descriptions
            overwrite: If True, overwrites existing nodes
            existing_graph: Existing graph instance to use.
                          If None, creates new unregistered graph with temporary ID.
                          The caller (EM-tools) is responsible for setting proper graph_id
                          and registering it in MultiGraphManager.
        """

        super().__init__(filepath=filepath, id_column=id_column, overwrite=overwrite)

        self.sheet_name = sheet_name
        self.desc_column = desc_column

        # ✅ REFACTOR: Follow same pattern as MappedXLSXImporter
        if existing_graph:
            # Use provided graph (EM_ADVANCED mode)
            self.graph = existing_graph
            self.graph_id = existing_graph.graph_id
            self._use_existing_graph = True
        else:
            # Create new UNREGISTERED graph (3DGIS mode)
            # Caller must set proper graph_id and register it
            self.graph = Graph(graph_id="temp_graph")
            self._use_existing_graph = False

    def _read_excel_file(self) -> pd.DataFrame:
        """
        Read the Excel file using pandas, compatible with locked files on Windows.

        OPTIMIZED: Single-pass reading, memory-efficient, platform-aware strategies.
        """
        file_content = None
        temp_file_path = None

        try:
            import io
            import tempfile
            import shutil
            import platform

            abs_filepath = bpy.path.abspath(self.filepath)
            is_windows = platform.system() == "Windows"

            # ✅ PERFORMANCE: Read file into memory ONCE using optimal strategy
            if is_windows:
                # Windows: Copy to temp (handles locked files)
                try:
                    temp_dir = tempfile.gettempdir()
                    temp_filename = f"em_import_{os.path.basename(abs_filepath)}"
                    temp_file_path = os.path.join(temp_dir, temp_filename)

                    # Try copy strategies
                    try:
                        shutil.copy2(abs_filepath, temp_file_path)
                    except PermissionError:
                        shutil.copyfile(abs_filepath, temp_file_path)

                    working_path = temp_file_path

                except FileNotFoundError:
                    raise ImportError(f"File not found: {abs_filepath}")
                except Exception as e:
                    raise ImportError(f"Cannot access file: {abs_filepath}. Error: {str(e)}")

            else:
                # macOS/Linux: Memory buffer (faster)
                try:
                    with open(abs_filepath, 'rb') as f:
                        file_content = io.BytesIO(f.read())
                    working_path = file_content

                except FileNotFoundError:
                    raise ImportError(f"File not found: {abs_filepath}")
                except PermissionError:
                    raise ImportError(f"Permission denied: {abs_filepath}")
                except Exception as e:
                    raise ImportError(f"Error reading file: {str(e)}")

            # ✅ PERFORMANCE: Single-pass read with ExcelFile context manager
            with pd.ExcelFile(working_path, engine='openpyxl') as excel_file:
                # Validate sheet exists
                if self.sheet_name not in excel_file.sheet_names:
                    raise ImportError(
                        f"Sheet '{self.sheet_name}' not found. "
                        f"Available: {', '.join(excel_file.sheet_names)}"
                    )

                # Read DataFrame with optimizations
                df = pd.read_excel(
                    excel_file,  # ✅ Use ExcelFile object (no re-read)
                    sheet_name=self.sheet_name,
                    na_values=['', 'NA', 'N/A'],
                    keep_default_na=True,
                    dtype=str,  # ✅ PERFORMANCE: Read as string (faster)
                    engine='openpyxl'
                )

            if df.empty:
                raise ImportError("Excel file is empty")

            if self.id_column not in df.columns:
                raise ImportError(
                    f"ID column '{self.id_column}' not found. "
                    f"Available: {', '.join(df.columns)}"
                )

            return df

        except ImportError:
            raise
        except Exception as e:
            raise ImportError(f"Error reading Excel file: {str(e)}")

        finally:
            # ✅ CLEANUP: Release resources
            if file_content is not None:
                try:
                    file_content.close()
                except:
                    pass

            # ✅ CLEANUP: Remove temporary file on Windows
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                except Exception as e:
                    print(f"Warning: Could not remove temp file: {e}")

            # ✅ MEMORY: Force garbage collection
            import gc
            gc.collect()

    
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

        OPTIMIZED: Vectorized operations, batch processing.

        Returns:
            Graph: The populated graph object
        """
        try:
            # Verify graph exists
            if self.graph is None:
                self.graph = Graph(graph_id=self.graph_id)

            df = self._read_excel_file()

            # ✅ Rename description column if specified
            if self.desc_column and self.desc_column in df.columns:
                df = df.rename(columns={self.desc_column: 'Description'})

            # ✅ PERFORMANCE: Pre-filter rows with missing IDs (vectorized)
            df = df[df[self.id_column].notna()].copy()

            total_rows = len(df)
            successful_rows = 0

            # ✅ PERFORMANCE: Use itertuples (5-10x faster than iterrows)
            for row_tuple in df.itertuples(index=False, name='Row'):
                try:
                    # Convert tuple to dict
                    row_dict = {
                        col: getattr(row_tuple, col)
                        for col in df.columns
                        if pd.notna(getattr(row_tuple, col))
                    }

                    if row_dict:
                        self.process_row(row_dict)
                        successful_rows += 1

                except Exception as e:
                    self.warnings.append(f"Error processing row: {str(e)}")

            # Add import summary
            self.warnings.append(f"\nImport summary:")
            self.warnings.append(f"Total rows processed: {total_rows}")
            self.warnings.append(f"Successful rows: {successful_rows}")
            self.warnings.append(f"Failed/skipped rows: {total_rows - successful_rows}")

            # ✅ MEMORY: Explicitly release DataFrame
            del df
            import gc
            gc.collect()

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
