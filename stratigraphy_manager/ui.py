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
        em_settings = scene.em_settings
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
            if len(scene.epoch_list) > 0 and scene.epoch_list_index < len(scene.epoch_list):
                current_epoch = scene.epoch_list[scene.epoch_list_index].name
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
            if scene.em_settings.em_proxy_sync is True:
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
        
        # ✅ PORTED: Use strat.show_documents
        if strat.show_documents:
            from ..functions import is_graph_available, get_us_document_nodes
            from pathlib import Path
            import hashlib
            import json
            
            graph_available, graph = is_graph_available(context)
            
            if not graph_available:
                docs_box.label(text="No graph loaded", icon='ERROR')
                return
            
            # Get document nodes for this US
            doc_nodes = get_us_document_nodes(graph, selected_us.node_id)
            
            if not doc_nodes:
                docs_box.label(text="No documents found for this unit", icon='INFO')
                return
            
            # Get thumbnails directory
            em_tools = scene.em_tools
            if em_tools.active_file_index < 0 or not em_tools.graphml_files:
                docs_box.label(text="No active GraphML file", icon='ERROR')
                return
            
            active_graphml = em_tools.graphml_files[em_tools.active_file_index]
            graphml_path = Path(bpy.path.abspath(active_graphml.filepath))
            
            if not graphml_path.exists():
                docs_box.label(text="GraphML file not found", icon='ERROR')
                return
            
            thumbs_root = graphml_path.parent / ".emtools_cache" / "thumbs"
            index_file = thumbs_root / "index.json"
            
            # Load thumbnails index
            index_data = {}
            if index_file.exists():
                try:
                    with open(index_file, 'r', encoding='utf-8') as f:
                        index_data = json.load(f)
                except Exception as e:
                    print(f"Error loading thumbnail index: {e}")
            
            # Helper function for file hash
            def get_file_hash(filepath):
                with open(filepath, 'rb') as f:
                    return hashlib.sha256(f.read()).hexdigest()[:16]
            
            # Collect US thumbnails
            us_thumbnails = []
            
            for doc_node in doc_nodes:
                # Get LinkNode that connects to this document
                for pred in graph.predecessors(doc_node.name):
                    pred_node = graph.nodes[pred]
                    target_node = pred_node
                    
                    if hasattr(target_node, 'node_type') and target_node.node_type == 'LinkNode':
                        file_url = target_node.data.get("url", "") if hasattr(target_node, 'data') else ""
                        
                        if file_url:
                            file_path = os.path.abspath(bpy.path.abspath(file_url))
                            
                            if os.path.exists(file_path):
                                file_hash = get_file_hash(file_path)
                                doc_key = f"doc_{file_hash}"
                                
                                if doc_key in index_data.get("items", {}):
                                    item_data = index_data["items"][doc_key]
                                    thumb_rel_path = item_data.get("thumb", "")
                                    
                                    if thumb_rel_path:
                                        thumb_abs_path = thumbs_root / thumb_rel_path
                                        
                                        if thumb_abs_path.exists():
                                            us_thumbnails.append((
                                                doc_key,
                                                str(thumb_abs_path),
                                                doc_node.name,
                                                item_data.get("src_path", "")
                                            ))
            
            if not us_thumbnails:
                docs_box.label(text="No thumbnails available", icon='INFO')
                return
            
            # Display thumbnails in grid
            content_box = docs_box.box()
            
            for doc_key, thumb_path, doc_name, src_path in us_thumbnails:
                row = content_box.row(align=True)
                
                # Thumbnail preview
                try:
                    # ✅ PORTED: Use strat.preview_image
                    if strat.preview_image and strat.preview_image.filepath == thumb_path:
                        row.template_preview(strat.preview_image, show_buttons=False)
                    else:
                        # Load image
                        img = bpy.data.images.load(thumb_path, check_existing=True)
                        strat.preview_image = img
                        row.template_preview(img, show_buttons=False)
                except Exception as e:
                    row.label(text=f"Preview error: {doc_name}", icon='ERROR')
                
                # Action buttons
                col = row.column(align=True)
                
                # Open folder button
                op = col.operator("strat.open_document_folder", text="", icon='FILE_FOLDER')
                op.document_path = src_path
                
                # Open file button
                op = col.operator("strat.open_document_file", text="", icon='FILE')
                op.document_path = src_path
                
                # Preview button
                op = col.operator("strat.preview_document", text="", icon='ZOOM_IN')
                op.document_path = src_path
                op.document_name = doc_name

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