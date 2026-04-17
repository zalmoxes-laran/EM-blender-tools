# em_statistics/metrics.py
"""Geometry metrics: closure check, volume/weight/surface computation."""

import math
import bmesh


def is_mesh_closed(bm):
    """Verifies if a bmesh is closed, with additional safety checks."""
    try:
        return all(len(edge.link_faces) == 2 for edge in bm.edges if edge.is_valid)
    except Exception as e:
        print(f"Mesh closure check error: {e}")
        return False


def calculate_object_metrics(obj, selected_material, materials):
    """Calculate volume, weight, and surface metrics for an object.

    Returns:
        tuple: (volume, weight, measurement_type, total_surface, vertical_surface)
    """
    if not obj or obj.type != 'MESH':
        return None, None, None, None, None

    print(f"Processing object: {obj.name}")

    mesh = obj.data.copy()
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.faces.ensure_lookup_table()

    # Reset bmesh to handle potential degenerate geometries
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

    if not bm.faces or len(bm.faces) == 0:
        bm.free()
        return 0, 0, "Empty Mesh", 0, 0

    # Volume
    try:
        if is_mesh_closed(bm):
            measurement_type = "Closed Mesh"
            volume = bm.calc_volume()
        else:
            measurement_type = "Open Mesh - Bounding Box"
            dimensions = obj.dimensions
            volume = max(0, dimensions.x * dimensions.y * dimensions.z)
    except Exception as e:
        print(f"Volume calculation error: {e}")
        measurement_type = "Volume Calculation Failed"
        volume = 0

    # Total surface
    try:
        total_surface = sum(f.calc_area() for f in bm.faces if f.calc_area() > 0)
    except Exception as e:
        print(f"Total surface calculation error: {e}")
        total_surface = 0

    # Vertical surface
    def is_vertical_face(face):
        try:
            normal = face.normal.normalized()
            return 85 <= math.degrees(normal.angle((0, 0, 1))) <= 95
        except Exception as e:
            print(f"Vertical face calculation error: {e}")
            return False

    try:
        vertical_surface = sum(f.calc_area() for f in bm.faces if is_vertical_face(f))
    except Exception as e:
        print(f"Vertical surface calculation error: {e}")
        vertical_surface = 0

    bm.free()

    # Weight
    try:
        material_name = selected_material.strip().lower()
        weight = volume * materials.get(material_name, 0) if volume and material_name in materials else 0
    except Exception as e:
        print(f"Weight calculation error: {e}")
        weight = 0

    return volume, weight, measurement_type, total_surface, vertical_surface
