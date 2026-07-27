"""Operators for the EM Resources tab (R4).

Scan the DosCo / library folder into the R1 FS-index backend (stable IDs), and
"hat" a Shelf orphan into a Master Document that ADOPTS the FS stable ID as its
node_id. All graph writes go through the s3dgraphy graph (em.json = truth) and
persist through the existing GraphML round-trip. Nothing here is a 3D object.
"""

from __future__ import annotations

import os

import bpy
from bpy.types import Operator

from . import resource_backend

# Session cache: folder → scanned FSIndexBackend. The manifest on disk keeps IDs
# stable across sessions; this cache keeps the SAME backend instance between
# "scan" and "hat" within a session so a listed orphan's stable ID matches the
# id adopted on hatting.
_BACKENDS: dict = {}


def get_cached_backend(folder: str):
    return _BACKENDS.get(os.path.abspath(folder)) if folder else None


def _active(context):
    """(ok, graph, folder, graph_code). Reports nothing; UI/ops decide."""
    from ..functions import check_active_graph
    ok, graph = check_active_graph(context, show_message=False)
    if not ok or graph is None:
        return False, None, "", None
    folder = ""
    try:
        em_tools = context.scene.em_tools
        item = em_tools.graphml_files[em_tools.active_file_index]
        if getattr(item, "dosco_dir", ""):
            folder = bpy.path.abspath(item.dosco_dir)
    except Exception:
        folder = ""
    graph_code = None
    attrs = getattr(graph, "attributes", None) or {}
    if isinstance(attrs, dict):
        graph_code = attrs.get("graph_code")
    return True, graph, folder, graph_code


class EM_OT_resources_scan(Operator):
    bl_idname = "em.resources_scan"
    bl_label = "Scan resources folder"
    bl_description = ("Scan the DosCo / library folder into the resource index "
                      "(stable IDs). Orphans appear in the Shelf.")
    bl_options = {'REGISTER'}

    def execute(self, context):
        p = context.scene.em_resources
        if not resource_backend.resources_supported():
            self.report({'ERROR'},
                        "Resource layer unavailable: the active s3dgraphy is stale — "
                        "activate the dev/updated s3dgraphy (./em.sh s3d), then reopen.")
            return {'CANCELLED'}
        ok, _graph, folder, _gc = _active(context)
        if not ok:
            self.report({'WARNING'}, "No active graph selected.")
            return {'CANCELLED'}
        if not folder or not os.path.isdir(folder):
            self.report({'WARNING'},
                        "No valid DosCo/library folder set for the active GraphML.")
            return {'CANCELLED'}
        try:
            backend = resource_backend.get_backend(folder)
        except Exception as exc:
            self.report({'ERROR'}, f"Scan failed: {exc}")
            return {'CANCELLED'}
        _BACKENDS[os.path.abspath(folder)] = backend
        n = len(backend.entries(present_only=True))
        p.scanned_folder = folder
        p.status = f"Indexed {n} file(s)"
        for area in context.screen.areas:
            area.tag_redraw()
        return {'FINISHED'}


class EM_OT_resources_hat_document(Operator):
    bl_idname = "em.resources_hat_document"
    bl_label = "Create Document from resource"
    bl_description = ("Promote this Shelf resource to a Master Document. The "
                      "document adopts the resource's stable ID as its node id.")
    bl_options = {'REGISTER', 'UNDO'}

    resource_id: bpy.props.StringProperty()  # type: ignore
    key_id: bpy.props.StringProperty()  # type: ignore
    new_name: bpy.props.StringProperty(name="Name")  # type: ignore
    new_description: bpy.props.StringProperty(name="Description", default="")  # type: ignore

    def invoke(self, context, event):
        if not self.new_name:
            self.new_name = self.key_id or "Document"
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        col = self.layout.column()
        col.prop(self, "new_name")
        col.prop(self, "new_description")
        col.label(text=f"Adopts stable ID: {self.resource_id[:8]}…", icon='LINKED')
        col.label(text="Anchor it to an epoch later in the EM tree.", icon='INFO')

    def execute(self, context):
        if not resource_backend.resources_supported():
            self.report({'ERROR'}, "Resource layer unavailable (stale s3dgraphy).")
            return {'CANCELLED'}
        ok, graph, _folder, _gc = _active(context)
        if not ok:
            self.report({'WARNING'}, "No active graph.")
            return {'CANCELLED'}
        if not self.resource_id:
            return {'CANCELLED'}
        try:
            node = resource_backend.hat_orphan_as_document(
                graph, self.resource_id,
                name=self.new_name or self.key_id or "Document",
                description=self.new_description.strip())
        except Exception as exc:
            self.report({'ERROR'}, f"Create document failed: {exc}")
            return {'CANCELLED'}
        # Refresh EMTools document lists so it shows up immediately.
        try:
            from ..master_document_helpers import refresh_document_lists
            refresh_document_lists(context, node, graph)
        except Exception:
            pass
        context.scene.em_resources.status = f"Hatted {self.key_id or self.resource_id[:8]} → Document"
        for area in context.screen.areas:
            area.tag_redraw()
        return {'FINISHED'}


classes = (
    EM_OT_resources_scan,
    EM_OT_resources_hat_document,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
