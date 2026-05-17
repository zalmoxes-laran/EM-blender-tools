# anastylosis_manager/ui.py
"""UIList, Panel, and graph-load handler for the Anastylosis Manager."""

import bpy
from bpy.types import Panel, UIList

from .. import icons_manager
from .lod_utils import LOD_MIN_LEVEL, LOD_MAX_LEVEL, detect_lod_variants


class ANASTYLOSIS_UL_List(UIList):
    """Compact RMSF row.

    Layout: ``[LOD] [RMSF_select] [name]   [🔍 SF] [SF name | "[---]"]
    [🔍 Doc] [Doc name | "[---]"]   [📤 publish] [🗑 delete]``

    Scene-selection actions (jump to SF proxy in viewport, jump to
    Document in catalog) are intentionally NOT on the row anymore —
    they live in the detail panel under the UIList. Keeps the row
    reserved for *associations* (search / create + status display).
    """

    _PLACEHOLDER = "[---]"

    def draw_item(self, context, layout, data, item, icon, active_data,
                  active_propname, index):
        try:
            if self.layout_type not in {'DEFAULT', 'COMPACT'}:
                layout.alignment = 'CENTER'
                layout.label(text="", icon='OBJECT_DATA')
                return

            row = layout.row(align=True)

            # ── LOD indicator (column 1, fixed width) ──────────────
            lod_variants = detect_lod_variants(item.name)
            lod_col = row.row(align=True)
            lod_col.ui_units_x = 2.3
            if len(lod_variants) >= 1:
                op = lod_col.operator(
                    "anastylosis.open_lod_menu",
                    text=str(item.active_lod), icon='MOD_DECIM')
                op.anastylosis_index = index
            else:
                lod_col.label(text="X", icon='MOD_DECIM')

            # ── RMSF_select clickable icon + mesh name (col 2-3) ──
            # The icon is a button that selects the mesh in the
            # viewport. The name stays editable inline so the user
            # can still rename the row in place.
            object_exists = (hasattr(item, 'object_exists')
                             and item.object_exists)
            rmsf_icon = icons_manager.get_icon_value("RMSF_select")
            if not rmsf_icon:
                rmsf_icon = icons_manager.get_icon_value(
                    "show_all_special_finds")
            sel_btn = row.row(align=True)
            sel_btn.enabled = object_exists
            if object_exists and rmsf_icon:
                op = sel_btn.operator(
                    "anastylosis.select_from_list",
                    text="", icon_value=rmsf_icon, emboss=False)
                op.anastylosis_index = index
            elif object_exists:
                op = sel_btn.operator(
                    "anastylosis.select_from_list",
                    text="", icon='MESH_ICOSPHERE', emboss=False)
                op.anastylosis_index = index
            else:
                sel_btn.label(text="", icon='ERROR')
            row.prop(item, "name", text="", emboss=False)

            # ── SF picker + SF name display (column 4-5) ───────────
            sf_find_icon = icons_manager.get_icon_value("SF_find")
            if sf_find_icon:
                op = row.operator(
                    "anastylosis.search_sf_node",
                    text="", icon_value=sf_find_icon, emboss=False)
            else:
                op = row.operator(
                    "anastylosis.search_sf_node",
                    text="", icon='VIEWZOOM', emboss=False)
            op.anastylosis_index = index
            sf_name = getattr(item, 'sf_node_name', '') or ''
            row.label(text=sf_name if sf_name else self._PLACEHOLDER)

            # ── Doc picker + Doc name display (column 6-7) ─────────
            doc_find_icon = icons_manager.get_icon_value("Document_find")
            if doc_find_icon:
                op = row.operator(
                    "anastylosis.search_doc_node",
                    text="", icon_value=doc_find_icon, emboss=False)
            else:
                op = row.operator(
                    "anastylosis.search_doc_node",
                    text="", icon='FILE_TEXT', emboss=False)
            op.anastylosis_index = index
            doc_name = getattr(item, 'doc_node_name', '') or ''
            row.label(text=doc_name if doc_name else self._PLACEHOLDER)

            # ── Publish flag (column 8) ────────────────────────────
            if hasattr(item, 'is_publishable'):
                pub_icon = (
                    icons_manager.get_icon_value("em_publish")
                    if item.is_publishable
                    else icons_manager.get_icon_value("em_no_publish"))
                if pub_icon:
                    row.prop(item, "is_publishable",
                             text="", icon_value=pub_icon)
                else:
                    row.prop(
                        item, "is_publishable", text="",
                        icon=('EXPORT' if item.is_publishable
                              else 'CANCEL'))

            # ── Delete row (column 9) ──────────────────────────────
            op = row.operator(
                "anastylosis.remove_from_list",
                text="", icon='TRASH', emboss=False)
            op.anastylosis_index = index

        except Exception as e:
            row = layout.row()
            row.label(text=f"Error: {str(e)}", icon='ERROR')


