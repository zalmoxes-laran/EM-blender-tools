"""Top-level orchestrator for the PyArchInit pyunitastratigrafiche import.

Called by EM_OT_import_3dgis_database after the existing US import has
populated the s3dgraphy graph.
"""

from datetime import datetime, timezone

import bpy  # type: ignore

from . import geom_constants as C
from .pyarchinit_db_reader import (
    PyArchInitReader,
    redacted_db_spec,
    PyArchInitDBError,
    TABLE_NAME,
)
from .wkb_parser import parse_wkb, WKBParseError
from .reimport_planner import build_reimport_plan
from .geom_blender_io import (
    ensure_collection,
    move_obj_to_collection,
    build_mesh_from_polygons,
    create_or_replace_object,
    apply_imported_geom_properties,
    refresh_modification_baseline,
    backup_then_replace,
    is_mesh_modified,
)
from .geom_georef import resolve_georef_anchor
from ..operators.addon_prefix_helpers import node_name_to_proxy_name


def import_geometries(context, db_path, graph, graph_code, force_update,
                     ask_user_callback, show_warning_callback,
                     filters=None):
    """Run the full geometry import. Returns a report dict.

    ``filters`` (optional dict): column -> value pairs propagated from
    the s3dgraphy US-table filter feature (commit b6377db). When set,
    only polygons whose pyunitastratigrafiche row matches the filter
    are read from the DB. Unknown filter columns (no equivalent on the
    spatial table) are silently ignored — see
    ``pyarchinit_db_reader._build_filter_clause``.
    """
    report = {
        "created": 0,
        "updated": 0,
        "skipped_user_modified": 0,
        "marked_orphan_obj": 0,
        "polygon_orphans": 0,
        "us_without_geometry": [],
        "malformed_geometries": [],
        "backup_collection": None,
        "warnings": [],
    }

    # Credential-stripped spec used for any persisted provenance / error
    # text. For a PostgreSQL URL this drops ``user:password@`` so the
    # password never reaches a custom property or a popup (issue #27).
    safe_spec = redacted_db_spec(db_path)

    try:
        reader = PyArchInitReader(db_path)
    except Exception as e:
        show_warning_callback("ERROR", f"Cannot open DB: {safe_spec}\n{e}")
        return report

    try:
        if not reader.table_exists():
            show_warning_callback(
                "WARNING",
                f"Table '{TABLE_NAME}' not present in DB — no geometries to import.",
            )
            return report
        try:
            geom_col, srid = reader.detect_geometry_column()
        except PyArchInitDBError as e:
            show_warning_callback("ERROR", str(e))
            return report

        polygons = []
        try:
            for row in reader.fetch_polygons(filters=filters):
                try:
                    row["parsed_rings"] = parse_wkb(row["wkb"])
                    polygons.append(row)
                except WKBParseError as e:
                    report["malformed_geometries"].append((row["us_key"], str(e)))
        except PyArchInitDBError as e:
            show_warning_callback("ERROR", str(e))
            return report

        if not polygons:
            show_warning_callback("INFO", "No polygons in DB.")
            return report

        anchor = resolve_georef_anchor(context, polygons, srid, ask_user_callback)
        if anchor is None:
            show_warning_callback(
                "ERROR",
                "Set shift in the Georeferencing panel "
                "(View3D → EM sidebar → Georeferencing) before "
                "importing geometries. EPSG alone is not sufficient — "
                "both EPSG and shift_x/y/z must be set.",
            )
            return report
        shift_xyz, epsg_used = anchor

        plan = build_reimport_plan(
            scene_objects=list(bpy.context.scene.objects),
            graph=graph,
            incoming_polygons=polygons,
            is_modified=is_mesh_modified,
            resolve_us_node=_resolve_us_node,
        )

        parent_coll = ensure_collection(C.COLL_US_GEOMETRIES)
        graph_coll = ensure_collection(graph_code, parent=parent_coll)

        for entry in plan["create"]:
            obj = _create_one(entry, graph_coll, shift_xyz, safe_spec,
                              graph_code, context=context, graph=graph)
            _link_to_node(entry["node"], obj)
            report["created"] += 1

        for entry in plan["update_safe"]:
            new_mesh = build_mesh_from_polygons(entry["poly"]["parsed_rings"], shift_xyz)
            old_mesh = entry["obj"].data
            entry["obj"].data = new_mesh
            if old_mesh.users == 0:
                bpy.data.meshes.remove(old_mesh)
            refresh_modification_baseline(entry["obj"])
            report["updated"] += 1

        if force_update and plan["skip_modified"]:
            ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
            report["backup_collection"] = C.COLL_BACKUP_PREFIX + ts
            for entry in plan["skip_modified"]:
                new_mesh = build_mesh_from_polygons(entry["poly"]["parsed_rings"], shift_xyz)
                backup_then_replace(entry["obj"], new_mesh, ts)
                report["updated"] += 1
        else:
            report["skipped_user_modified"] = len(plan["skip_modified"])

        if plan["mark_orphan_obj"]:
            orphan_coll = ensure_collection(C.COLL_US_ORPHANS)
            for obj in plan["mark_orphan_obj"]:
                obj[C.PROP_US_ORPHAN] = True
                move_obj_to_collection(obj, orphan_coll)
            report["marked_orphan_obj"] = len(plan["mark_orphan_obj"])

        _handle_polygon_orphans(polygons, graph, shift_xyz, safe_spec, report)
        _record_us_without_geometry(polygons, graph, report)
    finally:
        reader.close()

    return report


