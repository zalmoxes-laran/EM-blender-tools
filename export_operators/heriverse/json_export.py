# export_operators/heriverse/json_export.py
"""Operator to export only the JSON (graphs + metadata) in Heriverse format.

Renamed from legacy ``JSON_OT_exportEMformat`` to ``HERIVERSE_OT_export_json``
to disambiguate from the dead EMviq operator of the same Python class name.
The Blender-facing ``bl_idname`` stays ``export.heriversejson`` so existing
callers keep working.
"""

import bpy
from bpy.props import BoolProperty, StringProperty
from bpy.types import Operator
from bpy_extras.io_utils import ExportHelper

from ...functions import em_log


class HERIVERSE_OT_export_json(Operator, ExportHelper):
    """Export project data in Heriverse JSON format"""
    bl_idname = "export.heriversejson"
    bl_label = "Export Heriverse JSON"
    bl_options = {"REGISTER", "UNDO"}

    filename_ext = ".json"

    use_file_dialog: BoolProperty(
        name="Use File Dialog",
        description="Use the file dialog to choose where to save the JSON",
        default=True,
    ) # type: ignore

    filepath: StringProperty(
        name="File Path",
        description="Path to save the JSON file",
        default="",
    ) # type: ignore

    def invoke(self, context, event):
        if self.use_file_dialog:
            return ExportHelper.invoke(self, context, event)
        return self.execute(context)

    def execute(self, context):
        em_log("\n=== Starting Heriverse JSON Export ===", "INFO")
        try:
            from s3dgraphy.exporter.json_exporter import JSONExporter
            exporter = JSONExporter(self.filepath)
            em_log(f"Created JSONExporter for path: {self.filepath}", "DEBUG")

            em_tools = context.scene.em_tools
            publishable_graph_ids = []
            for graphml_item in em_tools.graphml_files:
                is_publishable = getattr(graphml_item, 'is_publishable', True)
                if is_publishable:
                    publishable_graph_ids.append(graphml_item.name)

            em_log(f"Exporting {len(publishable_graph_ids)} publishable graphs: {publishable_graph_ids}", "DEBUG")

            if not publishable_graph_ids:
                self.report({'WARNING'}, "No publishable graphs found to export")
                return {'CANCELLED'}

            # DP-56: mirror scene georef state onto each graph's
            # GeoPositionNode before serialization. In 1.6 the GeoNode is
            # a passive reflection of scene state (scene.em_georef, BGIS,
            # or 3DSC) — populated here so the Heriverse JSON carries the
            # shift + EPSG for frontend consumption.
            try:
                from ...georef_manager import graph_sync
                from s3dgraphy import get_graph
                g = context.scene.em_georef
                for graph_id in publishable_graph_ids:
                    graph = get_graph(graph_id)
                    if graph is None:
                        continue
                    graph_sync.push_to_geonode(
                        graph,
                        g.epsg or None,
                        g.shift_x, g.shift_y, g.shift_z,
                    )
            except Exception as exc:
                em_log(f"[DP-56] GeoPositionNode mirror skipped: {exc}", "WARNING")

            exporter.export_graphs(graph_ids=publishable_graph_ids)
            em_log("Graphs exported successfully", "DEBUG")

            self.report({'INFO'}, f"Heriverse data successfully exported to {self.filepath}")
            return {'FINISHED'}

        except Exception as e:
            em_log(f"Error during JSON export: {str(e)}", "ERROR")
            import traceback
            em_log(traceback.format_exc(), "ERROR")
            self.report({'ERROR'}, f"Error during export: {str(e)}")
            return {'CANCELLED'}


classes = (
    HERIVERSE_OT_export_json,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
