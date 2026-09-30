"""Il pannello delle letture 3D: figlio del Visual Manager, perché è la lente.

Non crea e non registra niente nel grafo: mostra dove guardano le letture, sul
modello su cui sono state prese (EM16-UX: la lente sta accanto a ciò che mostra).
"""

import bpy  # type: ignore
from bpy.types import Panel  # type: ignore

from . import core


class VIEW3D_PT_em_readings(Panel):
    bl_label = "3D readings"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "EM"
    bl_parent_id = "VIEW3D_PT_visual_panel"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        layout.operator("em.show_readings", icon='CURVE_PATH')
        coll = bpy.data.collections.get(core.COLLECTION)
        if coll is None:
            return
        objs = [o for o in coll.objects if o.get(core.PROP_ID)]
        layout.label(text=f"{len(objs)} in {core.COLLECTION} · read-only",
                     icon='LOCKED')
        moved = [o for o in objs if o.get(core.PROP_MOVED)]
        if moved:
            box = layout.box()
            box.label(text="Moved in Blender, not in the graph:", icon='ERROR')
            for o in moved[:8]:
                box.label(text=o.name)
            box.label(text="Show again to put them back.")


classes = (VIEW3D_PT_em_readings,)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
