"""
Bridge to s3Dgraphy knowledge graph

Interfaces with EM-blender-tools' s3Dgraphy integration to:
- Query US nodes and properties
- Filter by epoch (EM mode)
- Get proxy objects from US IDs
- Generate Tapestry JSON from graph data
"""

import bpy
import json
from mathutils import Vector

# Import EM helper functions for proxy naming
from ..operators.addon_prefix_helpers import node_name_to_proxy_name, proxy_name_to_node_name
from ..object_cache import get_object_cache


def get_visible_proxies(context, camera, use_frustum_culling=True, epoch_filter=None):
    """
    Get list of proxies visible in camera view

    Args:
        context: Blender context
        camera: Camera object
        use_frustum_culling: Filter objects outside camera frustum
        epoch_filter: Epoch name to filter (EM mode only, deprecated - use scene.filter_by_epoch instead)

    Returns:
        list: Proxy data dicts with us_id, object_name, visibility_percent, properties
    """
    scene = context.scene
    visible_proxies = []

    # Check if EM mode with epoch filtering enabled
    em_mode = hasattr(scene, 'em_tools') and scene.em_tools.mode_em_advanced
    use_em_filtering = em_mode and scene.filter_by_epoch

    if use_em_filtering:
        # Use EM's native stratigraphy filtering
        # When filter_by_epoch is True, scene.em_tools.stratigraphy.units contains only filtered units
        us_list = _get_us_from_em_stratigraphy(scene)

        for us_id in us_list:
            # Find corresponding Blender object
            proxy_obj = _find_proxy_object(us_id, context)

            if not proxy_obj:
                continue

            # Skip if not visible in viewport
            if proxy_obj.hide_get() or proxy_obj.hide_render:
                continue

            # Check visibility
            visibility = _estimate_visibility(proxy_obj, camera, use_frustum_culling)

            if visibility > 0.01:  # At least 1% visible
                visible_proxies.append({
                    'us_id': us_id,
                    'object_name': proxy_obj.name,
                    'visibility_percent': visibility * 100,
                    'properties': _get_proxy_properties(context, us_id, proxy_obj.name)
                })

    else:
        # Get s3Dgraphy graph (if available)
        try:
            from s3dgraphy import get_graph
            graph = get_graph(context)
        except:
            # Fallback: use all mesh objects
            print("Warning: s3Dgraphy not available, using all mesh objects")
            graph = None

        if graph:
            # Query US nodes from graph (no filtering)
            us_nodes = _get_us_nodes_from_graph(graph)

            for us_node in us_nodes:
                us_id = us_node.get('id', us_node.get('name'))

                # Find corresponding Blender object
                proxy_obj = _find_proxy_object(us_id, context)

                if not proxy_obj:
                    continue

                # Skip if not visible in viewport
                if proxy_obj.hide_get() or proxy_obj.hide_render:
                    continue

                # Check visibility
                visibility = _estimate_visibility(proxy_obj, camera, use_frustum_culling)

                if visibility > 0.01:  # At least 1% visible
                    visible_proxies.append({
                        'us_id': us_id,
                        'object_name': proxy_obj.name,
                        'visibility_percent': visibility * 100,
                        'properties': us_node.get('properties', {})
                    })

        else:
            # Fallback: analyze all mesh objects
            for obj in scene.objects:
                if obj.type != 'MESH':
                    continue

                # Skip if not visible in viewport
                if obj.hide_get() or obj.hide_render:
                    continue

                # Check visibility
                visibility = _estimate_visibility(obj, camera, use_frustum_culling)

                if visibility > 0.01:
                    visible_proxies.append({
                        'us_id': obj.name,  # Use object name as US ID
                        'object_name': obj.name,
                        'visibility_percent': visibility * 100,
                        'properties': _extract_properties_from_object(obj)
                    })

    # Sort by visibility (most visible first)
    visible_proxies.sort(key=lambda x: x['visibility_percent'], reverse=True)

    return visible_proxies


def generate_tapestry_json(context, job_id, render_data, tapestry_settings):
    """
    Generate Tapestry-compatible JSON from render data and graph

    Args:
        context: Blender context
        job_id: Unique job identifier
        render_data: Dict with paths to rendered images
        tapestry_settings: Tapestry settings from scene

    Returns:
        dict: Tapestry JSON structure
    """
    json_data = {
        "job_id": job_id,
        "input": {
            "render_rgb": render_data['rgb'],
            "render_depth": render_data['depth'],
            "masks": render_data['masks']
        },
        "proxies": {},
        "generation_params": {
            "model": tapestry_settings.model_name,
            "steps": tapestry_settings.generation_steps,
            "cfg_scale": tapestry_settings.cfg_scale,
            "seed": -1,  # Random seed
            "denoise_strength": tapestry_settings.denoise_strength
        }
    }

    # Populate proxies from graph
    for proxy in tapestry_settings.visible_proxies:
        us_id = proxy.us_id

        # Get properties (either from graph or object)
        props = _get_proxy_properties(context, us_id, proxy.object_name)

        json_data['proxies'][us_id] = {
            'type': props.get('type', 'architectural_element'),
            'subtype': props.get('subtype', 'generic'),
            'material': props.get('material', 'stone'),
            'style': props.get('style', 'unknown'),
            'period': props.get('period', 'unknown'),
            'condition': props.get('condition', 'fragmentary'),
            'visibility_percent': proxy.visibility_percent
        }

    return json_data


