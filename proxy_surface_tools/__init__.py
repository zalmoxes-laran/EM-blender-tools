"""`Proxy & surface tools` — the container that gives the drawing tools a rank.

EM16-UX (E.D., 11-09-2026). The criterion from here on is that there are three
families of panel: the **managers**, which register and curate entities of the
graph; the **tools**, which produce geometry; the **lens**, which neither
creates nor registers but changes how you see what is there.

Proxy Box, Surface Areas and Proxy Inflate are tools sitting among managers in
the `EM Scene` tab. Nesting them under one container is what tells them apart
IN RANK without moving them away from the work they serve — which is why this
panel is empty of its own content: it is a level of nesting, not a place with
things in it.

`Proxy Inflate Manager` arrives here from the Visual Manager, and the reason is
the rule above: it inflates geometry, so it is a tool. The Visual Manager is
the lens — it colours properties of the graph — and the projection panel that
stays there paints colours rather than making geometry.
"""

import bpy  # type: ignore
from bpy.types import Panel  # type: ignore


class EM_PT_proxy_surface_tools(Panel):
    """Empty by design: a level of nesting, not a place with things in it.

    Its children declare it with `bl_parent_id`, so opening this panel opens
    them with it and closing it puts the whole toolbox away — which is the
    point of the grouping.
    """

    bl_label = "Proxy & surface tools"
    bl_idname = "EM_PT_proxy_surface_tools"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "EM Scene"
    bl_order = 6
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        self.layout.label(text="", icon='TOOL_SETTINGS')

    def draw(self, context):
        # Nothing of its own. The one line it does draw says what the container
        # is for, because a panel that opens onto three collapsed children and
        # no words looks like it failed to load.
        col = self.layout.column()
        col.scale_y = 0.8
        col.label(text="Tools that draw geometry, grouped away from the managers.",
                  icon='INFO')


_CLASSES = (EM_PT_proxy_surface_tools,)


def register():
    for cls in _CLASSES:
        try:
            bpy.utils.register_class(cls)
        except ValueError:
            pass


def unregister():
    for cls in reversed(_CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except (RuntimeError, ValueError):
            pass
