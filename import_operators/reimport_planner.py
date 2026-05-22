"""Diff existing imported meshes against incoming polygons.

Pure-Python so unit-testable without Blender. The Blender layer
provides the `is_modified` and `resolve_us_node` callbacks.
"""

from .geom_constants import PROP_IS_IMPORTED_GEOM, PROP_US_NODE_ID


def build_reimport_plan(
    scene_objects,
    graph,
    incoming_polygons,
    is_modified,
    resolve_us_node,
):
    """Return a four-bucket plan for a re-import operation.

    Args:
        scene_objects:    iterable of Blender Object-like dicts.
        graph:            opaque graph reference passed back to resolve_us_node.
        incoming_polygons: list of {us_key: str, ...} dicts.
        is_modified:      callable(obj) -> bool. Decides if a mesh has been
                          modified by the user since import.
        resolve_us_node:  callable(graph, us_key) -> node or None. Finds the
                          s3dgraphy US node for a given DB key tuple.

    Returns:
        dict with keys 'create', 'update_safe', 'skip_modified',
        'mark_orphan_obj'. Polygon orphans (us_key with no matching node)
        are NOT placed in this plan — the caller routes them elsewhere.
    """
    plan = {
        "create": [],
        "update_safe": [],
        "skip_modified": [],
        "mark_orphan_obj": [],
    }

    existing_by_node_id = {}
    for obj in scene_objects:
        if not obj.get(PROP_IS_IMPORTED_GEOM):
            continue
        node_id = obj.get(PROP_US_NODE_ID)
        if not node_id:
            continue
        existing_by_node_id[node_id] = obj

    incoming_by_node_id = {}
    for poly in incoming_polygons:
        node = resolve_us_node(graph, poly["us_key"])
        if node is None:
            continue  # polygon orphan — handled by the caller
        incoming_by_node_id[node.id] = (poly, node)

    for node_id, (poly, node) in incoming_by_node_id.items():
        existing = existing_by_node_id.get(node_id)
        if existing is None:
            plan["create"].append({"poly": poly, "node": node})
        elif is_modified(existing):
            plan["skip_modified"].append({"poly": poly, "node": node, "obj": existing})
        else:
            plan["update_safe"].append({"poly": poly, "node": node, "obj": existing})

    for node_id, obj in existing_by_node_id.items():
        if node_id not in incoming_by_node_id:
            plan["mark_orphan_obj"].append(obj)

    return plan
