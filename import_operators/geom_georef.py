"""Resolve the scene shift / EPSG used to anchor imported geometries.

Reads scene.em_georef via its public PropertyGroup fields. The
PropertyGroup's update callbacks propagate to BlenderGIS and 3DSC
adapters automatically.

Policy (since v1.6.0_dev — georef gating tightened): a fully
``CONFIGURED`` em_georef (both EPSG and a non-zero shift) is the only
green path for geometry import. ``EPSG_ONLY`` and ``UNSET`` both
return ``None`` (the caller's CANCEL signal) so the import operator
can show a clear error pointing the user to the Georeferencing panel
instead of silently auto-anchoring to the polygon centroid — silent
auto-anchoring across multiple imports could place geometries from
different scenes at inconsistent reference points.
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


def resolve_georef_anchor(context, polygons, db_srid):
    """Return ((shift_x, shift_y, shift_z), epsg_used) or None to cancel.

    Returns ``None`` whenever ``classify_georef_state`` is not
    ``CONFIGURED``. The caller (``import_geometries`` in
    ``pyarchinit_geom_importer.py``) surfaces a user-facing ERROR
    message pointing to the Georeferencing panel.

    Under the current block-until-CONFIGURED policy there is no
    auto-anchor fallback. If a future iteration needs a modal popup
    to ask the user where to anchor (EPSG-only or unset state), the
    callback can be re-introduced as an explicit parameter at that
    time; until then the API stays minimal.
    """
    g = context.scene.em_georef
    state = classify_georef_state(g)

    if state != STATE_CONFIGURED:
        # Block — the caller will show a clear error. Silent
        # auto-anchoring is no longer allowed because EPSG-only or
        # unset state silently anchoring at the centroid could place
        # geometries from different sites/scenes at inconsistent
        # reference points.
        return None

    if db_srid and g.epsg.strip() != str(db_srid):
        # Non-blocking warning is surfaced by the orchestrator.
        pass
    return (g.shift_x, g.shift_y, g.shift_z), g.epsg
