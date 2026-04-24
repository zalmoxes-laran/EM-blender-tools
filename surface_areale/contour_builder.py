"""
Contour Builder for Surface Areale.
Converts Grease Pencil strokes into a clean, closed, resampled contour
projected onto the target RM surface.
"""

from mathutils import Vector
from mathutils.bvhtree import BVHTree
import math
import numpy as np


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


# ══════════════════════════════════════════════════════════════════════
# CONTOUR VALIDATION & AUTO-FIX
# ══════════════════════════════════════════════════════════════════════

def validate_contour(points, auto_fix=True):
    """
    Validate a closed contour and optionally auto-fix problems.

    Checks: duplicate consecutive points, self-intersections, open contours,
    minimum point count.

    Args:
        points: List of Vector (closed contour)
        auto_fix: If True, attempt to repair issues

    Returns:
        Tuple (cleaned_points, warnings: list[str], is_valid: bool)
    """
    warnings = []
    pts = [p.copy() for p in points]

    # ── Check 1: Remove duplicate consecutive points ──────────────────
    if auto_fix and len(pts) > 1:
        cleaned = [pts[0]]
        removed = 0
        for i in range(1, len(pts)):
            if (pts[i] - pts[i - 1]).length > 1e-6:
                cleaned.append(pts[i])
            else:
                removed += 1
        # Also check last-to-first wrap
        if len(cleaned) > 1 and (cleaned[-1] - cleaned[0]).length < 1e-6:
            cleaned.pop()
            removed += 1
        if removed > 0:
            warnings.append(f"Removed {removed} duplicate consecutive point(s)")
        pts = cleaned

    # ── Check 2: Minimum point count (early) ─────────────────────────
    if len(pts) < 3:
        return pts, ["Contour has fewer than 3 points"], False

    # ── Check 3: Detect and resolve self-intersections ────────────────
    if auto_fix:
        pts_2d, axes, centroid = _project_to_2d(pts)
        intersections = _find_self_intersections(pts_2d)

        if len(intersections) > 3:
            warnings.append(
                f"Contour has {len(intersections)} self-intersections "
                f"(too complex to auto-fix, please redraw)")
            # Still try to fix the first one
            intersections = intersections[:1]

        if intersections:
            warnings.append(
                f"Fixed {len(intersections)} self-intersection(s)")
            pts_2d = _resolve_self_intersections(pts_2d, intersections)
            # Convert back to 3D
            pts = _unproject_from_2d(pts_2d, axes, centroid)

    # ── Check 4: Warn about open contour ─────────────────────────────
    if len(pts) >= 3:
        gap = (pts[0] - pts[-1]).length
        # Estimate average segment length for threshold
        total_len = sum((pts[i + 1] - pts[i]).length for i in range(len(pts) - 1))
        avg_seg = total_len / max(len(pts) - 1, 1)
        if gap > avg_seg * 5:
            warnings.append(
                f"Contour appears open (gap={gap:.4f}m), auto-closed")

    # ── Final check ──────────────────────────────────────────────────
    if len(pts) < 3:
        return pts, warnings + ["Contour degenerate after cleanup"], False

    return pts, warnings, True


def _project_to_2d(points):
    """
    Project 3D points onto their best-fit plane (PCA).

    Returns:
        Tuple (points_2d: list[Vector], axes: tuple, centroid: Vector)
        axes = (axis_u, axis_v, normal) for unprojection
    """
    coords = np.array([(p.x, p.y, p.z) for p in points])
    centroid_np = coords.mean(axis=0)
    centered = coords - centroid_np
    cov = np.cov(centered.T)
    eigenvalues, eigenvectors = np.linalg.eigh(cov)
    idx = eigenvalues.argsort()[::-1]
    eigenvectors = eigenvectors[:, idx]

    centroid = Vector(centroid_np)
    axis_u = Vector(eigenvectors[:, 0]).normalized()
    axis_v = Vector(eigenvectors[:, 1]).normalized()
    normal = Vector(eigenvectors[:, 2]).normalized()

    points_2d = []
    for p in points:
        d = p - centroid
        points_2d.append(Vector((d.dot(axis_u), d.dot(axis_v))))

    return points_2d, (axis_u, axis_v, normal), centroid


def _unproject_from_2d(points_2d, axes, centroid):
    """Convert 2D PCA-projected points back to 3D."""
    axis_u, axis_v, normal = axes
    result = []
    for p2 in points_2d:
        result.append(centroid + axis_u * p2.x + axis_v * p2.y)
    return result


