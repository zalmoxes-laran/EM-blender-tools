"""
Utility functions for the Proxy Box Creator
Handles geometry calculations, graph operations, and extractor creation.
"""

import bpy
import mathutils
from mathutils import Vector
from typing import Optional, Tuple, List, Dict


def get_available_documents(graph) -> List[Tuple[str, str]]:
    """
    Get list of available DocumentNode items for dropdowns.
    
    Args:
        graph: The active s3dgraphy graph
        
    Returns:
        List of tuples (document_id, display_name)
    """
    if not graph:
        return []
    
    documents = []
    for node in graph.nodes.values():
        # Check if it's a DocumentNode (has document-like attributes)
        if hasattr(node, 'node_type') and 'Document' in node.node_type:
            doc_id = node.node_id
            doc_name = getattr(node, 'name', doc_id)
            documents.append((doc_id, f"{doc_id} - {doc_name}"))
    
    return documents


def get_document_from_paradata_manager(context) -> Optional[Tuple[str, str]]:
    """
    Get the currently selected document from the Paradata Manager's document list.
    Reads from the active element in the sources UI list (em_sources_list or em_v_sources_list).
    
    Args:
        context: Blender context
        
    Returns:
        Tuple of (document_id, document_name) or None if no selection
    """
    scene = context.scene
    
    # Determine which list to use based on streaming mode
    if hasattr(scene, 'paradata_streaming_mode') and scene.paradata_streaming_mode:
        # Use virtual/filtered lists
        source_list = scene.em_v_sources_list if hasattr(scene, 'em_v_sources_list') else None
        source_index = scene.em_v_sources_list_index if hasattr(scene, 'em_v_sources_list_index') else -1
    else:
        # Use full lists
        source_list = scene.em_sources_list if hasattr(scene, 'em_sources_list') else None
        source_index = scene.em_sources_list_index if hasattr(scene, 'em_sources_list_index') else -1
    
    # Check if there's a valid selection in the sources list
    if source_list and source_index >= 0 and source_index < len(source_list):
        selected_source = source_list[source_index]
        
        # The source item should have name and potentially id_node
        if hasattr(selected_source, 'name'):
            doc_name = selected_source.name
            # Try to get the node ID if available
            doc_id = getattr(selected_source, 'id_node', doc_name)
            
            return (doc_id, doc_name)
    
    return None


def get_next_extractor_number(graph, document_id: str) -> int:
    """
    Find the last extractor number for a given document and return the next one.
    
    Args:
        graph: The active s3dgraphy graph
        document_id: ID of the document node (e.g., "D10")
        
    Returns:
        Next extractor number (e.g., if last is D10.10, returns 11)
    """
    if not graph:
        return 1
    
    max_number = 0
    prefix = f"{document_id}."
    
    # Scan all nodes looking for extractors belonging to this document
    for node in graph.nodes.values():
        node_id = node.node_id
        
        # Check if this is an extractor for our document
        if node_id.startswith(prefix):
            try:
                # Extract the number after the dot
                number_part = node_id[len(prefix):]
                # Handle cases like "D10.11" vs "D10.11.extra"
                if '.' in number_part:
                    number_part = number_part.split('.')[0]
                number = int(number_part)
                max_number = max(max_number, number)
            except (ValueError, IndexError):
                continue
    
    return max_number + 1


def get_next_combiner_number(graph) -> int:
    """
    Find the last combiner number in the graph and return the next one.
    
    Args:
        graph: The active s3dgraphy graph
        
    Returns:
        Next combiner number (e.g., if last is C.9, returns 10)
    """
    if not graph:
        return 1
    
    max_number = 0
    
    # Scan all nodes looking for combiners
    for node in graph.nodes.values():
        node_id = node.node_id
        
        # Check if this is a combiner (starts with "C.")
        if node_id.startswith("C."):
            try:
                number_part = node_id[2:]  # Remove "C."
                # Handle cases like "C.10" vs "C.10.extra"
                if '.' in number_part:
                    number_part = number_part.split('.')[0]
                number = int(number_part)
                max_number = max(max_number, number)
            except (ValueError, IndexError):
                continue
    
    return max_number + 1


