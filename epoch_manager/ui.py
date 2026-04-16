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
        scene = context.scene
        
        # NUOVA LOGICA: Nascondere se in modalità Landscape
        if hasattr(scene, 'landscape_mode_active') and scene.landscape_mode_active:
            return False
        
        # Logica originale: mostra solo in modalità Advanced EM
        return em_tools.mode_em_advanced


    def draw(self, context):
        layout = self.layout
        scene = context.scene
        em_tools = scene.em_tools
        epochs = em_tools.epochs
        ob = context.object

        header_row = layout.row(align=True)
        header_row.label(text="Epochs", icon='TIME')
        help_op = header_row.operator("em.help_popup", text="", icon='QUESTION')
        help_op.title = "Epochs Manager"
        help_op.text = (
            "List of epochs from the active graph. Pick one\n"
            "to make it the Active Epoch (used by filters,\n"
            "RM assignment, and visibility tools). Expand\n"
            "details for time-span and custom HDR lighting."
        )
        help_op.url = "panels/epochs_manager.html#_Epochs_Manager"
        help_op.project = 'em_tools'

        row = layout.row()
        row.template_list(
            "EM_UL_named_epoch_managers", "", em_tools.epochs, "list", em_tools.epochs, "list_index")

        if len(epochs.list) > 0:
            # Add the subpanel with epoch details
            if epochs.list_index >= 0 and len(epochs.list) > 0:
                epoch = epochs.list[epochs.list_index]
                
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

                # --- Epoch Lighting section ---
                box_light = layout.box()
                row = box_light.row()
                row.prop(scene, "show_epoch_lighting",
                         icon='TRIA_DOWN' if scene.show_epoch_lighting else 'TRIA_RIGHT',
                         emboss=False, text="Epoch Lighting")

                if scene.show_epoch_lighting:
                    col = box_light.column(align=True)
                    col.prop(epoch, "epoch_lighting_enabled", text="Custom Lighting")

                    # Sub-column disabled when lighting is off
                    sub = col.column(align=True)
                    sub.enabled = epoch.epoch_lighting_enabled
                    sub.separator()
                    sub.prop(epoch, "epoch_hdr_path", text="HDR")
                    sub.prop(epoch, "epoch_hdr_rotation", text="Rotation")
                    sub.prop(epoch, "epoch_hdr_intensity", text="Intensity")

                    if epoch.epoch_lighting_enabled and not epoch.epoch_hdr_path:
                        row = box_light.row()
                        row.alert = True
                        row.label(text="No HDR image assigned", icon='ERROR')

                    row = box_light.row()
                    row.operator("epoch_manager.apply_epoch_lighting",
                                 text="Apply Lighting", icon='WORLD')

        #else:
        #    row.label(text="No epochs here :-(")

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
