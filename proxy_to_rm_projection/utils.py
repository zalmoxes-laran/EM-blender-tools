"""
Utility functions for Proxy to RM Projection
This module contains the core algorithms for ray casting, color extraction,
and material application for the proxy projection system.
"""

import bpy
import bmesh
import mathutils
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
import numpy as np


def get_filtered_proxy_objects(em_list):
    """
    Get proxy objects from the filtered stratigraphy list.
    
    Args:
        em_list: The filtered em_list from stratigraphy manager
        
    Returns:
        List of proxy objects with their properties
    """
    proxy_objects = []
    
    for item in em_list:
        # Get the actual Blender object
        obj = bpy.data.objects.get(item.name)
        
        if obj and obj.type == 'MESH':
            # Extract proxy color from material
            proxy_color = get_proxy_color(obj)
            
            proxy_objects.append({
                'object': obj,
                'color': proxy_color,
                'name': item.name,
                'node_type': getattr(item, 'node_type', 'US')
            })
    
    return proxy_objects


def get_rm_objects_for_epoch(scene):
    """
    Get RM objects that belong to the active epoch.
    
    Args:
        scene: Blender scene
        
    Returns:
        List of RM objects for the current epoch
    """
    if scene.epoch_list_index < 0 or scene.epoch_list_index >= len(scene.epoch_list):
        return []
        
    active_epoch = scene.epoch_list[scene.epoch_list_index]
    rm_objects = []
    
    # Check if RM sync is active
    if not getattr(scene, 'sync_rm_visibility', False):
        print("Warning: RM temporal sync not active - projection may not work correctly")
    
    # Get RM objects from the RM manager list
    for rm_item in scene.rm_list:
        # Check if this RM belongs to the active epoch
        belongs_to_epoch = False
        
        # Check if active epoch is in the RM's epoch list
        for epoch_item in rm_item.epochs:
            if epoch_item.name == active_epoch.name:
                belongs_to_epoch = True
                break
        
        if belongs_to_epoch:
            obj = bpy.data.objects.get(rm_item.name)
            if obj and obj.type == 'MESH':
                rm_objects.append({
                    'object': obj,
                    'name': rm_item.name,
                    'is_linked': obj.library is not None,
                    'is_publishable': rm_item.is_publishable
                })
    
    return rm_objects


def get_proxy_color(proxy_obj):
    """
    Extract color from proxy object's material.
    
    Args:
        proxy_obj: Proxy object
        
    Returns:
        RGBA color tuple, or default if no material
    """
    if not proxy_obj.data.materials:
        return (0.5, 0.5, 0.5, 1.0)  # Default gray
    
    material = proxy_obj.data.materials[0]
    if not material or not material.use_nodes:
        return (0.5, 0.5, 0.5, 1.0)
    
    # Find Principled BSDF node
    for node in material.node_tree.nodes:
        if node.type == 'BSDF_PRINCIPLED':
            base_color = node.inputs['Base Color'].default_value
            return (base_color[0], base_color[1], base_color[2], base_color[3])
    
    return (0.5, 0.5, 0.5, 1.0)


def create_bvh_tree(obj):
    """
    Create a BVH tree for efficient ray casting.
    
    Args:
        obj: Blender mesh object
        
    Returns:
        BVHTree for the object
    """
    # Apply object transformation to get world coordinates
    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_obj = obj.evaluated_get(depsgraph)
    
    mesh = eval_obj.to_mesh()
    
    # Transform vertices to world space
    matrix_world = obj.matrix_world
    vertices = [matrix_world @ v.co for v in mesh.vertices]
    
    # Create BVH tree
    bvh = BVHTree.FromPolygons(vertices, [p.vertices for p in mesh.polygons])
    
    # Clean up
    eval_obj.to_mesh_clear()
    
    return bvh


def calculate_vertex_proxy_intersection(rm_obj, proxy_objects, settings):
    """
    Calculate which proxy intersects with each vertex of the RM object.
    
    Args:
        rm_obj: RM object dictionary
        proxy_objects: List of proxy object dictionaries
        settings: Projection settings
        
    Returns:
        Dictionary mapping vertex indices to proxy colors
    """
    obj = rm_obj['object']
    
    # Get mesh in world coordinates
    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_obj = obj.evaluated_get(depsgraph)
    mesh = eval_obj.to_mesh()
    
    # Create BVH trees for all proxies
    proxy_bvh_trees = {}
    for proxy_data in proxy_objects:
        try:
            proxy_bvh_trees[proxy_data['name']] = create_bvh_tree(proxy_data['object'])
        except Exception as e:
            print(f"Warning: Could not create BVH tree for proxy {proxy_data['name']}: {e}")
            continue
    
    vertex_colors = {}
    matrix_world = obj.matrix_world
    
    # Get batch size
    batch_sizes = {'SMALL': 1000, 'MEDIUM': 5000, 'LARGE': 10000}
    batch_size = batch_sizes.get(settings.batch_size, 5000)
    
    # Process vertices in batches
    total_vertices = len(mesh.vertices)
    
    for batch_start in range(0, total_vertices, batch_size):
        batch_end = min(batch_start + batch_size, total_vertices)
        
        for i in range(batch_start, batch_end):
            vertex = mesh.vertices[i]
            world_co = matrix_world @ vertex.co
            
            # Test intersection with each proxy
            intersected_proxy = None
            
            for proxy_data in proxy_objects:
                proxy_name = proxy_data['name']
                
                if proxy_name not in proxy_bvh_trees:
                    continue
                
                bvh = proxy_bvh_trees[proxy_name]
                
                # Cast rays in multiple directions to check if point is inside
                if is_point_inside_mesh(world_co, bvh, settings.max_ray_distance):
                    intersected_proxy = proxy_data
                    break  # Use first intersecting proxy
            
            if intersected_proxy:
                vertex_colors[i] = intersected_proxy['color']
    
    # Clean up
    eval_obj.to_mesh_clear()
    
    return vertex_colors


