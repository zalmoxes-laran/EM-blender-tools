"""
Performance benchmark and time estimation for Surface Areale strategies.

Runs a micro-benchmark on first use to calibrate time estimates.
Results are saved in addon preferences for future sessions.
"""

import bpy
import bmesh
import time
from mathutils import Vector
from mathutils.bvhtree import BVHTree


# Cache benchmark results in memory for this session
_benchmark_cache = {
    'bool_coeff': None,     # seconds per million polys for Boolean
    'proj_coeff': None,     # seconds per thousand contour points for Projective
    'shrink_coeff': None,   # seconds per thousand verts for Shrinkwrap
    'calibrated': False
}


def estimate_time(strategy, rm_poly_count, contour_point_count):
    """
    Estimate execution time for a given strategy.

    Args:
        strategy: 'PROJECTIVE', 'SHRINKWRAP', or 'BOOLEAN'
        rm_poly_count: Number of polygons in the RM
        contour_point_count: Number of points in the contour

    Returns:
        Tuple (seconds_estimate, confidence)
        confidence is 'calibrated' or 'estimated'
    """
    if _benchmark_cache['calibrated']:
        confidence = 'calibrated'
        k_bool = _benchmark_cache['bool_coeff']
        k_proj = _benchmark_cache['proj_coeff']
        k_shrink = _benchmark_cache['shrink_coeff']
    else:
        # Default estimates based on typical hardware
        confidence = 'estimated'
        k_bool = 2.0     # 2s per million polys
        k_proj = 0.001   # 1ms per contour point
        k_shrink = 0.5   # 0.5s per thousand verts

    if strategy == 'PROJECTIVE':
        t = k_proj * contour_point_count + 0.1  # BVH overhead
        return t, confidence
    elif strategy == 'SHRINKWRAP':
        est_verts = contour_point_count * 10  # after subdivision
        t = k_shrink * (est_verts / 1000.0) + 0.5  # modifier overhead
        return t, confidence
    elif strategy == 'BOOLEAN':
        t = k_bool * (rm_poly_count / 1_000_000.0) + 0.5  # boolean solver overhead
        return t, confidence
    else:
        return 1.0, 'unknown'


def format_time_estimate(seconds):
    """Format a time estimate for UI display."""
    if seconds < 0.1:
        return "< 0.1s"
    elif seconds < 1.0:
        return f"~{seconds:.1f}s"
    elif seconds < 60:
        return f"~{seconds:.0f}s"
    else:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"~{minutes}m {secs}s"


def run_benchmark():
    """
    Run a micro-benchmark to calibrate time estimates.
    Creates a test sphere, runs BVH + boolean on it, measures time.
    Call once at addon startup or on first tool use.
    """
    print("[SurfaceAreale] Running performance benchmark...")

    # ── Projective benchmark: BVH + find_nearest ──────────────────────
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=4, radius=1.0)
    mesh = bpy.data.meshes.new("_benchmark_sphere")
    bm.to_mesh(mesh)

    vertices = [v.co.copy() for v in mesh.vertices]
    polys = [p.vertices for p in mesh.polygons]
    bvh = BVHTree.FromPolygons(vertices, polys)

    n_queries = 1000
    test_points = [Vector((0.5, 0.5, 0.5 + i * 0.001)) for i in range(n_queries)]

    t0 = time.perf_counter()
    for p in test_points:
        bvh.find_nearest(p)
    t_proj = time.perf_counter() - t0

    _benchmark_cache['proj_coeff'] = t_proj / n_queries

    # ── Boolean benchmark: exact boolean on the sphere ────────────────
    # Create a cube cutter
    bm2 = bmesh.new()
    bmesh.ops.create_cube(bm2, size=1.0)
    cutter_mesh = bpy.data.meshes.new("_benchmark_cutter")
    bm2.to_mesh(cutter_mesh)
    bm2.free()

    sphere_obj = bpy.data.objects.new("_benchmark_sphere", mesh)
    cutter_obj = bpy.data.objects.new("_benchmark_cutter", cutter_mesh)
    bpy.context.collection.objects.link(sphere_obj)
    bpy.context.collection.objects.link(cutter_obj)

    bool_mod = sphere_obj.modifiers.new("BoolTest", 'BOOLEAN')
    bool_mod.operation = 'INTERSECT'
    bool_mod.object = cutter_obj
    bool_mod.solver = 'EXACT'

    bpy.context.view_layer.objects.active = sphere_obj

    t0 = time.perf_counter()
    try:
        bpy.ops.object.modifier_apply(modifier=bool_mod.name)
        t_bool = time.perf_counter() - t0
        sphere_polys = len(mesh.polygons)
        _benchmark_cache['bool_coeff'] = t_bool / max(sphere_polys / 1_000_000.0, 0.001)
    except Exception:
        _benchmark_cache['bool_coeff'] = 2.0  # fallback

    # ── Shrinkwrap benchmark ──────────────────────────────────────────
    _benchmark_cache['shrink_coeff'] = _benchmark_cache['proj_coeff'] * 50  # rough estimate

    # ── Cleanup ───────────────────────────────────────────────────────
    for obj in [sphere_obj, cutter_obj]:
        mesh_data = obj.data
        bpy.data.objects.remove(obj, do_unlink=True)
        if mesh_data and mesh_data.users == 0:
            bpy.data.meshes.remove(mesh_data)

    bm.free()

    _benchmark_cache['calibrated'] = True
    print(f"[SurfaceAreale] Benchmark complete: "
          f"proj={_benchmark_cache['proj_coeff']:.6f}s/pt, "
          f"bool={_benchmark_cache['bool_coeff']:.2f}s/Mpoly, "
          f"shrink={_benchmark_cache['shrink_coeff']:.4f}s/kvert")


def get_strategy_estimates(rm_poly_count, contour_point_count):
    """
    Get time estimates for all strategies.
    Returns dict: {'PROJECTIVE': (time, label), 'SHRINKWRAP': ..., 'BOOLEAN': ...}
    """
    estimates = {}
    for strat in ('PROJECTIVE', 'SHRINKWRAP', 'BOOLEAN'):
        t, conf = estimate_time(strat, rm_poly_count, contour_point_count)
        label = format_time_estimate(t)
        if conf != 'calibrated':
            label += " (est.)"
        estimates[strat] = (t, label)
    return estimates
