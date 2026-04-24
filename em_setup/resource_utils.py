# em_setup/resource_utils.py
"""
Shared utility functions for resource folder processing.
Extracted from AUXILIARY_OT_import_now to allow reuse by both
auxiliary files and standalone resource collections.
"""

import os
import uuid
import bpy

from s3dgraphy.nodes.document_node import DocumentNode
from s3dgraphy.nodes.link_node import LinkNode


# ============================================================================
# PATH RESOLUTION
# ============================================================================

def resolve_resource_path(raw_path):
    """
    Resolve a resource folder path to an absolute path.
    Consolidates the duplicated resolution logic from operators.py,
    thumb_operators.py, etc.

    Supports:
    - Absolute paths: used directly
    - Blender-relative (// prefix): resolved via bpy.path.abspath()
    - Simple relative: resolved relative to .blend directory

    Args:
        raw_path: The raw path string (may be absolute, //-relative, or simple relative)

    Returns:
        str: Resolved absolute path

    Raises:
        ValueError: If .blend file is not saved and path is simple relative
    """
    if not raw_path:
        raise ValueError("Empty path")

    if os.path.isabs(raw_path) and not raw_path.startswith("//"):
        return os.path.normpath(raw_path)
    elif raw_path.startswith("//"):
        return os.path.normpath(bpy.path.abspath(raw_path))
    else:
        blend_path = bpy.data.filepath
        if blend_path:
            blend_dir = os.path.dirname(blend_path)
            return os.path.normpath(os.path.join(blend_dir, raw_path))
        else:
            raise ValueError("Blend file not saved, cannot resolve relative paths without // prefix")


def resolve_dosco_dir(graphml):
    """
    Resolve the DOSCO directory for a GraphML file item.

    Handles both legacy (graphml.dosco_dir) and new auxiliary file system
    (graphml.auxiliary_files with file_type == "dosco").

    After migrate_legacy_dosco_to_auxiliary() runs, graphml.dosco_dir is
    cleared to "". The actual path lives in auxiliary_files. This function
    checks both locations so consumers don't need to know the storage details.

    Args:
        graphml: A GraphMLFileItem PropertyGroup instance

    Returns:
        str: Resolved absolute DOSCO directory path, or "" if not configured
    """
    # 1. Check legacy property (for pre-migration .blend files)
    raw_path = getattr(graphml, 'dosco_dir', '')
    if raw_path:
        try:
            return resolve_resource_path(raw_path)
        except ValueError:
            pass

    # 2. Check auxiliary files (post-migration)
    if hasattr(graphml, 'auxiliary_files'):
        for aux in graphml.auxiliary_files:
            if getattr(aux, 'file_type', '') == 'dosco':
                folder = getattr(aux, 'dosco_folder', '')
                if folder:
                    try:
                        return resolve_resource_path(folder)
                    except ValueError:
                        pass

    return ""


# ============================================================================
# NODE TYPE FILTERING
# ============================================================================

# All stratigraphic node types recognized by the system
STRATIGRAPHIC_NODE_TYPES = [
    'US', 'USVs', 'USVn', 'VSF', 'SF', 'USD', 'serSU', 'serUSD',
    'serUSVn', 'serUSVs', 'TSU', 'UL', 'SE', 'BR', 'unknown'
]


def get_node_ids_by_types(graph, target_types=None):
    """
    Get node identifiers from the graph, optionally filtered by node type.

    Args:
        graph: The s3dgraphy graph instance
        target_types: Optional list of node type strings to include.
                      If None, uses the legacy behavior (exclude D., DOC., PROP. prefixes).
                      Use STRATIGRAPHIC_NODE_TYPES for stratigraphic-only filtering.

    Returns:
        list: Node name strings that match the criteria
    """
    node_ids = []
    for node in graph.nodes:
        original_name = getattr(node, 'attributes', {}).get('original_name', node.name)

        if target_types is not None:
            # Filter by explicit node types
            node_type = getattr(node, 'node_type', None)
            if node_type and node_type in target_types:
                if original_name:
                    node_ids.append(original_name)
        else:
            # Legacy behavior: include everything except D., DOC., PROP. prefixes
            if original_name and not original_name.startswith(('D.', 'DOC.', 'PROP.')):
                node_ids.append(original_name)

    return node_ids


