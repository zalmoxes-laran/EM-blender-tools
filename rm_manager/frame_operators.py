"""The frame of a tileset in the RM panels (MICRO tileset, shift e epoche,
E.D. 25 Oct 2026).

Many surveys export SHIFTED coordinates while declaring them in the project's
CRS: the Basilica Iulia's RealityScan tileset was written as E − 291407,
N − 4640813 declared as EPSG:6708, and its root transform put it on the
equator. ``data.frame`` on the tileset's resource (s3Dgraphy nodes datamodel
1.6.38) says it once: «the coordinates of this file are CRS X minus shift S».

Shown on the container's alternative and on a Cesium tileset object
(:func:`draw_frame`):

* **Edit…** (:class:`RM_OT_tileset_frame_edit`) — CRS, shift X/Y/Z, note;
* **Use the graph's shift** (:class:`RM_OT_tileset_frame_from_graph`) — the
  graph's ``geo_position`` (EPSG + shift), else the scene's Georeferencing;
* **From a SHIFT file…** (:class:`RM_OT_tileset_frame_from_file`) — the
  ``EPSG::NNNN X Y [Z]`` line of a ``SHIFT*.txt`` (the georef manager's parser);
* **Remove** (:class:`RM_OT_tileset_frame_clear`).

Each is ONE operator with UNDO: one write into the graph (s3Dgraphy's
``set_frame``) and the panel's copy on the container / object. Blender's undo
restores the copy, not the graph (the graph lives outside Blender's data):
:func:`_undo_sync` writes the restored copy back into the graph for the nodes
these operators wrote in this session, so Ctrl+Z takes the frame back too.

After a write the container's box is measured again where the frame puts it
(``alternative_operators.place_box``: the root relocated, the residual said).
A Cesium tileset object (an empty with ``tileset_path``) is never placed by
EM Tools from its root transform: there the frame is data only.
"""

from __future__ import annotations

import os
from typing import Optional, Set, Tuple

import bpy  # type: ignore
from bpy.props import IntProperty, StringProperty  # type: ignore
from bpy.types import Operator  # type: ignore

from . import tileset_frame as tf

#: the nodes whose frame these operators wrote in this session: only these are
#: brought back into the graph after an undo
_WRITTEN: Set[str] = set()

_COPY_KEY = "em_frame"          # an object's copy (JSON)
_NODE_KEY = "em_frame_node"     # the node it was written on


def _graph(context):
    from .alternative_operators import _graph as g
    return g(context)


def _target(context, container_index: int, object_name: str) -> Tuple[object, Optional[str], str]:
    """``(holder, node_id, label)``: the container or the object whose copy is
    kept, the graph node the frame is written on, a name for the reports."""
    graph = _graph(context)
    if object_name:
        obj = bpy.data.objects.get(object_name)
        if obj is None or graph is None:
            return obj, None, object_name
        from .containers import resolve_rm_node_id
        rm = resolve_rm_node_id(graph, obj, scene=context.scene, migra=False)
        return obj, tf.frame_node(graph, rm) if rm else None, obj.name
    scene = context.scene
    idx = container_index if container_index >= 0 else scene.rm_containers_index
    if not (0 <= idx < len(scene.rm_containers)):
        return None, None, ""
    cont = scene.rm_containers[idx]
    node = tf.frame_node(graph, cont.alt_asset_id) if (graph is not None and cont.alt_asset_id) else None
    return cont, node, cont.alt_name or cont.label


def _current(holder) -> Optional[dict]:
    if holder is None:
        return None
    if isinstance(holder, bpy.types.Object):
        return tf.loads(holder.get(_COPY_KEY, ""))
    return tf.loads(holder.alt_frame)


def _write(op, context, frame: Optional[dict]) -> set:
    """One write: the graph (s3Dgraphy's ``set_frame``), the panel's copy,
    the box of the container measured again. → the operator's answer."""
    holder, node, label = _target(context, op.container_index, op.object_name)
    graph = _graph(context)
    if holder is None or graph is None or not node:
        op.report({'WARNING'}, "No tileset node in the graph to write the frame on "
                               "(open the em.json, or press Project for the container)")
        return {'CANCELLED'}
    tf.write_frame(graph, node, frame)
    _WRITTEN.add(node)
    copy = tf.dumps(tf.read_frame({"frame": frame}) if frame else None)
    said = f"«{label}»: {tf.frame_line(tf.loads(copy))}"
    if isinstance(holder, bpy.types.Object):
        holder[_COPY_KEY] = copy
        holder[_NODE_KEY] = node
    else:
        holder.alt_frame = copy
        from .alternative_operators import apply_view, place_box
        note = place_box(holder, context, graph)
        apply_view(holder, context)
        if note:
            said += f" · {note}"
    op.report({'INFO'}, said)
    return {'FINISHED'}


