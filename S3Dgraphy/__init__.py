# s3Dgraphy/__init__.py

## s3Dgraphy python module to record and manage stratigraphic data as knowledge graphs in a multitemporal, 3D space.
## Written by Emanuel Demetrescu 2024
## GNU-GPL 3.0 Licence

from .graph import Graph
from .node import (
    Node, StratigraphicNode, GroupNode, ActivityNodeGroup,
    ParadataNodeGroup, ParadataNode, DocumentNode, CombinerNode,
    ExtractorNode, PropertyNode, EpochNode
)
from .edge import Edge
from .import_graphml import GraphMLImporter
from .utils import convert_shape2type
from .multigraph import (
    MultiGraphManager, load_graph, get_graph, get_all_graph_ids, remove_graph
)
