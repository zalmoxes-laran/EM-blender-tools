"""
UI components for the Stratigraphy Manager
This module contains all UI classes for the Stratigraphy Manager, including
panels and list UI elements.
"""

import bpy
from bpy.types import Panel, UIList

from .data import ensure_valid_index

class EM_STRAT_UL_List(UIList):
    """Custom UIList for displaying stratigraphic units with visibility toggle"""
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        icons_style = 'OUTLINER'
        scene = context.scene
        is_in_scene = item.icon == 'RESTRICT_INSTANCED_OFF'
        
        # Layout with better spacing
        row = layout.row(align=True)
        
        # First column: Chain icon (active or inactive)
        first_split = row.split(factor=0.03)
        col1 = first_split.column(align=True)
        
        # Use the same column structure but control enablement at the column level
        sub_col = col1.column(align=True)
        sub_col.enabled = is_in_scene
        
        # Always use an operator, but the column enablement controls its functionality
        op = sub_col.operator("select.fromlistitem", text="", icon=item.icon, emboss=False)
        if op:
            op.list_type = "em_list"
            op.specific_item = item.name
        
        remaining = first_split.column(align=True)
        
        # Name column (25% of remaining space)
        name_split = remaining.split(factor=0.25)
        col2 = name_split.column(align=True)
        col2.label(text=item.name)
        
        # Description and visibility toggle
        desc_vis_split = name_split.column(align=True).split(factor=0.98)
        col3 = desc_vis_split.column(align=True)
        col3.label(text=item.description)
        
        # Visibility toggle
        col4 = desc_vis_split.column(align=True)
        col4.enabled = is_in_scene
        if hasattr(item, "is_visible"):
            vis_icon = 'HIDE_OFF' if item.is_visible else 'HIDE_ON'
            op = col4.operator("em.strat_toggle_visibility", text="", icon=vis_icon, emboss=False)
            if op:
                op.index = index