def _find_self_intersections(points_2d):
    """
    Find self-intersection points in a 2D closed polygon.

    Returns list of (seg_i, seg_j, intersection_point_2d) tuples.
    Only checks non-adjacent segment pairs.
    """
    n = len(points_2d)
    intersections = []

    for i in range(n):
        a1 = points_2d[i]
        a2 = points_2d[(i + 1) % n]
        # Start j from i+2 to skip adjacent segments
        for j in range(i + 2, n):
            # Skip if segments share an endpoint (adjacent wrap-around)
            if j == (i - 1) % n or (i == 0 and j == n - 1):
                continue
            b1 = points_2d[j]
            b2 = points_2d[(j + 1) % n]
            pt = _segment_intersection_2d(a1, a2, b1, b2)
            if pt is not None:
                intersections.append((i, j, pt))

    return intersections


def _segment_intersection_2d(a1, a2, b1, b2):
    """
    Find intersection point of two 2D line segments.
    Returns Vector or None if no intersection.
    """
    dx1 = a2.x - a1.x
    dy1 = a2.y - a1.y
    dx2 = b2.x - b1.x
    dy2 = b2.y - b1.y

    denom = dx1 * dy2 - dy1 * dx2
    if abs(denom) < 1e-10:
        return None  # Parallel or collinear

    t = ((b1.x - a1.x) * dy2 - (b1.y - a1.y) * dx2) / denom
    u = ((b1.x - a1.x) * dy1 - (b1.y - a1.y) * dx1) / denom

    eps = 1e-6
    if eps < t < 1.0 - eps and eps < u < 1.0 - eps:
        ix = a1.x + t * dx1
        iy = a1.y + t * dy1
        return Vector((ix, iy))

    return None


def _resolve_self_intersections(points_2d, intersections):
    """
    Resolve self-intersections by keeping the larger loop.

    For each intersection, splits the contour at the crossing point
    and keeps the sub-loop with the larger signed area.
    """
    # Process only the first intersection (iterative for multiple would be complex)
    if not intersections:
        return points_2d

    seg_i, seg_j, ix_pt = intersections[0]
    n = len(points_2d)

    # Insert intersection point, creating two loops:
    # Loop A: ix_pt → points[seg_i+1..seg_j] → ix_pt
    # Loop B: ix_pt → points[seg_j+1..seg_i] → ix_pt (wrapping around)

    loop_a = [ix_pt]
    idx = (seg_i + 1) % n
    while idx != (seg_j + 1) % n:
        loop_a.append(points_2d[idx])
        idx = (idx + 1) % n

    loop_b = [ix_pt]
    idx = (seg_j + 1) % n
    while idx != (seg_i + 1) % n:
        loop_b.append(points_2d[idx])
        idx = (idx + 1) % n

    # Keep the loop with larger area
    area_a = abs(_signed_area_2d(loop_a))
    area_b = abs(_signed_area_2d(loop_b))

    return loop_a if area_a >= area_b else loop_b


def _signed_area_2d(points_2d):
    """Compute signed area of a 2D polygon using the shoelace formula."""
    n = len(points_2d)
    if n < 3:
        return 0.0
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += points_2d[i].x * points_2d[j].y
        area -= points_2d[j].x * points_2d[i].y
    return area / 2.0


def _point_in_polygon_2d(point, polygon):
    """
    Winding number test for point-in-polygon (robust for concave polygons).

    Args:
        point: Vector (2D)
        polygon: list of Vector (2D)

    Returns: True if point is inside polygon
    """
    n = len(polygon)
    winding = 0
    for i in range(n):
        y1 = polygon[i].y
        y2 = polygon[(i + 1) % n].y
        if y1 <= point.y:
            if y2 > point.y:
                # Upward crossing
                if _is_left(polygon[i], polygon[(i + 1) % n], point) > 0:
                    winding += 1
        else:
            if y2 <= point.y:
                # Downward crossing
                if _is_left(polygon[i], polygon[(i + 1) % n], point) < 0:
                    winding -= 1
    return winding != 0


def _is_left(p0, p1, p2):
    """Test if point p2 is left of the line from p0 to p1."""
    return (p1.x - p0.x) * (p2.y - p0.y) - (p2.x - p0.x) * (p1.y - p0.y)


