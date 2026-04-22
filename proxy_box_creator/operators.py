"""Operators for the Proxy Box Creator (DP-47 / DP-07 flow).

Organised around the two-step UI:

- **Step 1** — pick / establish an anchor DocumentNode:
  - :class:`PROXYBOX_OT_pick_from_selected` — introspect the active
    selection and, when possible, auto-resolve the mesh's Document.
  - :class:`PROXYBOX_OT_link_selected_to_doc` — when the selection
    is not yet linked, open a picker (search + create-new) and wire
    everything up (promote to rm_list, add has_representation_model
    edge, set ``settings.document_node_id``).
  - :class:`PROXYBOX_OT_search_document` — set the anchor document
    from the Document catalog without requiring a scene selection.
  - :class:`PROXYBOX_OT_clear_document` — clear the anchor.

- **Step 2** — record 3D measurement points:
  - :class:`PROXYBOX_OT_record_point` — record the 3D cursor for
    one of the seven rows. When the Step-1 anchor is set and
    ``propagate_doc_to_points`` is on, the point inherits the
    document and an auto-computed extractor id (gap-aware across
    both graph-side extractors and IDs already staged on other
    proxy-box points).
  - :class:`PROXYBOX_OT_clear_point` /
    :class:`PROXYBOX_OT_clear_all_points` — clear one / all rows.
"""

from __future__ import annotations

import re

import bpy  # type: ignore
from bpy.types import Operator  # type: ignore
from bpy.props import IntProperty, StringProperty  # type: ignore


# ══════════════════════════════════════════════════════════════════════
# Internal helpers
# ══════════════════════════════════════════════════════════════════════

def _active_graph(context):
    """Return ``(graph_info, graph)`` or ``(None, None)`` when there is
    no active graphml loaded.
    """
    em_tools = context.scene.em_tools
    if (em_tools.active_file_index < 0
            or em_tools.active_file_index >= len(em_tools.graphml_files)):
        return None, None
    try:
        from s3dgraphy import get_graph
        gi = em_tools.graphml_files[em_tools.active_file_index]
        return gi, get_graph(gi.name)
    except Exception:
        return None, None


def _active_mesh_candidate(context):
    """Return the active (or first selected) RM-candidate object, or
    None. Uses the standard RM candidate filter (MESH / CURVE /
    non-COLLECTION EMPTY).
    """
    from ..rm_manager.containers import is_rm_candidate
    obj = context.active_object
    if obj is not None and is_rm_candidate(obj):
        return obj
    for o in context.selected_objects:
        if is_rm_candidate(o):
            return o
    return None


def _resolve_document_for_mesh(scene, graph, mesh_obj):
    """Return ``(doc_id, doc_name)`` for the DocumentNode linked to
    ``mesh_obj``, or ``(None, "")`` when no link exists. Resolution
    order:

    1. Mesh's ``em_rm_container_doc_id`` custom property (set by the
       RM container flow).
    2. Any ``has_representation_model`` edge pointing to the mesh's
       RepresentationModelNode, resolved via ``em_rm_node_id`` or the
       matching ``rm_list`` entry's node_id.
    """
    if graph is None or mesh_obj is None:
        return None, ""
    doc_id = mesh_obj.get("em_rm_container_doc_id", "") or ""
    if doc_id:
        try:
            n = graph.find_node_by_id(doc_id)
            if n is not None and getattr(n, 'node_type', '') == 'document':
                return doc_id, getattr(n, 'name', '') or doc_id
        except Exception:
            pass
    rm_id = mesh_obj.get("em_rm_node_id", "") or ""
    if not rm_id:
        for item in scene.rm_list:
            if item.name == mesh_obj.name and item.node_id:
                rm_id = item.node_id
                break
    if not rm_id:
        return None, ""
    for edge in graph.edges:
        if (edge.edge_target == rm_id
                and edge.edge_type == "has_representation_model"):
            src = graph.find_node_by_id(edge.edge_source)
            if src is None:
                continue
            if getattr(src, 'node_type', '') != 'document':
                continue
            return src.node_id, getattr(src, 'name', '') or src.node_id
    return None, ""


