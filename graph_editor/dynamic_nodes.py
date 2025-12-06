"""
Dynamic Node Generator for EMGraph
Automatically generates Blender node classes from s3dgraphy JSON datamodel.

This allows complete freedom to update node types without modifying Python code.
"""

import bpy
from bpy.types import Node
from typing import Dict, List, Set, Tuple, Optional, Type
from .socket_generator import load_datamodels, generate_sockets, get_node_color_from_datamodel


# ============================================================================
# BASE NODE CLASS
# ============================================================================

class EMGraphNodeBase(Node):
    """Base class for all EMGraph nodes - dynamically generated"""
    bl_icon = 'QUESTION'

    # Custom properties
    node_id: bpy.props.StringProperty(name="Node ID")  # type: ignore
    node_type: bpy.props.StringProperty(name="Node Type")  # type: ignore

    def draw_label(self):
        """Custom label showing the node's label property if available"""
        if hasattr(self, 'label') and self.label:
            return self.label
        return self.bl_label


# ============================================================================
# DYNAMIC NODE CLASS GENERATION
# ============================================================================

_GENERATED_CLASSES = []
_NODE_TYPE_MAP = {}  # Maps node_type string → Blender node class


def get_all_node_types_from_datamodel(nodes_datamodel: Dict) -> List[Dict]:
    """
    Estrae TUTTI i tipi di nodi dal datamodel JSON, includendo sottotipi.

    Returns:
        List of dicts with: {
            'type': str,              # e.g., "US", "PropertyNode"
            'parent': str,            # e.g., "StratigraphicNode", "ParadataNode"
            'label': str,             # Human-readable label
            'description': str,
            'class_name': str,        # Python class name
            'icon': str               # Blender icon
        }
    """
    all_types = []

    # Process each major category in the datamodel
    categories = [
        'node_types',
        'stratigraphic_nodes',
        'temporal_nodes',
        'paradata_nodes',
        'group_nodes',
        'visualization_nodes',
        'reference_nodes',
        'rights_nodes'
    ]

    for category in categories:
        if category not in nodes_datamodel:
            continue

        category_data = nodes_datamodel[category]

        for parent_type, parent_info in category_data.items():
            # Process the parent type itself
            if parent_type != 'subtypes':
                parent_class = parent_info.get('class', parent_type)

                node_info = {
                    'type': parent_type,
                    'parent': parent_info.get('parent', 'Node'),
                    'label': parent_info.get('label', parent_type),
                    'description': parent_info.get('description', ''),
                    'class_name': parent_class,
                    'icon': _get_icon_from_symbol(parent_info.get('symbol', ''))
                }
                all_types.append(node_info)

                # Process subtypes if they exist
                if 'subtypes' in parent_info:
                    for subtype, subtype_info in parent_info['subtypes'].items():
                        subtype_class = subtype_info.get('class', subtype)

                        subnode_info = {
                            'type': subtype,
                            'parent': parent_type,
                            'label': subtype_info.get('label', subtype),
                            'description': subtype_info.get('description', ''),
                            'class_name': subtype_class,
                            'icon': _get_icon_from_symbol(subtype_info.get('symbol', ''))
                        }
                        all_types.append(subnode_info)

    # ✅ FIXED: Aggiungi versioni lowercase per i paradata nodes
    # s3dgraphy usa node_type='document' (lowercase) nei grafi
    lowercase_mappings = [
        {'type': 'document', 'parent': 'ParadataNode', 'label': 'Document',
         'description': 'Document node (lowercase variant)', 'class_name': 'DocumentNode', 'icon': 'FILE_TEXT'},
        {'type': 'property', 'parent': 'ParadataNode', 'label': 'Property',
         'description': 'Property node (lowercase variant)', 'class_name': 'PropertyNode', 'icon': 'PROPERTIES'},
        {'type': 'extractor', 'parent': 'ParadataNode', 'label': 'Extractor',
         'description': 'Extractor node (lowercase variant)', 'class_name': 'ExtractorNode', 'icon': 'TRACKING'},
        {'type': 'combiner', 'parent': 'ParadataNode', 'label': 'Combiner',
         'description': 'Combiner node (lowercase variant)', 'class_name': 'CombinerNode', 'icon': 'LINK_BLEND'},
        {'type': 'link', 'parent': 'ReferenceNode', 'label': 'Link',
         'description': 'Link node (lowercase variant)', 'class_name': 'LinkNode', 'icon': 'LINKED'},
        {'type': 'geo_position', 'parent': 'ReferenceNode', 'label': 'Geo Position',
         'description': 'Geo position node (lowercase variant)', 'class_name': 'GeoPositionNode', 'icon': 'WORLD'},
    ]
    all_types.extend(lowercase_mappings)

    print(f"\n✅ Extracted {len(all_types)} node types from datamodel (including lowercase variants)")
    return all_types


