"""
UI components for the Stratigraphy Manager
This module contains all UI classes for the Stratigraphy Manager, including
panels and list UI elements.
"""

import bpy
from bpy.types import Panel, UIList

from .data import ensure_valid_index

from .. import icons_manager  

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

        # 1) Header "Filter system" with triangle
        row = filter_box.row(align=True)

        #row.separator()
        row.alignment = 'EXPAND'
        icon = 'TRIA_DOWN' if scene.show_filter_system else 'TRIA_RIGHT'
        row.prop(
            scene,
            "show_filter_system",
            emboss=False,
            icon=icon,
            text=""
        )
        row.label(text="Available filters", icon='FILTER')

        # PULSANTI SHOW ALL - inseriti prima del pulsante help
        # Crea una sotto-riga per i pulsanti piccoli
        quick_row = row.row(align=True)
        quick_row.scale_x = 1.0  # Rende tutti i pulsanti di questa riga più piccoli
        quick_row.enabled = graph_available  # Abilitati solo se il grafo è disponibile
        
        # Pulsante Show All Proxies
        quick_row.operator(
            "em.strat_show_all_proxies", 
            text="", 
            #icon='MESH_CIRCLE'
            icon_value=icons_manager.get_icon_value("show_all_proxies")
        )
        
        # Pulsante Show All RMs
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
            "  red cross icon in the top right corner.\n"
            "- Small icons: Show All Proxies / Show All RMs\n"
        )
        help1.url = "EMstructure.html#us-usv-manager"



        # 2) Filter contents (only when open)
        if scene.show_filter_system:

            # Epoch / Activity toggles
            row = filter_box.row(align=True)
            filter_controls_row = row.row(align=True)
            
            row = filter_box.row(align=True)
            filter_controls_row = row.row(align=True)

            filter_controls_row.enabled = graph_available

            if len(scene.epoch_list) > 0 and scene.epoch_list_index < len(scene.epoch_list):
                current_epoch = scene.epoch_list[scene.epoch_list_index].name
                filter_controls_row.prop(
                    scene, "filter_by_epoch",
                    text=current_epoch, toggle=True, icon='SORTTIME'
                )
            else:
                filter_controls_row.label(text="No epoch", icon='SORTTIME')

            filter_controls_row.separator()

            if (len(scene.activity_manager.activities) > 0
                and scene.activity_manager.active_index < len(scene.activity_manager.activities)):
                current_activity = scene.activity_manager.activities[scene.activity_manager.active_index].name
                filter_controls_row.prop(
                    scene, "filter_by_activity",
                    text=current_activity, toggle=True, icon='NETWORK_DRIVE'
                )
            else:
                filter_controls_row.label(text="No activities", icon='ERROR')

            filter_controls_row.separator()

            # Sync 3D scene
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

            # Debug (solo se sperimentale ON)
            if (hasattr(context.scene.em_tools, "experimental_features")
                and context.scene.em_tools.experimental_features):
                sync_filter_box = filter_box.box()
                row = sync_filter_box.row(align=True)
                row.operator("em.strat_activate_collections",
                            text="Show All Collections", icon='OUTLINER_COLLECTION')
                row.operator("em.debug_filters", text="Debug Graph", icon='CONSOLE')

            # Opzioni avanzate per epoch
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

                # Bottoni Help
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

        # STRATIGRAPHY LIST
        row = layout.row()
        row.template_list("EM_STRAT_UL_List", "EM nodes", scene, "em_list", scene, "em_list_index")
        if scene.em_list and ensure_valid_index(scene.em_list, "em_list_index"):
            
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
            op = col.operator("select.listitem", text="", icon="RESTRICT_SELECT_OFF")
            if op:
                op.list_type = "em_list"

            row = box.row()
            row.prop(item, "description", text="", slider=True, emboss=True)

            if scene.em_settings.em_proxy_sync is True:
                if obj is not None:
                    from ..functions import check_if_current_obj_has_brother_inlist, select_list_element_from_obj_proxy
                    if check_if_current_obj_has_brother_inlist(obj.name, "em_list"):
                            select_list_element_from_obj_proxy(obj, "em_list")
        #else:
        #    row.label(text="No stratigraphic units here :-(")

        # ✅ NUOVO: Documents section
        self.draw_documents_section(layout, context)

    def draw_documents_section(self, layout, context):
        """Draw documents section for selected stratigraphic unit"""
        scene = context.scene
        
        # Check if we have a selected stratigraphic unit
        if not scene.em_list or scene.em_list_index < 0:
            return
        
        selected_us = scene.em_list[scene.em_list_index]
        
        # Documents header box
        docs_box = layout.box()
        
        # Header with triangle
        header_row = docs_box.row(align=True)
        
        # Use a scene boolean for show/hide (simple approach)
        if not hasattr(scene, 'show_strat_documents'):
            scene.show_strat_documents = False
        
        icon = 'TRIA_DOWN' if scene.show_strat_documents else 'TRIA_RIGHT'
        header_row.prop(scene, "show_strat_documents", emboss=False, icon=icon, text="")
        header_row.label(text=f"Documents for {selected_us.name}", icon='DOCUMENTS')
        
        # Documents content (if expanded)
        if scene.show_strat_documents:
            
            # Controlla se ci sono thumbnails disponibili
            from ..thumb_utils import has_doc_thumbs
            
            if has_doc_thumbs():
                # ✅ NUOVO: Griglia anteprime con thumbnails
                thumb_row = docs_box.row()
                thumb_row.template_icon_view(
                    scene.em_tools, 
                    "em_doc_previews", 
                    show_labels=False,
                    scale=5.0
                )
                
                # Pulsanti azione per documento selezionato
                if hasattr(scene.em_tools, 'em_doc_previews') and scene.em_tools.em_doc_previews:
                    action_row = docs_box.row(align=True)
                    '''
                    # Pulsante seleziona (opzionale)
                    select_op = action_row.operator(
                        "emtools.select_doc_from_thumb", 
                        text="Select",
                        icon='RESTRICT_SELECT_OFF'
                    )
                    select_op.doc_key = scene.em_tools.em_doc_previews
                    '''
                    # Pulsante apri originale (IMPORTANTE: usa sempre src_path)
                    open_op = action_row.operator(
                        "emtools.open_original_doc", 
                        text="Open original",
                        icon='FILE_FOLDER'
                    )
                    open_op.doc_key = scene.em_tools.em_doc_previews
            
            else:
                # ✅ FALLBACK: Sistema precedente senza thumbnails
                documents = self._get_documents_from_graph(context, selected_us.id_node)
                
                if len(documents) == 0:
                    # No documents message
                    content_row = docs_box.row()
                    content_row.label(text="No documents found", icon='INFO')
                else:
                    # Show each document (sistema precedente)
                    for doc_node in documents:
                        self.draw_document_item(docs_box, context, doc_node)
                
                # Suggerimento per generare thumbnails
                if documents:  # Solo se ci sono documenti
                    hint_row = docs_box.row()
                    hint_row.label(text="💡 Genera thumbnails in EMsetup → File ausiliari", icon='INFO')

    def _get_documents_from_graph(self, context, us_node_id):
        """Get DocumentNode connected to this US directly from the graph"""
        from s3dgraphy import get_graph
        
        try:
            scene = context.scene
            em_tools = scene.em_tools
            
            if em_tools.active_file_index >= 0:
                graphml = em_tools.graphml_files[em_tools.active_file_index]
                graph = get_graph(graphml.name)
                
                if graph:
                    connected_docs = []
                    
                    # Find edges from US to DocumentNode
                    for edge in graph.edges:
                        if edge.edge_source == us_node_id:
                            target_node = graph.find_node_by_id(edge.edge_target)
                            if target_node and hasattr(target_node, 'node_type') and target_node.node_type == 'document':
                                connected_docs.append(target_node)
                    
                    print(f"Found {len(connected_docs)} documents for US node {us_node_id}")
                    return connected_docs
                    
        except Exception as e:
            print(f"Error getting documents from graph: {e}")
        
        return []

    def draw_document_item(self, layout, context, doc_node):
        """Draw individual document item with asset-style preview"""
        
        # Document item box
        item_box = layout.box()
        
        # Get file info
        doc_url = getattr(doc_node, 'url', '')
        if not doc_url:
            # Simple text fallback
            item_box.label(text=f"{doc_node.name} (No URL)", icon='FILE')
            return
        
        ext = doc_url.lower().split('.')[-1] if '.' in doc_url else 'unknown'
        is_image = ext in ['jpg', 'jpeg', 'png', 'tif', 'tiff', 'bmp']
        
        if is_image:
            # Image preview with asset-style layout
            self.draw_image_asset_item(item_box, context, doc_node, doc_url, ext)
        else:
            # Non-image document
            self.draw_document_text_item(item_box, context, doc_node, doc_url, ext)

    def draw_image_asset_item(self, layout, context, doc_node, doc_url, ext):
        """Draw image with asset-style preview"""
        
        # Main row: preview + info + buttons
        main_row = layout.row(align=True)
        
        # Left: Image preview area
        preview_col = main_row.column(align=True)
        preview_col.scale_x = 0.3
        
        # Check if preview exists (READ ONLY)
        preview_image = self._check_existing_preview(doc_node.name)
        
        if preview_image:
            # Show existing image preview
            preview_col.template_preview(preview_image, show_buttons=False)
        else:
            # Show load button placeholder
            preview_box = preview_col.box()
            preview_box.scale_y = 2.0
            load_op = preview_box.operator("strat.preview_document", text="Load", icon='PREVIEW_RANGE')
            load_op.document_url = doc_url
            load_op.document_name = doc_node.name
        
        # Right: Info and buttons
        info_col = main_row.column(align=True)
        
        # Document name
        info_col.label(text=doc_node.name, icon='IMAGE_DATA')
        info_col.label(text=f"{ext.upper()} Image", icon='FILE')
        
        # Action buttons row
        buttons_row = info_col.row(align=True)
        buttons_row.scale_y = 0.8
        
        # Load/Refresh preview
        load_op = buttons_row.operator("strat.preview_document", text="Preview", icon='PREVIEW_RANGE')
        load_op.document_url = doc_url
        load_op.document_name = doc_node.name
        
        # Open file
        open_op = buttons_row.operator("strat.open_document_file", text="Open", icon='FILE_FOLDER')
        open_op.document_url = doc_url
        
        # Open folder
        folder_op = buttons_row.operator("strat.open_document_folder", text="Folder", icon='FOLDER_REDIRECT')
        folder_op.document_url = doc_url

    def _check_existing_preview(self, doc_name):
        """Check if preview already exists (READ ONLY)"""
        preview_name = f"StratPreview_{doc_name}"
        
        # SOLO lettura - nessuna modifica
        for img in bpy.data.images:
            if img.name == preview_name:
                return img
        
        return None

    def draw_document_text_item(self, layout, context, doc_node, doc_url, ext):
        """Draw non-image document item"""
        
        main_row = layout.row(align=True)
        
        # Document icon
        icon_col = main_row.column(align=True)
        icon_col.scale_x = 0.15
        if ext == 'pdf':
            icon_col.label(text="", icon='FILE_TEXT')
        else:
            icon_col.label(text="", icon='FILE')
        
        # Info
        info_col = main_row.column(align=True)
        info_col.label(text=doc_node.name)
        info_col.label(text=f"{ext.upper()} Document")
        
        # Buttons
        buttons_col = main_row.column(align=True)
        buttons_row = buttons_col.row(align=True)
        buttons_row.scale_x = 0.8
        
        open_op = buttons_row.operator("strat.open_document_file", text="", icon='FILE_FOLDER')
        open_op.document_url = doc_url
        
        folder_op = buttons_row.operator("strat.open_document_folder", text="", icon='FOLDER_REDIRECT')
        folder_op.document_url = doc_url

    def draw_image_preview(self, layout, context):
        """Draw image preview section"""
        scene = context.scene
        docs = scene.strat_documents
        
        if not docs.loaded_image:
            return
        
        # Preview box
        preview_box = layout.box()
        preview_row = preview_box.row()
        preview_row.label(text="Preview:", icon='IMAGE_DATA')
        
        # Image preview
        preview_row = preview_box.row()
        preview_row.template_preview(docs.loaded_image, show_buttons=False)


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
