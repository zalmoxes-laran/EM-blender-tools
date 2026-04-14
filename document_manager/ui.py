"""UI components for the 3D Document Manager.

Panel in the EM Annotator sidebar tab, alongside RM Manager and Anastylosis Manager.
Provides document listing with master/instance distinction, 3D representation management,
image import, camera creation, and look-through controls.
"""

import bpy
from bpy.types import Panel, UIList
from .. import icons_manager


# Map certainty classes to Blender layer color icons
CERTAINTY_ICONS = {
    "direct": "COLLECTION_COLOR_01",          # red
    "reconstructed": "COLLECTION_COLOR_02",   # orange
    "hypothetical": "COLLECTION_COLOR_03",    # yellow
    # Reserved for future use:
    # "comparative": "COLLECTION_COLOR_04",   # green
    # "analogical": "COLLECTION_COLOR_05",    # blue
    "unknown": "COLLECTION_COLOR_08",         # gray
}

CERTAINTY_LABELS = {
    "direct": "Direct",
    "reconstructed": "Reconstructed",
    "hypothetical": "Hypothetical",
    "unknown": "Unknown",
}


class DOCMANAGER_UL_documents(UIList):
    """UIList for document items with master indicators and 3D state."""

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)

        # Certainty icon for masters, dot for instances
        if item.is_master:
            cert_icon = CERTAINTY_ICONS.get(item.certainty_class, "KEYTYPE_MOVING_HOLD_VEC")
            row.label(text="", icon=cert_icon)
        else:
            row.label(text="", icon="DOT")

        # Name (with date for masters)
        name_col = row.row(align=True)
        name_col.scale_x = 0.4
        name_text = item.name
        if item.absolute_start_date:
            name_text = f"{item.name} ({item.absolute_start_date})"
        name_col.label(text=name_text)

        # 3D state indicators
        state_col = row.row(align=True)
        state_col.scale_x = 0.15
        if item.has_quad:
            state_col.label(text="", icon="MESH_PLANE")
        if item.has_camera:
            # Camera icon as inline look-through button
            op = state_col.operator("em.docmanager_look_through", text="", icon="CAMERA_DATA", emboss=False)

        # Description
        desc_col = row.row(align=True)
        desc_col.label(text=item.description if item.description else "")

    def filter_items(self, context, data, propname):
        """Custom filtering and sorting."""
        items = getattr(data, propname)
        filter_flags = [self.bitflag_filter_item] * len(items)

        settings = context.scene.doc_settings

        for i, item in enumerate(items):
            if settings.filter_masters and not item.is_master:
                filter_flags[i] = 0
            if settings.filter_with_3d and not item.has_quad:
                filter_flags[i] = 0

        # Sort: masters first, then alphabetical
        def sort_key(idx):
            it = items[idx]
            return (0 if it.is_master else 1, it.name)

        order = sorted(range(len(items)), key=sort_key)
        return filter_flags, order


