"""
Generation strategies for Surface Areale meshes.
Three strategies with increasing complexity:
  A. Projective — nearly-planar surfaces (fast)
  B. Shrinkwrap — surfaces with edges/corners (medium)
  C. Boolean + LOD — fully 3D surfaces (slower, most accurate)
"""

import bpy
import bmesh
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
from mathutils.geometry import delaunay_2d_cdt


# ══════════════════════════════════════════════════════════════════════
# STRATEGY DISPATCHER
# ══════════════════════════════════════════════════════════════════════

def generate_areale(contour_points, contour_normals, whisker_point,
                    rm_obj, bvh_tree, settings):
    """
    Dispatch to the correct strategy based on settings.strategy.
    If strategy is 'AUTO', runs the complexity classifier first.

    Returns: bpy.types.Object (the areale mesh)
    """
    strategy = settings.strategy

    if strategy == 'AUTO':
        analysis = classify_complexity(contour_points, contour_normals, bvh_tree)
        strategy = analysis['recommended_strategy']
        print(f"[SurfaceAreale] Auto-classified: {analysis['scenario']} "
              f"(planarity={analysis['planarity']:.3f}, "
              f"normal_var={analysis['normal_variation']:.1f}°) "
              f"→ {strategy}")

    if strategy == 'PROJECTIVE':
        return strategy_projective(contour_points, contour_normals,
                                   whisker_point, rm_obj, bvh_tree, settings)
    elif strategy == 'SHRINKWRAP':
        return strategy_shrinkwrap(contour_points, contour_normals,
                                   whisker_point, rm_obj, bvh_tree, settings)
    elif strategy == 'BOOLEAN':
        return strategy_boolean(contour_points, contour_normals,
                                whisker_point, rm_obj, bvh_tree, settings)
    else:
        raise ValueError(f"Unknown strategy: {strategy}")


# ══════════════════════════════════════════════════════════════════════
# COMPLEXITY CLASSIFIER
# ══════════════════════════════════════════════════════════════════════

def classify_complexity(contour_points, contour_normals, bvh_tree):
    """
    Classify the surface complexity into Scenario A, B, or C.

    Metrics:
    1. Planarity — PCA variance ratio of the contour
    2. Normal variation — max angle between sampled surface normals
    3. Area ratio — geodesic area vs projected area estimate

    Returns dict with: scenario, planarity, normal_variation, area_ratio,
                       recommended_strategy
    """
    # ── Metric 1: Planarity (PCA) ─────────────────────────────────────
    coords = np.array([(p.x, p.y, p.z) for p in contour_points])
    centroid = coords.mean(axis=0)
    centered = coords - centroid
    cov = np.cov(centered.T)
    eigenvalues = np.linalg.eigvalsh(cov)
    eigenvalues = np.sort(eigenvalues)[::-1]  # descending

    # Planarity: ratio of smallest eigenvalue to largest
    # 0 = perfectly planar, 1 = equally spread in all directions
    total_var = eigenvalues.sum()
    planarity = eigenvalues[2] / total_var if total_var > 1e-10 else 0.0

    # ── Metric 2: Normal variation ────────────────────────────────────
    # Sample normals from contour points + interior
    normals_np = np.array([(n.x, n.y, n.z) for n in contour_normals])
    if len(normals_np) > 1:
        # Compute pairwise dot products with the mean normal
        mean_normal = normals_np.mean(axis=0)
        mean_normal /= (np.linalg.norm(mean_normal) + 1e-10)
        dots = np.clip(normals_np @ mean_normal, -1.0, 1.0)
        angles = np.degrees(np.arccos(dots))
        max_angle = float(angles.max())
    else:
        max_angle = 0.0

    # ── Metric 3: Area ratio (geodesic vs projected) ──────────────────
    # Approximate: project contour onto PCA plane, compare 2D area with 3D perimeter
    # Simple heuristic based on planarity and normal spread
    area_ratio = 1.0 + planarity * 5.0 + (max_angle / 90.0)

    # ── Classification ────────────────────────────────────────────────
    if planarity < 0.02 and max_angle < 20.0:
        scenario = 'A'
        recommended = 'PROJECTIVE'
    elif planarity < 0.15 and max_angle < 90.0:
        scenario = 'B'
        recommended = 'SHRINKWRAP'
    else:
        scenario = 'C'
        recommended = 'BOOLEAN'

    return {
        'scenario': scenario,
        'planarity': planarity,
        'normal_variation': max_angle,
        'area_ratio': area_ratio,
        'recommended_strategy': recommended
    }


