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
                if is_point_inside_mesh(world_co, bvh, settings.max_ray_distance, settings.ray_casting_precision):
                    intersected_proxy = proxy_data
                    break  # Use first intersecting proxy
            
            if intersected_proxy:
                vertex_colors[i] = intersected_proxy['color']
    
    # Clean up
    eval_obj.to_mesh_clear()
    
    return vertex_colors


def is_point_inside_mesh(point, bvh, max_distance=10.0, precision='MEDIUM'):
    """
    Check if a point is inside a mesh using ray casting.
    
    Args:
        point: World coordinate point
        bvh: BVH tree of the mesh
        max_distance: Maximum ray distance
        precision: Precision level ('LOW', 'MEDIUM', 'HIGH')
        
    Returns:
        True if point is inside mesh
    """
    # Get precision settings
    precision_settings = get_precision_settings(precision)
    threshold = precision_settings['threshold']
    
    # Cast rays in multiple directions and count intersections
    directions = [
        Vector((1, 0, 0)),
        Vector((-1, 0, 0)),
        Vector((0, 1, 0)),
        Vector((0, -1, 0)),
        Vector((0, 0, 1)),
        Vector((0, 0, -1))
    ]
    
    # Add more directions for HIGH precision
    if precision == 'HIGH':
        directions.extend([
            Vector((1, 1, 0)).normalized(),
            Vector((1, -1, 0)).normalized(),
            Vector((-1, 1, 0)).normalized(),
            Vector((-1, -1, 0)).normalized(),
            Vector((1, 0, 1)).normalized(),
            Vector((1, 0, -1)).normalized(),
        ])
    
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
    return inside_count >= threshold


