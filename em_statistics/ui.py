# em_statistics/ui.py

import bpy
from bpy.types import Panel


class EM_PT_ExportPanel(Panel):
    bl_label = "Export statistics (Experimental)"
    bl_idname = "EM_PT_ExportPanel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'EM Bridge'
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        # Show only if experimental features are enabled
        return hasattr(context.scene, 'em_tools') and context.scene.em_tools.experimental_features

    def draw_header(self, context):
        self.layout.label(text="", icon='EXPERIMENTAL')

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


classes = (
    EM_PT_ExportPanel,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