def get_target_types_from_enum(target_node_types_enum):
    """
    Convert the AuxiliaryFileProperties (with file_type='resource_collection').target_node_types enum value
    to a list of s3dgraphy node type strings.

    Args:
        target_node_types_enum: One of 'STRATIGRAPHIC', 'DOCUMENT', 'EXTRACTOR', 'ALL'

    Returns:
        list or None: List of node type strings, or None for ALL (legacy behavior)
    """
    if target_node_types_enum == 'ALL':
        return None  # No filtering = legacy behavior
    elif target_node_types_enum == 'STRATIGRAPHIC':
        return STRATIGRAPHIC_NODE_TYPES
    elif target_node_types_enum == 'DOCUMENT':
        return ['document']
    elif target_node_types_enum == 'EXTRACTOR':
        return ['extractor']
    else:
        return None


# ============================================================================
# FOLDER SCANNING
# ============================================================================

def find_folders_by_name(root_folder, target_name):
    """
    Recursively find all folders matching target_name inside root_folder.

    Args:
        root_folder: Absolute path to start scanning from
        target_name: Folder name to match

    Returns:
        list: Absolute paths of matching folders
    """
    matching_folders = []

    try:
        for root, dirs, files in os.walk(root_folder):
            if target_name in dirs:
                match_path = os.path.join(root, target_name)
                matching_folders.append(match_path)
                print(f"Found matching folder: {match_path}")

    except Exception as e:
        print(f"Error scanning {root_folder}: {e}")

    return matching_folders


def find_files_by_prefix(root_folder, prefix, allowed_formats=None):
    """
    Find all files whose name starts with the given prefix.
    Used for FILENAME_PREFIX scan mode.

    Args:
        root_folder: Absolute path to scan
        prefix: Filename prefix to match (e.g. "USM100")
        allowed_formats: Optional set of allowed extensions (e.g. {'.jpg', '.png'})

    Returns:
        list: Tuples of (absolute_file_path, filename)
    """
    results = []

    try:
        for root, dirs, files in os.walk(root_folder):
            for filename in files:
                if filename.startswith(prefix):
                    if allowed_formats:
                        ext = os.path.splitext(filename)[1].lower()
                        if ext not in allowed_formats:
                            continue
                    results.append((os.path.join(root, filename), filename))

    except Exception as e:
        print(f"Error scanning {root_folder} for prefix {prefix}: {e}")

    return results


# ============================================================================
# NODE LOOKUP
# ============================================================================

def find_node_by_name(graph, target_name):
    """
    Find a node in the graph by its name or original_name.

    Args:
        graph: The s3dgraphy graph instance
        target_name: The node name to search for

    Returns:
        Node or None
    """
    for node in graph.nodes:
        original_name = getattr(node, 'attributes', {}).get('original_name', node.name)
        if node.name == target_name or original_name == target_name:
            return node
    return None


# ============================================================================
# DOCUMENT/LINK NODE CREATION
# ============================================================================

def determine_edge_type_for_document(target_node):
    """
    Determine the appropriate edge type for connecting a DocumentNode
    based on the type of the target node.

    Args:
        target_node: The graph node that will be connected to the DocumentNode

    Returns:
        str: Edge type string
    """
    node_type = getattr(target_node, 'node_type', None)

    if node_type in STRATIGRAPHIC_NODE_TYPES:
        return "has_documentation"
    elif node_type == "property":
        return "has_documentation"
    elif node_type == "extractor":
        return "extracted_from"
    else:
        return "generic_connection"


def get_folder_suffix(folder_path, base_resource_folder):
    """
    Get a disambiguation suffix from the folder's relative position.

    Args:
        folder_path: Absolute path to the matched folder
        base_resource_folder: Absolute path to the resource root

    Returns:
        str: Suffix string for document naming
    """
    relative_path = os.path.relpath(folder_path, base_resource_folder)
    parts = relative_path.split(os.sep)
    if len(parts) > 1:
        return "_".join(parts[:-1])
    return "main"


