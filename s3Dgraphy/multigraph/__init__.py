# s3Dgraphy/multigraph/__init__.py

"""
Initialization for the s3Dgraphy multigraph module.

This module provides classes and functions to manage multiple graphs,
allowing loading, retrieving, and removing of individual graph instances
within a multi-graph structure.
"""

from .multigraph import (
    MultiGraphManager, 
    load_graph_from_file, 
    get_graph, 
    get_all_graph_ids, 
    remove_graph,
    get_active_graph,         
    set_active_graph,           
    get_all_graphs,           
    get_active_graph_id       
)

__all__ = [
    "MultiGraphManager", 
    "load_graph_from_file", 
    "get_graph", 
    "get_all_graph_ids",
    "remove_graph",
    "get_active_graph",       
    "set_active_graph",       
    "get_all_graphs",         
    "get_active_graph_id"     
]