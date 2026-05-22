"""Resolve the scene shift / EPSG used to anchor imported geometries.

Reads (and conditionally writes) scene.em_georef via its public PropertyGroup
fields. The PropertyGroup's update callbacks propagate to BlenderGIS and 3DSC
adapters automatically.
"""

import bpy  # type: ignore


STATE_UNSET = "UNSET"
STATE_EPSG_ONLY = "EPSG_ONLY"
STATE_CONFIGURED = "CONFIGURED"


def classify_georef_state(g):
    has_epsg = bool(g.epsg) and g.epsg.strip() not in ("", "4326")
    has_shift = any(abs(c) > 1e-9 for c in (g.shift_x, g.shift_y, g.shift_z))
    if has_shift and has_epsg:
        return STATE_CONFIGURED
    if has_epsg and not has_shift:
        return STATE_EPSG_ONLY
    return STATE_UNSET


def compute_centroid(polygons_iter):
    """Mean of all outer-ring vertices (good enough for anchoring)."""
    sx = sy = 0.0
    n = 0
    for poly in polygons_iter:
        for rings in poly["parsed_rings"]:
            outer = rings[0]
            for x, y, _ in outer:
                sx += x
                sy += y
                n += 1
    if n == 0:
        return None
    return (sx / n, sy / n)


def write_georef(context, epsg, shift_x, shift_y, shift_z):
    """Write through the public PropertyGroup so update_* callbacks fire."""
    g = context.scene.em_georef
    g.epsg = str(epsg)
    g.shift_x = float(shift_x)
    g.shift_y = float(shift_y)
    g.shift_z = float(shift_z)


def resolve_georef_anchor(context, polygons, db_srid, ask_user_callback):
    """Return ((shift_x, shift_y, shift_z), epsg_used) or None to cancel.

    `polygons` is a list of dicts with a 'parsed_rings' field already populated
    by the WKB parser. `ask_user_callback(state, centroid, db_srid)` shows the
    appropriate popup and returns 'AUTO' / 'CANCEL' / 'MANUAL_EPSG:<value>'.
    """
    g = context.scene.em_georef
    state = classify_georef_state(g)

    if state == STATE_CONFIGURED:
        if db_srid and g.epsg.strip() != str(db_srid):
            # Non-blocking warning is surfaced by the orchestrator.
            pass
        return (g.shift_x, g.shift_y, g.shift_z), g.epsg

    centroid = compute_centroid(polygons)
    if centroid is None:
        return (0.0, 0.0, 0.0), g.epsg or "4326"

    if state == STATE_UNSET:
        choice = ask_user_callback(state, centroid, db_srid)
        if choice == "CANCEL":
            return None
        # AUTO
        write_georef(context, str(db_srid or "4326"),
                     centroid[0], centroid[1], 0.0)
        return (centroid[0], centroid[1], 0.0), str(db_srid or "4326")

    # STATE_EPSG_ONLY: anchor without asking
    write_georef(context, g.epsg, centroid[0], centroid[1], 0.0)
    return (centroid[0], centroid[1], 0.0), g.epsg
