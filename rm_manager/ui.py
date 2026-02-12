import os as os
import bpy  # type: ignore
from bpy.types import Panel, UIList, Menu  # type: ignore

from ..functions import is_graph_available
from .. import icons_manager

# ✅ OPTIMIZED: Import object cache for O(1) lookups
from ..object_cache import get_object_cache

__all__ = [
    'VIEW3D_PT_RM_Tileset_Properties',
    'RM_UL_List',
    'RM_UL_EpochList',
    'RM_MT_epoch_selector',
    'VIEW3D_PT_RM_Manager',
    'register_ui',
    'unregister_ui',
]


class VIEW3D_PT_RM_Tileset_Properties(Panel):  # Nome corretto per la registrazione
    bl_label = "Tileset Properties"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'EM Annotator'
    bl_parent_id = "VIEW3D_PT_RM_Manager"
    bl_options = {'DEFAULT_CLOSED'}
    
    @classmethod
    def poll(cls, context):
        # Show when a tileset is selected in the RM list
        scene = context.scene
        if scene.rm_list_index >= 0 and scene.rm_list_index < len(scene.rm_list):
            rm_item = scene.rm_list[scene.rm_list_index]
            obj = get_object_cache().get_object(rm_item.name)
            # Check if it's a tileset
            return obj and "tileset_path" in obj
        return False
    
    def draw(self, context):
        layout = self.layout
        scene = context.scene
        
        # Get the selected RM item and corresponding object
        rm_item = scene.rm_list[scene.rm_list_index]
        obj = get_object_cache().get_object(rm_item.name)
        
        # Display the tileset path
        layout.label(text="Tileset Properties:")
        
        # Path field - identico al GraphML
        row = layout.row(align=True)
        row.prop(obj, '["tileset_path"]', text="Path")
        
        # Pulsante browse per file ZIP
        op = row.operator("rm.set_tileset_path", text="", icon='FILEBROWSER')
        op.object_name = obj.name
        
        # Show warning if path doesn't exist
        path = obj.get("tileset_path", "")
        if path and not os.path.exists(bpy.path.abspath(path)):
            row = layout.row()
            row.alert = True
            row.label(text="Warning: File not found!", icon='ERROR')

