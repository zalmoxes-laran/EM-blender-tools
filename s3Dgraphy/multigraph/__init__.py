# s3Dgraphy/multigraph/__init__.py

"""
Initialization for the s3Dgraphy multigraph module.

This module provides classes and functions to manage multiple graphs,
allowing loading, retrieving, and removing of individual graph instances
within a multi-graph structure.
"""

from .multigraph import MultiGraphManager, load_graph_from_file, get_graph, get_all_graph_ids, remove_graph

# Define what is available for import when using 'from multigraph import *'
__all__ = [
    "MultiGraphManager", "load_graph_from_file", "get_graph", "get_all_graph_ids", "remove_graph"
]