def _get_icon_from_symbol(symbol: str) -> str:
    """Maps datamodel symbols to Blender icons"""
    icon_map = {
        'white rectangle': 'MESH_CUBE',
        'black parallelogram': 'MESH_UVSPHERE',
        'document': 'FILE_TEXT',
        'extractor': 'TRACKING',
        'combiner': 'LINK_BLEND',
        'property': 'PROPERTIES',
        '': 'NODE'
    }
    return icon_map.get(symbol.lower(), 'NODE')


def create_node_class(node_info: Dict, base_class: Type = EMGraphNodeBase) -> Type:
    """
    Dynamically creates a Blender Node class from node_info.

    Args:
        node_info: Dict with node type information
        base_class: Base class to inherit from

    Returns:
        Dynamically created class
    """
    node_type = node_info['type']
    class_name = f"EMGraph_{node_type}_Node"
    bl_idname = f"EMGraph{node_type}NodeType"

    # Get color from datamodel
    color = get_node_color_from_datamodel(node_type)

    def init(self, context):
        """Initialize node with sockets from datamodel"""
        # ✅ FIXED: Generate sockets based on node_type, not parent
        # This ensures EpochNode gets 'has_first_epoch' input socket
        node_type = node_info['type']
        generate_sockets(self, node_type)

        # Set custom color if available
        if color:
            self.use_custom_color = True
            self.color = color

    # Create the class dynamically
    new_class = type(class_name, (base_class,), {
        'bl_idname': bl_idname,
        'bl_label': node_info['label'],
        'bl_icon': node_info['icon'],
        '__doc__': node_info['description'],
        'init': init,
        '__module__': __name__
    })

    return new_class


def generate_all_node_classes() -> List[Type]:
    """
    Generates all node classes from the datamodel JSON.

    Returns:
        List of generated Blender Node classes
    """
    global _GENERATED_CLASSES, _NODE_TYPE_MAP

    print("\n" + "="*60)
    print("DYNAMIC NODE GENERATION")
    print("="*60)

    # Load datamodels
    nodes_datamodel, connections_datamodel = load_datamodels()

    if not nodes_datamodel:
        print("❌ Cannot generate nodes: datamodel not loaded")
        return []

    # Extract all node types
    all_node_types = get_all_node_types_from_datamodel(nodes_datamodel)

    # Generate classes
    generated_classes = []

    for node_info in all_node_types:
        try:
            node_class = create_node_class(node_info)
            generated_classes.append(node_class)

            # Map node_type string → class for validation
            _NODE_TYPE_MAP[node_info['type']] = node_class

            print(f"  ✓ Generated: {node_info['type']} ({node_class.bl_label})")

        except Exception as e:
            print(f"  ✗ Error generating {node_info['type']}: {e}")
            import traceback
            traceback.print_exc()

    _GENERATED_CLASSES = generated_classes

    print(f"\n✅ Successfully generated {len(generated_classes)} node classes")
    print("="*60 + "\n")

    return generated_classes


# ============================================================================
# EDGE VALIDATION
# ============================================================================

def build_node_hierarchy(nodes_datamodel: Dict) -> Dict[str, Set[str]]:
    """
    Builds a hierarchy map: parent_type → set of all subtypes

    Example:
        {
            'StratigraphicNode': {'US', 'USVs', 'USVn', 'SF', ...},
            'ParadataNode': {'PropertyNode', 'ExtractorNode', ...}
        }
    """
    hierarchy = {}

    all_types = get_all_node_types_from_datamodel(nodes_datamodel)

    for node_info in all_types:
        parent = node_info['parent']
        node_type = node_info['type']

        if parent not in hierarchy:
            hierarchy[parent] = set()

        hierarchy[parent].add(node_type)

    return hierarchy


