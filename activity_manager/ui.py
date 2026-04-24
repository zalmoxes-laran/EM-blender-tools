# activity_manager/ui.py

import bpy
from bpy.types import Panel, UIList


class ACTIVITY_UL_list(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            layout.label(text=item.name, icon='NETWORK_DRIVE')
        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.label(text="")


class VIEW3D_PT_activity_manager(Panel):
    bl_label = "Activity Manager"
    bl_idname = "VIEW3D_PT_activity_manager"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'EM'
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        em_tools = context.scene.em_tools
        # Hidden in landscape/multigraph mode (not yet multigraph-aware)
        if getattr(context.scene, 'landscape_mode_active', False):
            return False
        return em_tools.mode_em_advanced

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        header_row = layout.row(align=True)
        header_row.label(text="Activities", icon='NETWORK_DRIVE')
        help_op = header_row.operator("em.help_popup", text="", icon='QUESTION')
        help_op.title = "Activity Manager"
        help_op.text = (
            "Activities group semantically related US\n"
            "(e.g. demolition, construction). The active\n"
            "one feeds the Stratigraphy Manager's\n"
            "Activity Filter."
        )
        help_op.url = "panels/activity_manager.html#_Activity_Manager"
        help_op.project = 'em_tools'

        activity_manager = scene.activity_manager
        layout.template_list(
            "ACTIVITY_UL_list", "activity_list",
            activity_manager, "activities",
            activity_manager, "active_index",
        )


classes = (
    ACTIVITY_UL_list,
    VIEW3D_PT_activity_manager,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