# ══════════════════════════════════════════════════════════════════════
# STRATEGY A — PROJECTIVE (nearly-planar)
# ══════════════════════════════════════════════════════════════════════

def strategy_projective(contour_points, contour_normals, whisker_point,
                        rm_obj, bvh_tree, settings):
    """
    Projective strategy for nearly-planar surfaces (Scenario A).
    PCA → Delaunay 2D → project onto RM → adaptive subdivision.
    """
    if len(contour_points) < 3:
        raise ValueError("Contour needs at least 3 points")

    centroid, axis_u, axis_v, axis_n = _compute_plane_pca(contour_points)

    mat_to_local = Matrix([
        [axis_u.x, axis_u.y, axis_u.z, 0],
        [axis_v.x, axis_v.y, axis_v.z, 0],
        [axis_n.x, axis_n.y, axis_n.z, 0],
        [0, 0, 0, 1]
    ])

    verts_2d = []
    for p in contour_points:
        local = mat_to_local @ (p - centroid)
        verts_2d.append(Vector((local.x, local.y)))

    n_pts = len(verts_2d)
    edges = [(i, (i + 1) % n_pts) for i in range(n_pts)]

    result = delaunay_2d_cdt(verts_2d, edges, [], 2, 1e-6)
    out_verts_2d, out_edges, out_faces = result[0], result[1], result[2]

    if not out_faces:
        raise ValueError("Delaunay triangulation produced no faces")

    mat_to_world = mat_to_local.inverted()

    verts_3d = []
    for v2d in out_verts_2d:
        local_3d = Vector((v2d.x, v2d.y, 0.0))
        world_3d = mat_to_world @ local_3d + centroid
        location, normal, index, dist = bvh_tree.find_nearest(world_3d)
        if location is not None:
            verts_3d.append(Vector(location))
        else:
            verts_3d.append(world_3d)

    bm = _build_bmesh_from_triangulation(verts_3d, out_faces)
    _adaptive_subdivide(bm, bvh_tree, settings.conformity_threshold,
                        settings.subdivision_iterations)

    return _bmesh_to_object(bm, "EM_SurfaceAreale")


# ══════════════════════════════════════════════════════════════════════
# STRATEGY B — SHRINKWRAP ADAPTIVE (edges/corners)
# ══════════════════════════════════════════════════════════════════════

