# anastylosis_manager/ui.py
"""UIList, Panel, and graph-load handler for the Anastylosis Manager."""

import bpy
from bpy.types import Panel, UIList

from .. import icons_manager
from .lod_utils import LOD_MIN_LEVEL, LOD_MAX_LEVEL, detect_lod_variants


class ANASTYLOSIS_UL_List(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        try:
            if self.layout_type in {'DEFAULT', 'COMPACT'}:
                # Get the object
                obj = bpy.data.objects.get(item.name)

                # Main row
                row = layout.row(align=True)

                # LOD indicator — fixed width, first element
                lod_variants = detect_lod_variants(item.name)
                sub = row.row(align=True)
                sub.ui_units_x = 2.3
                if len(lod_variants) >= 1:
                    op = sub.operator("anastylosis.open_lod_menu", text=str(item.active_lod), icon='MOD_DECIM')
                    op.anastylosis_index = index
                else:
                    sub.label(text="X", icon='MOD_DECIM')

                # Object name
                if hasattr(item, 'object_exists') and item.object_exists:
                    icon_value=icons_manager.get_icon_value("show_all_special_finds")
                    row.prop(item, "name", text="", emboss=False, icon_value=icon_value)
                else:
                    row.prop(item, "name", text="", emboss=False, icon='ERROR')

                # Search SF/VSF button (between name and SF label)
                op = row.operator("anastylosis.search_sf_node", text="", icon='VIEWZOOM', emboss=False)
                op.anastylosis_index = index

                # Associated SF/VSF node
                if hasattr(item, 'sf_node_name') and item.sf_node_name:
                    icon_value=icons_manager.get_icon_value("show_all_proxies")
                    row.label(text=item.sf_node_name, icon_value=icon_value)
                else:
                    row.label(text="[Not Connected]", icon='QUESTION')

                # Selection object (inline)
                op = row.operator("anastylosis.select_from_list", text="", icon='RESTRICT_SELECT_OFF', emboss=False)
                op.anastylosis_index = index

                # Publish flag with custom icons
                if hasattr(item, 'is_publishable'):
                    pub_icon = icons_manager.get_icon_value("em_publish") if item.is_publishable else icons_manager.get_icon_value("em_no_publish")
                    if pub_icon:
                        row.prop(item, "is_publishable", text="", icon_value=pub_icon)
                    else:
                        row.prop(item, "is_publishable", text="", icon='EXPORT' if item.is_publishable else 'CANCEL')

                # Trash bin for removing
                op = row.operator("anastylosis.remove_from_list", text="", icon='TRASH', emboss=False)
                op.anastylosis_index = index

            elif self.layout_type in {'GRID'}:
                layout.alignment = 'CENTER'
                layout.label(text="", icon='OBJECT_DATA')

        except Exception as e:
            # In case of error, show basic element
            row = layout.row()
            row.label(text=f"Error: {str(e)}", icon='ERROR')


class VIEW3D_PT_Anastylosis_Manager(Panel):
    bl_label = "Anastylosis (RMSF)"
    bl_idname = "VIEW3D_PT_Anastylosis_Manager"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'EM Annotator'
    bl_order = 2
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

        # Show connection info if an item is selected
        if anastylosis.list_index >= 0 and len(anastylosis.list) > 0:
            item = anastylosis.list[anastylosis.list_index]

            if item.sf_node_id:
                box = layout.box()
                row = box.row(align=True)
                sf_icon = 'OUTLINER_OB_EMPTY' if item.is_virtual else 'MESH_ICOSPHERE'
                row.label(text=f"Connected to: {item.sf_node_name}", icon=sf_icon)
                help_op = row.operator("em.help_popup", text="", icon='QUESTION')
                help_op.title = "Anastylosis Target"
                help_op.text = (
                    "The Special Find (SF) or Virtual SF (VSF)\n"
                    "node this object represents. The connection\n"
                    "is made via a has_representation_model edge\n"
                    "in the graph."
                )
                help_op.url = "panels/anastylosis_manager.html#anastylosis-target"
                help_op.project = 'em_tools'
            else:
                box = layout.box()
                row = box.row(align=True)
                row.label(text="Not connected to any SpecialFind", icon='INFO')
                help_op = row.operator("em.help_popup", text="", icon='QUESTION')
                help_op.title = "Anastylosis Target"
                help_op.text = (
                    "This object is not linked to any SF/VSF.\n"
                    "Select it in the scene and use 'Link to SF'\n"
                    "to create the connection."
                )
                help_op.url = "panels/anastylosis_manager.html#anastylosis-target"
                help_op.project = 'em_tools'

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