def is_allowed_format(filename, allowed_formats):
    """
    Check if a file has an allowed format.

    Args:
        filename: The filename to check
        allowed_formats: List of allowed format strings, or None for no restriction

    Returns:
        bool
    """
    if allowed_formats is None:
        return True
    ext = filename.lower().split('.')[-1]
    return ext in [fmt.lower() for fmt in allowed_formats]


def create_document_for_resource(graph, target_node, file_path, filename, folder_suffix, base_resource_folder):
    """
    Create DocumentNode + LinkNode for a resource file, with duplicate checking.

    Args:
        graph: The s3dgraphy graph instance
        target_node: The node to attach the document to
        file_path: Absolute path to the resource file
        filename: The filename
        folder_suffix: Disambiguation suffix for document naming
        base_resource_folder: Absolute path to the resource folder root

    Returns:
        DocumentNode: The created or existing DocumentNode
    """
    # Calculate path relative to base_resource_folder
    try:
        relative_path = os.path.relpath(file_path, base_resource_folder)
        relative_path = relative_path.replace("\\", "/")
    except ValueError:
        print(f"Warning: Cannot calculate relative path for {filename}, using absolute")
        relative_path = file_path

    # Determine edge type based on target node type
    edge_type = determine_edge_type_for_document(target_node)

    # Check for existing DocumentNode with same URL (deduplication)
    existing_doc = None
    for node in graph.nodes:
        if (hasattr(node, 'node_type') and node.node_type == 'document' and
                hasattr(node, 'url') and node.url == relative_path):
            existing_doc = node
            print(f"Found existing DocumentNode for file: {filename}")
            break

    if existing_doc:
        # Ensure edge exists to target node
        edge_exists = False
        edge_id = f"{target_node.node_id}_{edge_type}_{existing_doc.node_id}"

        for edge in graph.edges:
            if (edge.edge_source == target_node.node_id and
                    edge.edge_target == existing_doc.node_id and
                    edge.edge_type == edge_type):
                edge_exists = True
                break

        if not edge_exists:
            graph.add_edge(
                edge_id=edge_id,
                edge_source=target_node.node_id,
                edge_target=existing_doc.node_id,
                edge_type=edge_type
            )
            print(f"Added {edge_type} edge to existing DocumentNode")

        return existing_doc

    # Create new DocumentNode
    existing_docs = [n for n in graph.nodes
                     if hasattr(n, 'name') and n.name.startswith(f"DOC.{target_node.name}")]
    doc_index = len(existing_docs) + 1

    if folder_suffix and folder_suffix != "main":
        doc_id = f"DOC.{target_node.name}.{folder_suffix}.{doc_index:03d}"
    else:
        doc_id = f"DOC.{target_node.name}.{doc_index:03d}"

    print(f"Creating NEW DocumentNode: {doc_id}")
    print(f"  File path: {file_path}")
    print(f"  Relative path: {relative_path}")

    doc_node = DocumentNode(
        node_id=str(uuid.uuid4()),
        name=doc_id,
        url=relative_path
    )
    doc_node.attributes = getattr(doc_node, 'attributes', {})
    doc_node.attributes['resource_type'] = filename.split('.')[-1].lower()

    graph.add_node(doc_node)

    # Create edge to target node
    edge_id = f"{target_node.node_id}_{edge_type}_{doc_node.node_id}"
    graph.add_edge(
        edge_id=edge_id,
        edge_source=target_node.node_id,
        edge_target=doc_node.node_id,
        edge_type=edge_type
    )

    # Create LinkNode
    link_id = f"LINK.{doc_id}"
    link_node = LinkNode(
        node_id=str(uuid.uuid4()),
        name=link_id,
        url=relative_path
    )
    link_node.data['filename'] = filename

    graph.add_node(link_node)

    # Create edge between DocumentNode and LinkNode
    link_edge_id = f"{doc_node.node_id}_has_linked_resource_{link_node.node_id}"
    graph.add_edge(
        edge_id=link_edge_id,
        edge_source=doc_node.node_id,
        edge_target=link_node.node_id,
        edge_type="has_linked_resource"
    )

    print(f"Created DocumentNode and LinkNode for: {filename}")
    return doc_node


