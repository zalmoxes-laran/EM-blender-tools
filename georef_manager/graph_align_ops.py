'''
G1 · Blender side of «Align graphs to the scene».

The scene's reference system is the reference graph's (the first loaded, or
the one chosen in the panel). For every other loaded graph this reads its
GeoPositionNode, computes the placement (`graph_align.place`) and moves that
graph's objects there — by the DIFFERENCE from what was applied before, so
pressing twice does not move twice. What was applied, and how it was computed,
is written on the graph's row, in the log and in the report: never silent.

Which objects are a graph's: those named ``<graph_code>.<…>`` (the multigraph
naming), or carrying ``em_graph_code`` / ``em_graph_id``. Only top-level ones
are moved; children follow their parents.
'''

from __future__ import annotations

import math

import bpy
from bpy.props import BoolProperty
from bpy.types import Operator

from . import graph_align, graph_sync


def _log(msg, level="INFO"):
    try:
        from ..functions import em_log
        em_log(msg, level)
    except Exception:  # noqa: BLE001
        print(msg)


def anchor_of_graph(graph) -> graph_align.Anchor:
    node = graph_sync.get_geo_node(graph)
    return graph_align.anchor_from_data(getattr(node, 'data', None) if node else None)


def scene_anchor(scene) -> graph_align.Anchor:
    g = scene.em_georef
    return graph_align.anchor_from_data({
        'epsg': g.epsg, 'shift_x': g.shift_x, 'shift_y': g.shift_y,
        'shift_z': g.shift_z, 'rotation': g.rotation})


def reference_row(em_tools, georef):
    '''The reference row: the one named in the panel, else the first loaded.'''
    from s3dgraphy import get_graph
    rows = list(em_tools.graphml_files)
    wanted = getattr(georef, 'reference_graph', '') or ''
    for row in rows:
        if row.name == wanted and get_graph(row.name) is not None:
            return row
    for row in rows:
        if get_graph(row.name) is not None:
            return row
    return None


def objects_of(row):
    code = getattr(row, 'graph_code', '') or ''
    out = []
    for ob in bpy.data.objects:
        if ob.parent is not None:
            continue
        mine = (ob.get('em_graph_id') == row.name
                or (code and (ob.get('em_graph_code') == code
                              or ob.name.startswith(code + '.'))))
        if mine:
            out.append(ob)
    return out


def _matrix(dx, dy, dz, rot_deg):
    from mathutils import Matrix
    return (Matrix.Translation((dx, dy, dz))
            @ Matrix.Rotation(math.radians(rot_deg), 4, 'Z'))


def move_objects(row, placement, apply_objects=True) -> int:
    '''Move the graph's objects from the old placement to the new one.'''
    old = (_matrix(row.geo_dx, row.geo_dy, row.geo_dz, row.geo_rot_z)
           if row.geo_applied else _matrix(0, 0, 0, 0))
    new = _matrix(placement.dx, placement.dy, placement.dz, placement.rot_z_deg)
    delta = new @ old.inverted()
    moved = 0
    if apply_objects:
        for ob in objects_of(row):
            ob.matrix_world = delta @ ob.matrix_world
            moved += 1
    row.geo_applied = True
    row.geo_dx, row.geo_dy, row.geo_dz = placement.dx, placement.dy, placement.dz
    row.geo_rot_z = placement.rot_z_deg
    return moved


def align_all(context, *, apply_objects=True, reprojector=None) -> list:
    '''Align every loaded graph to the reference. → list of sentences.'''
    from s3dgraphy import get_graph
    scene = context.scene
    em_tools = scene.em_tools
    georef = scene.em_georef
    ref_row = reference_row(em_tools, georef)
    if ref_row is None:
        return ['no graph loaded']
    if not georef.reference_graph:
        georef.reference_graph = ref_row.name
    ref_anchor = anchor_of_graph(get_graph(ref_row.name))
    said = []
    ref_source = 'its GeoPositionNode'
    if not ref_anchor.georeferenced and graph_align.anchor_from_data(
            {'epsg': georef.epsg}).georeferenced:
        ref_anchor = scene_anchor(scene)
        ref_source = 'the scene Georeferencing panel (the graph declares no EPSG)'
    ref_label = ref_row.graph_code or ref_row.name
    said.append(f"scene CRS = {ref_label} (EPSG {ref_anchor.epsg}), from {ref_source}")
    ref_row.geo_applied = False
    ref_row.geo_dx = ref_row.geo_dy = ref_row.geo_dz = ref_row.geo_rot_z = 0.0
    ref_row.geo_note = graph_align.place(ref_anchor, ref_anchor).sentence()

    chosen = None   # (reprojector, via, why_not), asked once
    for row in em_tools.graphml_files:
        if row.name == ref_row.name:
            continue
        graph = get_graph(row.name)
        if graph is None:
            continue
        other = anchor_of_graph(graph)
        run, via, missing = None, '', ''
        if (other.georeferenced and ref_anchor.georeferenced
                and other.epsg != ref_anchor.epsg):
            if reprojector is not None:
                run, via = reprojector, 'test'
            else:
                if chosen is None:
                    chosen = _choose(context, ref_anchor.epsg)
                run, via, missing = chosen
        placement = graph_align.place(ref_anchor, other, run, via=via,
                                      missing=missing)
        label = row.graph_code or row.name
        if placement.ok:
            moved = move_objects(row, placement, apply_objects)
            sentence = placement.sentence() + f"; {moved} object(s) moved"
        else:
            sentence = placement.sentence()
            if row.geo_applied:
                sentence += (f"; objects left where the last alignment put them "
                             f"(({row.geo_dx:.3f}, {row.geo_dy:.3f}, "
                             f"{row.geo_dz:.3f}) m, {row.geo_rot_z:+.4f}°)")
        row.geo_note = sentence
        said.append(f"{label}: {sentence}")
    for line in said:
        _log(f"[georef G1] {line}")
    return said


def _choose(context, probe_epsg):
    try:
        from ..sync_manager import room as room_cfg
        base = room_cfg._session.get('base_url') or ''
        token = room_cfg._session.get('token')
    except Exception:  # noqa: BLE001
        base, token = '', None
    base = base or str(getattr(context.scene, 'em_room_url', '') or '').strip()
    return graph_align.choose_reprojector(base or None, token,
                                          probe=(int(probe_epsg), int(probe_epsg)))


class EM_OT_georef_align_graphs(Operator):
    '''Put every graph of the scene in the scene's reference system'''

    bl_idname = "em.georef_align_graphs"
    bl_label = "Align graphs to the scene"
    bl_description = (
        "Place every loaded graph in the scene's reference system (the "
        "reference graph's): same EPSG → the difference of the shifts; "
        "different EPSG → the origin reprojected and the Z rotation from the "
        "grid convergence (server /v1/reproject, else local pyproj). What was "
        "applied is written on each graph and in the log")
    bl_options = {'REGISTER', 'UNDO'}

    apply_objects: BoolProperty(
        name="Move the objects",
        description="Also move the graph's objects (named <code>.…) by the "
                    "difference from what was applied before",
        default=True)  # type: ignore

    def execute(self, context):
        said = align_all(context, apply_objects=self.apply_objects)
        refused = [s for s in said if 'needed' in s or 'no EPSG' in s
                   or 'failed' in s]
        self.report({'WARNING'} if refused else {'INFO'}, ' · '.join(said))
        return {'FINISHED'}


CLASSES = (EM_OT_georef_align_graphs,)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:  # noqa: BLE001
            pass