def _next_extractor_for_doc(graph, doc_name: str,
                             existing_in_settings) -> str:
    """Gap-aware next free extractor name for ``doc_name``.

    Scans extractor nodes matching ``{doc_name}.N`` in the graph and
    ``extractor_id`` values already staged on other proxy-box points.
    Returns the smallest unused ``N`` — fills the first gap when one
    exists, otherwise ``max + 1``.
    """
    if not doc_name:
        return ""
    pat = re.compile(rf'^{re.escape(doc_name)}\.(\d+)$')
    used: set[int] = set()
    if graph is not None:
        for node in graph.nodes:
            if getattr(node, 'node_type', '') != 'extractor':
                continue
            name = getattr(node, 'name', '')
            if not isinstance(name, str):
                continue
            m = pat.match(name)
            if m:
                used.add(int(m.group(1)))
    for eid in existing_in_settings:
        if not eid:
            continue
        m = pat.match(eid)
        if m:
            used.add(int(m.group(1)))
    if not used:
        return f"{doc_name}.1"
    lo, hi = min(used), max(used)
    for n in range(lo, hi + 1):
        if n not in used:
            return f"{doc_name}.{n}"
    return f"{doc_name}.{hi + 1}"


# ══════════════════════════════════════════════════════════════════════
# STEP 1 — Document anchor operators
# ══════════════════════════════════════════════════════════════════════

class PROXYBOX_OT_pick_from_selected(Operator):
    """Step 1 — resolve the anchor document from the active selection.

    If the selected mesh is already linked to a DocumentNode via an
    RM container or a ``has_representation_model`` edge, the anchor is
    set immediately. Otherwise the link/create-document dialog is
    invoked to establish the link first.
    """
    bl_idname = "proxybox.pick_from_selected"
    bl_label = "Pick from selected"
    bl_description = (
        "Resolve the Step-1 anchor document from the active selection. "
        "When the mesh is already linked to a DocumentNode the anchor "
        "is set automatically; otherwise a dialog lets you pick an "
        "existing document or create a new one."
    )
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        em_tools = context.scene.em_tools
        if em_tools.active_file_index < 0:
            return False
        return _active_mesh_candidate(context) is not None

    def execute(self, context):
        scene = context.scene
        settings = scene.em_tools.proxy_box
        obj = _active_mesh_candidate(context)
        if obj is None:
            self.report({'ERROR'},
                        "No RM-candidate object selected "
                        "(need MESH / CURVE / plain EMPTY)")
            return {'CANCELLED'}
        _gi, graph = _active_graph(context)
        if graph is None:
            self.report({'ERROR'}, "No active graph")
            return {'CANCELLED'}
        doc_id, doc_name = _resolve_document_for_mesh(scene, graph, obj)
        if doc_id:
            settings.document_node_id = doc_id
            settings.document_node_name = doc_name
            self.report({'INFO'},
                        f"Anchor document resolved: {doc_name} "
                        f"(from {obj.name})")
            return {'FINISHED'}
        return bpy.ops.proxybox.link_selected_to_doc('INVOKE_DEFAULT')