class VIEW3D_PT_3DDocumentManager(Panel):
    """Document Manager — manage all documents in the graph as spatial-temporal entities."""
    bl_label = "Document Manager"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "EM Annotator"
    bl_idname = "VIEW3D_PT_3DDocumentManager"
    bl_context = "objectmode"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return hasattr(context.scene, 'em_tools') and context.scene.em_tools.mode_em_advanced

    def draw_header(self, context):
        layout = self.layout
        icon_id = icons_manager.get_icon_value("document")
        if icon_id:
            layout.label(text="", icon_value=icon_id)
        else:
            layout.label(text="", icon='FILE')

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        doc_list = scene.doc_list
        doc_settings = scene.doc_settings
        idx = scene.doc_list_index

        # --- Sync controls ---
        sync_box = layout.box()
        row = sync_box.row(align=True)
        row.operator("em.docmanager_sync", text="Sync from Graph", icon="FILE_REFRESH")
        # Create Document — experimental only (requires GraphML write-back for persistence)
        if context.scene.em_tools.experimental_features:
            row.operator("docmanager.create_document", text="", icon="ADD")
        row.label(text=f"{len(doc_list)} docs")

        # --- Summary bar ---
        total = len(doc_list)
        if total > 0:
            masters = sum(1 for item in doc_list if item.is_master)
            dated = sum(1 for item in doc_list if item.absolute_start_date)
            with_3d = sum(1 for item in doc_list if item.has_quad)

            summary_row = layout.row(align=True)
            summary_row.label(text=f"Masters: {masters}", icon="KEYTYPE_KEYFRAME_VEC")
            summary_row.label(text=f"Dated: {dated}", icon="TIME")
            summary_row.label(text=f"3D: {with_3d}", icon="MESH_PLANE")

        # --- Filter row ---
        filter_row = layout.row(align=True)
        filter_row.prop(doc_settings, "filter_masters", toggle=True)
        filter_row.prop(doc_settings, "filter_with_3d", toggle=True)

        # --- Document list ---
        row = layout.row()
        row.template_list(
            "DOCMANAGER_UL_documents", "",
            scene, "doc_list",
            scene, "doc_list_index",
            rows=8,
        )

        # --- Detail panel for selected document ---
        if 0 <= idx < total:
            item = doc_list[idx]

            detail_box = layout.box()
            col = detail_box.column(align=True)

            # Header
            header = col.row()
            header.label(text=item.name, icon="FILE_TEXT")
            if item.is_master:
                cert_icon = CERTAINTY_ICONS.get(item.certainty_class, "KEYTYPE_MOVING_HOLD_VEC")
                cert_label = CERTAINTY_LABELS.get(item.certainty_class, "Unknown")
                header.label(text=f"Master ({cert_label})", icon=cert_icon)
            else:
                header.label(text="Instance", icon="DOT")

            # Description
            if item.description:
                col.separator()
                col.label(text=item.description, icon="TEXT")

            # Chronology (masters only)
            if item.is_master:
                col.separator()
                chrono_row = col.row()
                chrono_row.label(text="Chronology:", icon="TIME")
                if item.absolute_start_date:
                    chrono_row.label(text=item.absolute_start_date)
                else:
                    chrono_row.label(text="not set", icon="ERROR")
                if item.epoch_name:
                    col.label(text=f"Epoch: {item.epoch_name}")

            # Source type
            if item.source_type:
                col.separator()
                if item.source_type == "analytical":
                    col.label(text="Analytical (from context)", icon="DOCUMENTS")
                else:
                    col.label(text="Comparative (from analogues)", icon="WORLD")

            # Completeness indicators
            col.separator()
            comp_row = col.row(align=True)
            comp_row.label(text="Desc", icon="CHECKMARK" if item.description else "X")
            comp_row.label(text="Date", icon="CHECKMARK" if item.absolute_start_date else "X")
            comp_row.label(text="URL", icon="CHECKMARK" if item.url else "X")
            comp_row.label(text="3D", icon="CHECKMARK" if item.has_quad else "X")

            # --- 3D Representation section ---
            col.separator()
            repr_box = col.box()
            repr_col = repr_box.column(align=True)
            repr_col.label(text="3D Representation", icon="SCENE_DATA")

            if not item.has_quad:
                # No quad yet — show import button
                repr_col.label(text="No 3D representation", icon="INFO")
                repr_col.operator("em.docmanager_import_image", text="Import Image", icon="IMAGE_DATA")
            else:
                # Quad exists
                repr_col.label(text=f"Quad: {item.quad_object_name}", icon="MESH_PLANE")
                dim_row = repr_col.row(align=True)
                dim_row.label(text=f"{item.quad_width:.2f} x {item.quad_height:.2f} m")
                dim_row.label(text=f"({item.dimensions_type})")

                if not item.has_camera:
                    repr_col.operator("em.docmanager_create_camera", text="Create Camera", icon="CAMERA_DATA")
                else:
                    # Camera exists — show controls
                    repr_col.label(text=f"Camera: {item.camera_object_name}", icon="CAMERA_DATA")
                    cam_obj = bpy.data.objects.get(item.camera_object_name)
                    if cam_obj and cam_obj.type == 'CAMERA':
                        repr_col.prop(cam_obj.data, "lens", text="Focal Length")

                    cam_row = repr_col.row(align=True)
                    cam_row.operator("em.docmanager_look_through", text="Look Through", icon="HIDE_OFF")

                # Utility actions
                repr_col.separator()
                action_row = repr_col.row(align=True)
                action_row.operator("em.docmanager_select_object", text="Select Quad", icon="RESTRICT_SELECT_OFF")
                action_row.operator("em.docmanager_open_url", text="Open File", icon="URL")

            # Rename object from document (works with any selected mesh)
            if context.active_object and context.active_object.type == 'MESH':
                repr_col.separator()
                repr_col.operator("em.docmanager_rename_object", text="Rename Object from Document", icon="LINK_BLEND")

        # --- Settings (collapsible) ---
        settings_header = layout.row()
        settings_header.prop(
            doc_settings, "show_settings",
            icon="TRIA_DOWN" if doc_settings.show_settings else "TRIA_RIGHT",
            emboss=False, text="Settings"
        )
        if doc_settings.show_settings:
            settings_box = layout.box()
            settings_box.prop(doc_settings, "zoom_to_selected")
            settings_box.prop(doc_settings, "default_focal_length")
            settings_box.prop(doc_settings, "default_alpha")


classes = (
    DOCMANAGER_UL_documents,
    VIEW3D_PT_3DDocumentManager,
)


def register_ui():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister_ui():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
