import os as os
import bpy  # type: ignore
from bpy.types import Panel, UIList, Menu  # type: ignore

from ..functions import is_graph_available
from .. import icons_manager
from .operators import (
    detect_lod_variants,
    LOD_MIN_LEVEL,
    LOD_MAX_LEVEL,
)

# ✅ OPTIMIZED: Import object cache for O(1) lookups
from ..object_cache import get_object_cache

__all__ = [
    'RM_UL_List',
    'RM_UL_EpochList',
    'RMCONTAINER_UL_list',
    'RM_MT_epoch_selector',
    'RM_MT_batch_lod_selected',
    'VIEW3D_PT_RM_Manager',
    'register_ui',
    'unregister_ui',
]


# Master-Document variant → UIList icon (EM 1.6). Mirrors the Document
# Manager colour coding so containers and documents look consistent.
_MASTERDOC_VARIANT_ICONS = {
    "reality_based": "COLLECTION_COLOR_01",  # red
    "observable":    "COLLECTION_COLOR_02",  # orange
    "asserted":      "COLLECTION_COLOR_03",  # yellow
    "em_based":      "COLLECTION_COLOR_05",  # blue
}


def _container_icon(scene, container):
    """Pick the right icon for a container based on its document's
    geometry axis (variant_style_key). Fallback to a neutral icon for
    un-linked Legacy containers.
    """
    if not container.doc_node_id:
        return "PACKAGE"  # Legacy / unlinked
    try:
        from s3dgraphy import get_graph
        em_tools = scene.em_tools
        if em_tools.active_file_index < 0:
            return "PACKAGE"
        gi = em_tools.graphml_files[em_tools.active_file_index]
        graph = get_graph(gi.name)
        if graph is None:
            return "PACKAGE"
        n = graph.find_node_by_id(container.doc_node_id)
        if n is not None and hasattr(n, 'variant_style_key'):
            key = n.variant_style_key()
            return _MASTERDOC_VARIANT_ICONS.get(key, "KEYTYPE_KEYFRAME_VEC")
    except Exception:
        pass
    return "KEYTYPE_KEYFRAME_VEC"


class RMCONTAINER_UL_list(UIList):
    """UIList of RM Containers (top-level). Each row shows the
    variant icon driven by the linked DocumentNode's geometry axis,
    the user-visible label, the document reference code, and the
    mesh count.
    """

    def draw_item(self, context, layout, data, item, icon, active_data,
                  active_propname, index):
        row = layout.row(align=True)
        row.label(text="", icon=_container_icon(context.scene, item))
        row.prop(item, "label", text="", emboss=False)
        ref = item.doc_name if item.doc_name else "—"
        row.label(text=f"[{ref}]")
        # Inline link/create icon — placed next to the document ref so
        # the user always sees the document-link action near the doc
        # name. FILE_TEXT echoes the document icon used elsewhere.
        link_op = row.operator("rmcontainer.link_or_create_doc",
                               text="", icon='FILE_TEXT', emboss=False)
        link_op.container_index = index
        row.label(text=f"({len(item.mesh_names)})")
        op = row.operator("rmcontainer.unregister", text="",
                          icon='TRASH', emboss=False)
        op.container_index = index


class RM_UL_List(UIList):
    def filter_items(self, context, data, propname):
        """Filter the mesh list by the active RM container.

        - No active container (``rm_containers`` empty or invalid
          index) → show every mesh in ``rm_list`` (fallback, matches
          historical behaviour before DP-47).
        - Active container present → filter strictly by its
          ``mesh_names`` membership. An empty container shows an
          empty list — NOT the full rm_list — so the user can see at
          a glance that the container is empty and populate it via
          "Add selected" or "Move selected".
        """
        try:
            from .containers import active_container
        except Exception:
            active_container = None  # type: ignore
        items = getattr(data, propname)
        filter_flags = [self.bitflag_filter_item] * len(items)
        order: list = []
        if active_container is None:
            return filter_flags, order
        ac = active_container(context.scene)
        if ac is None:
            return filter_flags, order
        allowed = {e.name for e in ac.mesh_names}
        for i, item in enumerate(items):
            if item.name not in allowed:
                filter_flags[i] = 0
        return filter_flags, order

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
                
                # Main row
                row = layout.row(align=True)

                # LOD indicator — fixed width, first element
                lod_variants = detect_lod_variants(item.name)
                sub = row.row(align=True)
                sub.ui_units_x = 2.3
                if len(lod_variants) >= 1:
                    op = sub.operator("rm.open_lod_menu", text=str(item.active_lod), icon='MOD_DECIM')
                    op.rm_index = index
                else:
                    sub.label(text="X", icon='MOD_DECIM')

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
                op.rm_index = index

                # Flag pubblicabile (custom icons)
                if hasattr(item, 'is_publishable'):
                    pub_icon = icons_manager.get_icon_value("em_publish") if item.is_publishable else icons_manager.get_icon_value("em_no_publish")
                    if pub_icon:
                        row.prop(item, "is_publishable", text="", icon_value=pub_icon)
                    else:
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


