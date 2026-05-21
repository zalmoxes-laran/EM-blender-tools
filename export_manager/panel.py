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
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout

        if context.mode != 'OBJECT':
            from ..ui_helpers import draw_objectmode_required_box
            draw_objectmode_required_box(layout)
            return

        export_vars = context.window_manager.export_vars

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

            if provider.help_url:
                help_op = row.operator("em.help_popup", text="", icon='QUESTION')
                help_op.title = provider.help_title or "Help"
                help_op.text = provider.help_text or ""
                help_op.url = provider.help_url
                help_op.project = 'em_tools'

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
