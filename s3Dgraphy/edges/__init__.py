# s3Dgraphy/edges/__init__.py

"""
Initialization for the s3Dgraphy edges module.

This module contains classes and definitions related to edges, 
which define the relationships and connections between nodes in the s3Dgraphy graphs.
"""

from .edge import Edge

# Define what is available for import when using 'from edges import *'
__all__ = [
    "Edge"
]