class RM_MT_batch_lod_selected(Menu):
    bl_label = "Batch LOD for Selected"
    bl_idname = "RM_MT_batch_lod_selected"

    def draw(self, context):
        layout = self.layout
        for level in range(LOD_MIN_LEVEL, LOD_MAX_LEVEL + 1):
            op = layout.operator("rm.batch_lod_selected", text=f"Set LOD {level}")
            op.target_lod = level

class VIEW3D_PT_RM_Manager(Panel):
    bl_label = "Representation Model (RM)"
    bl_idname = "VIEW3D_PT_RM_Manager"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'EM Annotator'
    bl_order = 1
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

        # ═══════════════════════════════════════════════════════════════
        # SECTION 1 (TOP) — RM Containers (DP-47 extension)
        # Container-level commands are at the TOP of the section,
        # followed by the container UIList and an active-container
        # summary. Mesh-level controls live in SECTION 2 below (between
        # the two UILists) because they operate on the content of the
        # selected container.
        #
        # Note: we can't write to Scene data during draw() (Blender
        # restriction on ID writes). The Legacy bootstrap and the full
        # sanitisation both run via explicit operators — we just
        # *detect* when a bootstrap is needed and show a one-click
        # button.
        # ═══════════════════════════════════════════════════════════════
        from .containers import active_container

        # Bootstrap notice — visible only when there are legacy RMs
        # and no containers yet.
        if len(scene.rm_containers) == 0 and len(scene.rm_list) > 0:
            boot_box = layout.box()
            boot_row = boot_box.row(align=True)
            boot_row.label(
                text=f"{len(scene.rm_list)} legacy RM(s) "
                     f"not yet grouped into a container",
                icon='INFO')
            boot_row.operator("rmcontainer.bootstrap_legacy",
                              text="Bootstrap", icon='PACKAGE')

        # Warnings banner (orphan meshes removed by the sync pass).
        if len(scene.rm_container_warnings) > 0:
            warn_box = layout.box()
            warn_box.alert = True
            wrow = warn_box.row(align=True)
            wrow.label(
                text=f"{len(scene.rm_container_warnings)} missing mesh(es) "
                     f"removed from containers",
                icon='ERROR')
            wrow.operator("rmcontainer.acknowledge_warnings",
                          text="Acknowledge", icon='CHECKMARK')
            col = warn_box.column(align=True)
            col.scale_y = 0.8
            for w in list(scene.rm_container_warnings)[:6]:
                col.label(
                    text=f"  • {w.mesh_name}  (from {w.container_label})",
                    icon='DOT')
            if len(scene.rm_container_warnings) > 6:
                col.label(
                    text=f"  • ... and {len(scene.rm_container_warnings) - 6} "
                         f"more")

        cont_box = layout.box()
        cont_box.label(text="RM Containers (wrapped by DocumentNodes)",
                       icon='OUTLINER_COLLECTION')
        # Container-level commands ABOVE the UIList (dominating the
        # list). "Add RM container" creates an empty unlinked
        # container; linking/creating documents is then handled by the
        # inline link icon on each container row, which opens a search
        # dropdown with "+ Add New Document..." as the first option.
        cmd_row = cont_box.row(align=True)
        cmd_row.operator("rmcontainer.create_empty",
                         text="Add RM container", icon='ADD')
        cmd_row.operator("rmcontainer.sync",
                         text="Sync", icon='FILE_REFRESH')
        # Container UIList
        row = cont_box.row()
        row.template_list(
            "RMCONTAINER_UL_list", "rm_containers",
            scene, "rm_containers",
            scene, "rm_containers_index",
            rows=4,
        )
        ac = active_container(scene)
        if ac is not None:
            cont_box.label(
                text=f"Active: {ac.label!r}  |  "
                     f"{len(ac.mesh_names)} mesh(es)  |  "
                     f"doc: {ac.doc_name or '—'}")

        # ═══════════════════════════════════════════════════════════════
        # SECTION 2 (MIDDLE) — Mesh-level controls between the two
        # UILists. These operate on the content of the ACTIVE container:
        # the Active Epoch selector picks which epoch the
        # promote/remove-epoch buttons will target, and the "Sel: N
        # objs" row carries the batch mesh operations.
        # ═══════════════════════════════════════════════════════════════

        # Show active epoch
        has_active_epoch = False
        epochs = em_tools.epochs
        if len(epochs.list) > 0 and epochs.list_index >= 0:
            active_epoch = epochs.list[epochs.list_index]
            has_active_epoch = True

        # Active Epoch Selector Box
        box = layout.box()
        if has_active_epoch:
            row = box.row(align=True)
            # Active graph indicator
            if em_tools.graphml_files and 0 <= em_tools.active_file_index < len(em_tools.graphml_files):
                gf = em_tools.graphml_files[em_tools.active_file_index]
                code = gf.graph_code if hasattr(gf, 'graph_code') and gf.graph_code not in ("site_id", "") else gf.name
                from ..stratigraphy_manager.ui import _get_graph_icon
                row.label(text=code, icon=_get_graph_icon(code))
            row.label(text="Active Epoch:", icon='TIME')
            row.menu("RM_MT_epoch_selector", text=active_epoch.name)
            row.operator("rm.select_all_from_active_epoch", text="", icon='SELECT_EXTEND')
            row.operator("rm.detect_orphaned_epochs", text="", icon='ORPHAN_DATA')
            row.operator("rm.cleanup_missing_objects", text="", icon='TRASH')
            help_op = row.operator("em.help_popup", text="", icon='QUESTION')
            help_op.title = "RM Manager"
            help_op.text = (
                "Manage Representation Models (RM) linked to epochs and graph data.\n"
                "Use the active epoch selector, RM list actions, LOD controls,\n"
                "and Cesium tileset tools to keep reconstruction models consistent.\n"
                "See the full manual section for workflow details."
            )
            help_op.url = "panels/rm_manager.html#_RM_Manager"
            help_op.project = 'em_tools'
        else:
            row = box.row(align=True)
            # Active graph indicator
            if em_tools.graphml_files and 0 <= em_tools.active_file_index < len(em_tools.graphml_files):
                gf = em_tools.graphml_files[em_tools.active_file_index]
                code = gf.graph_code if hasattr(gf, 'graph_code') and gf.graph_code not in ("site_id", "") else gf.name
                from ..stratigraphy_manager.ui import _get_graph_icon
                row.label(text=code, icon=_get_graph_icon(code))
            row.label(text="No active epoch selected", icon='INFO')
            row.operator("rm.detect_orphaned_epochs", text="", icon='ORPHAN_DATA')
            row.operator("rm.cleanup_missing_objects", text="", icon='TRASH')
            help_op = row.operator("em.help_popup", text="", icon='QUESTION')
            help_op.title = "RM Manager"
            help_op.text = (
                "Manage Representation Models (RM) linked to epochs and graph data.\n"
                "Use the active epoch selector, RM list actions, LOD controls,\n"
                "and Cesium tileset tools to keep reconstruction models consistent.\n"
                "See the full manual section for workflow details."
            )
            help_op.url = "panels/rm_manager.html#_RM_Manager"
            help_op.project = 'em_tools'

        # Main action buttons — operate on selected mesh objects.
        # The "+ to container" button is placed here so mesh-level
        # controls stay grouped.
        if has_active_epoch:
            selected_objects = context.selected_objects
            if selected_objects:
                sel_count = len(selected_objects)
                box = layout.box()
                row = box.row(align=True)
                row.label(text=f"Sel: {sel_count} obj{'s' if sel_count != 1 else ''}", icon='OBJECT_DATA')
                row.operator("rm.select_from_object", text="", icon='VIEWZOOM')
                op = row.operator("rm.promote_to_rm", text="", icon='ADD')
                op.mode = 'SELECTED'
                row.operator("rm.remove_epoch_from_selected", text="", icon='REMOVE')
                sub = row.row(align=True)
                sub.alert = True
                sub.operator("rm.demote_from_rm", text="", icon='TRASH')
                has_lod_objects = any(len(detect_lod_variants(obj.name)) >= 1 for obj in selected_objects)
                if has_lod_objects:
                    sub = row.row(align=True)
                    sub.menu("RM_MT_batch_lod_selected", text="", icon='MOD_DECIM')
                # Container-scoped ops: add selected meshes to the
                # active container, or move them between containers.
                # Each enabled by its own poll().
                row.separator()
                row.operator("rmcontainer.add_selected_meshes",
                             text="", icon='IMPORT')
                row.operator("rmcontainer.move_selected_to_container",
                             text="", icon='EXPORT')
        else:
            box = layout.box()
            box.label(text="Select an epoch to manage RM objects", icon='INFO')

        # ═══════════════════════════════════════════════════════════════
        # SECTION 3 (BOTTOM) — Mesh list, filtered by active container.
        # ═══════════════════════════════════════════════════════════════
        row = layout.row()
        row.template_list(
            "RM_UL_List", "rm_list",
            scene, "rm_list",
            scene, "rm_list_index"
        )
        
        # List of associated epochs only if an RM is selected
        if scene.rm_list_index >= 0 and len(scene.rm_list) > 0:
            item = scene.rm_list[scene.rm_list_index]

            # LOD Management (if selected item has LOD variants)
            lod_variants = detect_lod_variants(item.name)
            if len(lod_variants) >= 1:
                box = layout.box()
                lod_header = box.row(align=True)
                lod_header.label(text="Levels of Detail", icon='MOD_DECIM')
                help_op = lod_header.operator("em.help_popup", text="", icon='QUESTION')
                help_op.title = "RM Levels of Detail"
                help_op.text = (
                    "Switch between multiple LOD variants\n"
                    "of the representation model. LOD0 is the\n"
                    "coarsest, LOD3 the most detailed. Batch\n"
                    "switch moves all RMs up or down together."
                )
                help_op.url = "panels/rm_manager.html#rm-lod"
                help_op.project = 'em_tools'

                row = box.row(align=True)
                op = row.operator("rm.open_linked_file", text="", icon='FILE_FOLDER')
                op.rm_index = scene.rm_list_index
                row.label(text="LOD:")
                for lod_level in range(LOD_MIN_LEVEL, LOD_MAX_LEVEL + 1):
                    sub = row.row(align=True)
                    sub.scale_x = 0.7
                    op = sub.operator(
                        "rm.switch_lod",
                        text=str(lod_level),
                        depress=(item.active_lod == lod_level)
                    )
                    op.rm_index = scene.rm_list_index
                    op.target_lod = lod_level

                box.separator()
                row = box.row(align=True)
                row.label(text="Batch LOD switch:", icon='PRESET')
                op = row.operator("rm.batch_switch_lod", text="", icon='TRIA_LEFT')
                op.direction = -1
                op = row.operator("rm.batch_switch_lod", text="", icon='TRIA_RIGHT')
                op.direction = 1
            
            # Show the list of associated epochs
            box = layout.box()
            row = box.row(align=True)
            row.label(text=f"Epochs for {item.name}:", icon='TIME')
            help_op = row.operator("em.help_popup", text="", icon='QUESTION')
            help_op.title = "RM Epochs"
            help_op.text = (
                "Epochs the RM belongs to. One is marked\n"
                "as 'first' (filled keyframe icon). Filters\n"
                "in the Stratigraphy Manager use these to\n"
                "decide which RMs to show at a given time."
            )
            help_op.url = "panels/rm_manager.html#rm-epochs"
            help_op.project = 'em_tools'
            
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
        
        # Settings (collapsible)
        box = layout.box()
        row = box.row()
        row.prop(scene.rm_settings, "show_settings",
                icon="TRIA_DOWN" if scene.rm_settings.show_settings else "TRIA_RIGHT",
                text="Settings",
                emboss=False)

        if scene.rm_settings.show_settings:
            row = box.row()
            row.prop(scene.rm_settings, "zoom_to_selected")

            if em_tools.experimental_features:
                row = box.row()
                row.prop(scene.rm_settings, "show_mismatches")
                row = box.row()
                row.prop(scene.rm_settings, "auto_update_on_load")

        # Cesium Tilesets management
        if has_active_epoch:
            box = layout.box()
            box.label(text="Cesium Tilesets:", icon='ORIENTATION_GLOBAL')
            row = box.row()
            row.operator("rm.add_tileset", text="Add New Cesium Tileset", icon='ADD')

            # Inline tileset properties (replaces the old subpanel)
            if scene.rm_list_index >= 0 and scene.rm_list_index < len(scene.rm_list):
                rm_item = scene.rm_list[scene.rm_list_index]
                obj = get_object_cache().get_object(rm_item.name)
                if obj and "tileset_path" in obj:
                    row = box.row()
                    row.prop(
                        scene.rm_settings, "show_tileset_properties",
                        icon="TRIA_DOWN" if scene.rm_settings.show_tileset_properties else "TRIA_RIGHT",
                        text=f"Tileset Properties: {rm_item.name}",
                        emboss=False,
                    )

                    if scene.rm_settings.show_tileset_properties:
                        row = box.row(align=True)
                        row.prop(obj, '["tileset_path"]', text="Path")
                        op = row.operator("rm.set_tileset_path", text="", icon='FILEBROWSER')
                        op.object_name = obj.name

                        path = obj.get("tileset_path", "")
                        if path and not os.path.exists(bpy.path.abspath(path)):
                            row = box.row()
                            row.alert = True
                            row.label(text="Warning: File not found!", icon='ERROR')

# NOTE: VIEW3D_PT_RMDoc_Manager has been moved to document_manager/ui.py
# as a standalone panel (bl_order=3) rather than a sub-panel of RM Manager.

classes = [
    VIEW3D_PT_RM_Manager,
    RM_UL_List,
    RM_UL_EpochList,
    RMCONTAINER_UL_list,
    RM_MT_epoch_selector,
    RM_MT_batch_lod_selected,
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
