"""EM ▸ Export ▸ Export statistics… (T1, 5 Oct 2026): the panel of the old EM
Room tab as a dialog in the header menu — a rare gesture, and a file's.

The body is what the panel drew (now in `_dead_code/em_statistics/ui.py`): the
options of the CSV and the export operator that writes it."""

import bpy
from bpy.types import Operator


class EM_OT_export_statistics_dialog(Operator):
    """Export mesh statistics (volume, optional weight by material) to CSV"""

    bl_idname = "em.export_statistics_dialog"
    bl_label = "Export statistics"
    bl_options = {'REGISTER'}

    def invoke(self, context, event):
        return context.window_manager.invoke_popup(self, width=380)

    def draw(self, context):
        layout = self.layout
        header_row = layout.row(align=True)
        header_row.label(text="Mesh Statistics", icon='MESH_DATA')
        help_op = header_row.operator("em.help_popup", text="", icon='QUESTION')
        help_op.title = "Export Statistics"
        help_op.text = (
            "Export mesh statistics (volume, optional\n"
            "weight by material) to CSV for reporting\n"
            "and material take-off calculations."
        )
        help_op.url = "panels/export_statistics.html#export-statistics"
        help_op.project = 'em_tools'
        scene_props = context.scene.em_properties
        layout.prop(scene_props, "export_volume")
        layout.prop(scene_props, "export_weight")
        if scene_props.export_weight:
            layout.prop(scene_props, "material_list")
        layout.operator("export_mesh.csv")

    def execute(self, context):
        return {'FINISHED'}


classes = (EM_OT_export_statistics_dialog,)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
