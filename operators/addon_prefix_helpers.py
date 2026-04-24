# EMtools Helper Functions for Prefix Management
# Add to functions.py or create a new prefix_utils.py

import bpy # type: ignore
from s3dgraphy.utils.utils import manage_id_prefix, get_base_name, add_graph_prefix

def get_active_graph_code(context=None):
    """
    Get the graph code from the currently active GraphML file.
    
    Args:
        context: Blender context (optional, will use bpy.context if None)
    
    Returns:
        str or None: The graph code if available, None otherwise
    """
    if context is None:
        context = bpy.context
    
    scene = context.scene
    em_tools = scene.em_tools
    
    # Check if we have a valid active GraphML file
    if em_tools.active_file_index < 0 or not em_tools.graphml_files:
        return None
    
    graphml = em_tools.graphml_files[em_tools.active_file_index]
    
    # Get graph code, skip invalid codes
    if hasattr(graphml, 'graph_code') and graphml.graph_code not in ["", "site_ID", None]:
        return graphml.graph_code
    
    return None


def get_graph_code_from_graph(graph):
    """
    Get the graph code directly from a graph object.
    
    Args:
        graph: s3dgraphy Graph instance
    
    Returns:
        str or None: The graph code if available, None otherwise
    """
    if graph and hasattr(graph, 'attributes'):
        return graph.attributes.get('graph_code', None)
    return None


def node_name_to_proxy_name(node_name, context=None, graph=None):
    """
    Convert a node name to a proxy object name (adds prefix if needed).
    
    Use this when searching for a 3D object from a node.
    
    Args:
        node_name: The node's name (without prefix)
        context: Blender context (optional)
        graph: Graph instance (optional, will use active graph if None)
    
    Returns:
        str: The proxy object name with prefix
        
    Example:
        >>> node_name_to_proxy_name('US001')
        'VDL16.US001'  # If active graph code is VDL16
    """
    # Get graph code — try graph attributes first, then active Blender property
    graph_code = None
    if graph:
        graph_code = get_graph_code_from_graph(graph)
    if not graph_code:
        graph_code = get_active_graph_code(context)

    # Add prefix only if we have a graph code
    if graph_code:
        return add_graph_prefix(node_name, graph_code)
    
    return node_name


def proxy_name_to_node_name(proxy_name, context=None, graph=None):
    """
    Convert a proxy object name to a node name (removes prefix).
    
    Use this when finding a node from a 3D object.
    
    Args:
        proxy_name: The proxy object's name (potentially with prefix)
        context: Blender context (optional)
        graph: Graph instance (optional)
    
    Returns:
        str: The node name without prefix
        
    Example:
        >>> proxy_name_to_node_name('VDL16.US001')
        'US001'
    """
    # Always remove prefix (get base name)
    return get_base_name(proxy_name)


def should_use_prefix_in_ui(context=None):
    """
    Determine if UI lists should show prefixes.
    
    Returns True only in multi-graph mode where disambiguation is needed.
    
    Args:
        context: Blender context (optional)
    
    Returns:
        bool: True if prefixes should be shown in UI, False otherwise
    """
    if context is None:
        context = bpy.context
    
    scene = context.scene
    em_tools = scene.em_tools
    
    # Check if we're in multi-graph mode
    # TODO: Implement proper multi-graph detection
    # For now, always return False (no prefixes in UI)
    
    # Future logic:
    # if len(em_tools.graphml_files) > 1 and multiple graphs are loaded:
    #     return True
    
    return False


def get_proxy_from_node(node, context=None, graph=None):
    """
    Get the 3D proxy object corresponding to a node.
    
    Args:
        node: The node object (with .name attribute)
        context: Blender context (optional)
        graph: Graph instance (optional)
    
    Returns:
        bpy.types.Object or None: The proxy object if found, None otherwise
    """
    proxy_name = node_name_to_proxy_name(node.name, context, graph)
    return bpy.data.objects.get(proxy_name)


def get_node_from_proxy(proxy_obj, graph, context=None):
    """
    Get the node corresponding to a 3D proxy object.
    
    Args:
        proxy_obj: The proxy object (bpy.types.Object)
        graph: s3dgraphy Graph instance
        context: Blender context (optional)
    
    Returns:
        Node or None: The node if found, None otherwise
    """
    node_name = proxy_name_to_node_name(proxy_obj.name, context, graph)
    
    # Search by name in the graph
    # Note: This assumes nodes have a .name attribute
    for node in graph.nodes:
        if node.name == node_name:
            return node
    
    return None