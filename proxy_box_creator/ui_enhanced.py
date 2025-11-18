"""
Enhanced UI for Proxy Box Creator with Paradata support
Compact two-row design for each measurement point
"""

import bpy
from bpy.types import Panel

# Point type labels (importato da utils)
POINT_TYPE_LABELS = {
    0: "Alignment Start",
    1: "Alignment End",
    2: "Thickness",
    3: "Quota Min",
    4: "Quota Max",
    5: "Length Start",
    6: "Length End"
}


class PROXYBOX_PT_points_panel_enhanced(Panel):
    """Enhanced panel for point recording with paradata support"""
    bl_label = "Measurement Points"
    bl_idname = "PROXYBOX_PT_points_panel_enhanced"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "EM Annotator"
    bl_parent_id = "PROXYBOX_PT_main_panel"
    bl_options = {'DEFAULT_CLOSED'}
    
    def draw(self, context):
        layout = self.layout
        settings = context.scene.em_tools.proxy_box
        scene = context.scene
        
        # Check if we're in "With Extractors" mode
        show_paradata = settings.create_extractors
        
        # For each of the 7 points
        for i in range(7):
            point_label = POINT_TYPE_LABELS.get(i, f"Point {i+1}")
            
            # ═══════════════════════════════════════════════════════
            # FIRST ROW: Point name, coordinates, Record button
            # ═══════════════════════════════════════════════════════
            box = layout.box()
            row = box.row(align=True)
            
            # Point label (with icon if recorded)
            if i < len(settings.points) and settings.points[i].is_recorded:
                row.label(text=point_label + ":", icon='CHECKMARK')
            else:
                row.label(text=point_label + ":", icon='RADIOBUT_OFF')
            
            # Coordinates display
            if i < len(settings.points) and settings.points[i].is_recorded:
                point = settings.points[i]
                pos = point.position
                coord_text = f"({pos[0]:.2f}, {pos[1]:.2f}, {pos[2]:.2f})"
            else:
                coord_text = "(not recorded)"
            
            row.label(text=coord_text)
            
            # Record button
            op = row.operator("proxybox.record_point", text="", icon='MOUSE_LMB')
            op.point_index = i
            
            # ═══════════════════════════════════════════════════════
            # SECOND ROW: Document and Extractor (only if mode enabled)
            # ═══════════════════════════════════════════════════════
            if show_paradata:
                # Ensure point exists
                if i >= len(settings.points):
                    continue
                    
                point = settings.points[i]
                
                # Create a subtle sub-row for paradata
                sub_row = box.row(align=True)
                sub_row.scale_y = 0.9
                
                # Document section
                doc_col = sub_row.column(align=True)
                doc_row = doc_col.row(align=True)
                doc_row.label(text="Doc:", icon='FILE_TEXT')
                
                if point.source_document:
                    # Show only document NAME, not ID
                    display_name = point.source_document_name if point.source_document_name else point.source_document
                    doc_row.label(text=display_name)
                    
                    # Small copy button
                    op = doc_row.operator("proxybox.copy_document_to_all", 
                                         text="", icon='COPYDOWN')
                    op.point_index = i
                else:
                    # Show placeholder
                    doc_row.label(text="(not assigned)")
                
                # Pick document button
                op = doc_row.operator("proxybox.search_document", 
                                     text="", icon='VIEWZOOM')
                op.point_index = i
                
                # Extractor section
                ext_col = sub_row.column(align=True)
                ext_row = ext_col.row(align=True)
                ext_row.label(text="Ext:", icon='EMPTY_AXIS')
                
                if point.source_document:
                    # Editable extractor ID field
                    ext_row.prop(point, "extractor_id", text="")
                    
                    # Calculate button (only if document is assigned)
                    op = ext_row.operator("proxybox.calculate_extractor_id", 
                                         text="", icon='FILE_REFRESH')
                    op.point_index = i
                else:
                    # Show placeholder when no document assigned
                    ext_row.label(text="(assign doc first)")
        
        # Separator
        layout.separator()
        
        # Clear all button
        layout.operator("proxybox.clear_all_points", icon='X')
        
        # Status summary
        layout.separator()
        self._draw_status_summary(layout, settings)
    
    def _draw_status_summary(self, layout, settings):
        """Draw a compact status summary"""
        box = layout.box()
        box.label(text="Status:", icon='INFO')
        
        col = box.column(align=True)
        
        # Points recorded
        recorded_count = sum(1 for p in settings.points[:7] if p.is_recorded)
        all_recorded = recorded_count == 7
        
        row = col.row()
        if all_recorded:
            row.label(text="✓ Points recorded: 7/7", icon='CHECKMARK')
        else:
            row.label(text=f"○ Points recorded: {recorded_count}/7", icon='ERROR')
        
        # Documents assigned (only if in paradata mode)
        if settings.create_extractors:
            docs_count = sum(1 for p in settings.points[:7] if p.source_document)
            all_have_docs = docs_count == 7
            
            row = col.row()
            if all_have_docs:
                row.label(text=f"✓ Documents assigned: 7/7", icon='CHECKMARK')
            else:
                row.label(text=f"○ Documents assigned: {docs_count}/7", icon='ERROR')
            
            # Extractors calculated
            ext_count = sum(1 for p in settings.points[:7] if p.extractor_id)
            all_have_ext = ext_count == 7
            
            row = col.row()
            if all_have_ext:
                row.label(text=f"✓ Extractors calculated: 7/7", icon='CHECKMARK')
            else:
                row.label(text=f"○ Extractors calculated: {ext_count}/7", icon='INFO')


# List of classes to register
classes = [
    PROXYBOX_PT_points_panel_enhanced,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()