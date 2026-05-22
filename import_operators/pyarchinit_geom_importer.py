"""Top-level orchestrator for the PyArchInit pyunitastratigrafiche import.

Called by EM_OT_import_3dgis_database after the existing US import has
populated the s3dgraphy graph.
"""

from datetime import datetime, timezone

import bpy  # type: ignore

from . import geom_constants as C
from .pyarchinit_db_reader import (
    open_readonly,
    table_exists,
    detect_geometry_column,
    fetch_polygons,
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


def import_geometries(context, db_path, graph, graph_code, force_update,
                     ask_user_callback, show_warning_callback):
    """Run the full geometry import. Returns a report dict."""
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

    try:
        conn = open_readonly(db_path)
    except Exception as e:
        show_warning_callback("ERROR", f"Cannot open DB: {db_path}\n{e}")
        return report

    try:
        if not table_exists(conn):
            show_warning_callback(
                "WARNING",
                f"Table '{TABLE_NAME}' not present in DB — no geometries to import.",
            )
            return report
        try:
            geom_col, srid = detect_geometry_column(conn)
        except PyArchInitDBError as e:
            show_warning_callback("ERROR", str(e))
            return report

        polygons = []
        for row in fetch_polygons(conn, geom_col):
            try:
                row["parsed_rings"] = parse_wkb(row["wkb"])
                polygons.append(row)
            except WKBParseError as e:
                report["malformed_geometries"].append((row["us_key"], str(e)))

        if not polygons:
            show_warning_callback("INFO", "No polygons in DB.")
            return report

        anchor = resolve_georef_anchor(context, polygons, srid, ask_user_callback)
        if anchor is None:
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
            obj = _create_one(entry, graph_coll, shift_xyz, db_path, graph_code)
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

        _handle_polygon_orphans(polygons, graph, shift_xyz, db_path, report)
        _record_us_without_geometry(polygons, graph, report)
    finally:
        conn.close()

    return report


def _resolve_us_node(graph, us_key):
    """Find an US node in the graph whose attributes match the (sito, area, us) key.

    Implementation detail: the existing PyArchInitImporter stores keys with
    underscores in node names (e.g. "SITE1_A_1"). We accept both
    'sito=SITE1,area=A,us=1' form and the underscored form.
    """
    if graph is None:
        return None
    key = us_key.replace("sito=", "").replace(",area=", "_").replace(",us=", "_")
    for node in getattr(graph, "nodes", []):
        if getattr(node, "name", None) == key:
            return node
    return None


def _create_one(entry, parent_coll, shift_xyz, db_path, graph_code):
    poly = entry["poly"]
    node = entry["node"]
    mesh = build_mesh_from_polygons(poly["parsed_rings"], shift_xyz)
    obj_name = f"{graph_code}.{node.name}"
    obj = create_or_replace_object(obj_name, mesh, parent_coll)
    apply_imported_geom_properties(
        obj=obj,
        us_node_id=node.id,
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
    polygon_keys = {p["us_key"] for p in polygons}
    for node in getattr(graph, "nodes", []):
        node_name = getattr(node, "name", "")
        try:
            sito, area, us = node_name.split("_")
        except ValueError:
            continue
        key = f"sito={sito},area={area},us={us}"
        if key not in polygon_keys:
            report["us_without_geometry"].append(node_name)
            attrs = getattr(graph, "attributes", None)
            if isinstance(attrs, dict):
                attrs.setdefault(C.GRAPH_ATTR_AUX_US_NO_GEOM, []).append(node.id)
