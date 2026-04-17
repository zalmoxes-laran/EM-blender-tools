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
        print("\n=== Starting Heriverse JSON Export ===")
        try:
            from s3dgraphy.exporter.json_exporter import JSONExporter
            exporter = JSONExporter(self.filepath)
            print(f"Created JSONExporter for path: {self.filepath}")

            em_tools = context.scene.em_tools
            publishable_graph_ids = []
            for graphml_item in em_tools.graphml_files:
                is_publishable = getattr(graphml_item, 'is_publishable', True)
                if is_publishable:
                    publishable_graph_ids.append(graphml_item.name)

            print(f"Exporting {len(publishable_graph_ids)} publishable graphs: {publishable_graph_ids}")

            if not publishable_graph_ids:
                self.report({'WARNING'}, "No publishable graphs found to export")
                return {'CANCELLED'}

            exporter.export_graphs(graph_ids=publishable_graph_ids)
            print("Graphs exported successfully")

            self.report({'INFO'}, f"Heriverse data successfully exported to {self.filepath}")
            return {'FINISHED'}

        except Exception as e:
            print(f"Error during JSON export: {str(e)}")
            import traceback
            print(traceback.format_exc())
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