class EM_ToolsPanel:
    """Base panel for Stratigraphy Manager"""
    bl_label = "Stratigraphy Manager"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        em_settings = scene.em_settings
        obj = context.object

        # Verifica la presenza di un grafo attivo
        from ..functions import is_graph_available
        graph_available, _ = is_graph_available(context)        

        header_box = layout.box()
        row = header_box.row(align=True)    
        #row.label(text="Stratigraphy Manager", icon='OUTLINER_DATA_COLLECTION')

        if not scene.filter_by_epoch and not scene.filter_by_activity:
            row.label(text="Total Rows: " + str(len(scene.em_list)), icon='PRESET')
        elif scene.filter_by_epoch or scene.filter_by_activity:
            row.label(text="Filtered Rows: " + str(len(scene.em_list)), icon='FILTER')
        
        if scene.filter_by_epoch or scene.filter_by_activity:
            row.operator("em.reset_filters", text="", icon='CANCEL')

        # FILTER SECTION
        filter_box = layout.box()

        row = filter_box.row(align=True)
        row.label(text="Available filters: " , icon='FILTER')



        row = filter_box.row(align=True)
        filter_controls_row = row.row(align=True)
        filter_controls_row.enabled = graph_available

        if len(scene.epoch_list) > 0 and scene.epoch_list_index < len(scene.epoch_list):
            current_epoch = scene.epoch_list[scene.epoch_list_index].name
            #filter_controls_row = row.row(align=True)
            filter_controls_row.prop(scene, "filter_by_epoch", text=current_epoch, toggle=True, icon='SORTTIME')

        else:
            # Just display a message
            filter_controls_row.label(text="No epoch", icon="SORTTIME")

        filter_controls_row.separator()

        if len(scene.activity_manager.activities) > 0:
            if len(scene.activity_manager.activities) > 0 and scene.activity_manager.active_index < len(scene.activity_manager.activities):
                current_activity = scene.activity_manager.activities[scene.activity_manager.active_index].name
                if hasattr(scene, "filter_by_activity"):
                    filter_controls_row.prop(scene, "filter_by_activity", text=current_activity, toggle=True, icon='NETWORK_DRIVE')
                    #filter_controls_row.label(text=current_activity, icon="")
            else:
                filter_controls_row.label(text="No activities", icon="ERROR")
        else:
            filter_controls_row.label(text="No activities", icon="ERROR")

        filter_controls_row.separator()

        if scene.filter_by_epoch or scene.filter_by_activity:
            sync_filter_box = filter_box.box() # layout.box()
            row = sync_filter_box.row(align=True)
            row.label(text="Sync 3D scene with filter results: ", icon='UV_SYNC_SELECT')

            row = sync_filter_box.row(align=True)
            sync_controls_row = row.row(align=True)
            sync_controls_row.enabled = graph_available

            # Proxy sync
            sync_controls_row.prop(scene, "sync_list_visibility", text="Proxies", 
                    icon='HIDE_OFF' if scene.sync_list_visibility else 'HIDE_ON')

            # RM sync
            if scene.filter_by_epoch:
                sync_controls_row.prop(scene, "sync_rm_visibility", text="RM Models", 
                        icon='OBJECT_DATA')

        # Debug button (only if experimental features are enabled)
        if hasattr(context.scene.em_tools, "experimental_features") and context.scene.em_tools.experimental_features:

            # Button to activate all collections with proxies
            row = sync_filter_box.row(align=True)
            row.operator("em.strat_activate_collections", text="Show All Collections", icon='OUTLINER_COLLECTION')
            row.operator("em.debug_filters", text="Debug Graph", icon='CONSOLE')

        # We verify that the properties exist before using them
        if hasattr(scene, "filter_by_epoch"):
            # If epoch filter is active, show option to include surviving units
            if scene.filter_by_epoch:
                time_filter_box = filter_box.box() # layout.box()
                
                sub_row = time_filter_box.row(align=True)
                
                sub_row.label(text="Epoch Filter includes: ", icon='SORTTIME')

                sub_row = time_filter_box.row(align=True)
                sub_row.enabled = graph_available
                icon = 'CHECKBOX_HLT' if scene.include_surviving_units else 'CHECKBOX_DEHLT'
                op = sub_row.operator("em.toggle_include_surviving", 
                    text="Surviving Units",
                    icon=icon)
                
                # Help button for surviving units
                help_op = sub_row.operator("em.help_popup", text="", icon='QUESTION')
                help_op.title = "Survival Filter Help"
                help_op.text = "Survival Filter:\n- When enabled: Shows all units that exist in this epoch\n- When disabled: Shows only units created in this epoch"
                help_op.url = "https://docs.extendedmatrix.org/survival-filter"
                
                sub_row.separator()

                # Add reconstruction filter
                #sub_row = filter_box.row(align=True)
                icon = 'CHECKBOX_HLT' if scene.show_reconstruction_units else 'CHECKBOX_DEHLT'
                op = sub_row.operator("em.toggle_show_reconstruction", 
                    text=" Reconstructive Units",
                    icon=icon)
                
                # Help button for reconstruction units
                help_op = sub_row.operator("em.help_popup", text="", icon='QUESTION')
                help_op.title = "Reconstruction Filter Help"
                help_op.text = "Reconstruction Filter:\n- When enabled: Shows reconstruction units\n- When disabled: Hides reconstruction units"
                help_op.url = "https://docs.extendedmatrix.org/reconstruction-filter"



        # STRATIGRAPHY LIST
        row = layout.row()

        if scene.em_list and ensure_valid_index(scene.em_list, "em_list_index"):
            row.template_list("EM_STRAT_UL_List", "EM nodes", scene, "em_list", scene, "em_list_index")
            item = scene.em_list[scene.em_list_index]
    
            # SELECTED ITEM DETAILS
            box = layout.box()
            row = box.row(align=True)
            split = row.split()
            col = split.column()
            row.prop(item, "name", text="")
            
            # node type
            split = row.split()
            col = split.column()
            row.label(text="  Type: "+item.node_type)
            
            '''
            # Add visibility toggle
            if hasattr(item, "is_visible"):
                icon = 'HIDE_OFF' if item.is_visible else 'HIDE_ON'
                op = row.operator("em.strat_toggle_visibility", text="", icon=icon)
                if op:
                    op.index = scene.em_list_index
            '''

            # link proxy and US - MODIFIED BUTTON TO IMPROVE VISIBILITY
            split = row.split()
            col = split.column()
            op = col.operator("listitem.toobj", icon="LINK_BLEND", text='')
            if op:
                op.list_type = "em_list"
            
            # Add button to select the row from 3D scene
            split = row.split()
            col = split.column()
            col.operator("select.listitem", text="", icon="RESTRICT_SELECT_OFF")
                    
            row = box.row()
            row.prop(item, "description", text="", slider=True, emboss=True)

            if scene.em_settings.em_proxy_sync is True:
                if obj is not None:
                    from ..functions import check_if_current_obj_has_brother_inlist, select_list_element_from_obj_proxy
                    if check_if_current_obj_has_brother_inlist(obj.name, "em_list"):
                            select_list_element_from_obj_proxy(obj, "em_list")
        else:
            row.label(text="No stratigraphic units here :-(")

class VIEW3D_PT_ToolsPanel(Panel, EM_ToolsPanel):
    """Panel in the 3D View for the Stratigraphy Manager"""
    bl_category = "EM"
    bl_idname = "VIEW3D_PT_ToolsPanel"
    bl_context = "objectmode"

def register_ui():
    """Register UI classes."""
    classes = [
        EM_STRAT_UL_List,
        VIEW3D_PT_ToolsPanel,
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
        VIEW3D_PT_ToolsPanel,
        EM_STRAT_UL_List,
    ]
    
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except ValueError:
            # Class might already be unregistered
            pass
