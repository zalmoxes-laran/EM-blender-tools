"""RM to Proxy Suite — parent panel hosting the Proxy-Box Creator and
Surface Areas as independent, collapsible sub-panels.

Each sub-panel (see ``proxy_box_creator/ui.py`` and
``surface_areale/ui.py``) declares ``bl_parent_id = "VIEW3D_PT_RMToProxySuite"``
so they nest under this one in the N-panel sidebar. The sub-panels
remain fully independent modules with their own registration and
their own header icon; this file only provides the shared container.
"""

import bpy  # type: ignore
from bpy.types import Panel  # type: ignore

from . import icons_manager


class VIEW3D_PT_RMToProxySuite(Panel):
    """Suite container: Representation Model → Proxy pipelines
    (experimental — shipping in EM 1.6).

    Holds:
    - Proxy Box Creator (``PROXYBOX_PT_main_panel``)
    - Surface Areas (``VIEW3D_PT_SurfaceAreale``)

    Each appears as a collapsible sub-panel with its own icon to the
    left of the expand triangle. The suite is gated behind
    ``experimental_features`` so users who haven't opted in don't see
    any of the RM→Proxy tooling.
    """

    bl_label = "RM to Proxy Suite"
    bl_idname = "VIEW3D_PT_RMToProxySuite"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'EM Annotator'
    bl_order = 6
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        em_tools = getattr(context.scene, 'em_tools', None)
        if em_tools is None:
            return False
        if not getattr(em_tools, 'mode_em_advanced', False):
            return False
        return getattr(em_tools, 'experimental_features', False)

    def draw_header(self, context):
        layout = self.layout
        # Reuse the custom "RM2Proxy" PNG already shipped by the
        # addon (see icons_manager) so the suite has a distinctive
        # header. Fallback to a stock icon when the custom preview
        # is unavailable (e.g. first load during development).
        icon_id = icons_manager.get_icon_value("RM2Proxy")
        if icon_id:
            layout.label(text="", icon_value=icon_id)
        else:
            layout.label(text="", icon='EXPERIMENTAL')

    def draw(self, context):
        layout = self.layout
        em_tools = context.scene.em_tools
        # Red experimental disclaimer — same pattern used by the old
        # RM2Proxy parent panel before consolidation into the Suite.
        header = layout.row()
        header.alert = True
        header.label(
            text="Surface Areas / RM2Proxy is experimental — "
                 "EM 1.6 preview",
            icon='EXPERIMENTAL')
        if em_tools.active_file_index < 0:
            layout.label(text="Load a GraphML first", icon='ERROR')


def register():
    try:
        bpy.utils.register_class(VIEW3D_PT_RMToProxySuite)
    except ValueError:
        # Already registered — unregister and retry (hot-reload safe).
        try:
            bpy.utils.unregister_class(VIEW3D_PT_RMToProxySuite)
        except Exception:
            pass
        bpy.utils.register_class(VIEW3D_PT_RMToProxySuite)


def unregister():
    try:
        bpy.utils.unregister_class(VIEW3D_PT_RMToProxySuite)
    except Exception:
        pass
