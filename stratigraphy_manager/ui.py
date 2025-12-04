"""
UI components for the Stratigraphy Manager
This module contains all UI classes for the Stratigraphy Manager, including
panels and list UI elements.

✅ PORTED TO NEW ARCHITECTURE: Uses scene.em_tools.stratigraphy.* paths
✅ DUAL-SYNC: Maintains backward compatibility with legacy scene.em_list
"""

import bpy
from bpy.types import Panel, UIList

from .data import ensure_valid_index
from .. import icons_manager  
import os

class EM_STRAT_UL_List(UIList):
    """Custom UIList for displaying stratigraphic units with visibility toggle"""
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        icons_style = 'OUTLINER'
        scene = context.scene
        is_in_scene = item.icon == 'LINKED'  # Check if the item is linked in the scene
        
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
        em_settings = scene.em_tools.settings
        em_tools = scene.em_tools  # ✅ NEW: Access centralized properties
        strat = em_tools.stratigraphy  # ✅ NEW: Stratigraphy manager props
        obj = context.object

        # Verifica la presenza di un grafo attivo
        from ..functions import is_graph_available
        graph_available, _ = is_graph_available(context)        

        # ==================
        # HEADER BOX
        # ==================
        header_box = layout.box()
        row = header_box.row(align=True)    

        # ✅ PORTED: Use strat.units instead of scene.em_list
        if not scene.filter_by_epoch and not scene.filter_by_activity:
            row.label(text="Total Rows: " + str(len(strat.units)), icon='PRESET')
        elif scene.filter_by_epoch or scene.filter_by_activity:
            row.label(text="Filtered Rows: " + str(len(strat.units)), icon='FILTER')
        
        if scene.filter_by_epoch or scene.filter_by_activity:
            row.operator("em.reset_filters", text="", icon='CANCEL')

        # ==================
        # FILTER SECTION
        # ==================
        filter_box = layout.box()

        # 1) Header "Filter system" with triangle
        row = filter_box.row(align=True)
        row.alignment = 'EXPAND'
        
        # ✅ PORTED: Use strat.show_filter_system
        icon = 'TRIA_DOWN' if strat.show_filter_system else 'TRIA_RIGHT'
        row.prop(
            strat,
            "show_filter_system",
            emboss=False,
            icon=icon,
            text=""
        )
        row.label(text="Available filters", icon='FILTER')

        # PULSANTI SHOW ALL - Quick actions
        quick_row = row.row(align=True)
        quick_row.scale_x = 1.0
        quick_row.enabled = graph_available
        
        quick_row.operator(
            "em.strat_show_all_proxies", 
            text="", 
            icon_value=icons_manager.get_icon_value("show_all_proxies")
        )
        
        quick_row.operator(
            "em.strat_show_all_rms",
            text="", 
            icon_value=icons_manager.get_icon_value("show_all_RMs")
        )

        help1 = row.operator("em.help_popup", text="", icon='QUESTION')
        help1.title = "Filter System Help"
        help1.text = (
            "- Once activated the filter,\n"
            "  try changing epochs and/or activities\n"
            "  in their manager panel.\n"
            "- The filter will be applied in realtime\n"
            "  to the selected epoch and/or activity.\n"
            "- To reset the filter, click on the\n"
            "  X icon in the top right corner.\n"
            "- Small icons: Show All Proxies / Show All RMs\n"
        )
        help1.url = "EMtools_manual/docs/user_guide/Stratigraphy_manager.html"

        # 2) Filter contents (only when open)
        # ✅ PORTED: Use strat.show_filter_system
        if strat.show_filter_system:
            
            # Epoch / Activity toggles
            row = filter_box.row(align=True)
            filter_controls_row = row.row(align=True)
            filter_controls_row.enabled = graph_available

            # Epoch filter toggle
            epochs = scene.em_tools.epochs
            if len(epochs.list) > 0 and epochs.list_index < len(epochs.list):
                current_epoch = epochs.list[epochs.list_index].name
                filter_controls_row.prop(
                    scene, "filter_by_epoch",
                    text=current_epoch, 
                    toggle=True, 
                    icon='SORTTIME'
                )
            else:
                filter_controls_row.label(text="No epoch", icon='SORTTIME')

            filter_controls_row.separator()

            # Activity filter toggle
            if (len(scene.activity_manager.activities) > 0
                and scene.activity_manager.active_index < len(scene.activity_manager.activities)):
                current_activity = scene.activity_manager.activities[scene.activity_manager.active_index].name
                filter_controls_row.prop(
                    scene, "filter_by_activity",
                    text=current_activity, 
                    toggle=True, 
                    icon='NETWORK_DRIVE'
                )
            else:
                filter_controls_row.label(text="No activities", icon='ERROR')

            filter_controls_row.separator()

            # Sync 3D scene (only when filters are active)
            if scene.filter_by_epoch or scene.filter_by_activity:
                sync_filter_box = filter_box.box()
                row = sync_filter_box.row(align=True)
                row.label(text="Sync 3D scene with filter results:", icon='UV_SYNC_SELECT')

                row = sync_filter_box.row(align=True)
                sync_controls_row = row.row(align=True)
                sync_controls_row.enabled = graph_available

                sync_controls_row.prop(
                    scene, "sync_list_visibility",
                    text="Proxies",
                    icon='HIDE_OFF' if scene.sync_list_visibility else 'HIDE_ON'
                )
                
                if scene.filter_by_epoch:
                    sync_controls_row.prop(
                        scene, "sync_rm_visibility",
                        text="RM Models",
                        icon='OBJECT_DATA'
                    )

            # Debug tools (only if experimental features ON)
            if (hasattr(em_tools, "experimental_features")
                and em_tools.experimental_features):
                sync_filter_box = filter_box.box()
                row = sync_filter_box.row(align=True)
                row.operator("em.strat_activate_collections",
                            text="Show All Collections", icon='OUTLINER_COLLECTION')
                row.operator("em.debug_filters", text="Debug Graph", icon='CONSOLE')

            # Advanced options for epoch filter
            if hasattr(scene, "filter_by_epoch") and scene.filter_by_epoch:
                time_filter_box = filter_box.box()
                sub_row = time_filter_box.row(align=True)
                sub_row.label(text="Epoch Filter includes:", icon='SORTTIME')

                sub_row = time_filter_box.row(align=True)
                sub_row.enabled = graph_available

                icon1 = 'CHECKBOX_HLT' if scene.include_surviving_units else 'CHECKBOX_DEHLT'
                sub_row.operator("em.toggle_include_surviving",
                                text="Surviving Units", icon=icon1)

                sub_row.separator()

                icon2 = 'CHECKBOX_HLT' if scene.show_reconstruction_units else 'CHECKBOX_DEHLT'
                sub_row.operator("em.toggle_show_reconstruction",
                                text="Reconstructive Units", icon=icon2)

                # Help buttons
                help1 = sub_row.operator("em.help_popup", text="", icon='QUESTION')
                help1.title = "Survival Filter Help"
                help1.text = (
                    "Survival Filter:\n"
                    "- When enabled: Shows all units that exist in this epoch\n"
                    "- When disabled: Shows only units created in this epoch"
                )
                help1.url = "https://docs.extendedmatrix.org/survival-filter"

                help2 = sub_row.operator("em.help_popup", text="", icon='QUESTION')
                help2.title = "Reconstruction Filter Help"
                help2.text = (
                    "Reconstruction Filter:\n"
                    "- When enabled: Shows reconstruction units\n"
                    "- When disabled: Hides reconstruction units"
                )
                help2.url = "https://docs.extendedmatrix.org/reconstruction-filter"

        # ==================
        # STRATIGRAPHY LIST
        # ==================
        # ✅ PORTED: Use template_list with strat PropertyGroup
        row = layout.row()
        row.template_list(
            "EM_STRAT_UL_List",  # UIList class name
            "EM nodes",           # unique identifier
            strat,                # data: StratigraphyManagerProps PropertyGroup
            "units",              # property name (CollectionProperty)
            strat,                # active_data: same PropertyGroup
            "units_index"         # active property name (IntProperty)
        )
        
        # ==================
        # SELECTED ITEM DETAILS
        # ==================
        # ✅ PORTED: Use strat.units and strat.units_index
        if strat.units and ensure_valid_index(strat.units, strat.units_index):
            item = strat.units[strat.units_index]
    
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

            # link proxy and US
            split = row.split()
            col = split.column()
            op = col.operator("listitem.toobj", icon="LINK_BLEND", text='')
            if op:
                op.list_type = "em_list"
            
            # Add button to select the row from 3D scene
            split = row.split()
            col = split.column()
            op = col.operator("select.listitem", text="", icon="RESTRICT_SELECT_OFF")
            if op:
                op.list_type = "em_list"

            row = box.row()
            row.prop(item, "description", text="", slider=True, emboss=True)

            # Proxy sync feature
            if scene.em_tools.settings.em_proxy_sync is True:
                if obj is not None:
                    from ..functions import check_if_current_obj_has_brother_inlist, select_list_element_from_obj_proxy
                    if check_if_current_obj_has_brother_inlist(obj.name, "em_list"):
                            select_list_element_from_obj_proxy(obj, "em_list")

        # ==================
        # DOCUMENTS SECTION
        # ==================
        self.draw_documents_section(layout, context)

    def draw_documents_section(self, layout, context):
        """Draw documents section for selected stratigraphic unit"""
        scene = context.scene
        strat = scene.em_tools.stratigraphy  # ✅ NEW: Use centralized props
        
        # ✅ PORTED: Use strat.units and strat.units_index
        if not strat.units or strat.units_index < 0:
            return
        
        selected_us = strat.units[strat.units_index]
        
        # Documents header box
        docs_box = layout.box()
        
        # Header with triangle
        header_row = docs_box.row(align=True)
        header_row.alignment = 'EXPAND'
        
        # ✅ PORTED: Use strat.show_documents
        icon = 'TRIA_DOWN' if strat.show_documents else 'TRIA_RIGHT'
        header_row.prop(
            strat,
            "show_documents",
            emboss=False,
            icon=icon,
            text=""
        )
        header_row.label(text="Associated Documents", icon='FILE_FOLDER')
        
        # Help button
        help_op = header_row.operator("em.help_popup", text="", icon='QUESTION')
        help_op.title = "Documents Help"
        help_op.text = (
            "This section shows documents linked to this stratigraphic unit.\n"
            "Click on thumbnail to preview, or use buttons to open files/folders."
        )
        help_op.url = "EMtools_manual/docs/user_guide/Documents.html"
        
        # ✅ FIXED: Use reload_doc_previews_for_us() instead of inline code
        if strat.show_documents:
            print("🔍 STRATIGRAPHY MANAGER: show_documents is True")
            from ..functions import is_graph_available
            from ..thumb_utils import reload_doc_previews_for_us, has_doc_thumbs

            graph_available, graph = is_graph_available(context)
            print(f"🔍 STRATIGRAPHY MANAGER: graph_available={graph_available}")

            if not graph_available:
                docs_box.label(text="No graph loaded", icon='ERROR')
                return

            # Check if thumbnails are available
            thumbs_available = has_doc_thumbs()
            print(f"🔍 STRATIGRAPHY MANAGER: has_doc_thumbs()={thumbs_available}")

            if not thumbs_available:
                info_box = docs_box.box()
                info_box.label(text="No thumbnails generated yet", icon='INFO')
                info_box.label(text="Go to EM Setup → Auxiliary Files")
                info_box.label(text="and click '(Re)generate thumbnails'")
                return

            # Add refresh button for cache
            refresh_row = docs_box.row()
            refresh_row.operator("emtools.refresh_us_thumbs", text="Refresh Documents", icon='FILE_REFRESH')

            # Load thumbnails for this US using the centralized function
            print(f"🔍 STRATIGRAPHY MANAGER: Calling reload_doc_previews_for_us({selected_us.id_node})")
            try:
                enum_items = reload_doc_previews_for_us(selected_us.id_node)
                print(f"🔍 STRATIGRAPHY MANAGER: Got {len(enum_items) if enum_items else 0} thumbnails")

                if not enum_items:
                    docs_box.label(text="No documents found for this unit", icon='INFO')
                    docs_box.label(text="Try clicking 'Refresh Documents' after importing", icon='INFO')
                    return

                # Display thumbnails using icon_value from preview collection
                # enum_items format: (doc_key, doc_name, src_path, icon_id, i)
                content_box = docs_box.box()

                for doc_key, doc_name, src_path, icon_id, idx in enum_items:
                    row = content_box.row(align=True)

                    # Thumbnail using icon_id from preview collection
                    row.label(text="", icon_value=icon_id)
                    row.label(text=doc_name)

                    # Action buttons
                    col = row.column(align=True)

                    # Open folder button
                    if src_path:
                        folder_path = os.path.dirname(bpy.path.abspath(src_path))
                        op = col.operator("wm.path_open", text="", icon='FILE_FOLDER')
                        op.filepath = folder_path

                        # Open file button
                        op = col.operator("wm.path_open", text="", icon='FILE')
                        op.filepath = bpy.path.abspath(src_path)

            except Exception as e:
                docs_box.label(text=f"Error loading thumbnails: {str(e)}", icon='ERROR')
                import traceback
                traceback.print_exc()

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