def is_edge_allowed(source_type: str, target_type: str, edge_type: str,
                    connections_datamodel: Dict, node_hierarchy: Dict[str, Set[str]]) -> bool:
    """
    Verifica se un edge è permesso tra due tipi di nodi.

    Implementa la logica di ereditarietà:
    - Se l'edge permette StratigraphicNode → StratigraphicNode
    - Allora permette anche US → USVs (sottotipi)

    Args:
        source_type: Tipo del nodo sorgente (es. "US")
        target_type: Tipo del nodo target (es. "USVs")
        edge_type: Tipo di edge (es. "is_before")
        connections_datamodel: JSON delle connessioni
        node_hierarchy: Mappa parent → subtypes

    Returns:
        True se la connessione è permessa
    """
    if 'edge_types' not in connections_datamodel:
        return True  # Se non ci sono regole, permetti tutto

    edge_types = connections_datamodel['edge_types']

    if edge_type not in edge_types:
        return True  # Edge type sconosciuto, permetti

    edge_info = edge_types[edge_type]

    if 'allowed_connections' not in edge_info:
        return True  # Nessuna restrizione

    allowed = edge_info['allowed_connections']
    allowed_sources = set(allowed.get('source', []))
    allowed_targets = set(allowed.get('target', []))

    # ✅ Espandi i tipi permessi per includere tutti i sottotipi
    expanded_sources = set()
    for allowed_source in allowed_sources:
        expanded_sources.add(allowed_source)
        # Aggiungi tutti i sottotipi
        if allowed_source in node_hierarchy:
            expanded_sources.update(node_hierarchy[allowed_source])

    expanded_targets = set()
    for allowed_target in allowed_targets:
        expanded_targets.add(allowed_target)
        # Aggiungi tutti i sottotipi
        if allowed_target in node_hierarchy:
            expanded_targets.update(node_hierarchy[allowed_target])

    # Verifica se la connessione è permessa
    source_ok = source_type in expanded_sources
    target_ok = target_type in expanded_targets

    return source_ok and target_ok


def validate_graph_edges(graph, connections_datamodel: Dict, nodes_datamodel: Dict):
    """
    Valida tutti gli edge del grafo e stampa quelli non permessi.

    Args:
        graph: Il grafo s3dgraphy da validare
        connections_datamodel: JSON delle connessioni
        nodes_datamodel: JSON dei nodi
    """
    print("\n" + "="*60)
    print("EDGE VALIDATION")
    print("="*60)

    # Build hierarchy
    node_hierarchy = build_node_hierarchy(nodes_datamodel)

    invalid_edges = []
    total_edges = 0

    for edge in graph.edges:
        total_edges += 1

        # Get node types
        # ✅ FIXED: Edge objects use edge_source/edge_target, not source/target
        source_node = graph.find_node_by_id(edge.edge_source)
        target_node = graph.find_node_by_id(edge.edge_target)

        if not source_node or not target_node:
            continue

        source_type = getattr(source_node, 'node_type', 'Unknown')
        target_type = getattr(target_node, 'node_type', 'Unknown')
        edge_type = edge.edge_type

        # Validate
        if not is_edge_allowed(source_type, target_type, edge_type,
                              connections_datamodel, node_hierarchy):
            invalid_edges.append({
                'source': source_node.name,
                'source_type': source_type,
                'target': target_node.name,
                'target_type': target_type,
                'edge_type': edge_type
            })

    # Report
    if invalid_edges:
        print(f"\n⚠️  Found {len(invalid_edges)} invalid edges (out of {total_edges} total):\n")

        for inv in invalid_edges:
            print(f"  ✗ {inv['source']} ({inv['source_type']}) "
                  f"--[{inv['edge_type']}]--> "
                  f"{inv['target']} ({inv['target_type']})")

        print(f"\nThese edges cannot be represented in EMGraph due to datamodel rules.")
    else:
        print(f"\n✅ All {total_edges} edges are valid according to datamodel rules.")

    print("="*60 + "\n")

    return invalid_edges


# ============================================================================
# REGISTRATION
# ============================================================================

def register_dynamic_nodes():
    """Register all dynamically generated node classes"""
    global _GENERATED_CLASSES

    # Generate classes if not already done
    if not _GENERATED_CLASSES:
        generate_all_node_classes()

    # Register with Blender
    for cls in _GENERATED_CLASSES:
        try:
            bpy.utils.register_class(cls)
        except ValueError as e:
            # Already registered, skip
            pass
        except Exception as e:
            print(f"Error registering {cls.__name__}: {e}")


def unregister_dynamic_nodes():
    """Unregister all dynamically generated node classes"""
    global _GENERATED_CLASSES

    for cls in reversed(_GENERATED_CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass

    _GENERATED_CLASSES.clear()
    _NODE_TYPE_MAP.clear()
