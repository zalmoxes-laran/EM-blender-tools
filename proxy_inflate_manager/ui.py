# proxy_inflate_manager/ui.py
"""Sub-panel of Visual Manager showing proxy inflate controls.

Gated behind `scene.em_tools.experimental_features` so it only appears when
the user enables experimental features in the addon preferences.
"""

import bpy
from bpy.types import Panel


class VIEW3D_PT_ProxyInflatePanel(Panel):
    bl_label = "Proxy Inflate Manager"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'EM'
    bl_parent_id = "VIEW3D_PT_visual_panel"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        em_tools = getattr(context.scene, 'em_tools', None)
        if em_tools is None:
            return False
        return getattr(em_tools, 'experimental_features', False)

    def draw_header(self, context):
        self.layout.label(text="", icon='EXPERIMENTAL')

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        # Header with help popup.
        header_row = layout.row(align=True)
        header_row.label(text="Proxy Inflate", icon='MOD_SOLIDIFY')
        help_op = header_row.operator(
            "em.help_popup", text="", icon='QUESTION')
        help_op.title = "Proxy Inflate Manager"
        help_op.text = (
            "Give flat proxies (boxes, shapes) visible thickness by\n"
            "extruding them via a Solidify modifier.\n"
            "  • Add / Activate / Deactivate / Remove per selection\n"
            "  • Inflate All applies inflation to every proxy at once\n"
            "  • Auto-Inflate on Export runs it as part of the pipeline."
        )
        help_op.url = "panels/proxy_inflate_manager.html#proxy-inflate"
        help_op.project = 'em_tools'

        # Inflation settings
        box = layout.box()
        box.row().label(text="Inflation Settings:")

        if hasattr(scene.em_tools, "proxy_inflate_thickness"):
            box.row().prop(scene.em_tools, "proxy_inflate_thickness", text="Thickness")
            box.row().prop(scene.em_tools, "proxy_inflate_offset", text="Offset")
        else:
            box.row().label(text="Settings not available. Please reload addon.")

        # Per-selection actions
        box = layout.box()
        box.row().label(text="Modify Selection:")
        row = box.row(align=True)
        row.operator("em.proxy_add_inflate", text="Add", icon='ADD')
        row.operator("em.proxy_activate_inflate", text="Activate", icon='PLAY')
        row.operator("em.proxy_deactivate_inflate", text="Deactivate", icon='PAUSE')
        row.operator("em.proxy_remove_inflate", text="Remove", icon='X')

        # Global actions
        box = layout.box()
        box.row().label(text="Global Operations:")
        box.row().operator("em.proxy_inflate_all", text="Inflate All Proxies", icon='MOD_SOLIDIFY')

        if hasattr(scene.em_tools, "proxy_auto_inflate_on_export"):
            box.row().prop(scene.em_tools, "proxy_auto_inflate_on_export", text="Auto-Inflate on Export")

        if hasattr(scene, "proxy_inflate_stats") and scene.proxy_inflate_stats:
            stats_box = layout.box()
            stats_box.row().label(text=f"Proxies with inflation: {scene.proxy_inflate_stats}")


classes = (
    VIEW3D_PT_ProxyInflatePanel,
)


def register():
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except ValueError:
            pass


def unregister():
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass
