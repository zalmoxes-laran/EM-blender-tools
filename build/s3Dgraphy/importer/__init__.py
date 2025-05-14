# s3Dgraphy/importer/__init__.py

"""
Initialization for the s3Dgraphy importer module.
This module provides classes and functions to import graph data from
external formats, like GraphML, XLSX, SQLite, and CSV into the s3Dgraphy structure.

The importer module supports two modes of operation:
1. Mapped mode - using JSON configuration files
2. Automatic mode - using column names with manual ID column specification
"""

from typing import Optional
from .import_graphml import GraphMLImporter
from .base_importer import BaseImporter
from .xlsx_importer import XLSXImporter
#from .mapped_xlsx_importer import MappedXLSXImporter
#from .pyarchinit_importer import PyArchInitImporter

def create_importer(
    filepath: str,
    format_type: str,
    mapping_name: Optional[str] = None,
    id_column: Optional[str] = None,
    overwrite: bool = False
) -> BaseImporter:
    """
    Factory function to create appropriate importer based on format type.
    
    Args:
        filepath (str): Path to the file to import
        format_type (str): Format type ('graphml', 'xlsx', 'sqlite', 'csv')
        mapping_name (str, optional): Name of the mapping file for tabular formats.
            Required for mapped mode operation.
        id_column (str, optional): Name of the ID column when not using mapping.
            Required for automatic mode operation.
        overwrite (bool, optional): If True, overwrites existing values.
            Defaults to False.
            
    Returns:
        BaseImporter: An instance of the appropriate importer class
        
    Raises:
        ValueError: If format type is not supported or if required parameters are missing
        
    Examples:
        # Using mapped mode with JSON configuration
        importer = create_importer(
            filepath='data.xlsx',
            format_type='xlsx',
            mapping_name='stratigraphic_units'
        )
        
        # Using automatic mode
        importer = create_importer(
            filepath='data.xlsx',
            format_type='xlsx',
            id_column='ID'
        )
        
        # Using with overwrite enabled
        importer = create_importer(
            filepath='data.xlsx',
            format_type='xlsx',
            mapping_name='stratigraphic_units',
            overwrite=True
        )
    """
    importers = {
        'graphml': lambda p, m, i, o: GraphMLImporter(p),  # GraphML ignores mapping, id_column and overwrite
        'xlsx': XLSXImporter,
        # Add more importers as they are implemented
        # 'sqlite': SQLiteImporter,
        # 'csv': CSVImporter,
    }
    
    # Validate format type
    if format_type not in importers:
        raise ValueError(
            f"Unsupported format type: {format_type}. "
            f"Supported formats are: {', '.join(importers.keys())}"
        )
        
    # Special handling for GraphML
    if format_type == 'graphml':
        return importers[format_type](filepath, mapping_name, id_column, overwrite)
    
    # Validate parameters for other formats
    if mapping_name is None and id_column is None:
        raise ValueError(
            f"Either mapping_name or id_column must be provided for {format_type} format. "
            "Use mapping_name for mapped mode or id_column for automatic mode."
        )
        
    # Create and return appropriate importer
    return importers[format_type](filepath, mapping_name, id_column, overwrite)

# Define what is available for import when using 'from s3Dgraphy.importer import *'
__all__ = [
    "GraphMLImporter",
    "BaseImporter",
    "XLSXImporter",
    "create_importer"
]