# ============================================================================
# HIGH-LEVEL RESOURCE PROCESSING
# ============================================================================

def process_node_resource_folder(graph, node_id, folder_path, allowed_formats, base_resource_folder):
    """
    Process all files in a node's matched resource folder.

    Args:
        graph: The s3dgraphy graph instance
        node_id: The node identifier
        folder_path: Absolute path to the matched folder
        allowed_formats: List of allowed format strings, or None
        base_resource_folder: Absolute path to the resource root
    """
    target_node = find_node_by_name(graph, node_id)
    if not target_node:
        print(f"Warning: Node {node_id} not found in graph")
        return

    folder_suffix = get_folder_suffix(folder_path, base_resource_folder)

    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        if os.path.isfile(file_path):
            if is_allowed_format(filename, allowed_formats):
                print(f"Creating DocumentNode for: {folder_suffix}/{filename}")
                create_document_for_resource(
                    graph, target_node, file_path, filename, folder_suffix, base_resource_folder
                )
            else:
                print(f"Skipping {filename} (format not allowed)")


def process_from_thumbnails_json(graph, base_resource_folder, index_data, allowed_formats=None):
    """
    Create DocumentNode and LinkNode by reading from the thumbnails JSON index (fast path).

    Args:
        graph: The s3dgraphy graph instance
        base_resource_folder: Absolute path to the resolved resource folder
        index_data: The loaded index.json data dict
        allowed_formats: Optional list of allowed format strings
    """
    created_docs = 0
    skipped_docs = 0

    for doc_key, item_data in index_data["items"].items():
        src_path = item_data.get("src_path", "")
        filename = item_data.get("filename", "")

        if not src_path or not filename:
            continue

        # Check format
        if allowed_formats:
            ext = filename.lower().split('.')[-1]
            if ext not in [fmt.lower() for fmt in allowed_formats]:
                skipped_docs += 1
                continue

        # Reconstruct absolute file path
        blend_path = bpy.data.filepath
        if blend_path:
            blend_dir = os.path.dirname(blend_path)
            file_path = os.path.normpath(os.path.join(blend_dir, src_path))
        else:
            file_path = os.path.normpath(os.path.join(base_resource_folder, src_path))

        if not os.path.exists(file_path):
            print(f"Warning: File not found: {file_path} - skipping")
            skipped_docs += 1
            continue

        # Calculate relative path to resource_folder for URL
        try:
            relative_path = os.path.relpath(file_path, base_resource_folder)
            relative_path = relative_path.replace("\\", "/")
        except ValueError:
            print(f"Warning: Cannot calculate relative path for {filename}")
            skipped_docs += 1
            continue

        # Identify target node from path (e.g. "US02/01.jpg" -> "US02")
        path_parts = relative_path.split('/')
        if len(path_parts) < 2:
            print(f"Warning: Cannot identify target node from path: {relative_path}")
            skipped_docs += 1
            continue

        target_node_name = path_parts[0]
        target_node = find_node_by_name(graph, target_node_name)
        if not target_node:
            print(f"Warning: Target node not found: {target_node_name} for file {filename}")
            skipped_docs += 1
            continue

        folder_suffix = "_".join(path_parts[:-1]) if len(path_parts) > 2 else path_parts[0]

        try:
            create_document_for_resource(
                graph, target_node, file_path, filename, folder_suffix, base_resource_folder
            )
            created_docs += 1
        except Exception as e:
            print(f"Error creating document for {filename}: {e}")
            skipped_docs += 1

    print(f"Created {created_docs} DocumentNodes from thumbnails JSON")
    if skipped_docs > 0:
        print(f"Skipped {skipped_docs} files")


