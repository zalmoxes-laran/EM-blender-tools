"""
Generation strategies for Surface Areale meshes.
Each strategy creates a mesh that conforms to the RM surface within the contour boundary.
"""

import bpy
import bmesh
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
from mathutils.geometry import delaunay_2d_cdt


def strategy_projective(contour_points, contour_normals, whisker_point,
                        rm_obj, bvh_tree, settings):
    """
    Projective strategy for nearly-planar surfaces (Scenario A).

    1. Compute best-fit plane via PCA
    2. Project contour to 2D on that plane
    3. Constrained Delaunay triangulation
    4. Project all vertices back onto RM surface
    5. Adaptive subdivision where deviation is too high

    Args:
        contour_points: List of Vector (3D contour points on RM surface)
        contour_normals: List of Vector (surface normals at contour points)
        whisker_point: Vector (point inside the contour for inside/outside)
        rm_obj: Blender mesh object (the RM)
        bvh_tree: BVHTree of the RM
        settings: SurfaceArealeSettings PropertyGroup

    Returns:
        bpy.types.Object: New Blender mesh object with the areale
    """
    if len(contour_points) < 3:
        raise ValueError("Contour needs at least 3 points")

    # ── Step 1: Compute best-fit plane via PCA ──────────────────────
    centroid, axis_u, axis_v, axis_n = _compute_plane_pca(contour_points)

    # Build transformation matrix: world → plane local
    # Local X = axis_u, Local Y = axis_v, Local Z = axis_n
    mat_to_local = Matrix([
        [axis_u.x, axis_u.y, axis_u.z, 0],
        [axis_v.x, axis_v.y, axis_v.z, 0],
        [axis_n.x, axis_n.y, axis_n.z, 0],
        [0, 0, 0, 1]
    ])

    # ── Step 2: Project contour to 2D ────────────────────────────────
    verts_2d = []
    for p in contour_points:
        local = mat_to_local @ (p - centroid)
        verts_2d.append(Vector((local.x, local.y)))

    # Build edge constraints for the contour boundary
    n_pts = len(verts_2d)
    edges = [(i, (i + 1) % n_pts) for i in range(n_pts)]

    # ── Step 3: Constrained Delaunay Triangulation ───────────────────
    # output_type=2 → only triangles inside the constrained region
    result = delaunay_2d_cdt(verts_2d, edges, [], 2, 1e-6)
    out_verts_2d, out_edges, out_faces, out_orig_verts, out_orig_edges, out_orig_faces = result

    if not out_faces:
        raise ValueError("Delaunay triangulation produced no faces")

    # ── Step 4: Convert back to 3D and project onto RM ───────────────
    mat_to_world = mat_to_local.inverted()

    verts_3d = []
    normals_3d = []
    for v2d in out_verts_2d:
        # Back to 3D (on the plane)
        local_3d = Vector((v2d.x, v2d.y, 0.0))
        world_3d = mat_to_world @ local_3d + centroid

        # Project onto RM surface
        location, normal, index, dist = bvh_tree.find_nearest(world_3d)
        if location is not None:
            verts_3d.append(Vector(location))
            normals_3d.append(Vector(normal))
        else:
            verts_3d.append(world_3d)
            normals_3d.append(axis_n.copy())

    # ── Step 5: Adaptive subdivision ─────────────────────────────────
    bm = bmesh.new()

    bm_verts = [bm.verts.new(v) for v in verts_3d]
    bm.verts.ensure_lookup_table()

    for face_indices in out_faces:
        try:
            face_verts = [bm_verts[i] for i in face_indices]
            bm.faces.new(face_verts)
        except (ValueError, IndexError):
            continue

    bm.faces.ensure_lookup_table()

    # Adaptive subdivision iterations
    threshold = settings.conformity_threshold
    for iteration in range(settings.subdivision_iterations):
        faces_to_subdivide = []

        for face in bm.faces:
            # Check midpoint deviation from RM surface
            center = face.calc_center_median()
            location, normal, index, dist = bvh_tree.find_nearest(center)

            if location is not None and dist is not None:
                if dist > threshold:
                    faces_to_subdivide.append(face)

        if not faces_to_subdivide:
            break

        # Subdivide the problematic faces (deduplicate shared edges)
        edges_to_subdivide = list({e for f in faces_to_subdivide for e in f.edges})
        bmesh.ops.subdivide_edges(
            bm,
            edges=edges_to_subdivide,
            cuts=1,
            use_grid_fill=True
        )

        bm.verts.ensure_lookup_table()
        bm.faces.ensure_lookup_table()

        # Re-project new vertices onto RM
        for v in bm.verts:
            location, normal, index, dist = bvh_tree.find_nearest(v.co)
            if location is not None:
                v.co = Vector(location)

    # ── Create Blender mesh object ───────────────────────────────────
    mesh = bpy.data.meshes.new("EM_SurfaceAreale")
    bm.to_mesh(mesh)
    bm.free()

    mesh.update()

    obj = bpy.data.objects.new("EM_SurfaceAreale", mesh)

    return obj


def _compute_plane_pca(points):
    """
    Compute best-fit plane using PCA on a set of 3D points.

    Returns:
        Tuple (centroid, axis_u, axis_v, normal)
        - centroid: Vector (center of the points)
        - axis_u: Vector (first principal component - largest spread)
        - axis_v: Vector (second principal component)
        - normal: Vector (third component - plane normal)
    """
    coords = np.array([(p.x, p.y, p.z) for p in points])
    centroid_np = coords.mean(axis=0)
    centered = coords - centroid_np

    # Covariance matrix
    cov = np.cov(centered.T)

    # Eigenvalue decomposition
    eigenvalues, eigenvectors = np.linalg.eigh(cov)

    # Sort by eigenvalue descending (eigh returns ascending)
    idx = eigenvalues.argsort()[::-1]
    eigenvalues = eigenvalues[idx]
    eigenvectors = eigenvectors[:, idx]

    centroid = Vector(centroid_np)
    axis_u = Vector(eigenvectors[:, 0]).normalized()
    axis_v = Vector(eigenvectors[:, 1]).normalized()
    normal = Vector(eigenvectors[:, 2]).normalized()

    return centroid, axis_u, axis_v, normal
