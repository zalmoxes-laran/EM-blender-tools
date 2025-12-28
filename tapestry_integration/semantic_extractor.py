"""
Semantic Data Extractor for s3Dgraphy

Extracts rich semantic data from s3Dgraphy knowledge graph for Tapestry AI generation.

Uses correct s3Dgraphy API:
- get_property_nodes_for_node() for properties
- get_connected_epoch_node_by_edge_type() for epochs
- has_linked_resource edges for visual references
"""

import bpy
from pathlib import Path


def extract_us_semantic_data(graph, us_node):
    """
    Extract complete semantic data for a US node

    Args:
        graph: s3Dgraphy graph instance
        us_node: US node from graph

    Returns:
        dict: Semantic data with epoch, properties, visual_references, relationships
    """
    semantic_data = {}

    # Extract epoch information
    epoch_info = _extract_epoch(graph, us_node)
    if epoch_info:
        semantic_data["epoch"] = epoch_info

    # Extract properties (dynamic from graph)
    properties = _extract_properties(graph, us_node)
    if properties:
        semantic_data["properties"] = properties

    # Extract interpretation/certainty
    interpretation = _extract_interpretation(us_node)
    if interpretation:
        semantic_data["interpretation"] = interpretation

    # Extract visual references for RAG
    visual_refs = _extract_visual_references(graph, us_node)
    if visual_refs:
        semantic_data["visual_references"] = visual_refs

    # Extract stratigraphic relationships
    relationships = _extract_relationships(graph, us_node)
    if relationships:
        semantic_data["relationships"] = relationships

    return semantic_data


def _extract_epoch(graph, us_node):
    """
    Extract epoch with temporal bounds

    Uses: graph.get_connected_epoch_node_by_edge_type(node, "has_first_epoch")
    """
    try:
        # Get epoch node connected via has_first_epoch edge
        epoch_node = graph.get_connected_epoch_node_by_edge_type(us_node, "has_first_epoch")

        if epoch_node:
            return {
                "name": epoch_node.get('name', 'Unknown'),
                "start_year": epoch_node.get('start_year'),
                "end_year": epoch_node.get('end_year'),
                "description": epoch_node.get('description', '')
            }

        # Fallback: check direct property
        if 'epoch' in us_node:
            return {"name": us_node['epoch']}

    except Exception as e:
        print(f"Warning: Could not extract epoch for {us_node.get('id')}: {e}")

    return None


def _extract_properties(graph, us_node):
    """
    Extract ALL properties dynamically using s3Dgraphy API

    Uses: graph.get_property_nodes_for_node(node_id)

    Returns dict with all properties (multilingual, dynamic schema)
    """
    properties = {}

    try:
        node_id = us_node.get('id') or us_node.get('name')

        # Get property nodes connected via has_property edge
        property_nodes = graph.get_property_nodes_for_node(node_id)

        for prop_node in property_nodes:
            # Property node has 'type' and 'value'
            prop_name = prop_node.get('type') or prop_node.get('name')
            prop_value = prop_node.get('value')

            if prop_name and prop_value is not None:
                properties[prop_name] = prop_value

        # Also copy direct properties from node (backward compatibility)
        if 'properties' in us_node and isinstance(us_node['properties'], dict):
            properties.update(us_node['properties'])

    except Exception as e:
        print(f"Warning: Could not extract properties for {us_node.get('id')}: {e}")

    return properties if properties else None


def _extract_interpretation(us_node):
    """Extract interpretation/certainty fields from node"""
    interpretation = {}

    # Check for interpretation fields
    if 'function' in us_node:
        interpretation['function'] = us_node['function']
    if 'certainty' in us_node:
        interpretation['certainty'] = us_node['certainty']
    if 'notes' in us_node:
        interpretation['notes'] = us_node['notes']

    return interpretation if interpretation else None


def _extract_visual_references(graph, us_node):
    """
    Extract visual references for RAG

    Workflow:
    1. US → has_paradata → ParadataNode
    2. ParadataNode → has_document → DocumentNode
    3. DocumentNode → has_linked_resource → LinkNode (contains uri/file_path)

    Or alternatively:
    1. US → (direct connection) → DocumentNode
    2. DocumentNode → has_linked_resource → LinkNode
    """
    visual_refs = []

    try:
        node_id = us_node.get('id') or us_node.get('name')

        # Method 1: Get documents via paradata chain
        try:
            paradata_chain = graph.get_paradata_chain(node_id)
            if paradata_chain:
                for paradata_node in paradata_chain:
                    # Get documents from paradata
                    doc_nodes = graph.get_connected_nodes_by_edge_type(
                        paradata_node.get('id'),
                        "has_document"
                    )

                    for doc_node in doc_nodes:
                        ref = _extract_reference_from_document(graph, doc_node)
                        if ref:
                            visual_refs.append(ref)
        except:
            pass

        # Method 2: Try direct document connections
        try:
            # Get documents directly connected to US
            doc_nodes = graph.get_connected_nodes_by_filters(
                us_node,
                target_node_type="DocumentNode",
                edge_type="all"
            )

            for doc_node in doc_nodes:
                ref = _extract_reference_from_document(graph, doc_node)
                if ref:
                    # Avoid duplicates
                    if not any(r.get('uri') == ref.get('uri') for r in visual_refs):
                        visual_refs.append(ref)
        except:
            pass

    except Exception as e:
        print(f"Warning: Could not extract visual references for {us_node.get('id')}: {e}")

    return visual_refs if visual_refs else None


def _extract_reference_from_document(graph, doc_node):
    """
    Extract file URI from document node

    Document → has_linked_resource → LinkNode (uri/file_path)
    """
    try:
        doc_id = doc_node.get('id') or doc_node.get('name')

        # Get linked resource (LinkNode)
        link_nodes = graph.get_connected_nodes_by_edge_type(
            doc_id,
            "has_linked_resource"
        )

        if link_nodes:
            link_node = link_nodes[0]  # Take first link

            # Extract URI/file path
            uri = (link_node.get('uri') or
                   link_node.get('file_path') or
                   link_node.get('path'))

            if uri:
                # Build reference
                ref = {
                    "type": doc_node.get('type', 'image'),
                    "uri": uri,
                    "description": doc_node.get('description', ''),
                    "weight": 1.0  # Default weight
                }

                # Add tags if present
                if 'tags' in doc_node:
                    ref['tags'] = doc_node['tags']

                return ref

    except Exception as e:
        print(f"Warning: Could not extract reference from document {doc_node.get('id')}: {e}")

    return None


def _extract_relationships(graph, us_node):
    """
    Extract stratigraphic relationships using s3Dgraphy API

    Common relationships:
    - is_after / is_before (temporal)
    - abuts / is_abutted_by
    - cuts / is_cut_by
    - fills / is_filled_by
    - bonds_with
    """
    relationships = {}

    try:
        node_id = us_node.get('id') or us_node.get('name')

        # Define stratigraphic edge types to extract
        rel_types = [
            'is_after',
            'is_before',
            'abuts',
            'is_abutted_by',
            'cuts',
            'is_cut_by',
            'fills',
            'is_filled_by',
            'bonds_with'
        ]

        for rel_type in rel_types:
            try:
                connected_nodes = graph.get_connected_nodes_by_edge_type(node_id, rel_type)

                if connected_nodes:
                    # Extract IDs/names of connected nodes
                    relationships[rel_type] = [
                        node.get('id') or node.get('name')
                        for node in connected_nodes
                    ]
            except:
                continue

    except Exception as e:
        print(f"Warning: Could not extract relationships for {us_node.get('id')}: {e}")

    return relationships if relationships else None
