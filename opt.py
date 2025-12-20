"""
Optimization Wrappers - EM Tools
=================================

Simplified API for all performance optimizations.
Import this single module instead of individual optimization modules.

Usage:
    from . import opt

    # Object lookups
    obj = opt.get_object("US001")
    meshes = opt.get_mesh_objects()

    # Graph queries
    index = opt.get_graph_index(graph)
    nodes = index.get_target_nodes(source_id, edge_type)

    # Material operations
    mats = opt.get_property_materials()
    opt.update_material_alpha(0.5)

    # Debouncing
    @opt.debounce(0.1)
    def my_update(context):
        pass

    # Thumbnails
    thumbs = opt.load_thumbnails_async(us_id, aux_files, callback)

    # Icons
    opt.mark_icons_dirty("em_tools.stratigraphy.units")
    opt.update_icons_if_needed(context, "em_tools.stratigraphy.units")

Author: Performance Optimization Team
Date: 2025-12-20
"""

import bpy
from typing import Optional, List, Callable, Tuple

# ============================================================================
# OBJECT CACHE WRAPPERS
# ============================================================================

def get_object(name: str):
    """
    Get Blender object by name (cached, O(1)).

    Args:
        name: Object name

    Returns:
        Object or None

    Replaces: bpy.data.objects.get(name)
    """
    from .object_cache import get_object_cache
    return get_object_cache().get_object(name)


def get_mesh_objects() -> List:
    """
    Get all mesh objects in scene (cached).

    Returns:
        List of mesh objects

    Replaces: [obj for obj in bpy.data.objects if obj.type == 'MESH']
    """
    from .object_cache import get_object_cache
    return get_object_cache().get_mesh_objects()


def find_proxy(node_name: str):
    """
    Find proxy for stratigraphic node.

    Args:
        node_name: Node name (e.g., "US001")

    Returns:
        Proxy object or None

    Handles both exact match and prefixed match (e.g., "DEMO25.US001")
    """
    from .object_cache import find_proxy_for_stratigraphic_node
    return find_proxy_for_stratigraphic_node(node_name)


def invalidate_objects():
    """Invalidate object cache after adding/removing objects"""
    from .object_cache import invalidate_object_cache
    invalidate_object_cache()


# ============================================================================
# GRAPH INDEX WRAPPERS
# ============================================================================

def get_graph_index(graph):
    """
    Get or create graph edge index.

    Args:
        graph: s3dgraphy graph instance

    Returns:
        GraphEdgeIndex instance

    Usage:
        index = opt.get_graph_index(graph)
        properties = index.get_target_nodes(node_id, "has_property")
    """
    from .graph_index import get_or_create_graph_index
    return get_or_create_graph_index(graph)


def invalidate_graph(graph):
    """Invalidate graph index after graph modifications"""
    from .graph_index import invalidate_graph_index
    invalidate_graph_index(graph)


# ============================================================================
# MATERIAL CACHE WRAPPERS
# ============================================================================

def get_property_materials() -> List:
    """
    Get all property materials (cached).

    Returns:
        List of property materials
    """
    from .material_cache import get_material_cache
    return get_material_cache().get_property_materials()


def get_principled_node(material):
    """
    Get Principled BSDF node for material (cached).

    Args:
        material: Blender material

    Returns:
        Principled BSDF node or None
    """
    from .material_cache import get_material_cache
    return get_material_cache().get_principled_node(material)


def update_material_alpha(alpha_value: float) -> int:
    """
    Update alpha for all property materials (optimized).

    Args:
        alpha_value: Alpha value (0-1)

    Returns:
        Number of materials updated
    """
    from .functions import update_property_materials_alpha
    return update_property_materials_alpha(alpha_value)


def update_materials_visible_only(context, alpha_value: float) -> int:
    """
    Update alpha only for visible materials (viewport culling).

    Args:
        context: Blender context
        alpha_value: Alpha value (0-1)

    Returns:
        Number of materials updated
    """
    from .optimizations import update_materials_visible_only
    return update_materials_visible_only(context, alpha_value)


def invalidate_materials():
    """Invalidate material cache after creating/deleting materials"""
    from .material_cache import invalidate_material_cache
    invalidate_material_cache()


# ============================================================================
# DEBOUNCING WRAPPERS
# ============================================================================

