"""
Contour Builder for Surface Areale.
Converts Grease Pencil strokes into a clean, closed, resampled contour
projected onto the target RM surface.
"""

from mathutils import Vector
from mathutils.bvhtree import BVHTree
import math


def extract_gp_strokes(gp_obj):
    """
    Extract all strokes from a Grease Pencil object as lists of 3D points.

    Args:
        gp_obj: Blender GreasePencil object

    Returns:
        List of strokes, each stroke is a list of Vector
    """
    strokes_data = []

    if not gp_obj or not gp_obj.data:
        return strokes_data

    gp_data = gp_obj.data
    matrix = gp_obj.matrix_world

    for layer in gp_data.layers:
        for frame in layer.frames:
            # GP v3 (Blender 4.3+): frame.drawing.strokes
            if hasattr(frame, 'drawing') and frame.drawing:
                drawing = frame.drawing
                if hasattr(drawing, 'strokes'):
                    for stroke in drawing.strokes:
                        points = _extract_stroke_points(stroke, matrix)
                        if len(points) >= 2:
                            strokes_data.append(points)
            # Legacy fallback: frame.strokes
            elif hasattr(frame, 'strokes'):
                for stroke in frame.strokes:
                    points = _extract_stroke_points(stroke, matrix)
                    if len(points) >= 2:
                        strokes_data.append(points)

    return strokes_data


def _extract_stroke_points(stroke, matrix):
    """Extract world-space points from a GP stroke, handling API variations."""
    points = []
    for point in stroke.points:
        # GP v3 uses 'position', legacy uses 'co'
        if hasattr(point, 'position'):
            co = Vector(point.position)
        elif hasattr(point, 'co'):
            co = Vector(point.co)
        else:
            continue
        world_co = matrix @ co
        points.append(world_co)
    return points


def identify_whisker(strokes):
    """
    Separate contour strokes from the whisker stroke.
    The whisker is identified as the shortest stroke (or the last one drawn).

    Args:
        strokes: List of strokes (each a list of Vector)

    Returns:
        Tuple (contour_strokes, whisker_point)
        whisker_point is the midpoint of the whisker stroke
    """
    if len(strokes) < 2:
        raise ValueError("At least 2 strokes required: contour + whisker")

    # Find the shortest stroke — that's the whisker
    min_len = float('inf')
    whisker_idx = -1
    for i, stroke in enumerate(strokes):
        stroke_length = _stroke_length(stroke)
        if stroke_length < min_len:
            min_len = stroke_length
            whisker_idx = i

    whisker_stroke = strokes[whisker_idx]
    contour_strokes = [s for i, s in enumerate(strokes) if i != whisker_idx]

    # Whisker point = midpoint of whisker stroke
    mid_idx = len(whisker_stroke) // 2
    whisker_point = whisker_stroke[mid_idx].copy()

    return contour_strokes, whisker_point


def concatenate_strokes(strokes):
    """
    Concatenate multiple strokes into a single ordered contour by
    connecting strokes based on proximity of their endpoints.

    Args:
        strokes: List of strokes (each a list of Vector)

    Returns:
        Single ordered list of Vector forming the contour
    """
    if not strokes:
        return []
    if len(strokes) == 1:
        return list(strokes[0])

    # Start with the first stroke
    result = list(strokes[0])
    remaining = list(strokes[1:])

    while remaining:
        best_idx = -1
        best_dist = float('inf')
        best_reverse = False

        end_point = result[-1]

        for i, stroke in enumerate(remaining):
            # Distance from our end to stroke start
            d_start = (end_point - stroke[0]).length
            # Distance from our end to stroke end (needs reversal)
            d_end = (end_point - stroke[-1]).length

            if d_start < best_dist:
                best_dist = d_start
                best_idx = i
                best_reverse = False

            if d_end < best_dist:
                best_dist = d_end
                best_idx = i
                best_reverse = True

        # Also check distance from our start
        start_point = result[0]
        for i, stroke in enumerate(remaining):
            d_to_start = (start_point - stroke[-1]).length
            d_to_start_rev = (start_point - stroke[0]).length

            if d_to_start < best_dist:
                best_dist = d_to_start
                best_idx = i
                best_reverse = False
                # Prepend instead of append — handled below

        chosen = remaining.pop(best_idx)
        if best_reverse:
            chosen = list(reversed(chosen))

        # Decide whether to append or prepend
        d_append = (result[-1] - chosen[0]).length
        d_prepend = (result[0] - chosen[-1]).length

        if d_prepend < d_append:
            result = list(chosen) + result
        else:
            result.extend(chosen)

    return result