# ══════════════════════════════════════════════════════════════════════
# MULTI-CONTOUR SUPPORT (annular shapes)
# ══════════════════════════════════════════════════════════════════════

def group_contour_strokes(strokes):
    """
    Group strokes into separate contours based on endpoint proximity.
    Strokes that form closed loops are their own group. Open strokes
    are merged greedily by closest endpoint.

    Args:
        strokes: List of strokes (each a list of Vector)

    Returns:
        List of contour groups, each group is a list of strokes
    """
    if not strokes:
        return []
    if len(strokes) == 1:
        return [strokes]

    # Separate closed loops from open strokes
    closed_threshold = 0.01  # 1cm
    closed_groups = []
    open_strokes = []

    for stroke in strokes:
        if len(stroke) >= 3 and (stroke[0] - stroke[-1]).length < closed_threshold:
            closed_groups.append([stroke])
        else:
            open_strokes.append(stroke)

    if not open_strokes:
        return closed_groups

    # Group open strokes by endpoint proximity
    # Use a greedy approach: build groups by merging strokes whose
    # endpoints are close to each other
    groups = []
    remaining = list(open_strokes)

    while remaining:
        group = [remaining.pop(0)]
        changed = True
        while changed:
            changed = False
            for i in range(len(remaining) - 1, -1, -1):
                stroke = remaining[i]
                # Check if this stroke connects to any stroke in the group
                group_start = group[0][0]
                group_end = group[-1][-1]
                merge_threshold = closed_threshold * 5  # 5cm

                d_end_to_start = (group_end - stroke[0]).length
                d_end_to_end = (group_end - stroke[-1]).length
                d_start_to_end = (group_start - stroke[-1]).length
                d_start_to_start = (group_start - stroke[0]).length

                min_d = min(d_end_to_start, d_end_to_end,
                            d_start_to_end, d_start_to_start)

                if min_d < merge_threshold:
                    remaining.pop(i)
                    group.append(stroke)
                    changed = True

        groups.append(group)

    return closed_groups + groups


def classify_contours(processed_contours, whisker_point):
    """
    Classify multiple contour loops as outer boundary or inner holes.

    The outer contour is the one whose 2D projection contains the whisker_point
    and has the largest absolute area. All others are holes.

    Args:
        processed_contours: List of contour point lists (each already closed/resampled)
        whisker_point: Vector, midpoint of the whisker stroke

    Returns:
        Tuple (outer_contour: list[Vector], holes: list[list[Vector]])
    """
    if len(processed_contours) == 1:
        return processed_contours[0], []

    # Project all contours + whisker onto a shared PCA plane
    # Use the largest contour's points to define the plane
    all_points = [p for c in processed_contours for p in c]
    pts_2d_all, axes, centroid = _project_to_2d(all_points)

    # Project whisker point
    axis_u, axis_v, normal = axes
    wd = whisker_point - centroid
    whisker_2d = Vector((wd.dot(axis_u), wd.dot(axis_v)))

    # Project each contour separately
    contour_2d_list = []
    offset = 0
    for contour in processed_contours:
        n = len(contour)
        contour_2d = pts_2d_all[offset:offset + n]
        contour_2d_list.append(contour_2d)
        offset += n

    # Find the outer contour: contains whisker + largest area
    outer_idx = -1
    outer_area = 0.0

    for i, c2d in enumerate(contour_2d_list):
        if _point_in_polygon_2d(whisker_2d, c2d):
            area = abs(_signed_area_2d(c2d))
            if area > outer_area:
                outer_area = area
                outer_idx = i

    # Fallback: if whisker is not inside any contour, pick the largest
    if outer_idx == -1:
        for i, c2d in enumerate(contour_2d_list):
            area = abs(_signed_area_2d(c2d))
            if area > outer_area:
                outer_area = area
                outer_idx = i

    if outer_idx == -1:
        outer_idx = 0

    outer = processed_contours[outer_idx]
    holes = [c for i, c in enumerate(processed_contours) if i != outer_idx]

    return outer, holes


# ══════════════════════════════════════════════════════════════════════
# INTERNAL HELPERS
# ══════════════════════════════════════════════════════════════════════

def _stroke_length(stroke):
    """Calculate total length of a stroke."""
    length = 0.0
    for i in range(len(stroke) - 1):
        length += (stroke[i + 1] - stroke[i]).length
    return length
