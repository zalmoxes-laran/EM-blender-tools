"""
UI components for the Epoch Manager
This module contains all UI classes for the Epoch Manager, including
panels and list UI elements.
"""

import bpy
from bpy.types import Panel, UIList

class EM_UL_named_epoch_managers(UIList):
    """UIList for displaying epochs with visibility and selection toggles"""
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        epoch_list = item
        icons_style = 'OUTLINER'
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            # Show only the epoch name and color, removing dates
            layout.prop(epoch_list, "name", text="", emboss=False)
            
            # select operator
            icon = 'RESTRICT_SELECT_ON' if epoch_list.is_selected else 'RESTRICT_SELECT_OFF'
            if icons_style == 'OUTLINER':
                icon = 'VIEWZOOM' if epoch_list.use_toggle else 'VIEWZOOM'
            layout = layout.split(factor=0.1, align=True)
            layout.prop(epoch_list, "epoch_RGB_color", text="", emboss=True, icon_value=0)
            op = layout.operator(
                "epoch_manager.toggle_select", text="", emboss=False, icon=icon)

            op.group_em_idx = index

            # lock operator
            icon = 'LOCKED' if epoch_list.is_locked else 'UNLOCKED'
            if icons_style == 'OUTLINER':
                icon = 'RESTRICT_SELECT_OFF' if epoch_list.is_locked else 'RESTRICT_SELECT_ON'
            op = layout.operator("epoch_manager.toggle_selectable", text="", emboss=False, icon=icon)
            op.group_em_idx = index

            # view operator
            icon = 'RESTRICT_VIEW_OFF' if epoch_list.use_toggle else 'RESTRICT_VIEW_ON'
            op = layout.operator(
                "epoch_manager.toggle_visibility", text="", emboss=False, icon=icon)
            op.group_em_vis_idx = index

        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'

class EM_UL_List(UIList):
    """General list UI for displaying elements with icons"""
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        icons_style = 'OUTLINER'
        scene = context.scene
        layout = layout.split(factor=0.03, align=True)
        layout.label(text="", icon=item.icon_db)
        layout = layout.split(factor=0.30, align=True)
        layout.label(text=item.name, icon=item.icon)
        layout.label(text=item.description, icon='NONE', icon_value=0)

class EM_BasePanel:
    """Base panel for Epoch Manager"""
    bl_label = "Epochs Manager"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_options = {'DEFAULT_CLOSED'}
    
    @classmethod
    def poll(cls, context):
        em_tools = context.scene.em_tools
        # Returns True if mode_switch is False, so the panel is only shown in 3D GIS mode
        return em_tools.mode_switch

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        row = layout.row()
        ob = context.object

        if len(scene.em_list) > 0:
            row.template_list(
                "EM_UL_named_epoch_managers", "", scene, "epoch_list", scene, "epoch_list_index")
            
            # Add the subpanel with epoch details
            if scene.epoch_list_index >= 0 and len(scene.epoch_list) > 0:
                epoch = scene.epoch_list[scene.epoch_list_index]
                
                # Collapsible box for epoch details
                box = layout.box()
                row = box.row()
                row.prop(scene, "show_epoch_details", 
                        icon='TRIA_DOWN' if scene.show_epoch_details else 'TRIA_RIGHT',
                        emboss=False, text="Epoch details")
                
                # Show details only if the panel is expanded
                if scene.show_epoch_details:
                    col = box.column(align=True)
                    # Start and end dates
                    row = col.row()
                    row.label(text="Years time-span:")
                    row = col.row(align=True)
                    row.prop(epoch, "start_time", text="Start")
                    row.prop(epoch, "end_time", text="End")
        
        else:
            row.label(text="No epochs here :-(")

class VIEW3D_PT_BasePanel(Panel, EM_BasePanel):
    """Panel in the 3D View for the Epoch Manager"""
    bl_category = "EM"
    bl_idname = "VIEW3D_PT_BasePanel"
    bl_context = "objectmode"

def register_ui():
    """Register UI classes."""
    classes = [
        EM_UL_named_epoch_managers,
        EM_UL_List,
        VIEW3D_PT_BasePanel,
    ]
    
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except ValueError:
            # Class might already be registered
            pass

def unregister_ui():
    """Unregister UI classes."""
    classes = [
        VIEW3D_PT_BasePanel,
        EM_UL_List,
        EM_UL_named_epoch_managers,
    ]
    
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except ValueError:
            # Class might already be unregistered
            pass