class _FrameTarget:
    container_index: IntProperty(default=-1, options={'HIDDEN'})  # type: ignore
    object_name: StringProperty(default="", options={'HIDDEN'})  # type: ignore


class RM_OT_tileset_frame_edit(_FrameTarget, Operator):
    """The frame of the tileset's file: «its coordinates are the CRS minus
    the shift». Written on the tileset's resource in the graph"""
    bl_idname = "rm.tileset_frame_edit"
    bl_label = "Frame of the tileset"
    bl_options = {'REGISTER', 'UNDO'}

    crs: StringProperty(name="CRS", description="The CRS the file's coordinates are "
                        "declared in, e.g. EPSG:6708")  # type: ignore
    shift_x: StringProperty(name="Shift X", description="Subtracted from the CRS's X "
                            "(easting): written as text, a double, never rounded")  # type: ignore
    shift_y: StringProperty(name="Shift Y", description="Subtracted from the CRS's Y "
                            "(northing)")  # type: ignore
    shift_z: StringProperty(name="Shift Z", description="Subtracted from the height")  # type: ignore
    note: StringProperty(name="Note", description="Where the shift comes from, "
                         "e.g. «SHIFT6708.txt of the study»")  # type: ignore

    def invoke(self, context, event):
        holder, _node, _label = _target(context, self.container_index, self.object_name)
        f = _current(holder)
        if f is None:
            g, sc = _study(context)
            s = g or sc
            self.crs = (s or {}).get("crs") or ""
            self.shift_x = self.shift_y = self.shift_z = ""
            self.note = ""
        else:
            self.crs = f.get("crs") or ""
            self.shift_x, self.shift_y, self.shift_z = (repr(float(v)) for v in f["shift"])
            self.note = f.get("note", "")
        return context.window_manager.invoke_props_dialog(self, width=420)

    def draw(self, context):
        col = self.layout.column()
        col.label(text="The coordinates of this file are the CRS minus the shift")
        col.prop(self, "crs")
        col.prop(self, "shift_x")
        col.prop(self, "shift_y")
        col.prop(self, "shift_z")
        col.prop(self, "note")

    def execute(self, context):
        try:
            shift = [tf.parse_number(v) for v in (self.shift_x, self.shift_y, self.shift_z)]
        except ValueError as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        if not self.crs.strip() and not any(shift):
            self.report({'WARNING'}, "Neither a CRS nor a shift: use Remove to take the frame away")
            return {'CANCELLED'}
        return _write(self, context, tf.make_frame(self.crs.strip(), shift,
                                                   self.note.strip(), "manual"))


def _study(context):
    from .alternative_operators import study_frames
    return study_frames(context, _graph(context))


class RM_OT_tileset_frame_from_graph(_FrameTarget, Operator):
    """Use the graph's shift as the frame of the tileset's file: the CRS and
    shift of the graph's geo_position (else the scene's Georeferencing)"""
    bl_idname = "rm.tileset_frame_from_graph"
    bl_label = "Use the graph's shift"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        g, sc = _study(context)
        if g is not None:
            frame = tf.frame_from_study(g, "the graph's geo_position", "graph")
        elif sc is not None:
            frame = tf.frame_from_study(sc, "the scene's georeferencing", "graph")
        else:
            self.report({'WARNING'}, "Neither the graph nor the scene says a shift: "
                                     "use Edit… or From a SHIFT file…")
            return {'CANCELLED'}
        return _write(self, context, frame)