def strategy_shrinkwrap(contour_points, contour_normals, whisker_point,
                        rm_obj, bvh_tree, settings):
    """
    Shrinkwrap strategy for surfaces with edges/corners (Scenario B).

    1. Create an initial dense mesh from contour (Delaunay with higher subdivision)
    2. Apply Shrinkwrap modifier (Nearest Surface Point) to RM
    3. Adaptive refinement: subdivide where deviation is high
    4. Re-shrinkwrap after each subdivision pass

    Handles architraves, cornices, moldings where the surface bends at angles.
    """
    if len(contour_points) < 3:
        raise ValueError("Contour needs at least 3 points")

    centroid, axis_u, axis_v, axis_n = _compute_plane_pca(contour_points)

    mat_to_local = Matrix([
        [axis_u.x, axis_u.y, axis_u.z, 0],
        [axis_v.x, axis_v.y, axis_v.z, 0],
        [axis_n.x, axis_n.y, axis_n.z, 0],
        [0, 0, 0, 1]
    ])

    # Project contour to 2D
    verts_2d = []
    for p in contour_points:
        local = mat_to_local @ (p - centroid)
        verts_2d.append(Vector((local.x, local.y)))

    n_pts = len(verts_2d)
    edges = [(i, (i + 1) % n_pts) for i in range(n_pts)]

    # Delaunay triangulation
    result = delaunay_2d_cdt(verts_2d, edges, [], 2, 1e-6)
    out_verts_2d, out_faces = result[0], result[2]

    if not out_faces:
        raise ValueError("Delaunay triangulation produced no faces")

    mat_to_world = mat_to_local.inverted()

    # Convert back to 3D (on the PCA plane, NOT projected yet)
    verts_3d = []
    for v2d in out_verts_2d:
        local_3d = Vector((v2d.x, v2d.y, 0.0))
        world_3d = mat_to_world @ local_3d + centroid
        verts_3d.append(world_3d)

    bm = _build_bmesh_from_triangulation(verts_3d, out_faces)

    # Pre-subdivide the entire mesh for higher density before shrinkwrap
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=2, use_grid_fill=True)
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    # Create temporary object for shrinkwrap modifier
    temp_mesh = bpy.data.meshes.new("_temp_shrinkwrap")
    bm.to_mesh(temp_mesh)
    temp_obj = bpy.data.objects.new("_temp_shrinkwrap", temp_mesh)
    bpy.context.collection.objects.link(temp_obj)

    # Apply Shrinkwrap modifier
    mod = temp_obj.modifiers.new("Shrinkwrap", 'SHRINKWRAP')
    mod.target = rm_obj
    mod.wrap_method = 'NEAREST_SURFACEPOINT'
    mod.wrap_mode = 'ON_SURFACE'

    # Apply modifier
    bpy.context.view_layer.objects.active = temp_obj
    bpy.ops.object.modifier_apply(modifier=mod.name)

    # Get the shrinkwrapped mesh back into bmesh
    bm.free()
    bm = bmesh.new()
    bm.from_mesh(temp_obj.data)

    # Iterative refinement: subdivide where deviation is high, re-project
    threshold = settings.conformity_threshold
    for iteration in range(settings.subdivision_iterations):
        # Find faces with high deviation from RM surface
        faces_to_refine = []
        for face in bm.faces:
            center = face.calc_center_median()
            location, normal, idx, dist = bvh_tree.find_nearest(center)
            if location and dist and dist > threshold:
                faces_to_refine.append(face)

        if not faces_to_refine:
            break

        edges_to_sub = list({e for f in faces_to_refine for e in f.edges})
        bmesh.ops.subdivide_edges(bm, edges=edges_to_sub, cuts=1,
                                  use_grid_fill=True)
        bm.verts.ensure_lookup_table()

        # Re-project all vertices to nearest surface point
        for v in bm.verts:
            location, normal, idx, dist = bvh_tree.find_nearest(v.co)
            if location:
                v.co = Vector(location)

    # Create final object
    bm.to_mesh(temp_obj.data)
    temp_obj.data.update()

    # Rename and detach from temp
    final_obj = temp_obj
    final_obj.name = "EM_SurfaceAreale"
    final_obj.data.name = "EM_SurfaceAreale"

    bm.free()
    return final_obj


# ══════════════════════════════════════════════════════════════════════
# STRATEGY C — BOOLEAN + LOD (fully 3D)
# ══════════════════════════════════════════════════════════════════════

def strategy_boolean(contour_points, contour_normals, whisker_point,
                     rm_obj, bvh_tree, settings):
    """
    Boolean strategy for fully 3D surfaces (Scenario C).

    1. Extrude contour into a 3D "cookie cutter" along local normals
    2. Boolean intersect the cutter with a copy/LOD of the RM
    3. Re-project onto full-res RM if LOD was used

    CRITICAL: The cookie cutter must be in the same coordinate space as the
    RM copy. Since contour_points are in WORLD space (from BVH raycast) and
    the RM may have a non-identity matrix_world, we set the cutter's
    matrix_world to identity and build its vertices in world space, then
    apply all transforms on the RM copy so both are in world space.
    """
    if len(contour_points) < 3:
        raise ValueError("Contour needs at least 3 points")

    # ── Step 1: Build cookie cutter in world space ────────────────────
    extrude_dist = _estimate_extrude_distance(contour_points, contour_normals)
    cutter_obj = _build_cookie_cutter(contour_points, contour_normals, extrude_dist)

    # ── Step 2: Create RM copy with APPLIED transforms ────────────────
    # The RM may have a non-identity matrix_world. We need to apply all
    # transforms so the mesh vertices are in world space, matching the cutter.
    rm_copy = rm_obj.copy()
    rm_copy.data = rm_obj.data.copy()
    rm_copy.name = "_rm_copy"
    bpy.context.collection.objects.link(rm_copy)

    # Apply all transforms on the copy (location, rotation, scale → identity)
    bpy.context.view_layer.objects.active = rm_copy
    rm_copy.select_set(True)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    rm_copy.select_set(False)

    poly_count = len(rm_copy.data.polygons)
    used_lod = False

    if settings.use_lod and settings.lod_factor < 1.0:
        decimate_mod = rm_copy.modifiers.new("LOD_Decimate", 'DECIMATE')
        decimate_mod.ratio = settings.lod_factor
        bpy.context.view_layer.objects.active = rm_copy
        bpy.ops.object.modifier_apply(modifier=decimate_mod.name)
        lod_poly_count = len(rm_copy.data.polygons)
        print(f"[SurfaceAreale] LOD: {poly_count} -> {lod_poly_count} polys "
              f"(factor={settings.lod_factor:.2f})")
        used_lod = True
    else:
        print(f"[SurfaceAreale] Boolean on full-res: {poly_count} polys")

    # ── Step 3: Boolean intersection ──────────────────────────────────
    bool_mod = rm_copy.modifiers.new("Boolean_Areale", 'BOOLEAN')
    bool_mod.operation = 'INTERSECT'
    bool_mod.object = cutter_obj
    bool_mod.solver = 'EXACT'

    bpy.context.view_layer.objects.active = rm_copy
    try:
        bpy.ops.object.modifier_apply(modifier=bool_mod.name)
    except RuntimeError as e:
        print(f"[SurfaceAreale] Boolean failed: {e}, falling back to shrinkwrap")
        _cleanup_objects([cutter_obj, rm_copy])
        return strategy_shrinkwrap(contour_points, contour_normals,
                                   whisker_point, rm_obj, bvh_tree, settings)

    # ── Step 4: Clean up cutter ───────────────────────────────────────
    _cleanup_objects([cutter_obj])

    # Check we actually got geometry from the boolean
    if len(rm_copy.data.polygons) == 0:
        print(f"[SurfaceAreale] Boolean produced 0 faces, falling back to shrinkwrap")
        _cleanup_objects([rm_copy])
        return strategy_shrinkwrap(contour_points, contour_normals,
                                   whisker_point, rm_obj, bvh_tree, settings)

    # ── Step 5: If LOD was used, re-project onto full-res ─────────────
    if used_lod:
        bm = bmesh.new()
        bm.from_mesh(rm_copy.data)
        for v in bm.verts:
            location, normal, idx, dist = bvh_tree.find_nearest(v.co)
            if location:
                v.co = Vector(location)
        bm.to_mesh(rm_copy.data)
        bm.free()
        rm_copy.data.update()

    # Rename
    rm_copy.name = "EM_SurfaceAreale"
    rm_copy.data.name = "EM_SurfaceAreale"

    return rm_copy