class PROXYBOX_OT_link_selected_to_doc(Operator):
    """Link the selected RM candidate to a DocumentNode and set the
    Step-1 anchor.

    On confirm:

    - Auto-promotes the mesh to ``rm_list`` when an active epoch
      exists, so the downstream RM pipeline is consistent.
    - Ensures a RepresentationModelNode exists for the mesh.
    - Adds the ``has_representation_model`` edge from the picked
      Document to the RM node.
    - Sets ``settings.document_node_id`` and
      ``settings.document_node_name``.
    """
    bl_idname = "proxybox.link_selected_to_doc"
    bl_label = "Link selected mesh to document"
    bl_description = (
        "Establish a link between the selected mesh and a Document. "
        "Pick an existing one or create a new one; the mesh is "
        "promoted to rm_list and the has_representation_model edge is "
        "added."
    )
    bl_options = {'REGISTER', 'UNDO'}

    target_doc_name: StringProperty(
        name="Document",
        description="Existing document to link to",
        default="",
    )  # type: ignore

    @classmethod
    def poll(cls, context):
        em_tools = context.scene.em_tools
        return (em_tools.active_file_index >= 0
                and _active_mesh_candidate(context) is not None)

    def invoke(self, context, event):
        self.target_doc_name = ""
        return context.window_manager.invoke_props_dialog(self, width=420)

    def draw(self, context):
        layout = self.layout
        obj = _active_mesh_candidate(context)
        if obj is not None:
            layout.label(text=f"Mesh: {obj.name}", icon='OBJECT_DATA')
        layout.separator()
        from ..master_document_helpers import (
            draw_document_picker_with_create_button)
        # The shared picker offers "+ Add New Document..." which invokes
        # the standard create-master-document dialog. After the dialog
        # completes the user re-runs this operator to link.
        draw_document_picker_with_create_button(
            layout, context.scene,
            target_owner=self,
            target_prop_name="target_doc_name",
            create_new_operator="docmanager.create_master_document",
            create_new_label="+ Add New Document...",
        )

    def execute(self, context):
        scene = context.scene
        settings = scene.em_tools.proxy_box
        obj = _active_mesh_candidate(context)
        if obj is None:
            self.report({'ERROR'}, "No RM-candidate object selected")
            return {'CANCELLED'}
        _gi, graph = _active_graph(context)
        if graph is None:
            self.report({'ERROR'}, "No active graph")
            return {'CANCELLED'}
        if not self.target_doc_name:
            self.report(
                {'INFO'},
                "No document picked — use '+ Add New Document...' to "
                "create one, or type in the search field to filter "
                "existing ones.")
            return {'CANCELLED'}
        doc_node = None
        for node in graph.nodes:
            if (getattr(node, 'node_type', '') == 'document'
                    and getattr(node, 'name', '')
                    == self.target_doc_name):
                doc_node = node
                break
        if doc_node is None:
            self.report({'ERROR'},
                        f"Document {self.target_doc_name!r} not found "
                        f"in the graph")
            return {'CANCELLED'}
        doc_id = doc_node.node_id
        doc_display = getattr(doc_node, 'name', '') or doc_id

        # Auto-promote the mesh to rm_list when an active epoch exists,
        # so the downstream RM Manager is consistent with what we wire
        # up here. Mirrors RMCONTAINER_OT_add_selected_meshes.
        em_tools = scene.em_tools
        epochs = getattr(em_tools, 'epochs', None)
        has_active_epoch = (
            epochs is not None
            and len(epochs.list) > 0
            and epochs.list_index >= 0)
        rm_names = {rm.name for rm in scene.rm_list}
        if obj.name not in rm_names and has_active_epoch:
            try:
                prev_active = context.view_layer.objects.active
                prev_selection = list(context.selected_objects)
                for o in prev_selection:
                    o.select_set(False)
                obj.select_set(True)
                context.view_layer.objects.active = obj
                bpy.ops.rm.promote_to_rm('EXEC_DEFAULT', mode='SELECTED')
                obj.select_set(False)
                for o in prev_selection:
                    o.select_set(True)
                if prev_active is not None:
                    context.view_layer.objects.active = prev_active
            except Exception as e:
                self.report({'WARNING'},
                            f"Auto-promote to rm_list failed: {e}")
        elif obj.name not in rm_names and not has_active_epoch:
            self.report({'WARNING'},
                        "No active epoch — the mesh will not be added "
                        "to rm_list. Promote it manually later.")

        # Ensure the RepresentationModelNode + has_representation_model
        # edge are in place.
        from ..rm_manager.containers import (
            _ensure_rm_node_for_mesh, _has_edge)
        rm_id = _ensure_rm_node_for_mesh(scene, graph, obj)
        if rm_id and not _has_edge(
                graph, doc_id, rm_id, "has_representation_model"):
            try:
                graph.add_edge(
                    edge_id=(f"{doc_id}_has_representation_model_"
                             f"{rm_id}"),
                    edge_source=doc_id,
                    edge_target=rm_id,
                    edge_type="has_representation_model",
                )
            except Exception as e:
                self.report({'ERROR'}, f"Failed to add edge: {e}")
                return {'CANCELLED'}
        obj["em_rm_container_doc_id"] = doc_id

        settings.document_node_id = doc_id
        settings.document_node_name = doc_display
        self.report({'INFO'},
                    f"Linked {obj.name} to {doc_display} — anchor set")
        return {'FINISHED'}