class RM_OT_tileset_frame_from_file(_FrameTarget, Operator):
    """The frame of the tileset's file from a SHIFT file (EPSG::NNNN X Y [Z],
    the 3D Survey Collection's format)"""
    bl_idname = "rm.tileset_frame_from_file"
    bl_label = "From a SHIFT file"
    bl_options = {'REGISTER', 'UNDO'}

    filepath: StringProperty(subtype='FILE_PATH')  # type: ignore
    filter_glob: StringProperty(default="*.txt", options={'HIDDEN'})  # type: ignore

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        from ..georef_manager.shift_io import parse_shift_file
        path = bpy.path.abspath(self.filepath)
        try:
            rec = parse_shift_file(path)
        except (OSError, ValueError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        return _write(self, context, tf.make_frame(rec.epsg, [rec.x, rec.y, rec.z],
                                                   os.path.basename(path), "file"))


class RM_OT_tileset_frame_clear(_FrameTarget, Operator):
    """Remove the frame: the file's coordinates are taken as written"""
    bl_idname = "rm.tileset_frame_clear"
    bl_label = "Remove the frame"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        return _write(self, context, None)


# ── the panel ────────────────────────────────────────────────────────────────

def draw_frame(layout, holder, container_index: int = -1, object_name: str = "") -> None:
    """The frame's rows: what it says, Edit… / Use the graph's shift / From a
    SHIFT file… / Remove, the note, and (for a container) where the box went."""
    f = _current(holder)
    box = layout.box()
    row = box.row(align=True)
    row.label(text=f"Frame: {tf.frame_line(f)}", icon='ORIENTATION_GLOBAL')
    ops = box.row(align=True)

    def put(idname, text, icon):
        op = ops.operator(idname, text=text, icon=icon)
        op.container_index = container_index
        op.object_name = object_name

    put("rm.tileset_frame_edit", "Edit…", 'GREASEPENCIL')
    put("rm.tileset_frame_from_graph", "Use the graph's shift", 'WORLD')
    put("rm.tileset_frame_from_file", "SHIFT file…", 'FILE_TEXT')
    if f is not None:
        put("rm.tileset_frame_clear", "", 'X')
    small = box.column()
    small.scale_y = 0.7
    if f is not None and f.get("note"):
        small.label(text=f"«{f['note']}» ({f.get('source') or 'manual'})")
    note = getattr(holder, "alt_place_note", "") if not isinstance(holder, bpy.types.Object) else ""
    if note:
        r = small.row()
        r.alert = note.startswith("Not ")
        r.label(text=note, icon='ERROR' if r.alert else 'CHECKMARK')
    elif isinstance(holder, bpy.types.Object):
        small.label(text="EM Tools does not place this object from the tileset: "
                         "the frame travels in the graph", icon='INFO')


def refresh_object_frames(graphs) -> int:
    """The copy of the frame on every Cesium tileset object, from the graph
    (on opening an em.json). → how many objects carry one."""
    n = 0
    graphs = [g for g in graphs if g is not None]
    if not graphs:
        return 0
    from .containers import resolve_rm_node_id
    scene = bpy.context.scene
    for obj in bpy.data.objects:
        if "tileset_path" not in obj:
            continue
        for graph in graphs:
            rm = resolve_rm_node_id(graph, obj, scene=scene, migra=False)
            if not rm:
                continue
            f, _where = tf.frame_for(graph, rm)
            obj[_COPY_KEY] = tf.dumps(f)
            obj[_NODE_KEY] = tf.frame_node(graph, rm) or ""
            n += 1 if f else 0
            break
    return n


@bpy.app.handlers.persistent
def _undo_sync(*_args):
    """After an undo / redo: the restored copies back into the graph, for the
    nodes these operators wrote in this session."""
    if not _WRITTEN:
        return
    try:
        context = bpy.context
        graph = _graph(context)
        if graph is None:
            return
        pairs = []
        for cont in context.scene.rm_containers:
            if cont.alt_asset_id:
                node = tf.frame_node(graph, cont.alt_asset_id)
                pairs.append((node, tf.loads(cont.alt_frame)))
        for obj in bpy.data.objects:
            node = obj.get(_NODE_KEY, "")
            if node:
                pairs.append((node, tf.loads(obj.get(_COPY_KEY, ""))))
        for node, copy in pairs:
            if node not in _WRITTEN or graph.find_node_by_id(node) is None:
                continue
            now = tf.read_frame(getattr(graph.find_node_by_id(node), "data", None))
            if now != copy:
                tf.write_frame(graph, node, copy)
    except Exception as exc:  # noqa: BLE001 — an undo never fails for it
        print(f"[RM frame] undo: the graph not brought back ({exc})")


_CLASSES = [RM_OT_tileset_frame_edit, RM_OT_tileset_frame_from_graph,
            RM_OT_tileset_frame_from_file, RM_OT_tileset_frame_clear]


def register_frame_operators():
    for cls in _CLASSES:
        try:
            bpy.utils.register_class(cls)
        except ValueError:
            bpy.utils.unregister_class(cls)
            bpy.utils.register_class(cls)
    for hs in (bpy.app.handlers.undo_post, bpy.app.handlers.redo_post):
        if _undo_sync not in hs:
            hs.append(_undo_sync)


def unregister_frame_operators():
    for hs in (bpy.app.handlers.undo_post, bpy.app.handlers.redo_post):
        while _undo_sync in hs:
            hs.remove(_undo_sync)
    for cls in reversed(_CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:  # noqa: BLE001
            pass
