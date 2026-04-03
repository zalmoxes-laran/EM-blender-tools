"""UI components for the Document Manager — dedicated document management panel."""

import bpy
from bpy.types import Panel, UIList


# Map certainty classes to Blender icons
CERTAINTY_ICONS = {
    "direct": "KEYTYPE_KEYFRAME_VEC",        # red diamond
    "reconstructed": "KEYTYPE_EXTREME_VEC",   # orange diamond
    "hypothetical": "KEYTYPE_JITTER_VEC",     # yellow diamond
    "unknown": "KEYTYPE_MOVING_HOLD_VEC",     # gray diamond
}

# Map certainty classes to human-readable labels
CERTAINTY_LABELS = {
    "direct": "Direct",
    "reconstructed": "Reconstructed",
    "hypothetical": "Hypothetical",
    "unknown": "Unknown",
}


class DOCMANAGER_UL_documents(UIList):
    """UIList for the Document Manager — shows all documents with master indicators."""

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if item.is_master:
            certainty_icon = CERTAINTY_ICONS.get(item.certainty_class, "KEYTYPE_MOVING_HOLD_VEC")
            row = layout.row(align=True)
            row.label(text="", icon=certainty_icon)
            sub = row.row(align=True)
            sub.scale_x = 0.35
            name_text = item.name
            if item.absolute_start_date:
                name_text = f"{item.name} ({item.absolute_start_date})"
            sub.label(text=name_text)
            sub = row.row(align=True)
            sub.label(text=item.description if item.description else "")
        else:
            row = layout.row(align=True)
            row.label(text="", icon="DOT")
            sub = row.row(align=True)
            sub.scale_x = 0.35
            sub.label(text=item.name)
            sub = row.row(align=True)
            sub.label(text=item.description if item.description else "")

    def filter_items(self, context, data, propname):
        """Custom filtering: optionally show only masters."""
        items = getattr(data, propname)
        filter_flags = [self.bitflag_filter_item] * len(items)
        order = list(range(len(items)))

        # Filter: show only masters if filter is active
        if hasattr(context.scene, 'em_tools') and context.scene.em_tools.docmanager_filter_masters:
            for i, item in enumerate(items):
                if not item.is_master:
                    filter_flags[i] = 0

        # Sort: masters first, then alphabetical
        def sort_key(idx):
            item = items[idx]
            return (0 if item.is_master else 1, item.name)

        order = sorted(range(len(items)), key=sort_key)

        return filter_flags, order


class VIEW3D_PT_DocumentManager(Panel):
    """Dedicated Document Manager panel for managing documents as space-time entities."""
    bl_label = "Document Manager"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "EM"
    bl_idname = "VIEW3D_PT_DocumentManager"
    bl_context = "objectmode"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return hasattr(context.scene, 'em_tools') and context.scene.em_tools.mode_em_advanced

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        em_tools = scene.em_tools

        sources_list = em_tools.em_sources_list
        sources_index = em_tools.em_sources_list_index

        # --- Summary bar ---
        total = len(sources_list)
        masters = sum(1 for item in sources_list if item.is_master)
        with_date = sum(1 for item in sources_list if item.absolute_start_date)

        summary_box = layout.box()
        row = summary_box.row(align=True)
        row.label(text=f"Documents: {total}", icon="FILE_TEXT")
        row.label(text=f"Masters: {masters}", icon="KEYTYPE_KEYFRAME_VEC")
        row.label(text=f"Dated: {with_date}", icon="TIME")

        # --- Filter controls ---
        row = layout.row(align=True)
        filter_icon = "FILTER" if em_tools.docmanager_filter_masters else "FILTER"
        filter_text = "Masters Only" if em_tools.docmanager_filter_masters else "All Documents"
        row.operator("em.docmanager_filter_masters", text=filter_text, icon=filter_icon,
                     depress=em_tools.docmanager_filter_masters)

        # --- Document list ---
        row = layout.row()
        row.template_list(
            "DOCMANAGER_UL_documents", "",
            em_tools, "em_sources_list",
            em_tools, "em_sources_list_index",
            rows=8,
        )

        # --- Detail panel for selected document ---
        if 0 <= sources_index < total:
            item = sources_list[sources_index]

            detail_box = layout.box()
            col = detail_box.column(align=True)

            # Header with name
            row = col.row()
            row.label(text=item.name, icon="FILE_TEXT")
            if item.is_master:
                certainty_icon = CERTAINTY_ICONS.get(item.certainty_class, "KEYTYPE_MOVING_HOLD_VEC")
                certainty_label = CERTAINTY_LABELS.get(item.certainty_class, "Unknown")
                row.label(text=f"Master ({certainty_label})", icon=certainty_icon)
            else:
                row.label(text="Instance", icon="DOT")

            col.separator()

            # Description
            if item.description:
                row = col.row()
                row.label(text="Description:", icon="TEXT")
                row = col.row()
                row.label(text=item.description)

            # Chronology section
            if item.is_master:
                col.separator()
                row = col.row()
                row.label(text="Chronology:", icon="TIME")
                if item.absolute_start_date:
                    row = col.row()
                    row.label(text=f"  Start date: {item.absolute_start_date}")
                else:
                    row = col.row()
                    row.label(text="  Start date: not set", icon="ERROR")
                if item.epoch_name:
                    row = col.row()
                    row.label(text=f"  Epoch: {item.epoch_name}")

            # Source type
            if item.source_type:
                col.separator()
                row = col.row()
                source_icon = "DOCUMENTS" if item.source_type == "analytical" else "WORLD"
                source_label = "Analytical (from context)" if item.source_type == "analytical" else "Comparative (from analogues)"
                row.label(text=f"Type: {source_label}", icon=source_icon)

            # Completeness indicators
            col.separator()
            completeness_row = col.row(align=True)
            # Semantic completeness (has description?)
            sem_icon = "CHECKMARK" if item.description else "X"
            completeness_row.label(text="Desc", icon=sem_icon)
            # Chronological completeness (has date?)
            chrono_icon = "CHECKMARK" if item.absolute_start_date else "X"
            completeness_row.label(text="Date", icon=chrono_icon)
            # URL completeness
            url_icon = "CHECKMARK" if item.url else "X"
            completeness_row.label(text="URL", icon=url_icon)

            # Actions
            col.separator()
            row = col.row(align=True)
            row.operator("em.docmanager_open_url", text="Open URL", icon="URL")
            row.operator("em.docmanager_select_object", text="Select Object", icon="RESTRICT_SELECT_OFF")


classes = (
    DOCMANAGER_UL_documents,
    VIEW3D_PT_DocumentManager,
)


def register_ui():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister_ui():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
