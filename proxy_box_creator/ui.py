"""
Enhanced UI for Proxy Box Creator with Paradata support
Clean, organized layout with minimal redundancy
Version 2.2 - Reorganized
"""

import bpy
from bpy.types import Panel

# Point type labels
POINT_TYPE_LABELS = {
    0: "Alignment Start",
    1: "Alignment End",
    2: "Thickness",
    3: "Quota Min",
    4: "Quota Max",
    5: "Length Start",
    6: "Length End"
}


class PROXYBOX_PT_main_panel(Panel):
    """Main panel for Proxy Box Creator"""
    bl_label = "Proxy Box Creator"
    bl_idname = "PROXYBOX_PT_main_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "EM Annotator"
    bl_options = {'DEFAULT_CLOSED'}
    
    @classmethod
    def poll(cls, context):
        return hasattr(context.scene, 'em_tools')
    
    def draw_header(self, context):
        layout = self.layout
        layout.label(text="", icon='MESH_CUBE')
    
    def draw(self, context):
        layout = self.layout
        settings = context.scene.em_tools.proxy_box
        
        # ═══════════════════════════════════════════════════════
        # STATUS (always visible)
        # ═══════════════════════════════════════════════════════
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
                row.label(text="✓ Documents assigned: 7/7", icon='CHECKMARK')
            else:
                row.label(text=f"○ Documents assigned: {docs_count}/7", icon='ERROR')
            
            # Extractors calculated
            ext_count = sum(1 for p in settings.points[:7] if p.extractor_id)
            all_have_ext = ext_count == 7
            
            row = col.row()
            if all_have_ext:
                row.label(text="✓ Extractors calculated: 7/7", icon='CHECKMARK')
            else:
                row.label(text=f"○ Extractors calculated: {ext_count}/7", icon='INFO')
        
        layout.separator()
        
        # ═══════════════════════════════════════════════════════
        # CREATE PROXY BUTTON (prominent)
        # ═══════════════════════════════════════════════════════
        row = layout.row()
        row.scale_y = 1.5
        
        can_create = all_recorded
        if settings.create_extractors:
            all_have_docs = sum(1 for p in settings.points[:7] if p.source_document) == 7
            all_have_ext = sum(1 for p in settings.points[:7] if p.extractor_id) == 7
            can_create = all_recorded and all_have_docs and all_have_ext
        
        if can_create:
            row.operator("proxybox.create_proxy_enhanced", text="Create Proxy", icon='ADD')
        else:
            row.enabled = False
            if not all_recorded:
                row.operator("proxybox.create_proxy_enhanced", text="Record All Points First", icon='ERROR')
            elif settings.create_extractors and not all_have_docs:
                row.operator("proxybox.create_proxy_enhanced", text="Assign Documents First", icon='ERROR')
            else:
                row.operator("proxybox.create_proxy_enhanced", text="Calculate Extractors First", icon='ERROR')
        
        # Clear all button
        layout.separator()
        layout.operator("proxybox.clear_all_points", text="Clear All Points", icon='X')


class PROXYBOX_PT_settings_panel(Panel):
    """Settings panel - Collapsible"""
    bl_label = "Settings"
    bl_idname = "PROXYBOX_PT_settings_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "EM Annotator"
    bl_parent_id = "PROXYBOX_PT_main_panel"
    bl_options = {'DEFAULT_CLOSED'}
    
    def draw(self, context):
        layout = self.layout
        settings = context.scene.em_tools.proxy_box
        
        # Mode toggle
        box = layout.box()
        box.label(text="Mode:", icon='SETTINGS')
        box.prop(settings, "create_extractors", text="Activate paradata enrichment")
        
        layout.separator()
        
        # Proxy configuration
        box = layout.box()
        box.label(text="Proxy Configuration:", icon='OBJECT_DATA')
        
        col = box.column(align=True)
        col.prop(settings, "proxy_name", text="Name")
        col.prop(settings, "pivot_location", text="Pivot")
        col.prop(settings, "use_proxy_collection", text="Use Proxy Collection")


class PROXYBOX_PT_workflow_panel(Panel):
    """Workflow instructions - Collapsible"""
    bl_label = "Workflow"
    bl_idname = "PROXYBOX_PT_workflow_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "EM Annotator"
    bl_parent_id = "PROXYBOX_PT_main_panel"
    bl_options = {'DEFAULT_CLOSED'}
    
    def draw(self, context):
        layout = self.layout
        settings = context.scene.em_tools.proxy_box
        
        box = layout.box()
        
        if settings.create_extractors:
            # Workflow with paradata
            box.label(text="With Paradata Enrichment:", icon='INFO')
            col = box.column(align=True)
            col.scale_y = 0.9
            col.label(text="1. Position 3D cursor on model")
            col.label(text="2. Click 🔍 to pick source document")
            col.label(text="3. Click Record button")
            col.label(text="4. Click ↻ to calculate extractor ID")
            col.label(text="5. Repeat for all 7 points")
            col.label(text="6. Click 'Create Proxy'")
        else:
            # Workflow without paradata (geometry only)
            box.label(text="Geometry Only Mode:", icon='INFO')
            col = box.column(align=True)
            col.scale_y = 0.9
            col.label(text="1. Position 3D cursor on model")
            col.label(text="2. Click Record button")
            col.label(text="3. Repeat for all 7 points")
            col.label(text="4. Click 'Create Proxy'")
        
        layout.separator()
        
        # Point descriptions
        box = layout.box()
        box.label(text="Point Descriptions:", icon='QUESTION')
        col = box.column(align=True)
        col.scale_y = 0.8
        col.label(text="• Alignment Start/End: Define main axis")
        col.label(text="• Thickness: Define perpendicular width")
        col.label(text="• Quota Min/Max: Define height range")
        col.label(text="• Length Start/End: Define axis extent")


class PROXYBOX_PT_points_panel(Panel):
    """Measurement points panel with paradata support"""
    bl_label = "Measurement Points"
    bl_idname = "PROXYBOX_PT_points_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "EM Annotator"
    bl_parent_id = "PROXYBOX_PT_main_panel"
    bl_options = {'DEFAULT_CLOSED'}
    
    def draw(self, context):
        layout = self.layout
        settings = context.scene.em_tools.proxy_box
        
        # Check if we're in paradata mode
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


# List of classes to register
classes = [
    PROXYBOX_PT_main_panel,
    PROXYBOX_PT_settings_panel,
    PROXYBOX_PT_workflow_panel,
    PROXYBOX_PT_points_panel,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()