def process_resource_folder(graph, resource_folder_raw, source_item, graph_name,
                            allowed_formats=None, target_types=None):
    """
    High-level resource folder processing. Resolves path, checks for cached
    thumbnails JSON (fast path), falls back to physical folder scan.

    Works with both AuxiliaryFileProperties and AuxiliaryFileProperties (with file_type='resource_collection')
    (duck typing on .resource_folder).

    Args:
        graph: The s3dgraphy graph instance
        resource_folder_raw: The raw resource_folder path string
        source_item: The AuxiliaryFileProperties or AuxiliaryFileProperties (with file_type='resource_collection')
        graph_name: The graph name (for fallback graph lookup)
        allowed_formats: Optional list of allowed format strings.
                         If None and source_item has emdb/pyarchinit mapping, reads from mapping.
        target_types: Optional list of node type strings to filter.
                      If None, uses legacy behavior.
    """
    from ..thumb_utils import em_thumbs_root, load_index_json

    # Resolve path
    base_resource_folder = resolve_resource_path(resource_folder_raw)
    print(f"Resource folder resolved: {base_resource_folder}")

    if not os.path.exists(base_resource_folder):
        raise Exception(f"Resource folder not found: {base_resource_folder}")

    if not graph:
        from s3dgraphy import get_graph as _get_graph
        graph = _get_graph(graph_name)
        if not graph:
            raise Exception(f"Graph {graph_name} not found")

    # Try fast path: thumbnails JSON
    try:
        thumbs_root = em_thumbs_root(resource_folder_raw)
        index_data = load_index_json(thumbs_root)

        if index_data.get("items") and len(index_data["items"]) > 0:
            print(f"Found thumbnails JSON with {len(index_data['items'])} items - using fast import")
            process_from_thumbnails_json(graph, base_resource_folder, index_data, allowed_formats)
            return
        else:
            print(f"Thumbnails JSON exists but is empty - falling back to folder scan")
    except Exception as e:
        print(f"Could not load thumbnails JSON: {e} - falling back to folder scan")

    # Fallback: physical folder scan
    print(f"Processing resource folder: {base_resource_folder}")
    if allowed_formats:
        print(f"Allowed formats: {allowed_formats}")

    # Get node IDs to match against
    imported_ids = get_node_ids_by_types(graph, target_types)

    for node_id in imported_ids:
        matching_folders = find_folders_by_name(base_resource_folder, node_id)

        if matching_folders:
            print(f"Found {len(matching_folders)} folder(s) for ID {node_id}:")
            for folder_path in matching_folders:
                print(f"  - {folder_path}")
                process_node_resource_folder(graph, node_id, folder_path, allowed_formats, base_resource_folder)
        # No else print to avoid excessive logging


def process_resource_folder_by_prefix(graph, resource_folder_raw, target_types=None, allowed_formats=None):
    """
    Process resource folder using FILENAME_PREFIX scan mode.
    Matches filenames starting with node identifiers.

    Args:
        graph: The s3dgraphy graph instance
        resource_folder_raw: The raw resource_folder path string
        target_types: Optional list of node type strings to filter
        allowed_formats: Optional set of allowed file extensions (e.g. {'.jpg', '.png'})
    """
    base_resource_folder = resolve_resource_path(resource_folder_raw)

    if not os.path.exists(base_resource_folder):
        raise Exception(f"Resource folder not found: {base_resource_folder}")

    imported_ids = get_node_ids_by_types(graph, target_types)

    for node_id in imported_ids:
        matched_files = find_files_by_prefix(base_resource_folder, node_id, allowed_formats)

        if matched_files:
            target_node = find_node_by_name(graph, node_id)
            if not target_node:
                continue

            print(f"Found {len(matched_files)} file(s) matching prefix '{node_id}':")
            for file_path, filename in matched_files:
                folder_suffix = get_folder_suffix(os.path.dirname(file_path), base_resource_folder)
                create_document_for_resource(
                    graph, target_node, file_path, filename, folder_suffix, base_resource_folder
                )