def apply_vertex_colors(obj, vertex_colors, blend_strength):
    """
    Apply vertex colors to an object using vertex painting.
    
    Args:
        obj: Blender object
        vertex_colors: Dictionary mapping vertex indices to colors
        blend_strength: Blending strength (0-1)
    """
    if not vertex_colors:
        print(f"No vertex colors to apply for {obj.name}")
        return
    
    # Store current active object and mode
    old_active = bpy.context.view_layer.objects.active
    old_mode = obj.mode if obj == old_active else 'OBJECT'
    
    try:
        # Ensure we're in object mode first
        if obj == bpy.context.view_layer.objects.active and obj.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        
        # Set as active object
        bpy.context.view_layer.objects.active = obj
        
        # Ensure object is selected
        obj.select_set(True)
        
        # Get or create vertex color layer
        mesh = obj.data
        if not mesh.vertex_colors:
            mesh.vertex_colors.new(name="ProxyProjection")
        elif "ProxyProjection" not in mesh.vertex_colors:
            mesh.vertex_colors.new(name="ProxyProjection")
        
        # Set active vertex color layer
        for vc_layer in mesh.vertex_colors:
            if vc_layer.name == "ProxyProjection":
                mesh.vertex_colors.active = vc_layer
                break
        
        color_layer = mesh.vertex_colors.active
        
        if not color_layer:
            print(f"Could not create vertex color layer for {obj.name}")
            return
        
        # Apply colors directly to mesh data (no need for Edit mode)
        colored_loops = 0
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
                    colored_loops += 1
        
        print(f"Applied vertex colors to {colored_loops} loops on {obj.name}")
        
        # Update mesh
        mesh.update()
        
    except Exception as e:
        print(f"Error applying vertex colors to {obj.name}: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        # Restore previous state
        try:
            if old_active:
                bpy.context.view_layer.objects.active = old_active
                if old_active == obj and old_mode != 'OBJECT':
                    bpy.ops.object.mode_set(mode=old_mode)
        except:
            pass


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
    try:
        # Check if object has materials
        if not obj.data.materials:
            # Create new material
            mat = bpy.data.materials.new(name=f"{obj.name}_ProxyProjection")
            obj.data.materials.append(mat)
        else:
            # Use first material or create a copy
            original_mat = obj.data.materials[0]
            if original_mat:
                # Create a modified copy if it's not already a proxy projection material
                if not original_mat.name.endswith("_ProxyProjection"):
                    mat = original_mat.copy()
                    mat.name = f"{obj.name}_ProxyProjection"
                    obj.data.materials[0] = mat
                else:
                    mat = original_mat
            else:
                # Slot exists but is empty
                mat = bpy.data.materials.new(name=f"{obj.name}_ProxyProjection")
                obj.data.materials[0] = mat
        
        # Enable nodes
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        
        # Check if vertex color node already exists
        vertex_color_node = None
        for node in nodes:
            if node.type == 'VERTEX_COLOR' and node.layer_name == "ProxyProjection":
                vertex_color_node = node
                break
        
        # If no vertex color node exists, set up the material
        if not vertex_color_node:
            # Find or create principled BSDF
            principled_node = None
            for node in nodes:
                if node.type == 'BSDF_PRINCIPLED':
                    principled_node = node
                    break
            
            if not principled_node:
                # Clear and recreate nodes if corrupted
                nodes.clear()
                output_node = nodes.new(type='ShaderNodeOutputMaterial')
                principled_node = nodes.new(type='ShaderNodeBsdfPrincipled')
                output_node.location = (300, 0)
                principled_node.location = (0, 0)
                links.new(principled_node.outputs['BSDF'], output_node.inputs['Surface'])
            
            # Create vertex color node
            vertex_color_node = nodes.new(type='ShaderNodeVertexColor')
            vertex_color_node.layer_name = "ProxyProjection"
            vertex_color_node.location = (-200, 0)
            
            # Connect vertex color to base color
            links.new(vertex_color_node.outputs['Color'], principled_node.inputs['Base Color'])
            
            print(f"Set up vertex color material for {obj.name}")
        
    except Exception as e:
        print(f"Error setting up vertex color material for {obj.name}: {e}")
        import traceback
        traceback.print_exc()


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


def apply_shader_projection(obj, vertex_colors, settings):
    """
    Apply projection using shader nodes - much faster than vertex painting.
    OPTIMIZED: Processes all proxy colors for each mesh in one pass.
    
    Args:
        obj: Blender object
        vertex_colors: Dictionary mapping vertex indices to colors
        settings: Projection settings
    """
    if not vertex_colors:
        print(f"No vertex colors to apply for {obj.name}")
        return
    
    try:
        # OTTIMIZZAZIONE: Analizza tutti i colori proxy presenti
        proxy_colors_analysis = analyze_proxy_colors_distribution(vertex_colors)
        
        if len(proxy_colors_analysis['unique_colors']) == 1:
            # Caso semplice: un solo colore proxy
            proxy_color = proxy_colors_analysis['dominant_color']
            setup_simple_shader_projection_material(obj, proxy_color, settings.blend_strength)
        else:
            # Caso complesso: multipli colori proxy - usa sistema avanzato
            setup_multi_proxy_shader_material(obj, proxy_colors_analysis, settings.blend_strength)
        
        color_count = len(proxy_colors_analysis['unique_colors'])
        print(f"Applied shader projection to {obj.name} with {color_count} proxy color(s)")
        
    except Exception as e:
        print(f"Error applying shader projection to {obj.name}: {e}")
        import traceback
        traceback.print_exc()


def analyze_proxy_colors_distribution(vertex_colors):
    """
    Analyze the distribution of proxy colors in the vertex color data.
    
    Args:
        vertex_colors: Dictionary mapping vertex indices to colors
        
    Returns:
        Dictionary with color analysis
    """
    color_counts = {}
    total_vertices = len(vertex_colors)
    
    # Count occurrences of each color
    for color in vertex_colors.values():
        color_key = tuple(color)  # Make it hashable
        color_counts[color_key] = color_counts.get(color_key, 0) + 1
    
    # Find dominant color (most frequent)
    dominant_color_key = max(color_counts.keys(), key=lambda k: color_counts[k])
    dominant_coverage = color_counts[dominant_color_key] / total_vertices
    
    # Sort colors by frequency
    sorted_colors = sorted(color_counts.items(), key=lambda x: x[1], reverse=True)
    
    return {
        'unique_colors': list(color_counts.keys()),
        'color_counts': color_counts,
        'dominant_color': dominant_color_key,
        'dominant_coverage': dominant_coverage,
        'sorted_colors': sorted_colors,
        'total_vertices': total_vertices
    }


def setup_simple_shader_projection_material(obj, proxy_color, blend_strength):
    """
    Setup simple shader material for single proxy color.
    
    Args:
        obj: Blender object
        proxy_color: RGBA color from proxy
        blend_strength: Blend factor (0-1)
    """
    # Usa la funzione esistente per caso semplice
    setup_shader_projection_material(obj, proxy_color, blend_strength)


def setup_multi_proxy_shader_material(obj, color_analysis, blend_strength):
    """
    Setup advanced shader material for multiple proxy colors.
    Creates a more sophisticated node setup that handles multiple colors.
    
    Args:
        obj: Blender object
        color_analysis: Dictionary with color distribution analysis
        blend_strength: Blend factor (0-1)
    """
    try:
        # Check if object has materials
        if not obj.data.materials:
            mat = bpy.data.materials.new(name=f"{obj.name}_RMColoring_Multi")
            obj.data.materials.append(mat)
        else:
            original_mat = obj.data.materials[0]
            if original_mat:
                if not original_mat.name.endswith("_RMColoring_Multi"):
                    mat = original_mat.copy()
                    mat.name = f"{obj.name}_RMColoring_Multi"
                    obj.data.materials[0] = mat
                else:
                    mat = original_mat
            else:
                mat = bpy.data.materials.new(name=f"{obj.name}_RMColoring_Multi")
                obj.data.materials[0] = mat
        
        # Enable nodes
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        
        # Check if multi-proxy setup already exists
        existing_setup = any(node.name.startswith("RMColoring_Multi") for node in nodes)
        
        if not existing_setup:
            # Find or create principled BSDF
            principled_node = None
            for node in nodes:
                if node.type == 'BSDF_PRINCIPLED':
                    principled_node = node
                    break
            
            if not principled_node:
                nodes.clear()
                output_node = nodes.new(type='ShaderNodeOutputMaterial')
                principled_node = nodes.new(type='ShaderNodeBsdfPrincipled')
                output_node.location = (500, 0)
                principled_node.location = (250, 0)
                links.new(principled_node.outputs['BSDF'], output_node.inputs['Surface'])
            
            # Store original base color
            original_base_color = principled_node.inputs['Base Color'].default_value[:]
            
            # Create averaged color from all proxies (weighted by coverage)
            weighted_color = calculate_weighted_average_color(color_analysis)
            
            # Create proxy color node for weighted average
            proxy_color_node = nodes.new(type='ShaderNodeRGB')
            proxy_color_node.name = "RMColoring_Multi_ProxyColor"
            proxy_color_node.outputs[0].default_value = weighted_color
            proxy_color_node.location = (-300, 100)
            
            # Create original color node
            original_color_node = nodes.new(type='ShaderNodeRGB')
            original_color_node.name = "RMColoring_Multi_Original"
            original_color_node.outputs[0].default_value = original_base_color
            original_color_node.location = (-300, -100)
            
            # Create mix node
            mix_node = nodes.new(type='ShaderNodeMix')
            mix_node.data_type = 'RGBA'
            mix_node.blend_type = 'MIX'
            mix_node.name = "RMColoring_Multi_Mix"
            mix_node.location = (-50, 0)
            
            # Set blend strength
            if 'Factor' in mix_node.inputs:
                mix_node.inputs['Factor'].default_value = blend_strength
            elif 'Fac' in mix_node.inputs:
                mix_node.inputs['Fac'].default_value = blend_strength
            else:
                mix_node.inputs[0].default_value = blend_strength
            
            # Connect nodes
            if 'A' in mix_node.inputs and 'B' in mix_node.inputs:
                links.new(original_color_node.outputs['Color'], mix_node.inputs['A'])
                links.new(proxy_color_node.outputs['Color'], mix_node.inputs['B'])
                links.new(mix_node.outputs['Result'], principled_node.inputs['Base Color'])
            else:
                # Fallback for different Blender versions
                links.new(original_color_node.outputs['Color'], mix_node.inputs[1])
                links.new(proxy_color_node.outputs['Color'], mix_node.inputs[2])
                links.new(mix_node.outputs[0], principled_node.inputs['Base Color'])
            
            print(f"Set up multi-proxy shader material for {obj.name}")
        else:
            # Update existing multi-proxy setup
            weighted_color = calculate_weighted_average_color(color_analysis)
            
            for node in nodes:
                if node.name == "RMColoring_Multi_ProxyColor":
                    node.outputs[0].default_value = weighted_color
                elif node.name == "RMColoring_Multi_Mix":
                    if 'Factor' in node.inputs:
                        node.inputs['Factor'].default_value = blend_strength
                    elif 'Fac' in node.inputs:
                        node.inputs['Fac'].default_value = blend_strength
                    else:
                        node.inputs[0].default_value = blend_strength
        
    except Exception as e:
        print(f"Error setting up multi-proxy shader material for {obj.name}: {e}")
        import traceback
        traceback.print_exc()


def calculate_weighted_average_color(color_analysis):
    """
    Calculate weighted average color based on proxy coverage.
    
    Args:
        color_analysis: Dictionary with color distribution analysis
        
    Returns:
        Weighted average RGBA color tuple
    """
    total_weight = 0
    weighted_r = 0
    weighted_g = 0
    weighted_b = 0
    weighted_a = 0
    
    for color_tuple, count in color_analysis['color_counts'].items():
        weight = count / color_analysis['total_vertices']
        total_weight += weight
        
        weighted_r += color_tuple[0] * weight
        weighted_g += color_tuple[1] * weight
        weighted_b += color_tuple[2] * weight
        weighted_a += color_tuple[3] * weight
    
    if total_weight > 0:
        return (
            weighted_r / total_weight,
            weighted_g / total_weight,
            weighted_b / total_weight,
            weighted_a / total_weight
        )
    else:
        return (0.5, 0.5, 0.5, 1.0)


def setup_shader_projection_material(obj, proxy_color, blend_strength):
    """
    Setup material with shader nodes for proxy projection.
    
    Args:
        obj: Blender object
        proxy_color: RGBA color from proxy
        blend_strength: Blend factor (0-1)
    """
    try:
        # Check if object has materials
        if not obj.data.materials:
            # Create new material
            mat = bpy.data.materials.new(name=f"{obj.name}_RMColoring")
            obj.data.materials.append(mat)
        else:
            # Use first material or create a copy
            original_mat = obj.data.materials[0]
            if original_mat:
                # Create a modified copy if it's not already an RM coloring material
                if not original_mat.name.endswith("_RMColoring"):
                    mat = original_mat.copy()
                    mat.name = f"{obj.name}_RMColoring"
                    obj.data.materials[0] = mat
                else:
                    mat = original_mat
            else:
                # Slot exists but is empty
                mat = bpy.data.materials.new(name=f"{obj.name}_RMColoring")
                obj.data.materials[0] = mat
        
        # Enable nodes
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        
        # Check if RM coloring setup already exists
        rm_coloring_node = None
        for node in nodes:
            if node.type == 'RGB' and node.name.startswith("RMColoring"):
                rm_coloring_node = node
                break
        
        # If no RM coloring setup exists, create it
        if not rm_coloring_node:
            # Find or create principled BSDF
            principled_node = None
            for node in nodes:
                if node.type == 'BSDF_PRINCIPLED':
                    principled_node = node
                    break
            
            if not principled_node:
                # Clear and recreate nodes if corrupted
                nodes.clear()
                output_node = nodes.new(type='ShaderNodeOutputMaterial')
                principled_node = nodes.new(type='ShaderNodeBsdfPrincipled')
                output_node.location = (400, 0)
                principled_node.location = (150, 0)
                links.new(principled_node.outputs['BSDF'], output_node.inputs['Surface'])
            
            # Store original base color (if connected)
            original_base_color = None
            base_color_input = principled_node.inputs['Base Color']
            if base_color_input.is_linked:
                original_base_color = base_color_input.links[0].from_node
            else:
                original_base_color = base_color_input.default_value[:]
            
            # Create proxy color node
            rm_coloring_node = nodes.new(type='ShaderNodeRGB')
            rm_coloring_node.name = "RMColoring_ProxyColor"
            rm_coloring_node.outputs[0].default_value = proxy_color
            rm_coloring_node.location = (-300, 100)
            
            # Create mix node for blending
            mix_node = nodes.new(type='ShaderNodeMix')
            mix_node.data_type = 'RGBA'
            mix_node.blend_type = 'MIX'
            
            # Blender 4.0+ usa 'Factor' invece di 'Fac'
            if 'Factor' in mix_node.inputs:
                mix_node.inputs['Factor'].default_value = blend_strength
                factor_input = 'Factor'
            elif 'Fac' in mix_node.inputs:
                mix_node.inputs['Fac'].default_value = blend_strength
                factor_input = 'Fac'
            else:
                # Fallback per versioni diverse
                mix_node.inputs[0].default_value = blend_strength
                factor_input = mix_node.inputs[0].name
            
            # Input names possono essere diversi in Blender 4.4+
            if 'A' in mix_node.inputs and 'B' in mix_node.inputs:
                color1_input = mix_node.inputs['A']
                color2_input = mix_node.inputs['B']
                mix_output = mix_node.outputs['Result']
            elif 'Color1' in mix_node.inputs and 'Color2' in mix_node.inputs:
                color1_input = mix_node.inputs['Color1']
                color2_input = mix_node.inputs['Color2']
                mix_output = mix_node.outputs['Result']
            else:
                # Fallback generico
                color1_input = mix_node.inputs[1]
                color2_input = mix_node.inputs[2]
                mix_output = mix_node.outputs[0]
            
            mix_node.name = "RMColoring_Mix"
            mix_node.location = (-100, 0)
            
            # Connect proxy color to Color2 (overlay)
            links.new(rm_coloring_node.outputs['Color'], color2_input)
            
            # Connect original color to Color1 (base)
            if isinstance(original_base_color, tuple):
                # Was a default value, create RGB node
                original_color_node = nodes.new(type='ShaderNodeRGB')
                original_color_node.name = "RMColoring_Original"
                original_color_node.outputs[0].default_value = (*original_base_color[:3], 1.0)
                original_color_node.location = (-300, -100)
                links.new(original_color_node.outputs['Color'], color1_input)
            else:
                # Was connected to another node
                links.new(original_base_color.outputs[0], color1_input)
            
            # Connect mix result to principled BSDF
            links.new(mix_output, principled_node.inputs['Base Color'])
            
            print(f"Set up shader projection material for {obj.name}")
        else:
            # Update existing setup
            rm_coloring_node.outputs[0].default_value = proxy_color
            
            # Update blend strength if mix node exists
            for node in nodes:
                if node.name == "RMColoring_Mix":
                    # Gestisci diversi nomi per il factor input
                    if 'Factor' in node.inputs:
                        node.inputs['Factor'].default_value = blend_strength
                    elif 'Fac' in node.inputs:
                        node.inputs['Fac'].default_value = blend_strength
                    else:
                        # Fallback: usa il primo input (spesso è il factor)
                        node.inputs[0].default_value = blend_strength
                    break
        
    except Exception as e:
        print(f"Error setting up shader projection material for {obj.name}: {e}")
        import traceback
        traceback.print_exc()


def clear_shader_projection(obj):
    """
    Clear shader projection from an object by removing RM coloring nodes.
    
    Args:
        obj: Blender object
    """
    if not obj.data.materials:
        return
    
    for material in obj.data.materials:
        if not material or not material.use_nodes:
            continue
        
        nodes = material.node_tree.nodes
        links = material.node_tree.links
        
        # Find RM coloring nodes
        nodes_to_remove = []
        mix_node = None
        original_color_node = None
        
        for node in nodes:
            if node.name.startswith("RMColoring"):
                if "Mix" in node.name:
                    mix_node = node
                elif "Original" in node.name:
                    original_color_node = node
                else:
                    nodes_to_remove.append(node)
        
        # Restore original connection if mix node exists
        if mix_node:
            principled_node = None
            for node in nodes:
                if node.type == 'BSDF_PRINCIPLED':
                    principled_node = node
                    break
            
            if principled_node and original_color_node:
                # Reconnect original color directly
                links.new(original_color_node.outputs['Color'], 
                         principled_node.inputs['Base Color'])
            elif principled_node:
                # Reset to default color
                principled_node.inputs['Base Color'].default_value = (0.8, 0.8, 0.8, 1.0)
            
            nodes_to_remove.append(mix_node)
            if original_color_node:
                nodes_to_remove.append(original_color_node)
        
        # Remove all RM coloring nodes
        for node in nodes_to_remove:
            nodes.remove(node)


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