"""
UI panels for the Surface Areale system.
Integrated into the EM Annotator sidebar tab.
"""

import bpy
from bpy.types import Panel


class VIEW3D_PT_SurfaceAreale(Panel):
    """Surface Areale creation panel"""
    bl_label = "Surface Areale"
    bl_idname = "VIEW3D_PT_SurfaceAreale"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "EM Annotator"
    bl_order = 5

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        em_tools = scene.em_tools
        settings = em_tools.surface_areale
        has_graph = em_tools.active_file_index >= 0

        # ── Warning if no graph loaded ────────────────────────────────
        if not has_graph:
            box = layout.box()
            box.alert = True
            box.label(text="Load a GraphML first", icon='ERROR')
            return

        # ── Target RM ─────────────────────────────────────────────────
        box = layout.box()
        box.label(text="Target RM", icon='MESH_DATA')
        box.prop(settings, "target_rm", text="")

        if settings.target_rm and settings.target_rm.type == 'MESH':
            poly_count = len(settings.target_rm.data.polygons)
            box.label(text=f"Polygons: {poly_count:,}", icon='INFO')
            box.operator("emtools.detect_rm_document", icon='VIEWZOOM')

        # ── Document ──────────────────────────────────────────────────
        box = layout.box()
        box.label(text="Document", icon='FILE')

        if not settings.target_rm:
            box.label(text="Select a Target RM first")
        elif settings.linked_document:
            box.label(text=f"Linked: {settings.linked_document}", icon='CHECKMARK')
        else:
            box.label(text="No document linked to this RM", icon='ERROR')
            box.prop(settings, "create_new_document", text="Create New Document")

            if settings.create_new_document:
                row = box.row(align=True)
                row.prop(settings, "new_doc_name", text="Name")
                row.operator("emtools.suggest_next_doc", text="", icon='ADD')
                box.prop(settings, "new_doc_date", text="Date")
            else:
                # Search among existing documents (same pattern as US search)
                if hasattr(scene, 'doc_list') and scene.doc_list:
                    box.prop_search(
                        settings, "existing_document",
                        scene, "doc_list",
                        text="Document"
                    )
                else:
                    box.prop(settings, "existing_document", text="Document",
                             icon='VIEWZOOM')

        # ── US Type ───────────────────────────────────────────────────
        box = layout.box()
        box.label(text="Stratigraphic Unit", icon='LAYER_ACTIVE')
        box.prop(settings, "us_type", text="Type")

        if settings.us_type != 'GENERIC':
            box.prop(settings, "create_new_us", text="Create New US")

            if settings.create_new_us:
                row = box.row(align=True)
                row.prop(settings, "new_us_name", text="Name")
                row.operator("emtools.suggest_next_us", text="", icon='ADD')

                # Epoch search
                if hasattr(em_tools, 'epochs') and em_tools.epochs.list:
                    box.prop_search(
                        settings, "new_us_epoch",
                        em_tools.epochs, "list",
                        text="Epoch"
                    )
                else:
                    box.prop(settings, "new_us_epoch", text="Epoch")

                # Optional stratigraphic link
                if hasattr(em_tools, 'stratigraphy') and em_tools.stratigraphy.units:
                    box.prop_search(
                        settings, "link_to_existing_us",
                        em_tools.stratigraphy, "units",
                        text="Link to US"
                    )
            else:
                # Search existing US
                if hasattr(em_tools, 'stratigraphy') and em_tools.stratigraphy.units:
                    box.prop_search(
                        settings, "linked_us_name",
                        em_tools.stratigraphy, "units",
                        text="Existing US"
                    )
                else:
                    box.prop(settings, "linked_us_name", text="US Name")

        # ── Draw Button ───────────────────────────────────────────────
        layout.separator()

        if settings.is_drawing:
            row = layout.row(align=True)
            row.alert = True
            row.label(text="Drawing active...", icon='GREASEPENCIL')
            row = layout.row()
            row.label(text=f"Phase: {settings.drawing_phase}")
            row = layout.row()
            row.label(text="[B] Whisker | [Enter] Confirm | [Esc] Cancel")
        else:
            row = layout.row(align=True)
            row.scale_y = 1.5
            row.operator("emtools.draw_surface_areale", icon='GREASEPENCIL')


class VIEW3D_PT_SurfaceAreale_Settings(Panel):
    """Advanced settings for Surface Areale"""
    bl_label = "Settings"
    bl_idname = "VIEW3D_PT_SurfaceAreale_Settings"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "EM Annotator"
    bl_parent_id = "VIEW3D_PT_SurfaceAreale"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        settings = context.scene.em_tools.surface_areale

        layout.prop(settings, "strategy")

        layout.separator()
        layout.label(text="Geometry:")
        col = layout.column(align=True)
        col.prop(settings, "offset_distance")
        col.prop(settings, "resample_distance")
        col.prop(settings, "max_triangles")
        col.prop(settings, "subdivision_iterations")
        col.prop(settings, "conformity_threshold")

        layout.separator()
        layout.label(text="GP Drawing:")
        col = layout.column(align=True)
        col.prop(settings, "gp_stroke_color", text="Color")
        col.prop(settings, "gp_stroke_thickness", text="Thickness")


classes = [
    VIEW3D_PT_SurfaceAreale,
    VIEW3D_PT_SurfaceAreale_Settings,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
