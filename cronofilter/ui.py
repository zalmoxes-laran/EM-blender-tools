# cronofilter/ui.py
"""UIList + Panel for the CronoFilter chronological horizons manager."""

import bpy
from bpy.types import Panel, UIList


class CF_UL_HorizonList(UIList):
    """UI List for displaying chronological horizons"""

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        horizon = item
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)

            # Enabled checkbox
            row.prop(horizon, "enabled", text="")

            # Color indicator
            color_row = row.row()
            color_row.scale_x = 0.8
            color_row.prop(horizon, "color", text="")

            # Label
            label_row = row.row()
            label_row.prop(horizon, "label", text="", emboss=False)

            # Time range
            time_row = row.row()
            time_row.alignment = 'RIGHT'
            time_row.label(text=f"{horizon.start_time} - {horizon.end_time}")

        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.label(text=horizon.label)


class CF_PT_CronoFilterPanel(Panel):
    """Main CronoFilter panel"""
    bl_label = "CronoFilter"
    bl_idname = "CF_PT_cronofilter"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "EM"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        scene = context.scene
        return getattr(scene, 'landscape_mode_active', False)

    def draw(self, context):
        layout = self.layout
        cf_settings = context.scene.cf_settings

        # Header info
        box = layout.box()
        row = box.row(align=True)
        row.label(text="Chronological Horizons", icon='TIME')
        help_op = row.operator("em.help_popup", text="", icon='QUESTION')
        help_op.title = "CronoFilter"
        help_op.text = (
            "Filter scene objects by chronological horizons\n"
            "derived from the Epoch Manager. Useful for\n"
            "landscape-scale multi-site temporal slicing."
        )
        help_op.url = "panels/cronofilter.html#_CronoFilter"
        help_op.project = 'em_tools'

        # Auto + File operations
        ops_box = layout.box()
        row = ops_box.row(align=True)
        row.operator("cronofilter.auto_horizons", text="Auto from Epochs", icon='AUTO')
        row = ops_box.row(align=True)
        row.operator("cronofilter.save_horizons", text="Save", icon='FILE_TICK')
        row.operator("cronofilter.load_horizons", text="Load", icon='FILE_FOLDER')

        # Horizons list
        list_box = layout.box()
        row = list_box.row()
        row.label(text=f"Horizons ({len(cf_settings.horizons)}):")

        row = list_box.row()
        col = row.column()
        col.template_list("CF_UL_HorizonList", "horizons_list",
                          cf_settings, "horizons",
                          cf_settings, "active_horizon_index",
                          rows=4)

        # List buttons
        col = row.column(align=True)
        col.operator("cronofilter.add_horizon", text="", icon='ADD')
        col.operator("cronofilter.remove_horizon", text="", icon='REMOVE')
        col.separator()
        op = col.operator("cronofilter.move_horizon", text="", icon='TRIA_UP')
        op.direction = "UP"
        op = col.operator("cronofilter.move_horizon", text="", icon='TRIA_DOWN')
        op.direction = "DOWN"

        # Edit active horizon
        if cf_settings.horizons and cf_settings.active_horizon_index < len(cf_settings.horizons):
            active_horizon = cf_settings.horizons[cf_settings.active_horizon_index]

            edit_box = layout.box()
            row = edit_box.row()
            row.label(text="Edit Selected Horizon:", icon='GREASEPENCIL')

            row = edit_box.row()
            row.prop(active_horizon, "label")

            row = edit_box.row()
            col = row.column()
            col.prop(active_horizon, "start_time")
            col = row.column()
            col.prop(active_horizon, "end_time")

            row = edit_box.row()
            row.prop(active_horizon, "color")
            row.prop(active_horizon, "enabled")

        # Status
        status_box = layout.box()
        enabled_count = sum(1 for h in cf_settings.horizons if h.enabled)
        row = status_box.row()
        row.label(text=f"Status: {enabled_count}/{len(cf_settings.horizons)} horizons enabled")


classes = (
    CF_UL_HorizonList,
    CF_PT_CronoFilterPanel,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
