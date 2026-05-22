"""Blender-side helpers for the PyArchInit geometry import.

Anything that touches bpy / bmesh lives here so the rest of the
pipeline stays pure-Python and testable.
"""

import hashlib
from datetime import datetime, timezone

import bpy  # type: ignore
import bmesh  # type: ignore

from . import geom_constants as C


# ---------------------------------------------------------------------------
# Collection management
# ---------------------------------------------------------------------------

def ensure_collection(name, parent=None, hidden=False):
    """Return existing collection or create a new one linked under `parent`.

    If `parent` is None, links under the scene's master collection.
    """
    coll = bpy.data.collections.get(name)
    if coll is None:
        coll = bpy.data.collections.new(name)
        target = parent or bpy.context.scene.collection
        target.children.link(coll)
    if hidden:
        coll.hide_viewport = True
    return coll


def move_obj_to_collection(obj, dest):
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    dest.objects.link(obj)


# ---------------------------------------------------------------------------
# WKB rings → bmesh → mesh data
# ---------------------------------------------------------------------------

def build_mesh_from_polygons(polygons, shift_xyz):
    """Build a Blender Mesh datablock from a list of polygons.

    Each polygon = list of rings, each ring = list of (x, y, z) tuples.
    First ring of each polygon is treated as the outer boundary; subsequent
    rings are holes. All coordinates are shifted by `shift_xyz` before
    insertion.
    """
    sx, sy, sz = shift_xyz
    mesh = bpy.data.meshes.new("us_geom_temp")
    bm = bmesh.new()
    try:
        for rings in polygons:
            for ring in rings:
                if len(ring) >= 2 and ring[0] == ring[-1]:
                    ring = ring[:-1]
                verts = [bm.verts.new((x - sx, y - sy, z - sz)) for (x, y, z) in ring]
                if len(verts) >= 3:
                    try:
                        bm.faces.new(verts)
                    except ValueError:
                        pass
        bm.normal_update()
        bm.to_mesh(mesh)
    finally:
        bm.free()
    return mesh


# ---------------------------------------------------------------------------
# Object creation + property writing
# ---------------------------------------------------------------------------

def create_or_replace_object(target_name, mesh, parent_collection):
    """Return a Blender Object with `target_name` containing `mesh`.

    If an object with that name already exists AND is one of ours
    (em_is_imported_geom=True), reuse it and replace its mesh data.
    Otherwise, if the name clashes with a foreign object, suffix
    with NAME_SUFFIX_IMPORTED.
    """
    existing = bpy.data.objects.get(target_name)
    if existing is not None and existing.get(C.PROP_IS_IMPORTED_GEOM):
        old_mesh = existing.data
        existing.data = mesh
        if old_mesh.users == 0:
            bpy.data.meshes.remove(old_mesh)
        if existing.name not in [o.name for o in parent_collection.objects]:
            move_obj_to_collection(existing, parent_collection)
        return existing
    if existing is not None:
        target_name = target_name + C.NAME_SUFFIX_IMPORTED
    obj = bpy.data.objects.new(target_name, mesh)
    parent_collection.objects.link(obj)
    return obj


def apply_imported_geom_properties(obj, us_node_id, us_name, graph_code,
                                   db_path, us_key):
    """Stamp the immutable identity fields. Called only at FIRST import."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    obj[C.PROP_IS_IMPORTED_GEOM] = True
    obj[C.PROP_US_NODE_ID] = us_node_id
    obj[C.PROP_US_NAME] = us_name
    obj[C.PROP_GRAPH_CODE] = graph_code
    obj[C.PROP_PYARCHINIT_SOURCE] = db_path
    obj[C.PROP_PYARCHINIT_US_KEY] = us_key
    obj[C.PROP_IMPORT_TIMESTAMP] = now
    obj[C.PROP_US_ORPHAN] = False
    refresh_modification_baseline(obj)


def refresh_modification_baseline(obj):
    """Recompute the modification-detection baseline against the current mesh.

    Called at first import AND after a force-update rebuild.
    """
    obj[C.PROP_ORIGINAL_VERT_COUNT] = len(obj.data.vertices)
    obj[C.PROP_IMPORTED_MESH_HASH] = compute_mesh_hash(obj.data)


def compute_mesh_hash(mesh):
    """Stable hash over sorted vertex coords + face indices.

    Sensitive to vertex moves AND topology changes. Order-stable so
    Blender's internal reordering doesn't trigger false positives.
    """
    h = hashlib.sha1()
    verts = sorted(
        (round(v.co.x, 6), round(v.co.y, 6), round(v.co.z, 6))
        for v in mesh.vertices
    )
    for v in verts:
        h.update(repr(v).encode())
    faces = sorted(tuple(sorted(p.vertices)) for p in mesh.polygons)
    for f in faces:
        h.update(repr(f).encode())
    return "sha1:" + h.hexdigest()


def is_object_transform_identity(obj):
    loc_zero = all(abs(c) < 1e-9 for c in obj.location)
    rot_zero = all(abs(c) < 1e-9 for c in obj.rotation_euler)
    scale_one = all(abs(c - 1.0) < 1e-9 for c in obj.scale)
    return loc_zero and rot_zero and scale_one


def is_mesh_modified(obj):
    """Three-signal cascade (vert count, mesh hash, transform identity)."""
    orig_count = obj.get(C.PROP_ORIGINAL_VERT_COUNT)
    if orig_count is not None and len(obj.data.vertices) != orig_count:
        return True
    orig_hash = obj.get(C.PROP_IMPORTED_MESH_HASH)
    if orig_hash and compute_mesh_hash(obj.data) != orig_hash:
        return True
    if not is_object_transform_identity(obj):
        return True
    return False


def backup_then_replace(obj, new_mesh, timestamp):
    """Duplicate `obj` into a hidden backup collection, then swap its mesh
    data in-place to point at `new_mesh`."""
    backup_coll = ensure_collection(
        C.COLL_BACKUP_PREFIX + timestamp, hidden=True
    )
    backup_obj = obj.copy()
    backup_obj.data = obj.data.copy()
    backup_obj.name = f"{obj.name}.backup.{timestamp}"
    move_obj_to_collection(backup_obj, backup_coll)
    backup_obj[C.PROP_IS_BACKUP] = True

    old_mesh = obj.data
    obj.data = new_mesh
    if old_mesh.users == 0:
        bpy.data.meshes.remove(old_mesh)
    refresh_modification_baseline(obj)