def is_point_inside_mesh(point, bvh, max_distance=10.0):
    """
    Check if a point is inside a mesh using ray casting.
    
    Args:
        point: World coordinate point
        bvh: BVH tree of the mesh
        max_distance: Maximum ray distance
        
    Returns:
        True if point is inside mesh
    """
    # Cast rays in multiple directions and count intersections
    directions = [
        Vector((1, 0, 0)),
        Vector((-1, 0, 0)),
        Vector((0, 1, 0)),
        Vector((0, -1, 0)),
        Vector((0, 0, 1)),
        Vector((0, 0, -1))
    ]
    
    inside_count = 0
    
    for direction in directions:
        # Cast ray
        hit, _, _, _ = bvh.ray_cast(point, direction, max_distance)
        
        if hit:
            # Cast ray in opposite direction
            hit_back, _, _, _ = bvh.ray_cast(point, -direction, max_distance)
            
            if hit_back:
                inside_count += 1
    
    # Point is inside if most rays hit in both directions
    return inside_count >= 3


def apply_vertex_colors(obj, vertex_colors, blend_strength):
    """
    Apply vertex colors to an object using vertex painting.
    
    Args:
        obj: Blender object
        vertex_colors: Dictionary mapping vertex indices to colors
        blend_strength: Blending strength (0-1)
    """
    # Ensure object is in Edit mode for vertex color operations
    current_mode = obj.mode
    
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    
    # Get or create vertex color layer
    mesh = obj.data
    if not mesh.vertex_colors:
        mesh.vertex_colors.new(name="ProxyProjection")
    
    color_layer = mesh.vertex_colors.active
    
    # Apply colors
    for poly in mesh.polygons:
        for loop_index in poly.loop_indices:
            vertex_index = mesh.loops[loop_index].vertex_index
            
            if vertex_index in vertex_colors:
                proxy_color = vertex_colors[vertex_index]
                
                # Get current color (if any)
                current_color = color_layer.data[loop_index].color
                
                # Blend colors
                blended_color = blend_colors(current_color, proxy_color, blend_strength)
                color_layer.data[loop_index].color = blended_color
    
    # Return to original mode
    bpy.ops.object.mode_set(mode=current_mode)


def blend_colors(color1, color2, blend_factor):
    """
    Blend two colors with specified factor.
    
    Args:
        color1: Base color (RGBA)
        color2: Overlay color (RGBA) 
        blend_factor: Blend factor (0-1)
        
    Returns:
        Blended color (RGBA)
    """
    return (
        color1[0] * (1 - blend_factor) + color2[0] * blend_factor,
        color1[1] * (1 - blend_factor) + color2[1] * blend_factor,
        color1[2] * (1 - blend_factor) + color2[2] * blend_factor,
        color1[3] * (1 - blend_factor) + color2[3] * blend_factor
    )


def setup_vertex_color_material(obj):
    """
    Setup material to use vertex colors.
    
    Args:
        obj: Blender object
    """
    if not obj.data.materials:
        # Create new material
        mat = bpy.data.materials.new(name=f"{obj.name}_ProxyProjection")
        obj.data.materials.append(mat)
    else:
        mat = obj.data.materials[0]
    
    # Enable nodes
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    
    # Clear existing nodes
    nodes.clear()
    
    # Create nodes
    output_node = nodes.new(type='ShaderNodeOutputMaterial')
    principled_node = nodes.new(type='ShaderNodeBsdfPrincipled')
    vertex_color_node = nodes.new(type='ShaderNodeVertexColor')
    
    # Set vertex color layer name
    vertex_color_node.layer_name = "ProxyProjection"
    
    # Position nodes
    output_node.location = (300, 0)
    principled_node.location = (0, 0)
    vertex_color_node.location = (-200, 0)
    
    # Connect nodes
    links.new(vertex_color_node.outputs['Color'], principled_node.inputs['Base Color'])
    links.new(principled_node.outputs['BSDF'], output_node.inputs['Surface'])


def clear_vertex_colors(obj):
    """
    Clear vertex colors from an object.
    
    Args:
        obj: Blender object
    """
    mesh = obj.data
    
    # Remove vertex color layers
    for color_layer in mesh.vertex_colors:
        if color_layer.name == "ProxyProjection":
            mesh.vertex_colors.remove(color_layer)


def get_precision_settings(precision_level):
    """
    Get ray casting settings based on precision level.
    
    Args:
        precision_level: 'LOW', 'MEDIUM', or 'HIGH'
        
    Returns:
        Dictionary with precision settings
    """
    settings = {
        'LOW': {
            'ray_directions': 6,
            'threshold': 2,
            'batch_size': 10000
        },
        'MEDIUM': {
            'ray_directions': 6,
            'threshold': 3,
            'batch_size': 5000
        },
        'HIGH': {
            'ray_directions': 12,
            'threshold': 6,
            'batch_size': 1000
        }
    }
    
    return settings.get(precision_level, settings['MEDIUM'])