class RM_UL_List(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        try:
            if self.layout_type in {'DEFAULT', 'COMPACT'}:
                # Get the object to check if it's a tileset
                obj = get_object_cache().get_object(item.name)
                is_tileset = obj and "tileset_path" in obj
                
                # Determine the appropriate icon
                if is_tileset:
                    obj_icon = 'ORIENTATION_GLOBAL'  # Global icon for tileset
                elif hasattr(item, 'object_exists') and item.object_exists:
                    obj_icon = 'OBJECT_DATA'
                else:
                    obj_icon = 'ERROR'
                
                # Show warning icon if there's a mismatch
                if hasattr(item, 'epoch_mismatch') and item.epoch_mismatch:
                    obj_icon = 'ERROR'
                
                # Layout
                row = layout.row(align=True)
                
                # Name of the RM model
                row.prop(item, "name", text="", emboss=False, icon=obj_icon)
                
                # Epoch of belonging
                if hasattr(item, 'first_epoch'):
                    if item.first_epoch == "no_epoch":
                        row.label(text="[No Epoch]", icon='QUESTION')
                    else:
                        row.label(text=item.first_epoch, icon='TIME')
                else:
                    row.label(text="[Unknown]", icon='QUESTION')

                # Add list item to epoch
                op = row.operator("rm.promote_to_rm", text="", icon='ADD', emboss=False)
                op.mode = 'RM_LIST'

                # Selection object (inline)
                op = row.operator("rm.select_from_list", text="", icon='RESTRICT_SELECT_OFF', emboss=False)
                
                # Flag pubblicabile
                if hasattr(item, 'is_publishable'):
                    row.prop(item, "is_publishable", text="", icon='EXPORT' if item.is_publishable else 'CANCEL')
                
                # Add trash bin button for demote functionality
                op = row.operator("rm.demote_from_rm_list", text="", icon='TRASH', emboss=False)
                op.rm_index = index
                
            elif self.layout_type in {'GRID'}:
                layout.alignment = 'CENTER'
                layout.label(text="", icon=obj_icon)
                
        except Exception as e:
            # In caso di errore, mostra un elemento base
            row = layout.row()
            row.label(text=f"Error: {str(e)}", icon='ERROR')

class RM_UL_EpochList(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)

            # Icona per indic
            # are la prima/altre epoche
            if item.is_first_epoch:
                row.label(text="", icon='KEYFRAME_HLT')  # Prima epoch
            else:
                row.label(text="", icon='KEYFRAME')  # Altre epoche

            # Nome dell'epoca
            row.label(text=item.name)

            # Bottone per rimuovere l'associazione con l'epoca
            # Mostra sempre il bottone per rimuovere, anche con una sola epoca
            op = row.operator("rm.remove_epoch_from_rm_list", text="", icon='X', emboss=False)

        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.label(text=item.name)


class RM_MT_epoch_selector(Menu):
    bl_label = "Select Active Epoch"
    bl_idname = "RM_MT_epoch_selector"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        epochs = scene.em_tools.epochs

        if len(epochs.list) == 0:
            layout.label(text="No epochs available", icon='ERROR')
            return

        # Draw each epoch as a menu item
        for i, epoch in enumerate(epochs.list):
            # Format: "Epoch Name"
            epoch_label = epoch.name

            # Create operator to set this epoch as active
            op = layout.operator("rm.set_active_epoch", text=epoch_label, icon='TIME')
            op.epoch_index = i

            # Highlight current active epoch
            if i == epochs.list_index:
                layout.separator()

class VIEW3D_PT_RM_Manager(Panel):
    bl_label = "RM Manager"
    bl_idname = "VIEW3D_PT_RM_Manager"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'EM Annotator'
    bl_options = {'DEFAULT_CLOSED'}
        
    @classmethod
    def poll(cls, context):
        em_tools = context.scene.em_tools
        # Show only if we're in advanced EM mode
        return em_tools.mode_em_advanced
    
    def draw_header(self, context):
        layout = self.layout
        icon_id = icons_manager.get_icon_value("show_all_RMs")
        if icon_id:
            layout.label(text="", icon_value=icon_id)
        else:
            layout.label(text="", icon='OBJECT_DATA')
    
    def draw(self, context):
        layout = self.layout
        scene = context.scene
        em_tools = scene.em_tools

        # Check if a graph is available
        graph_available, _graph = is_graph_available(context)

        '''
        # Update controls
        row = layout.row(align=True)
        row.operator("rm.update_list", text="Update from Scene", icon='FILE_REFRESH').from_graph = False

        # Check if a graph is available
        if graph_available:
            row.operator("rm.update_list", text="Update from Graph", icon='NODE_MATERIAL').from_graph = True
        '''
        # Orphaned epochs detector
        row = layout.row(align=True)
        row.operator("rm.detect_orphaned_epochs", text="Detect Orphaned Epochs", icon='ERROR')

        # Orphaned epochs mapping panel (only shown when orphaned epochs are detected)
        rm_settings = scene.rm_settings
        if rm_settings.has_orphaned_epochs and len(rm_settings.orphaned_epochs) > 0:
            box = layout.box()
            box.alert = True

            # Header
            header_row = box.row()
            header_row.label(text=f"Orphaned Epochs Detected: {len(rm_settings.orphaned_epochs)}", icon='ERROR')

            # Refresh button
            refresh_row = box.row(align=True)
            refresh_row.operator("rm.refresh_orphaned_epochs", text="Refresh", icon='FILE_REFRESH')
            refresh_row.operator("rm.clear_orphaned_epochs", text="Clear", icon='X')

            box.separator()

            # Mapping table
            for orphaned_item in rm_settings.orphaned_epochs:
                item_box = box.box()

                # Row 1: Orphaned epoch info
                info_row = item_box.row()
                info_row.label(text=f"Epoch: '{orphaned_item.orphaned_epoch_name}' ({orphaned_item.object_count} objects)", icon='TIME')

                # Row 2: Replacement dropdown and select button
                mapping_row = item_box.row(align=True)
                mapping_row.label(text="Replace with:", icon='FORWARD')
                mapping_row.prop(orphaned_item, "replacement_epoch", text="")

                # Select objects button
                select_op = mapping_row.operator("rm.select_orphaned_objects", text="", icon='RESTRICT_SELECT_OFF')
                select_op.orphaned_epoch_name = orphaned_item.orphaned_epoch_name

            box.separator()

            # Apply mapping button
            apply_row = box.row()
            apply_row.scale_y = 1.5
            apply_row.operator("rm.apply_epoch_mapping", text="Apply Mapping", icon='CHECKMARK')

        # Selection sync button
        row = layout.row(align=True)
        row.operator("rm.select_from_object", text="Select from Object", icon='RESTRICT_SELECT_OFF')

        # Show active epoch
        has_active_epoch = False
        epochs = em_tools.epochs
        if len(epochs.list) > 0 and epochs.list_index >= 0:
            active_epoch = epochs.list[epochs.list_index]
            has_active_epoch = True

        # Active Epoch Selector Box
        box = layout.box()
        if has_active_epoch:
            # Dropdown to change active epoch using menu
            row = box.row(align=True)
            row.label(text="Active Epoch:", icon='TIME')

            # Create a menu-based dropdown using operator
            row.menu("RM_MT_epoch_selector", text=active_epoch.name)

            # Button to select all RMs from active epoch
            row = box.row()
            row.operator("rm.select_all_from_active_epoch", text="Select All from this Epoch", icon='RESTRICT_SELECT_OFF')

            # Add Tileset button
            row = box.row()
            row.operator("rm.add_tileset", text="Add New Cesium Tileset", icon='ORIENTATION_GLOBAL')

            # Hint
            row = box.row()
            row.scale_y = 0.8
            row.label(text="You can add multiple tilesets to the same epoch", icon='INFO')
        else:
            box.label(text="No active epoch selected", icon='INFO')

        # Main action buttons
        if has_active_epoch:
            active_object = context.active_object
            if active_object:
                box = layout.box()
                box.label(text="Operations on selected objects in 3D scene:", icon='OBJECT_DATA')
                row = box.row(align=True)

                # Clarified button labels
                op = row.operator("rm.promote_to_rm", text="Add to Active Epoch", icon='ADD')
                op.mode = 'SELECTED'

                row.operator("rm.remove_epoch_from_selected", text="Remove from Active Epoch", icon='REMOVE')

                # Demote with warning color
                row = box.row(align=True)
                row.alert = True
                row.operator("rm.demote_from_rm", text="Remove from ALL Epochs", icon='TRASH')
        else:
            box = layout.box()
            box.label(text="Select an epoch to manage RM objects", icon='INFO')

        # List of RM models
        row = layout.row()
        row.template_list(
            "RM_UL_List", "rm_list",
            scene, "rm_list",
            scene, "rm_list_index"
        )
        
        # List of associated epochs only if an RM is selected
        if scene.rm_list_index >= 0 and len(scene.rm_list) > 0:
            item = scene.rm_list[scene.rm_list_index]
            
            # Show the list of associated epochs
            box = layout.box()
            row = box.row()
            row.label(text=f"Epochs for {item.name}:")
            
            # Sublist of epochs
            row = box.row()
            row.template_list(
                "RM_UL_EpochList", "rm_epochs",
                item, "epochs",
                item, "active_epoch_index",
                rows=3  # Limit to 3 rows by default
            )
            
            # If there's a mismatch, show a warning and buttons to resolve it
            if item.epoch_mismatch:
                row = box.row()
                row.alert = True
                row.label(text="Epoch Mismatch Detected!", icon='ERROR')
                
                row = box.row(align=True)
                row.operator("rm.show_mismatch_details", icon='INFO')
                
                row = box.row(align=True)
                if graph_available:
                    row.operator("rm.resolve_mismatches", text="Use Graph Epochs", icon='NODE_MATERIAL').use_graph_epochs = True
                row.operator("rm.resolve_mismatches", text="Use Scene Epochs", icon='OBJECT_DATA').use_graph_epochs = False
        
        if em_tools.experimental_features:
            # Settings (collapsible)
            box = layout.box()
            row = box.row()
            row.prop(scene.rm_settings, "show_settings", 
                    icon="TRIA_DOWN" if scene.rm_settings.show_settings else "TRIA_RIGHT",
                    text="Settings (experimental)", 
                    emboss=False)
                    
            if scene.rm_settings.show_settings:
                row = box.row()
                row.prop(scene.rm_settings, "zoom_to_selected")
                row = box.row()
                row.prop(scene.rm_settings, "show_mismatches")
                row = box.row()
                row.prop(scene.rm_settings, "auto_update_on_load")

classes = [
    VIEW3D_PT_RM_Manager,
    VIEW3D_PT_RM_Tileset_Properties,
    RM_UL_List,
    RM_UL_EpochList,
    RM_MT_epoch_selector,
]


def _register_class_once(cls):
    try:
        bpy.utils.register_class(cls)
    except ValueError:
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
        bpy.utils.register_class(cls)


def register_ui():
    for cls in classes:
        _register_class_once(cls)


def unregister_ui():
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