class PROXYBOX_OT_search_document(Operator):
    """Step 1 — pick the anchor document from the catalog (no scene
    selection required). Sets ``settings.document_node_id`` and
    ``.document_node_name`` on confirm; does not touch any mesh.
    """
    bl_idname = "proxybox.search_document"
    bl_label = "Search document"
    bl_description = (
        "Pick an existing Document from the catalog as the Step-1 "
        "anchor. The mesh link is NOT modified — use 'Pick from "
        "selected' for that."
    )
    bl_options = {'REGISTER', 'UNDO'}

    target_doc_name: StringProperty(
        name="Document",
        description="Existing document to use as the Step-1 anchor",
        default="",
    )  # type: ignore

    @classmethod
    def poll(cls, context):
        return context.scene.em_tools.active_file_index >= 0

    def invoke(self, context, event):
        self.target_doc_name = ""
        return context.window_manager.invoke_props_dialog(self, width=420)

    def draw(self, context):
        layout = self.layout
        layout.label(text="Pick the Step-1 anchor document:",
                     icon='FILE_TEXT')
        layout.separator()
        from ..master_document_helpers import (
            draw_document_picker_with_create_button)
        draw_document_picker_with_create_button(
            layout, context.scene,
            target_owner=self,
            target_prop_name="target_doc_name",
            create_new_operator="docmanager.create_master_document",
            create_new_label="+ Add New Document...",
        )

    def execute(self, context):
        settings = context.scene.em_tools.proxy_box
        if not self.target_doc_name:
            self.report({'INFO'}, "No document picked")
            return {'CANCELLED'}
        _gi, graph = _active_graph(context)
        if graph is None:
            self.report({'ERROR'}, "No active graph")
            return {'CANCELLED'}
        for node in graph.nodes:
            if (getattr(node, 'node_type', '') == 'document'
                    and getattr(node, 'name', '')
                    == self.target_doc_name):
                settings.document_node_id = node.node_id
                settings.document_node_name = (
                    getattr(node, 'name', '') or node.node_id)
                self.report(
                    {'INFO'},
                    f"Anchor document set: {settings.document_node_name}")
                return {'FINISHED'}
        self.report({'ERROR'},
                    f"Document {self.target_doc_name!r} not found")
        return {'CANCELLED'}


class PROXYBOX_OT_clear_document(Operator):
    """Clear the Step-1 anchor document (leaves points untouched)."""
    bl_idname = "proxybox.clear_document"
    bl_label = "Clear anchor document"
    bl_description = (
        "Clear the Step-1 anchor document. Points and their already-"
        "assigned extractor ids stay.")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        settings = context.scene.em_tools.proxy_box
        settings.document_node_id = ""
        settings.document_node_name = ""
        self.report({'INFO'}, "Anchor document cleared")
        return {'FINISHED'}


# ══════════════════════════════════════════════════════════════════════
# STEP 2 — Measurement point operators
# ══════════════════════════════════════════════════════════════════════

POINT_TYPE_LABELS = {
    0: "Alignment Start",
    1: "Alignment End",
    2: "Thickness",
    3: "Quota Min",
    4: "Quota Max",
    5: "Length Start",
    6: "Length End",
}


