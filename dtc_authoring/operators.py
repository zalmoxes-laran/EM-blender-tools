"""Operators for the DTC authoring panel (EMTools).

They author the DTC genesis (Process + input/output Resources + chain edges) on
the active s3dgraphy graph via the pure logic in dtc_graph.py. The graph is the
single source of truth; changes persist through the existing em.json round-trip.
DTC nodes are graph metadata — never Blender scene objects.
"""

from __future__ import annotations

import bpy
from bpy.types import Operator

from . import dtc_graph


def _active_graph(context):
    from ..functions import check_active_graph
    return check_active_graph(context)


def _guard(self, context):
    """(ok, graph) with the DTC-availability guard; reports + returns (False, None)."""
    ok, graph = _active_graph(context)
    if not ok:
        return False, None
    if not dtc_graph.dtc_supported():
        self.report({'ERROR'},
                    "DTC unavailable: the active s3dgraphy is stale — activate the "
                    "dev/updated s3dgraphy (./em.sh s3d), then reopen.")
        return False, None
    return True, graph


class EM_OT_dtc_add_process(Operator):
    bl_idname = "em.dtc_add_process"
    bl_label = "Add DTC process"
    bl_description = "Add a DTC process (transformation event) to the active graph"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        ok, graph = _guard(self, context)
        if not ok:
            return {'CANCELLED'}
        p = context.scene.em_dtc
        try:
            pid = dtc_graph.add_process(graph, p.process_kind or None)
        except Exception as exc:
            self.report({'ERROR'}, f"Add process failed: {exc}")
            return {'CANCELLED'}
        p.active_process = pid  # select the new process
        p.status = "Process added"
        return {'FINISHED'}


class EM_OT_dtc_add_input(Operator):
    bl_idname = "em.dtc_add_input"
    bl_label = "Add input resource"
    bl_description = "Add an INPUT Resource (LinkNode) and wire it into the selected process"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        ok, graph = _guard(self, context)
        if not ok:
            return {'CANCELLED'}
        p = context.scene.em_dtc
        if not p.active_process:
            self.report({'WARNING'}, "Select or add a process first")
            return {'CANCELLED'}
        try:
            dtc_graph.add_input(graph, p.active_process, p.input_kind, p.input_url)
        except Exception as exc:
            self.report({'ERROR'}, f"Add input failed: {exc}")
            return {'CANCELLED'}
        p.input_url = ""
        p.status = f"Added input ({p.input_kind})"
        return {'FINISHED'}


class EM_OT_dtc_add_output(Operator):
    bl_idname = "em.dtc_add_output"
    bl_label = "Add output resource"
    bl_description = "Add an OUTPUT Resource (LinkNode) produced by the selected process"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        ok, graph = _guard(self, context)
        if not ok:
            return {'CANCELLED'}
        p = context.scene.em_dtc
        if not p.active_process:
            self.report({'WARNING'}, "Select or add a process first")
            return {'CANCELLED'}
        try:
            dtc_graph.add_output(graph, p.active_process, p.output_kind, p.output_url,
                                 derive_from_inputs=p.derive_output)
        except Exception as exc:
            self.report({'ERROR'}, f"Add output failed: {exc}")
            return {'CANCELLED'}
        p.output_url = ""
        p.status = f"Added output ({p.output_kind})"
        return {'FINISHED'}


class EM_OT_dtc_remove(Operator):
    bl_idname = "em.dtc_remove_node"
    bl_label = "Remove"
    bl_description = "Remove this DTC node (process or resource) from the graph"
    bl_options = {'REGISTER', 'UNDO'}

    node_id: bpy.props.StringProperty()

    def execute(self, context):
        ok, graph = _guard(self, context)
        if not ok:
            return {'CANCELLED'}
        if not self.node_id:
            return {'CANCELLED'}
        p = context.scene.em_dtc
        try:
            dtc_graph.remove_node(graph, self.node_id)
        except Exception as exc:
            self.report({'ERROR'}, f"Remove failed: {exc}")
            return {'CANCELLED'}
        if p.active_process == self.node_id:
            p.active_process = ""
        p.status = "Removed"
        return {'FINISHED'}


classes = (
    EM_OT_dtc_add_process,
    EM_OT_dtc_add_input,
    EM_OT_dtc_add_output,
    EM_OT_dtc_remove,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