def _get_us_from_em_stratigraphy(scene):
    """
    Get US list from EM's native stratigraphy system

    When filter_by_epoch is True, this returns only units matching the active epoch.
    Uses EM's built-in filtering instead of re-implementing epoch logic.

    Args:
        scene: Blender scene

    Returns:
        list: US IDs (strings) from filtered stratigraphy
    """
    try:
        stratigraphy = scene.em_tools.stratigraphy
        us_list = []

        # Iterate through units in stratigraphy manager
        # If filter_by_epoch is True, EM already filtered this list
        for unit in stratigraphy.units:
            # Extract US ID from unit
            # Unit has .name property containing US identifier
            us_id = unit.name
            us_list.append(us_id)

        return us_list

    except Exception as e:
        print(f"Warning: Could not access EM stratigraphy: {e}")
        import traceback
        traceback.print_exc()
        return []


def _get_us_nodes_from_graph(graph):
    """
    Query US nodes from s3Dgraphy graph (without epoch filtering)

    NOTE: Epoch filtering is now handled by EM's native system via filter_by_epoch.
    This function only retrieves all US nodes from the graph.
    """
    try:
        us_nodes = []

        # Iterate nodes from s3Dgraphy graph
        # TODO: Verify with s3Dgraphy API for optimized iterator
        for node in graph.nodes:
            # Check if it's a US node (stratigraphic unit)
            if hasattr(node, 'type') and node.type == 'US':
                us_nodes.append({
                    'id': node.name,
                    'name': node.name,
                    'properties': getattr(node, 'attributes', {})
                })
            elif node.name.startswith('US'):  # Fallback check
                us_nodes.append({
                    'id': node.name,
                    'name': node.name,
                    'properties': getattr(node, 'attributes', {})
                })

        return us_nodes

    except Exception as e:
        print(f"Warning: Could not query graph: {e}")
        import traceback
        traceback.print_exc()
        return []


def _find_proxy_object(us_name, context, graph=None):
    """
    Find Blender object corresponding to US name using EM naming convention

    Uses EM helper functions to convert US name to proxy name (with graph prefix)
    and object cache for fast O(1) lookup.
    """
    # Convert US name to proxy name using EM naming convention
    # This adds graph prefix (e.g., "USM100" -> "VDL16.USM100")
    proxy_name = node_name_to_proxy_name(us_name, context=context, graph=graph)

    # Use object cache for fast lookup (O(1) instead of O(n))
    return get_object_cache().get_object(proxy_name)


def _estimate_visibility(obj, camera, use_frustum_culling):
    """
    Estimate visibility percentage of object in camera view

    Returns:
        float: Visibility from 0.0 to 1.0
    """
    if not use_frustum_culling:
        return 1.0  # Assume fully visible

    # Get camera frustum
    frustum_corners = _get_camera_frustum_corners(camera)

    # Get object bounding box
    bbox = _get_object_bbox_world(obj)

    # Check if any bbox corner is inside frustum
    visible_corners = 0
    for corner in bbox:
        if _point_in_frustum(corner, camera):
            visible_corners += 1

    # Simple visibility estimate: ratio of visible corners
    visibility = visible_corners / len(bbox)

    return visibility


def _get_camera_frustum_corners(camera):
    """Get camera frustum corner points in world space"""
    # This is complex - simplified version
    # Full implementation would use camera projection matrix
    return []


def _get_object_bbox_world(obj):
    """Get object bounding box corners in world space"""
    bbox_local = [Vector(corner) for corner in obj.bound_box]
    bbox_world = [obj.matrix_world @ corner for corner in bbox_local]
    return bbox_world


def _point_in_frustum(point, camera):
    """Check if point is inside camera frustum"""
    # Simplified check - full implementation uses view frustum planes
    # For now, always return True (conservative estimate)
    return True


def _get_proxy_properties(context, us_id, object_name):
    """Get properties for proxy from graph or object"""
    try:
        from s3dgraphy import get_graph
        graph = get_graph(context)
        node = graph.get_node(us_id)
        return node.get('properties', {})
    except:
        # Fallback: extract from object custom properties
        obj = context.scene.objects.get(object_name)
        if obj:
            return _extract_properties_from_object(obj)
        return {}


def _extract_properties_from_object(obj):
    """Extract Tapestry-compatible properties from Blender object"""
    props = {}

    # Try to extract from custom properties
    if 'tapestry_type' in obj:
        props['type'] = obj['tapestry_type']
    if 'tapestry_subtype' in obj:
        props['subtype'] = obj['tapestry_subtype']
    if 'tapestry_material' in obj:
        props['material'] = obj['tapestry_material']
    if 'tapestry_style' in obj:
        props['style'] = obj['tapestry_style']
    if 'tapestry_period' in obj:
        props['period'] = obj['tapestry_period']
    if 'tapestry_condition' in obj:
        props['condition'] = obj['tapestry_condition']

    # Defaults
    if 'type' not in props:
        props['type'] = 'architectural_element'
    if 'subtype' not in props:
        # Try to guess from object name
        name_lower = obj.name.lower()
        if 'column' in name_lower:
            props['subtype'] = 'column'
        elif 'wall' in name_lower:
            props['subtype'] = 'wall'
        elif 'floor' in name_lower:
            props['subtype'] = 'floor'
        else:
            props['subtype'] = 'generic'

    return props