class VIEW3D_PT_Anastylosis_Manager(Panel):
    bl_label = "Anastylosis (RMSF)"
    bl_idname = "VIEW3D_PT_Anastylosis_Manager"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'EM Annotator'
    bl_order = 3
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        em_tools = context.scene.em_tools
        # Show only if we're in advanced EM mode
        return em_tools.mode_em_advanced

    def draw_header(self, context):
        layout = self.layout
        icon_id = icons_manager.get_icon_value("show_all_special_finds")
        if icon_id:
            layout.label(text="", icon_value=icon_id)
        else:
            layout.label(text="", icon='MESH_ICOSPHERE')

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        from ..functions import is_graph_available

        # Check if a graph is available
        graph_available, graph = is_graph_available(context)

        # Operations on selected objects (only shown when objects are selected)
        selected_objects = context.selected_objects
        if selected_objects:
            sel_count = len(selected_objects)
            box = layout.box()
            row = box.row(align=True)
            row.label(text=f"Sel: {sel_count} obj{'s' if sel_count != 1 else ''}", icon='OBJECT_DATA')
            row.operator("anastylosis.select_from_object", text="", icon='VIEWZOOM')
            row.operator("anastylosis.add_selected", text="", icon='ADD')
            sub = row.row(align=True)
            sub.alert = True
            sub.operator("anastylosis.remove_selected", text="", icon='TRASH')
            # Batch LOD dropdown (only if at least one selected object has LOD variants)
            has_lod_objects = any(len(detect_lod_variants(obj.name)) >= 1 for obj in selected_objects)
            if has_lod_objects:
                sub = row.row(align=True)
                sub.menu("ANASTYLOSIS_MT_batch_lod_selected", text="", icon='MOD_DECIM')

        box = layout.box()
        row = box.row(align=True)
        # Active graph indicator
        em_tools = scene.em_tools
        if em_tools.graphml_files and 0 <= em_tools.active_file_index < len(em_tools.graphml_files):
            gf = em_tools.graphml_files[em_tools.active_file_index]
            code = gf.graph_code if hasattr(gf, 'graph_code') and gf.graph_code not in ("site_id", "") else gf.name
            from ..stratigraphy_manager.ui import _get_graph_icon
            row.label(text=code, icon=_get_graph_icon(code))
        row.operator("anastylosis.cleanup_missing_objects", text="", icon='TRASH')
        help_op = row.operator("em.help_popup", text="", icon='QUESTION')
        help_op.title = "Anastylosis Manager"
        help_op.text = (
            "Manage anastylosis models and their links to Special Find (SF) nodes.\n"
            "Use selection actions, list management, SF linking, and LOD tools\n"
            "to keep source-based reconstruction objects aligned with the graph.\n"
            "See the documentation section for complete workflow guidance."
        )
        help_op.url = "panels/anastylosis_manager.html#anastylosis-manager"
        help_op.project = 'em_tools'

        # List of anastylosis models
        row = layout.row()
        anastylosis = scene.em_tools.anastylosis
        row.template_list(
            "ANASTYLOSIS_UL_List", "anastylosis_list",
            anastylosis, "list",
            anastylosis, "list_index"
        )

        # Detail panel under the UIList — shown when a row is active.
        # Holds the chain summary plus the scene-selection / catalog-
        # jump buttons that no longer live on the UIList row.
        if anastylosis.list_index >= 0 and len(anastylosis.list) > 0:
            item = anastylosis.list[anastylosis.list_index]
            placeholder = "[---]"
            sf_text = item.sf_node_name or placeholder
            doc_text = item.doc_node_name or placeholder

            box = layout.box()

            # Chain summary line — RMSF → SF → Doc, placeholders where
            # missing so the user reads the row top-to-bottom.
            sf_icon = 'OUTLINER_OB_EMPTY' if item.is_virtual else 'MESH_ICOSPHERE'
            chain_row = box.row(align=True)
            rmsf_icon = (icons_manager.get_icon_value("RMSF_select")
                         or 0)
            if rmsf_icon:
                chain_row.label(text=item.name, icon_value=rmsf_icon)
            else:
                chain_row.label(text=item.name, icon='MESH_ICOSPHERE')
            chain_row.label(text="→")
            chain_row.label(text=sf_text, icon=sf_icon)
            chain_row.label(text="→")
            chain_row.label(text=doc_text, icon='FILE_TEXT')
            help_op = chain_row.operator(
                "em.help_popup", text="", icon='QUESTION')
            help_op.title = "RMSF chain"
            help_op.text = (
                "The two associations are orthogonal:\n"
                "  • RMSF → SF: identity / multitemporal axis.\n"
                "    The SF node represents the same object across\n"
                "    time; multiple RMSF meshes can point at it.\n"
                "  • RMSF → Document: paradata / source axis. The\n"
                "    document anchors trustworthiness, license, and\n"
                "    the right to extract derived data (sections,\n"
                "    diameters, surface areas)."
            )
            help_op.url = "panels/anastylosis_manager.html#anastylosis-target"
            help_op.project = 'em_tools'

            # Action row: jump buttons for the LINKED entities.
            # "Select RMSF" lives on the row icon, not here, so this
            # box stays focused on the connected SF / Doc only.
            # Buttons are disabled when the relevant association is
            # missing.
            actions = box.row(align=True)

            sub = actions.row(align=True)
            sub.enabled = bool(item.sf_node_name)
            op = sub.operator(
                "anastylosis.select_sf_proxy",
                text="Select SF proxy", icon='OUTLINER_OB_EMPTY')
            op.anastylosis_index = anastylosis.list_index

            sub = actions.row(align=True)
            sub.enabled = bool(item.doc_node_id)
            op = sub.operator(
                "anastylosis.jump_to_document",
                text="Show Document", icon='ZOOM_SELECTED')
            op.doc_node_id = item.doc_node_id

            sub = actions.row(align=True)
            sub.enabled = bool(item.doc_node_id)
            sub.alert = True
            op = sub.operator(
                "anastylosis.clear_doc_node",
                text="", icon='X')
            op.anastylosis_index = anastylosis.list_index

            # LOD Management (if the selected item has LOD variants)
            lod_variants = detect_lod_variants(item.name)

            if len(lod_variants) >= 1:
                box = layout.box()
                lod_header = box.row(align=True)
                lod_header.label(text="Anastylosis Fragments (LOD)", icon='MOD_DECIM')
                help_op = lod_header.operator("em.help_popup", text="", icon='QUESTION')
                help_op.title = "Anastylosis Fragments"
                help_op.text = (
                    "Switch between LOD variants of the\n"
                    "anastylosis fragment. LOD0 is the coarsest,\n"
                    "LOD3 the most detailed. Batch switches move\n"
                    "all fragments up or down together."
                )
                help_op.url = "panels/anastylosis_manager.html#anastylosis-fragments"
                help_op.project = 'em_tools'

                row = box.row(align=True)
                op = row.operator("anastylosis.open_linked_file", text="", icon='FILE_FOLDER')
                op.anastylosis_index = anastylosis.list_index
                row.label(text="LOD:")
                for lod_level in range(LOD_MIN_LEVEL, LOD_MAX_LEVEL + 1):
                    sub = row.row(align=True)
                    sub.scale_x = 0.7
                    op = sub.operator(
                        "anastylosis.switch_lod",
                        text=str(lod_level),
                        depress=(item.active_lod == lod_level)
                    )
                    op.anastylosis_index = anastylosis.list_index
                    op.target_lod = lod_level

                # Batch LOD switch for all items
                box.separator()
                row = box.row(align=True)
                row.label(text="Batch LOD switch:", icon='PRESET')
                op = row.operator("anastylosis.batch_switch_lod", text="", icon='TRIA_LEFT')
                op.direction = -1
                op = row.operator("anastylosis.batch_switch_lod", text="", icon='TRIA_RIGHT')
                op.direction = 1

        # Settings (collapsible)
        box = layout.box()
        row = box.row()
        row.prop(anastylosis.settings, "show_settings",
                icon="TRIA_DOWN" if anastylosis.settings.show_settings else "TRIA_RIGHT",
                text="Settings",
                emboss=False)

        if anastylosis.settings.show_settings:
            row = box.row()
            row.prop(anastylosis.settings, "zoom_to_selected")


@bpy.app.handlers.persistent
def update_anastylosis_list_on_graph_load(dummy):
    """Update anastylosis list when a graph is loaded"""

    # Ensure we're in a context where we can access scene
    if not bpy.context or not hasattr(bpy.context, 'scene'):
        return

    scene = bpy.context.scene

    # Check if graph is available
    if (hasattr(scene, 'em_tools') and
        hasattr(scene.em_tools, 'graphml_files') and
        len(scene.em_tools.graphml_files) > 0 and
        scene.em_tools.active_file_index >= 0):

        try:
            # BLENDER 4.5 COMPATIBLE: Timer callback must return None or float
            def timer_callback():
                bpy.ops.anastylosis.update_list(from_graph=True)
                return None  # Required for Blender 4.5+

            bpy.app.timers.register(timer_callback, first_interval=0.5)
        except Exception as e:
            print(f"Error updating anastylosis list on graph load: {e}")


classes = (
    ANASTYLOSIS_UL_List,
    VIEW3D_PT_Anastylosis_Manager,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    if update_anastylosis_list_on_graph_load not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(update_anastylosis_list_on_graph_load)


def unregister():
    if update_anastylosis_list_on_graph_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(update_anastylosis_list_on_graph_load)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