def close_contour(points):
    """
    Close the contour by connecting the last point to the first.

    Args:
        points: List of Vector

    Returns:
        List of Vector with the contour closed (last point connects to first)
    """
    if len(points) < 3:
        return points

    # If first and last are already close, don't add duplicate
    if (points[0] - points[-1]).length < 1e-5:
        return points

    return points  # The closing is implicit in edge generation


def resample_contour(points, distance):
    """
    Resample a contour to have uniformly spaced points.

    Args:
        points: List of Vector (closed contour)
        distance: Target distance between consecutive points

    Returns:
        List of Vector with uniform spacing
    """
    if len(points) < 2 or distance <= 0:
        return points

    # Calculate total length including closing edge
    total_length = 0.0
    for i in range(len(points)):
        next_i = (i + 1) % len(points)
        total_length += (points[next_i] - points[i]).length

    if total_length < distance:
        return points

    # Walk along the contour and place points at uniform distance
    resampled = [points[0].copy()]
    accumulated = 0.0
    current_segment = 0
    segment_pos = 0.0  # position along current segment [0, segment_length]

    n = len(points)

    while True:
        p0 = points[current_segment]
        p1 = points[(current_segment + 1) % n]
        seg_vec = p1 - p0
        seg_len = seg_vec.length

        if seg_len < 1e-8:
            current_segment = (current_segment + 1) % n
            segment_pos = 0.0
            if current_segment == 0:
                break
            continue

        # How far to the next resample point
        remaining_to_next = distance - accumulated

        remaining_in_segment = seg_len - segment_pos

        if remaining_in_segment >= remaining_to_next:
            # Place point in this segment
            segment_pos += remaining_to_next
            t = segment_pos / seg_len
            new_point = p0.lerp(p1, t)
            resampled.append(new_point)
            accumulated = 0.0

            # Check if we've gone around
            if len(resampled) > int(total_length / distance) + 2:
                break
        else:
            # Move to next segment
            accumulated += remaining_in_segment
            current_segment = (current_segment + 1) % n
            segment_pos = 0.0
            if current_segment == 0:
                break

    return resampled


def reproject_on_surface(points, bvh_tree):
    """
    Re-project each point onto the RM surface using BVHTree.

    Args:
        points: List of Vector
        bvh_tree: BVHTree of the target RM

    Returns:
        List of tuples (position, normal) for each point
    """
    projected = []
    for point in points:
        location, normal, index, dist = bvh_tree.find_nearest(point)
        if location is not None:
            projected.append((Vector(location), Vector(normal)))
        else:
            # Fallback: keep original point with up normal
            projected.append((point.copy(), Vector((0, 0, 1))))
    return projected


def create_bvh_from_object(obj):
    """
    Create a BVHTree from a Blender mesh object in world space.
    Reuses the pattern from proxy_to_rm_projection/utils.py.

    Args:
        obj: Blender mesh object

    Returns:
        BVHTree
    """
    import bpy

    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_obj = obj.evaluated_get(depsgraph)
    mesh = eval_obj.to_mesh()

    matrix_world = obj.matrix_world
    vertices = [matrix_world @ v.co for v in mesh.vertices]

    bvh = BVHTree.FromPolygons(vertices, [p.vertices for p in mesh.polygons])

    eval_obj.to_mesh_clear()

    return bvh


def _stroke_length(stroke):
    """Calculate total length of a stroke."""
    length = 0.0
    for i in range(len(stroke) - 1):
        length += (stroke[i + 1] - stroke[i]).length
    return length
