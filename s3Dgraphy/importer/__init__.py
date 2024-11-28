# s3Dgraphy/importer/__init__.py

"""
Initialization for the s3Dgraphy importer module.
This module provides classes and functions to import graph data from
external formats, like GraphML, XLSX, SQLite, and CSV into the s3Dgraphy structure.
"""

from .import_graphml import GraphMLImporter
from .base_importer import BaseImporter
from .xlsx_importer import XLSXImporter

def create_importer(filepath, format_type, mapping_name=None, overwrite=False):
    """
    Factory function to create appropriate importer based on format type.
    
    Args:
        filepath (str): Path to the file to import
        format_type (str): Format type ('graphml', 'xlsx', 'sqlite', 'csv')
        mapping_name (str, optional): Name of the mapping file for tabular formats.
            Required for 'xlsx', 'sqlite', and 'csv' formats.
            Not used for 'graphml' format.
        overwrite (bool, optional): If True, overwrites existing property values.
            If False, skips existing properties. Defaults to False.
            
    Returns:
        BaseImporter: An instance of the appropriate importer class
        
    Raises:
        ValueError: If format type is not supported or if mapping_name is required but not provided
    """
    importers = {
        'graphml': lambda p, m, o: GraphMLImporter(p),
        'xlsx': XLSXImporter,
        # Add more importers as they are implemented
        # 'sqlite': SQLiteImporter,
        # 'csv': CSVImporter,
    }
    
    if format_type not in importers:
        raise ValueError(f"Unsupported format type: {format_type}")
        
    if format_type == 'graphml':
        return importers[format_type](filepath, mapping_name, overwrite)
    else:
        if mapping_name is None:
            raise ValueError(f"Mapping name is required for {format_type} format")
        return importers[format_type](filepath, mapping_name, overwrite)

# Define what is available for import when using 'from importer import *'
__all__ = [
    "GraphMLImporter",
    "BaseImporter",
    "XLSXImporter",
    "create_importer"
]