# ══════════════════════════════════════════════════════════════════════
# ANNULAR SHAPES — CONTOUR WITH HOLES
# ══════════════════════════════════════════════════════════════════════

def generate_areale_with_holes(contour_points, contour_normals, whisker_point,
                                hole_points_list, hole_normals_list,
                                rm_obj, bvh_tree, settings):
    """
    Generate an areale with holes using Boolean operations.

    1. Generate outer areale via the selected strategy
    2. For each hole: build a cookie cutter from the hole contour
    3. Boolean DIFFERENCE: areale - hole_cutter

    Args:
        contour_points/normals: outer contour points and normals
        hole_points_list: list of point lists for each hole
        hole_normals_list: list of normal lists for each hole
        rm_obj: the RM mesh object
        bvh_tree: BVH tree of the RM
        settings: SurfaceArealeSettings

    Returns: bpy.types.Object (areale mesh with holes)
    """
    # Generate the outer areale via the standard pipeline
    areale_obj = generate_areale(
        contour_points, contour_normals, whisker_point,
        rm_obj, bvh_tree, settings
    )

    # Cut holes via Boolean DIFFERENCE
    for i, (hole_pts, hole_norms) in enumerate(
            zip(hole_points_list, hole_normals_list)):
        if len(hole_pts) < 3:
            print(f"[SurfaceAreale] Hole {i} has <3 points, skipping")
            continue

        extrude_dist = _estimate_extrude_distance(hole_pts, hole_norms)
        cutter_obj = _build_cookie_cutter(hole_pts, hole_norms, extrude_dist)

        bool_mod = areale_obj.modifiers.new(f"Hole_{i}", 'BOOLEAN')
        bool_mod.operation = 'DIFFERENCE'
        bool_mod.object = cutter_obj
        bool_mod.solver = 'EXACT'

        bpy.context.view_layer.objects.active = areale_obj
        try:
            bpy.ops.object.modifier_apply(modifier=bool_mod.name)
            print(f"[SurfaceAreale] Hole {i} cut successfully")
        except RuntimeError as e:
            print(f"[SurfaceAreale] Hole {i} boolean failed: {e}")
            # Remove the modifier if it wasn't applied
            if bool_mod.name in areale_obj.modifiers:
                areale_obj.modifiers.remove(
                    areale_obj.modifiers[bool_mod.name])

        _cleanup_objects([cutter_obj])

    return areale_obj


