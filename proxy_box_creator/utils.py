"""
Utility functions for the Proxy Box Creator
FIXED: Now generates HORIZONTAL (non-inclined) proxies
"""

import bpy
from mathutils import Vector
from typing import Optional, Dict, List, Tuple
import mathutils


def get_document_from_paradata_manager(context) -> Optional[Tuple[str, str]]:
    """
    Get the currently selected document from the Paradata Manager.
    
    Returns:
        Tuple of (document_id, document_name) or None
    """
    try:
        em_tools = context.scene.em_tools
        paradata_manager = em_tools.paradata_manager
        
        if paradata_manager.selected_document_index >= 0:
            doc_list = paradata_manager.document_list
            if paradata_manager.selected_document_index < len(doc_list):
                doc = doc_list[paradata_manager.selected_document_index]
                return (doc.node_id, doc.doc_name)
    except Exception as e:
        print(f"Error getting document from Paradata Manager: {e}")
    
    return None


def get_next_extractor_number(graph) -> int:
    """Get the next available extractor number in the graph."""
    if not graph:
        return 1
    
    max_num = 0
    for node_id in graph.nodes:
        # Check for extractor IDs like "D10.11"
        if '.' in node_id:
            parts = node_id.split('.')
            if len(parts) == 2:
                try:
                    # Try to parse the sub-number (after the dot)
                    sub_num = int(parts[1])
                    max_num = max(max_num, sub_num)
                except ValueError:
                    continue
    
    return max_num + 1


def get_next_combiner_number(graph) -> int:
    """Get the next available combiner number in the graph."""
    if not graph:
        return 1
    
    max_num = 0
    for node_id in graph.nodes:
        # Check for combiner IDs like "C.10"
        if node_id.startswith('C.'):
            try:
                num = int(node_id.split('.')[1])
                max_num = max(max_num, num)
            except (ValueError, IndexError):
                continue
    
    return max_num + 1


def create_extractor_node(graph, parent_doc_id: str, extractor_number: int, 
                         point_type: str, position: Vector) -> Optional[str]:
    """
    Create an extractor node in the graph.
    
    Args:
        graph: The active s3dgraphy graph
        parent_doc_id: ID of the parent document node
        extractor_number: Number for this extractor
        point_type: Type of point (e.g., "alignment_start")
        position: 3D coordinates
        
    Returns:
        Extractor node ID (e.g., "D10.11") or None on failure
    """
    if not graph:
        return None
    
    try:
        from s3dgraphy.nodes import ExtractorNode
        
        extractor_id = f"{parent_doc_id}.{extractor_number}"
        
        # Create the extractor node
        extractor = ExtractorNode(
            node_id=extractor_id,
            name=f"{point_type}_{extractor_number}"
        )
        
        # Add metadata
        extractor.attributes['point_type'] = point_type
        extractor.attributes['x'] = position.x
        extractor.attributes['y'] = position.y
        extractor.attributes['z'] = position.z
        extractor.attributes['purpose'] = "proxy_box_creator"
        
        # Add to graph
        graph.add_node(extractor)
        
        # Create edge from document to extractor
        edge_id = f"{parent_doc_id}_has_extractor_{extractor_id}"
        graph.add_edge(
            edge_id=edge_id,
            edge_source=parent_doc_id,
            edge_target=extractor_id,
            edge_type="has_extractor"
        )
        
        print(f"Created extractor: {extractor_id}")
        return extractor_id
        
    except Exception as e:
        print(f"✗ Error creating extractor: {e}")
        return None


def create_combiner_node(graph, combiner_number: int, extractor_ids: List[str]) -> Optional[str]:
    """
    Create a combiner node that connects multiple extractors.
    
    Args:
        graph: The active s3dgraphy graph
        combiner_number: Number for this combiner
        extractor_ids: List of extractor node IDs to connect
        
    Returns:
        Combiner node ID (e.g., "C.10") or None on failure
    """
    if not graph:
        return None
    
    try:
        from s3dgraphy.nodes import CombinerNode
        
        combiner_id = f"C.{combiner_number}"
        
        # Create the combiner node
        combiner = CombinerNode(
            node_id=combiner_id,
            name=combiner_id
        )
        
        # Add metadata
        combiner.attributes['extractor_count'] = len(extractor_ids)
        combiner.attributes['purpose'] = "proxy_box_creator"
        
        # Add to graph
        graph.add_node(combiner)
        
        # Create edges from extractors to combiner
        for extractor_id in extractor_ids:
            edge_id = f"{extractor_id}_has_combiner_{combiner_id}"
            graph.add_edge(
                edge_id=edge_id,
                edge_source=extractor_id,
                edge_target=combiner_id,
                edge_type="has_combiner"
            )
        
        print(f"Created combiner: {combiner_id} with {len(extractor_ids)} extractors")
        return combiner_id
        
    except Exception as e:
        print(f"✗ Error creating combiner: {e}")
        return None