def debounce(delay: float = 0.1):
    """
    Decorator to debounce function calls.

    Args:
        delay: Delay in seconds

    Usage:
        @opt.debounce(0.15)
        def update_icons(context):
            # Heavy operation
            pass
    """
    from .debounce import debounce_call
    return debounce_call(delay)


def debounce_function(func: Callable, delay: float = 0.1) -> Callable:
    """
    Create debounced version of function.

    Args:
        func: Function to debounce
        delay: Delay in seconds

    Returns:
        Debounced function
    """
    from .debounce import debounce_function as _debounce_function
    return _debounce_function(func, delay)


# ============================================================================
# ASYNC THUMBNAIL WRAPPERS
# ============================================================================

def load_thumbnails_async(us_node_id: str, aux_files: List,
                          on_ready: Optional[Callable] = None) -> List[Tuple]:
    """
    Load thumbnails asynchronously.

    Args:
        us_node_id: US node ID
        aux_files: Auxiliary files to search
        on_ready: Callback when ready

    Returns:
        Cached thumbnails or empty list

    Usage:
        def on_ready(thumbs):
            display(thumbs)

        thumbs = opt.load_thumbnails_async("US001", aux_files, on_ready)
    """
    from .thumb_async import load_thumbnails_async as _load_async
    return _load_async(us_node_id, aux_files, on_ready)


def get_cached_thumbnails(us_node_id: str) -> List[Tuple]:
    """Get cached thumbnails without loading"""
    from .thumb_async import get_cached_thumbnails
    return get_cached_thumbnails(us_node_id)


def clear_thumbnail_cache():
    """Clear thumbnail cache"""
    from .thumb_async import clear_thumbnail_cache
    clear_thumbnail_cache()


# ============================================================================
# ICON UPDATE WRAPPERS
# ============================================================================

def mark_icons_dirty(list_type: str):
    """
    Mark icons as needing update.

    Args:
        list_type: List identifier
    """
    from .optimizations import mark_icons_dirty
    mark_icons_dirty(list_type)


def update_icons_if_needed(context, list_type: str) -> bool:
    """
    Update icons only if dirty.

    Args:
        context: Blender context
        list_type: List identifier

    Returns:
        True if icons were updated
    """
    from .optimizations import update_icons_if_needed
    return update_icons_if_needed(context, list_type)


# ============================================================================
# PROGRESS BAR HELPERS
# ============================================================================

class Progress:
    """
    Context manager for progress bars.

    Usage:
        with opt.Progress(context, 100) as progress:
            for i, item in enumerate(items):
                progress.update(i)
                process(item)
    """

    def __init__(self, context, total: int):
        self.context = context
        self.total = total
        self.wm = context.window_manager

    def __enter__(self):
        self.wm.progress_begin(0, self.total)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.wm.progress_end()
        return False

    def update(self, current: int):
        """Update progress"""
        self.wm.progress_update(current)


def check_cancelled(context) -> bool:
    """
    Check if user pressed ESC.

    Args:
        context: Blender context

    Returns:
        True if cancelled
    """
    from .optimizations import check_cancelled
    return check_cancelled(context)


# ============================================================================
# STATISTICS & DEBUGGING
# ============================================================================

def print_stats():
    """Print all optimization statistics to console"""
    from .optimizations import print_optimization_stats
    print_optimization_stats()


def get_stats() -> dict:
    """
    Get all optimization statistics.

    Returns:
        Dict with stats for all caches
    """
    from .optimizations import get_optimization_stats
    return get_optimization_stats()


# ============================================================================
# BATCH OPERATIONS
# ============================================================================

def batch_get_objects(names: List[str]) -> List:
    """
    Get multiple objects efficiently.

    Args:
        names: List of object names

    Returns:
        List of objects (None for not found)
    """
    from .object_cache import get_object_cache
    cache = get_object_cache()
    return [cache.get_object(name) for name in names]


def batch_update_materials(materials: List, alpha: float):
    """
    Update multiple materials efficiently.

    Args:
        materials: List of materials
        alpha: Alpha value
    """
    from .material_cache import get_material_cache
    cache = get_material_cache()

    for mat in materials:
        node = cache.get_principled_node(mat)
        if node and 'Alpha' in node.inputs:
            node.inputs['Alpha'].default_value = alpha


# ============================================================================
# CONVENIENCE ALIASES
# ============================================================================

# Short aliases for common operations
obj = get_object
objs = get_mesh_objects
mats = get_property_materials
graph_idx = get_graph_index
