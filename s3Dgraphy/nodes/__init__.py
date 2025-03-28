# s3Dgraphy/nodes/__init__.py

"""
Initialization for the s3Dgraphy nodes module.

This module provides classes for various node types, which are essential components 
of the s3Dgraphy graph structure, including stratigraphic, document, activity, 
property nodes, and more.
"""

from .base_node import Node
from .stratigraphic_node import StratigraphicNode
from .epoch_node import EpochNode
from .property_node import PropertyNode
from .document_node import DocumentNode
from .combiner_node import CombinerNode
from .extractor_node import ExtractorNode
from .group_node import GroupNode, ActivityNodeGroup, ParadataNodeGroup, TimeBranchNodeGroup
from .paradata_node import ParadataNode
from .geo_position_node import GeoPositionNode
from .representation_node import RepresentationModelNode
from .author_node import AuthorNode
from .link_node import LinkNode
from .embargo_node import EmbargoNode
from .license_node import LicenseNode

# Define what is available for import when using 'from nodes import *'
__all__ = [
    "Node", 
    "StratigraphicNode", 
    "EpochNode", 
    "PropertyNode", 
    "DocumentNode",
    "CombinerNode", 
    "ExtractorNode", 
    "GroupNode", 
    "ActivityNodeGroup",
    "ParadataNodeGroup",
    "TimeBranchNodeGroup", 
    "ParadataNode", 
    "GeoPositionNode", 
    "RepresentationModelNode",
    "AuthorNode", 
    "LinkNode",
    "EmbargoNode",
    "LicenseNode"
]