def _build_cookie_cutter(contour_points, contour_normals, extrude_dist):
    """
    Build a closed tube mesh from a contour by extruding along normals.
    Used for Boolean operations (both INTERSECT and DIFFERENCE).

    The cutter is built in world space with identity matrix_world.

    Args:
        contour_points: list of Vector (world space)
        contour_normals: list of Vector (surface normals)
        extrude_dist: extrusion distance along normals

    Returns: bpy.types.Object (the cutter mesh)
    """
    bm_cutter = bmesh.new()

    bottom_verts = []
    top_verts = []
    for p, n in zip(contour_points, contour_normals):
        bottom_verts.append(bm_cutter.verts.new(p - n * extrude_dist))
        top_verts.append(bm_cutter.verts.new(p + n * extrude_dist))

    bm_cutter.verts.ensure_lookup_table()

    # Side faces
    n_pts = len(contour_points)
    for i in range(n_pts):
        i_next = (i + 1) % n_pts
        try:
            bm_cutter.faces.new([
                bottom_verts[i], bottom_verts[i_next],
                top_verts[i_next], top_verts[i]
            ])
        except ValueError:
            continue

    # Caps
    try:
        bm_cutter.faces.new(bottom_verts)
    except ValueError:
        pass
    try:
        bm_cutter.faces.new(list(reversed(top_verts)))
    except ValueError:
        pass

    bm_cutter.normal_update()

    cutter_mesh = bpy.data.meshes.new("_hole_cutter")
    bm_cutter.to_mesh(cutter_mesh)
    bm_cutter.free()
    cutter_obj = bpy.data.objects.new("_hole_cutter", cutter_mesh)
    bpy.context.collection.objects.link(cutter_obj)

    return cutter_obj


# ══════════════════════════════════════════════════════════════════════
# SHARED HELPERS
# ══════════════════════════════════════════════════════════════════════

def _compute_plane_pca(points):
    """Compute best-fit plane using PCA. Returns (centroid, axis_u, axis_v, normal)."""
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

    return centroid, axis_u, axis_v, normal


def _build_bmesh_from_triangulation(verts_3d, faces):
    """Build a bmesh from a list of 3D vertices and face index tuples."""
    bm = bmesh.new()
    bm_verts = [bm.verts.new(v) for v in verts_3d]
    bm.verts.ensure_lookup_table()
    for face_indices in faces:
        try:
            bm.faces.new([bm_verts[i] for i in face_indices])
        except (ValueError, IndexError):
            continue
    bm.faces.ensure_lookup_table()
    return bm


def _adaptive_subdivide(bm, bvh_tree, threshold, max_iterations):
    """Subdivide faces where midpoint deviates from RM surface beyond threshold."""
    for iteration in range(max_iterations):
        faces_to_subdivide = []
        for face in bm.faces:
            center = face.calc_center_median()
            location, normal, index, dist = bvh_tree.find_nearest(center)
            if location is not None and dist is not None and dist > threshold:
                faces_to_subdivide.append(face)

        if not faces_to_subdivide:
            break

        edges_to_sub = list({e for f in faces_to_subdivide for e in f.edges})
        bmesh.ops.subdivide_edges(bm, edges=edges_to_sub, cuts=1,
                                  use_grid_fill=True)
        bm.verts.ensure_lookup_table()
        bm.faces.ensure_lookup_table()

        for v in bm.verts:
            location, normal, index, dist = bvh_tree.find_nearest(v.co)
            if location is not None:
                v.co = Vector(location)


def _bmesh_to_object(bm, name):
    """Convert bmesh to a new Blender mesh object."""
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    return bpy.data.objects.new(name, mesh)


def _estimate_extrude_distance(contour_points, contour_normals):
    """Estimate a good extrusion distance for the boolean cookie cutter."""
    # Use the bounding box diagonal of the contour as reference
    coords = np.array([(p.x, p.y, p.z) for p in contour_points])
    bbox_size = coords.max(axis=0) - coords.min(axis=0)
    diagonal = float(np.linalg.norm(bbox_size))
    # Extrude distance = 20% of the contour diagonal, minimum 0.01
    return max(diagonal * 0.2, 0.01)


def _cleanup_objects(objects):
    """Remove temporary Blender objects and their data."""
    for obj in objects:
        mesh_data = obj.data
        bpy.data.objects.remove(obj, do_unlink=True)
        if mesh_data and mesh_data.users == 0:
            bpy.data.meshes.remove(mesh_data)
