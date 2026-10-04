"""U2 · the panel of «Offset proxy», under Proxy & surface tools."""

import bpy
from bpy.types import Panel

from . import operators as ops


class VIEW3D_PT_proxy_offset(Panel):
    bl_label = "Offset proxy"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "EM Scene"
    bl_parent_id = "EM_PT_proxy_surface_tools"
    bl_order = 3
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        self.layout.label(text="", icon='MOD_DISPLACE')

    def draw(self, context):
        layout = self.layout
        em = context.scene.em_tools
        row = layout.row(align=True)
        row.prop(em, "proxy_offset_distance", text="Distance")
        help_op = row.operator("em.help_popup", text="", icon='QUESTION')
        help_op.title = "Offset proxy"
        help_op.text = (
            "Where the annotated surface is flat (a facade)\n"
            "the proxy z-fights with the RM. This moves it a\n"
            "little outside, along its normals, with a modifier:\n"
            "the mesh is not touched and Back on the surface\n"
            "removes it. Changing the distance moves every\n"
            "proxy already offset."
        )
        help_op.url = "panels/proxy_tools.html#offset-proxy"
        help_op.project = 'em_tools'
        col = layout.column(align=True)
        row = col.row(align=True)
        op = row.operator("em.proxy_offset", text="Selected", icon='MOD_DISPLACE')
        op.scope = 'SELECTED'
        op = row.operator("em.proxy_offset", text="All proxies", icon='MOD_DISPLACE')
        op.scope = 'ALL'
        row = col.row(align=True)
        op = row.operator("em.proxy_offset_remove", text="Back on the surface", icon='X')
        op.scope = 'SELECTED'
        op = row.operator("em.proxy_offset_remove", text="All", icon='X')
        op.scope = 'ALL'
        n = ops.count_offset()
        layout.label(text=f"{n} prox{'y' if n == 1 else 'ies'} offset by {em.proxy_offset_distance * 1000:g} mm"
                     if n else "no proxy offset", icon='INFO')
        old = ops.count_old_inflate()
        if old:
            box = layout.box()
            box.label(text=f"{old} object(s) still carry the old inflation (Solidify)", icon='ERROR')
            box.operator("em.proxy_old_inflate_remove", icon='TRASH')


def register():
    bpy.utils.register_class(VIEW3D_PT_proxy_offset)


def unregister():
    try:
        bpy.utils.unregister_class(VIEW3D_PT_proxy_offset)
    except RuntimeError:
        pass
