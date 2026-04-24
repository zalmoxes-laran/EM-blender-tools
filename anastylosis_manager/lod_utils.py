# anastylosis_manager/lod_utils.py
"""LOD helpers: name parsing, fallback resolution, linked-mesh swapping, variant discovery."""

import re
import bpy


LOD_MIN_LEVEL = 0
LOD_MAX_LEVEL = 4
LOD_SUFFIX_RE = re.compile(r"^(.+)_LOD(\d+)$")
LOD_FALLBACK_WARNING = "Some Levels of Detail were not found. Fallback applied to the nearest available LOD."


def _split_lod_name(name):
    """Return (base_name, lod_level) if name ends with _LOD#, else (None, None)."""
    m = LOD_SUFFIX_RE.match(name or "")
    if not m:
        return None, None
    return m.group(1), int(m.group(2))


def _get_active_lod(item_name):
    """Get active LOD level from object name or mesh datablock name."""
    _, lod = _split_lod_name(item_name)
    if lod is not None:
        return lod
    obj = bpy.data.objects.get(item_name)
    if obj and obj.type == 'MESH' and obj.data:
        _, lod = _split_lod_name(obj.data.name)
        if lod is not None:
            return lod
    return 0


def _resolve_lod_with_fallback(available_levels, requested_level, min_level=LOD_MIN_LEVEL, max_level=LOD_MAX_LEVEL):
    """Clamp request to [min,max] and fallback to highest available <= request."""
    if not available_levels:
        return None

    req = max(min_level, min(max_level, int(requested_level)))
    levels_in_range = sorted({lvl for lvl in available_levels if min_level <= lvl <= max_level})
    if not levels_in_range:
        return None

    lower_or_equal = [lvl for lvl in levels_in_range if lvl <= req]
    if lower_or_equal:
        return max(lower_or_equal)

    # If no lower level exists, use the minimum available in range.
    return min(levels_in_range)


def _rename_object_to_lod(obj, target_lod):
    """Rename object suffix to _LODn only if the object already follows that convention."""
    base_name, _ = _split_lod_name(obj.name)
    if base_name is None:
        return
    obj.name = f"{base_name}_LOD{target_lod}"


def _switch_linked_mesh_lod(obj, requested_lod):
    """Switch linked mesh data to requested LOD with fallback to max available <= request."""
    if not obj or obj.type != 'MESH' or not obj.data or not obj.data.library:
        return False, None, None, "Object has no linked mesh library"

    mesh_name = obj.data.name
    base_name, _ = _split_lod_name(mesh_name)
    if base_name is None:
        return False, None, None, f"Mesh '{mesh_name}' has no _LODn suffix"

    lib_path = bpy.path.abspath(obj.data.library.filepath)
    target_mesh_name = None
    resolved_lod = None

    with bpy.data.libraries.load(lib_path, link=True) as (data_from, data_to):
        available_levels = []
        for name in data_from.meshes:
            m = LOD_SUFFIX_RE.match(name)
            if m and m.group(1) == base_name:
                available_levels.append(int(m.group(2)))

        resolved_lod = _resolve_lod_with_fallback(available_levels, requested_lod)
        if resolved_lod is None:
            return False, None, None, f"No LOD levels found for base '{base_name}' in library"

        target_mesh_name = f"{base_name}_LOD{resolved_lod}"
        data_to.meshes = [target_mesh_name]

    target_mesh = bpy.data.meshes.get(target_mesh_name)
    if target_mesh is None:
        return False, None, None, f"Mesh '{target_mesh_name}' could not be loaded from library"

    obj.data = target_mesh
    _rename_object_to_lod(obj, resolved_lod)
    return True, resolved_lod, target_mesh_name, None


def detect_lod_variants(obj_name):
    """Find LOD variants by checking both object names and mesh datablock names.
    Returns list of tuples (lod_level, obj_name) sorted by LOD level.
    """
    base_name, _ = _split_lod_name(obj_name)
    if base_name is None:
        # Object name has no LOD suffix — check mesh datablock name
        obj = bpy.data.objects.get(obj_name)
        if obj and obj.type == 'MESH' and obj.data:
            mesh_base, _ = _split_lod_name(obj.data.name)
            if mesh_base is not None:
                base_name = mesh_base
        if base_name is None:
            base_name = obj_name  # fallback

    variants = []
    seen = set()
    pattern = re.compile(r'^' + re.escape(base_name) + r'_LOD(\d+)$')

    for obj in bpy.data.objects:
        # Check object name
        m = pattern.match(obj.name)
        if m and obj.name not in seen:
            variants.append((int(m.group(1)), obj.name))
            seen.add(obj.name)
            continue
        # Check mesh datablock name (for linked mesh objects)
        if obj.type == 'MESH' and obj.data:
            m2 = pattern.match(obj.data.name)
            if m2 and obj.name not in seen:
                variants.append((int(m2.group(1)), obj.name))
                seen.add(obj.name)

    variants.sort(key=lambda x: x[0])
    return variants