def create_extractor_node(graph, document_id: str, extractor_number: int, 
                         position: Vector, point_type: str) -> Optional[str]:
    """
    Create an ExtractorNode in the graph with metadata.
    
    Args:
        graph: The active s3dgraphy graph
        document_id: ID of the source document
        extractor_number: Number for this extractor
        position: 3D coordinates
        point_type: Semantic type (alignment_start, thickness, etc.)
        
    Returns:
        Extractor node ID (e.g., "D10.11") or None on failure
    """
    if not graph:
        return None
    
    try:
        from s3dgraphy.nodes import ExtractorNode
        
        extractor_id = f"{document_id}.{extractor_number}"
        
        # Create the extractor node
        extractor = ExtractorNode(
            node_id=extractor_id,
            name=extractor_id
        )
        
        # Add metadata as attributes
        extractor.attributes['point_type'] = point_type
        extractor.attributes['coordinates'] = f"{position.x:.4f},{position.y:.4f},{position.z:.4f}"
        extractor.attributes['source_document'] = document_id
        
        # Add to graph
        graph.add_node(extractor)
        
        # Create edge from document to extractor
        edge_id = f"{document_id}_has_extractor_{extractor_id}"
        graph.add_edge(
            edge_id=edge_id,
            edge_source=document_id,
            edge_target=extractor_id,
            edge_type="has_extractor"
        )
        
        print(f"✓ Created extractor: {extractor_id} ({point_type})")
        return extractor_id
        
    except Exception as e:
        print(f"✗ Error creating extractor: {e}")
        return None


def create_combiner_node(graph, combiner_number: int, extractor_ids: List[str]) -> Optional[str]:
    """
    Create a CombinerNode and connect it to all extractors.
    
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
        
        print(f"✓ Created combiner: {combiner_id} with {len(extractor_ids)} extractors")
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
        
        print(f"✓ Created empty extractor: {extractor_id}")
        return empty
        
    except Exception as e:
        print(f"✗ Error creating empty: {e}")
        return None


def calculate_box_geometry(points: List[Vector]) -> Dict:
    """
    Calculate box geometry from 7 measurement points.
    
    Point roles:
    0: alignment_start (origin)
    1: alignment_end (defines longitudinal axis)
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
        - alignment_vector: Direction vector
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
    
    # Calculate alignment vector (longitudinal axis = X local)
    alignment_vector = (p_align_end - p_align_start).normalized()
    
    # Calculate thickness vector (transverse axis = Y local)
    # Project p_thickness onto the plane perpendicular to alignment_vector
    to_thickness = p_thickness - p_align_start
    projection_on_align = to_thickness.project(alignment_vector)
    thickness_vector = (to_thickness - projection_on_align).normalized()
    
    # Calculate thickness magnitude (distance from alignment line to thickness point)
    thickness = (to_thickness - projection_on_align).length
    
    # Z axis is vertical (global Z)
    z_vector = Vector((0, 0, 1))
    
    # Calculate height
    height = p_quota_max.z - p_quota_min.z
    
    # Calculate length (project start/end points onto alignment vector)
    start_proj = (p_start_length - p_align_start).project(alignment_vector)
    end_proj = (p_end_length - p_align_start).project(alignment_vector)
    
    length = (end_proj - start_proj).length
    
    # Calculate origin (corner of box at min length, min thickness, min Z)
    # Start from p_align_start, move along alignment to start_length projection
    origin = p_align_start + start_proj
    origin.z = p_quota_min.z
    
    # Calculate the 8 vertices of the box
    # Local coordinates relative to origin
    vertices = []
    
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
    
    return {
        'vertices': vertices,
        'center': center,
        'dimensions': (length, thickness, height),
        'alignment_vector': alignment_vector,
        'thickness_vector': thickness_vector,
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