def create_empty_extractor(context, extractor_id: str, position: Vector, 
                          collection_name: str = "Extractors") -> Optional[bpy.types.Object]:
    """
    Create an Empty object for visualization of the extractor point.
    
    Args:
        context: Blender context
        extractor_id: ID of the extractor (will be the object name)
        position: 3D coordinates
        collection_name: Name of collection to place the empty in
        
    Returns:
        The created Empty object or None on failure
    """
    try:
        # Create or get the Extractors collection
        if collection_name not in bpy.data.collections:
            extractors_collection = bpy.data.collections.new(collection_name)
            context.scene.collection.children.link(extractors_collection)
        else:
            extractors_collection = bpy.data.collections[collection_name]
        
        # Create the empty
        bpy.ops.object.empty_add(type='SPHERE', location=position)
        empty = context.active_object
        empty.name = extractor_id
        empty.empty_display_size = 0.1
        
        # Move to Extractors collection
        for collection in empty.users_collection:
            collection.objects.unlink(empty)
        extractors_collection.objects.link(empty)
        
        print(f"Created empty extractor: {extractor_id}")
        return empty
        
    except Exception as e:
        print(f"✗ Error creating empty: {e}")
        return None


def calculate_box_geometry(points: List[Vector]) -> Dict:
    """
    Calculate box geometry from 7 measurement points.
    
    FIXED: Now generates HORIZONTAL proxies by projecting the alignment vector 
    onto the XY plane, ignoring any vertical inclination.
    
    Point roles:
    0: alignment_start (origin)
    1: alignment_end (defines longitudinal axis - projected to XY plane)
    2: thickness (defines transverse direction)
    3: quota_min (minimum Z)
    4: quota_max (maximum Z)
    5: start_length (start of structure along axis)
    6: end_length (end of structure along axis)
    
    Args:
        points: List of 7 Vector objects
        
    Returns:
        Dictionary with:
        - vertices: List of 8 vertices for the box
        - center: Geometric center
        - dimensions: (length, width, height)
        - alignment_vector: Direction vector (horizontal)
    """
    if len(points) != 7:
        raise ValueError(f"Expected 7 points, got {len(points)}")
    
    # Extract points
    p_align_start = points[0]
    p_align_end = points[1]
    p_thickness = points[2]
    p_quota_min = points[3]
    p_quota_max = points[4]
    p_start_length = points[5]
    p_end_length = points[6]
    
    # ═══════════════════════════════════════════════════════════════════════
    # CRITICAL FIX: Project alignment vector to XY plane (make it horizontal)
    # ═══════════════════════════════════════════════════════════════════════
    
    # Calculate the alignment direction in 3D space
    alignment_3d = p_align_end - p_align_start
    
    # Project to XY plane by setting Z component to zero
    alignment_xy = Vector((alignment_3d.x, alignment_3d.y, 0.0))
    
    # Normalize to get the horizontal direction vector
    alignment_vector = alignment_xy.normalized()
    
    print(f"🔧 HORIZONTAL ALIGNMENT: Original 3D vector: {alignment_3d}")
    print(f"🔧 HORIZONTAL ALIGNMENT: Projected XY vector: {alignment_vector}")
    
    # ═══════════════════════════════════════════════════════════════════════
    # Calculate thickness vector (transverse axis = Y local)
    # Also project this to be perpendicular to horizontal alignment
    # ═══════════════════════════════════════════════════════════════════════
    
    # Project p_thickness onto the plane perpendicular to alignment_vector
    to_thickness = p_thickness - p_align_start
    
    # Project the thickness direction to XY plane as well
    to_thickness_xy = Vector((to_thickness.x, to_thickness.y, 0.0))
    
    # Remove component along alignment to get perpendicular direction
    projection_on_align = to_thickness_xy.project(alignment_vector)
    thickness_vector = (to_thickness_xy - projection_on_align).normalized()
    
    # Calculate thickness magnitude (distance from alignment line to thickness point)
    # Use the original 3D distance
    thickness = (to_thickness - to_thickness.project(alignment_3d)).length
    
    print(f"🔧 HORIZONTAL THICKNESS: Thickness vector: {thickness_vector}, magnitude: {thickness:.3f}m")
    
    # Z axis is always vertical (global Z)
    z_vector = Vector((0, 0, 1))
    
    # Calculate height (always vertical distance)
    height = p_quota_max.z - p_quota_min.z
    
    # ═══════════════════════════════════════════════════════════════════════
    # Calculate length by projecting start/end points onto HORIZONTAL alignment
    # ═══════════════════════════════════════════════════════════════════════
    
    # Project length points onto XY plane
    p_start_xy = Vector((p_start_length.x, p_start_length.y, 0.0))
    p_end_xy = Vector((p_end_length.x, p_end_length.y, 0.0))
    p_align_start_xy = Vector((p_align_start.x, p_align_start.y, 0.0))
    
    # Calculate projections along horizontal alignment
    start_proj = (p_start_xy - p_align_start_xy).project(alignment_vector)
    end_proj = (p_end_xy - p_align_start_xy).project(alignment_vector)
    
    length = (end_proj - start_proj).length
    
    print(f"🔧 HORIZONTAL LENGTH: Length: {length:.3f}m")
    
    # ═══════════════════════════════════════════════════════════════════════
    # Calculate origin (corner of box at min length, min thickness, min Z)
    # ═══════════════════════════════════════════════════════════════════════
    
    # Start from horizontal projection of p_align_start
    origin_xy = p_align_start_xy + start_proj
    
    # Set Z to minimum quota
    origin = Vector((origin_xy.x, origin_xy.y, p_quota_min.z))
    
    print(f"🔧 HORIZONTAL ORIGIN: Origin: {origin}")
    
    # ═══════════════════════════════════════════════════════════════════════
    # Calculate the 8 vertices of the box using HORIZONTAL axes
    # ═══════════════════════════════════════════════════════════════════════
    
    vertices = []
    
    # Generate vertices: 2 Z levels × 2 thickness positions × 2 length positions
    for i in range(2):  # Z levels (bottom, top)
        z_offset = i * height
        for j in range(2):  # Thickness (near, far)
            y_offset = j * thickness
            for k in range(2):  # Length (start, end)
                x_offset = k * length
                
                vertex = (
                    origin + 
                    alignment_vector * x_offset + 
                    thickness_vector * y_offset + 
                    z_vector * z_offset
                )
                vertices.append(vertex)
    
    # Calculate geometric center
    center = sum(vertices, Vector((0, 0, 0))) / len(vertices)
    
    print(f"HORIZONTAL BOX CREATED: Dimensions L×W×H = {length:.3f} × {thickness:.3f} × {height:.3f} m")
    
    return {
        'vertices': vertices,
        'center': center,
        'dimensions': (length, thickness, height),
        'alignment_vector': alignment_vector,  # Now horizontal!
        'thickness_vector': thickness_vector,  # Also horizontal!
        'z_vector': z_vector,
        'origin': origin,
        'quota_min': p_quota_min.z,
        'quota_max': p_quota_max.z
    }


