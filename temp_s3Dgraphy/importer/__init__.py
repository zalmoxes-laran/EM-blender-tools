# s3Dgraphy/importer/__init__.py

"""
Initialization for the s3Dgraphy importer module.

This module provides classes and functions to import graph data from 
external formats, like GraphML, into the s3Dgraphy structure.
"""

from .import_graphml import GraphMLImporter

# Define what is available for import when using 'from importer import *'
__all__ = [
    "GraphMLImporter"
]
