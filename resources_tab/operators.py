"""Operators for the EM Scene tab.

Scan the DosCo / library folder into the R1 FS-index backend (stable IDs), set the
DosCo folder via a folder picker, "hat" a Shelf orphan into a Master Document that
ADOPTS the FS stable ID as its node_id, and "Promote to MinIO" a local resource
(in-process s3dgraphy, preserving the stable ID). All graph writes go through the
s3dgraphy graph (em.json = truth) and persist through the existing GraphML
round-trip. Nothing here is a 3D object.
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


def _active_graphml_item(context):
    """The active GraphMLFileItem, or None."""
    try:
        em_tools = context.scene.em_tools
        return em_tools.graphml_files[em_tools.active_file_index]
    except Exception:
        return None


def _active(context):
    """(ok, graph, folder, graph_code). Reports nothing; UI/ops decide.
    Resolves the DosCo folder via the shared resolver (legacy dosco_dir AND the
    newer auxiliary-files system)."""
    from ..functions import check_active_graph
    ok, graph = check_active_graph(context, show_message=False)
    if not ok or graph is None:
        return False, None, "", None
    folder = ""
    item = _active_graphml_item(context)
    if item is not None:
        try:
            from ..em_setup.resource_utils import resolve_dosco_dir
            folder = resolve_dosco_dir(item) or ""
        except Exception:
            folder = bpy.path.abspath(item.dosco_dir) if getattr(item, "dosco_dir", "") else ""
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


class EM_OT_resources_set_dosco_folder(Operator):
    bl_idname = "em.resources_set_dosco_folder"
    bl_label = "Set DosCo folder"
    bl_description = ("Choose the DosCo / library folder for the active GraphML "
                      "(opens a folder browser)")
    bl_options = {'REGISTER'}

    # a directory-only file browser (subtype DIR_PATH, no filename field)
    directory: bpy.props.StringProperty(subtype='DIR_PATH')  # type: ignore

    def invoke(self, context, event):
        if _active_graphml_item(context) is None:
            self.report({'WARNING'}, "No active GraphML — select one in EM Setup.")
            return {'CANCELLED'}
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        item = _active_graphml_item(context)
        if item is None:
            self.report({'WARNING'}, "No active GraphML.")
            return {'CANCELLED'}
        item.dosco_dir = self.directory
        self.report({'INFO'}, f"DosCo folder set: {self.directory}")
        for area in context.screen.areas:
            area.tag_redraw()
        return {'FINISHED'}


class EM_OT_resources_promote_minio(Operator):
    bl_idname = "em.resources_promote_minio"
    bl_label = "Promote to MinIO"
    bl_description = ("Upload this local resource into the shared MinIO object "
                      "store (keeps its stable ID) and repoint its locator")
    bl_options = {'REGISTER', 'UNDO'}

    resource_id: bpy.props.StringProperty()  # type: ignore

    def execute(self, context):
        if not resource_backend.minio_supported():
            self.report({'ERROR'},
                        "MinIO unavailable: needs the dev s3dgraphy (./em.sh s3d) "
                        "AND the 'minio' extra (pip install s3dgraphy[minio]).")
            return {'CANCELLED'}
        ok, graph, _folder, _gc = _active(context)
        if not ok:
            self.report({'WARNING'}, "No active graph.")
            return {'CANCELLED'}
        if not self.resource_id:
            return {'CANCELLED'}
        try:
            res = resource_backend.promote_resource_to_minio(graph, self.resource_id)
        except Exception as exc:
            self.report({'ERROR'}, f"Promote failed: {exc}")
            return {'CANCELLED'}
        context.scene.em_resources.status = f"Promoted → {res['s3_uri']}"
        for area in context.screen.areas:
            area.tag_redraw()
        return {'FINISHED'}


classes = (
    EM_OT_resources_scan,
    EM_OT_resources_set_dosco_folder,
    EM_OT_resources_hat_document,
    EM_OT_resources_promote_minio,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
