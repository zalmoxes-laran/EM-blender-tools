import bpy# type: ignore

from .functions import *
from bpy.props import * # type: ignore
from bpy.types import Operator# type: ignore
from bpy.types import Menu, Panel, UIList, PropertyGroup# type: ignore
from bpy.props import StringProperty, BoolProperty, IntProperty, CollectionProperty, BoolVectorProperty, PointerProperty# type: ignore
from bpy.app.handlers import persistent# type: ignore
from .EM_list import *

class EM_UL_US_List(bpy.types.UIList):
    bl_idname = "EM_UL_US_List"

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        split = layout.split(factor=0.5)
        split.label(text=item.name)
        split.label(text=item.status)
        #split.label(text=item.y_pos)

class VIEW3D_PT_USListPanel(bpy.types.Panel):
    bl_label = "US List for Selected Epoch"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'EM'
    bl_options = {'DEFAULT_CLOSED'}
    
    @classmethod
    def poll(cls, context):
        em_tools = context.scene.em_tools
        # Restituisce True se mode_switch è False, quindi il pannello viene mostrato solo in modalità 3D GIS
        return em_tools.mode_switch

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        if len(scene.selected_epoch_us_list) > 0:
            row = layout.row()
            row.template_list(
                "EM_UL_US_List",
                "",
                scene,
                "selected_epoch_us_list",
                scene,
                "selected_epoch_us_list_index"
            )

            if scene.selected_epoch_us_list_index >= 0 and scene.selected_epoch_us_list_index < len(scene.selected_epoch_us_list):
                item = scene.selected_epoch_us_list[scene.selected_epoch_us_list_index]
                box = layout.box()
                box.label(text=f"Name: {item.name}")
                box.label(text=f"Description: {item.description}")
                box.label(text=f"Status: {item.status}")
        else:
            layout.label(text="No US elements in this epoch.")

class EM_UL_belongob(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        split = layout.split()
        #split.label(text=str(item.epoch))
        split.prop(item, "epoch", text="", emboss=False, translate=False, icon='SORTTIME')

classes = (
    VIEW3D_PT_USListPanel,
    EM_UL_US_List,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()