_STRATIGRAPHIC_NODE_TYPES = frozenset({
    "US", "USN", "USV", "USVS", "USVA", "USM", "USR",
    "SF", "TSU", "VSF", "USD",
})


def _resolve_us_node(graph, us_key):
    """Find the s3dgraphy US node matching a pyunitastratigrafiche row.

    PyArchInitImporter (mapping `pyarchinit_us_mapping.json`) names US
    nodes with the bare value of the `us` column (e.g. '1', '16',
    'USM100'). PropertyNodes are named after the property
    ('Interpretation', 'Structure', ...) so they don't collide with
    numeric US codes — but to be safe we prefer nodes whose
    `node_type` looks stratigraphic.
    """
    if graph is None:
        return None
    us_value = None
    for part in us_key.split(","):
        if part.startswith("us="):
            us_value = part.split("=", 1)[1].strip()
            break
    if not us_value:
        return None
    candidates = [
        n for n in getattr(graph, "nodes", [])
        if getattr(n, "name", None) == us_value
    ]
    if not candidates:
        return None
    for n in candidates:
        if getattr(n, "node_type", "") in _STRATIGRAPHIC_NODE_TYPES:
            return n
    return candidates[0]


def _create_one(entry, parent_coll, shift_xyz, db_path, graph_code,
                context=None, graph=None):
    poly = entry["poly"]
    node = entry["node"]
    mesh = build_mesh_from_polygons(poly["parsed_rings"], shift_xyz)
    # Mode-aware naming: in Advanced EM mode the graph carries a valid
    # ``graph_code`` and the proxy name becomes ``<CODE>.<node>``; in
    # 3DGIS mode (graph_code unset or placeholder) the helper returns
    # the bare ``<node>`` — see operators/addon_prefix_helpers.py.
    obj_name = node_name_to_proxy_name(node.name, context=context, graph=graph)
    obj = create_or_replace_object(obj_name, mesh, parent_coll)
    apply_imported_geom_properties(
        obj=obj,
        us_node_id=getattr(node, "node_id", None) or getattr(node, "id", ""),
        us_name=node.name,
        graph_code=graph_code,
        db_path=db_path,
        us_key=poly["us_key"],
    )
    return obj


def _link_to_node(node, obj):
    if hasattr(node, "attributes") and isinstance(node.attributes, dict):
        node.attributes[C.NODE_ATTR_IMPORTED_GEOM_OBJ_NAME] = obj.name


def _handle_polygon_orphans(polygons, graph, shift_xyz, db_path, report):
    for poly in polygons:
        node = _resolve_us_node(graph, poly["us_key"])
        if node is not None:
            continue
        orphan_coll = ensure_collection(C.COLL_US_ORPHAN_POLYGONS)
        mesh = build_mesh_from_polygons(poly["parsed_rings"], shift_xyz)
        obj_name = f"orphan_{poly['sito']}_{poly['area']}_{poly['us']}"
        obj = bpy.data.objects.new(obj_name, mesh)
        orphan_coll.objects.link(obj)
        obj[C.PROP_IS_IMPORTED_GEOM] = True
        obj[C.PROP_US_ORPHAN] = True

        attrs = getattr(graph, "attributes", None)
        if isinstance(attrs, dict):
            attrs.setdefault("aux_orphans", []).append({
                "key_id": poly["us_key"],
                "payload": {
                    "kind": C.ORPHAN_KIND_POLYGON_NO_US,
                    "source": db_path,
                    "wkb_hex_preview": poly["wkb_hex_preview"],
                    "obj_name": obj.name,
                },
            })
        report["polygon_orphans"] += 1


def _record_us_without_geometry(polygons, graph, report):
    if graph is None:
        return
    polygon_us_values = set()
    for p in polygons:
        for part in p["us_key"].split(","):
            if part.startswith("us="):
                polygon_us_values.add(part.split("=", 1)[1].strip())
                break
    for node in getattr(graph, "nodes", []):
        if getattr(node, "node_type", "") not in _STRATIGRAPHIC_NODE_TYPES:
            continue
        name = getattr(node, "name", "")
        if not name or name in polygon_us_values:
            continue
        report["us_without_geometry"].append(name)
        attrs = getattr(graph, "attributes", None)
        if isinstance(attrs, dict):
            node_id = getattr(node, "node_id", None) or getattr(node, "id", None)
            if node_id is not None:
                attrs.setdefault(C.GRAPH_ATTR_AUX_US_NO_GEOM, []).append(node_id)
