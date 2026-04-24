# export_manager/panel.py
"""Generic Export panel that iterates over registered providers."""

import bpy
from bpy.types import Panel

from .registry import get_providers


class VIEW3D_PT_ExportPanel(Panel):
    bl_label = "Export Manager"
    bl_idname = "VIEW3D_PT_ExportPanel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'EM Bridge'
    bl_context = "objectmode"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        export_vars = context.window_manager.export_vars

        header_row = layout.row(align=True)
        header_row.label(text="Export Manager", icon='EXPORT')
        help_op = header_row.operator("em.help_popup", text="", icon='QUESTION')
        help_op.title = "Export Manager"
        help_op.text = (
            "Export graphs, 3D data and paradata for\n"
            "Heriverse deployment, or as tabular CSV.\n"
            "Each sub-section targets a specific\n"
            "publication pipeline."
        )
        help_op.url = "panels/export_manager.html#export-manager"
        help_op.project = 'em_tools'

        for provider in get_providers():
            if not provider.poll(context):
                continue

            box = layout.box()
            row = box.row()

            expand_attr = f"{provider.id}_expanded"
            has_toggle = hasattr(export_vars, expand_attr)

            if has_toggle:
                expanded = getattr(export_vars, expand_attr)
                row.prop(
                    export_vars,
                    expand_attr,
                    text=provider.label,
                    icon='TRIA_DOWN' if expanded else 'TRIA_RIGHT',
                    emboss=False,
                )
            else:
                expanded = True
                row.label(text=provider.label, icon=provider.icon)

            if expanded:
                provider.draw(box, context)


classes = (
    VIEW3D_PT_ExportPanel,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