def create_box_mesh(name: str, geometry: Dict, pivot_location: str = 'CENTER') -> bpy.types.Object:
    """
    Create a box mesh from calculated geometry.
    
    Args:
        name: Name for the mesh object
        geometry: Dictionary from calculate_box_geometry()
        pivot_location: 'TOP', 'CENTER', or 'BOTTOM'
        
    Returns:
        Created mesh object
    """
    # Create mesh and object
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    
    # Get vertices
    vertices = geometry['vertices']
    
    # Define faces (6 faces of the box)
    # Vertices are ordered: bottom (0-3), top (4-7)
    # Each level: near-start, near-end, far-end, far-start
    faces = [
        [0, 1, 3, 2],  # Bottom
        [4, 5, 7, 6],  # Top
        [0, 1, 5, 4],  # Front (near side)
        [2, 3, 7, 6],  # Back (far side)
        [0, 2, 6, 4],  # Left (start)
        [1, 3, 7, 5],  # Right (end)
    ]
    
    # Adjust vertices based on pivot location
    if pivot_location == 'TOP':
        pivot = Vector((geometry['center'].x, geometry['center'].y, geometry['quota_max']))
    elif pivot_location == 'BOTTOM':
        pivot = Vector((geometry['center'].x, geometry['center'].y, geometry['quota_min']))
    else:  # CENTER
        pivot = geometry['center']
    
    # Offset all vertices so pivot is at origin
    adjusted_vertices = [v - pivot for v in vertices]
    
    # Create mesh
    mesh.from_pydata(adjusted_vertices, [], faces)
    mesh.update()
    
    # Set object location to pivot point
    obj.location = pivot
    
    return obj


def get_object_under_mouse(context, event) -> Optional[bpy.types.Object]:
    """
    Raycast to find the object under the mouse cursor.
    
    Args:
        context: Blender context
        event: Modal event with mouse coordinates
        
    Returns:
        Object under cursor or None
    """
    # Get the region and region 3D
    region = context.region
    region_3d = context.space_data.region_3d
    
    # Get mouse coordinates
    coord = (event.mouse_region_x, event.mouse_region_y)
    
    # Cast ray
    view_vector = mathutils.Vector(bpy.context.region_data.view_rotation @ mathutils.Vector((0.0, 0.0, -1.0)))
    ray_origin = bpy.context.region_data.view_matrix.inverted().translation
    
    # Perform raycast
    result, location, normal, index, obj, matrix = context.scene.ray_cast(
        context.view_layer.depsgraph,
        ray_origin,
        view_vector
    )
    
    if result and obj:
        return obj
    
    return None


# Point type labels for UI
POINT_TYPE_LABELS = {
    0: "Alignment Start",
    1: "Alignment End", 
    2: "Thickness",
    3: "Quota Min",
    4: "Quota Max",
    5: "Length Start",
    6: "Length End"
}

POINT_TYPE_IDS = {
    0: "alignment_start",
    1: "alignment_end",
    2: "thickness",
    3: "quota_min",
    4: "quota_max",
    5: "length_start",
    6: "length_end"
}