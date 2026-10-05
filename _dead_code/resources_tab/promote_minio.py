"""F1 (MICRO-DOVE-LAVORI, 5 Oct 2026) · «Promote to MinIO», out of Files.

It was a second way of uploading beside «Upload» (per file, into the room's
store); only the Files panel drew it, and no script, test or other module
called `em.resources_promote_minio` (grep, 5 Oct 2026). The MinIO promotion it
called (`resource_backend.promote_resource_to_minio`) stays: the Publication
Deck's «Publish this distribution» uses it.
"""

import bpy  # type: ignore
from bpy.types import Operator  # type: ignore

from ...resources_tab import resource_backend
from ...resources_tab.operators import _active


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