class PROXYBOX_OT_record_point(Operator):
    """Record the current 3D cursor position into one of the 7 rows.

    When the Step-1 anchor is set and ``propagate_doc_to_points`` is
    True, the point also inherits the anchor document and gets an
    auto-computed extractor id (gap-aware, counting both graph-side
    extractors and IDs already staged on other points).
    """
    bl_idname = "proxybox.record_point"
    bl_label = "Record Point"
    bl_description = (
        "Record the 3D cursor position for this point. When the "
        "Step-1 anchor is set and 'Propagate to all 7 points' is on, "
        "the source document and extractor id are filled "
        "automatically."
    )
    bl_options = {'REGISTER', 'UNDO'}

    point_index: IntProperty(
        name="Point Index",
        description="Index of the point to record (0-6)",
        min=0,
        max=6,
        default=0,
    )  # type: ignore

    def execute(self, context):
        settings = context.scene.em_tools.proxy_box
        while len(settings.points) <= self.point_index:
            settings.points.add()
        point = settings.points[self.point_index]
        point.position = context.scene.cursor.location
        point.is_recorded = True
        point.point_type = POINT_TYPE_LABELS.get(
            self.point_index, f"Point {self.point_index + 1}")

        propagate = (settings.propagate_doc_to_points
                     and bool(settings.document_node_name))
        if propagate:
            doc_name = settings.document_node_name
            point.source_document = doc_name
            point.source_document_name = doc_name
            _gi, graph = _active_graph(context)
            existing = [
                p.extractor_id for i, p in enumerate(settings.points[:7])
                if i != self.point_index
                and p.extractor_id
                and p.source_document == doc_name]
            point.extractor_id = _next_extractor_for_doc(
                graph, doc_name, existing)

        label = POINT_TYPE_LABELS.get(
            self.point_index, f"Point {self.point_index + 1}")
        pos = context.scene.cursor.location
        msg = (f"Recorded {label}: "
               f"({pos.x:.3f}, {pos.y:.3f}, {pos.z:.3f})")
        if propagate and point.extractor_id:
            msg += f"  [{point.extractor_id}]"
        self.report({'INFO'}, msg)
        return {'FINISHED'}


class PROXYBOX_OT_clear_point(Operator):
    """Clear one recorded measurement point."""
    bl_idname = "proxybox.clear_point"
    bl_label = "Clear Point"
    bl_description = (
        "Clear the recorded position and paradata for this point")
    bl_options = {'REGISTER', 'UNDO'}

    point_index: IntProperty(
        name="Point Index",
        description="Index of the point to clear (0-6)",
        min=0,
        max=6,
        default=0,
    )  # type: ignore

    def execute(self, context):
        settings = context.scene.em_tools.proxy_box
        if self.point_index >= len(settings.points):
            self.report({'WARNING'},
                        f"Point {self.point_index + 1} does not exist")
            return {'CANCELLED'}
        point = settings.points[self.point_index]
        point.position = (0.0, 0.0, 0.0)
        point.is_recorded = False
        point.source_document = ""
        point.source_document_name = ""
        point.extractor_id = ""
        self.report({'INFO'}, f"Cleared point {self.point_index + 1}")
        return {'FINISHED'}


class PROXYBOX_OT_clear_all_points(Operator):
    """Clear every recorded point (leaves the Step-1 anchor intact)."""
    bl_idname = "proxybox.clear_all_points"
    bl_label = "Clear All Points"
    bl_description = (
        "Clear every recorded point. The Step-1 anchor document stays, "
        "so re-recording only needs fresh measurements.")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        settings = context.scene.em_tools.proxy_box
        cleared_count = 0
        for point in settings.points:
            if point.is_recorded:
                point.position = (0.0, 0.0, 0.0)
                point.is_recorded = False
                point.source_document = ""
                point.source_document_name = ""
                point.extractor_id = ""
                cleared_count += 1
        if cleared_count > 0:
            self.report({'INFO'}, f"Cleared {cleared_count} point(s)")
        else:
            self.report({'INFO'}, "No points to clear")
        return {'FINISHED'}


classes = [
    PROXYBOX_OT_pick_from_selected,
    PROXYBOX_OT_link_selected_to_doc,
    PROXYBOX_OT_search_document,
    PROXYBOX_OT_clear_document,
    PROXYBOX_OT_record_point,
    PROXYBOX_OT_clear_point,
    PROXYBOX_OT_clear_all_points,
]


def register():
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except ValueError as e:
            print(f"[proxy_box] Warning: Could not register "
                  f"{cls.__name__}: {e}")


def unregister():
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass


if __name__ == "__main__":
    register()
