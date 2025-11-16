"""
UI panels for the Proxy Box Creator
Displays in the EM Annotator tab.
"""

import bpy # type: ignore
from bpy.types import Panel # type: ignore

from .utils import POINT_TYPE_LABELS


class PROXYBOX_PT_main_panel(Panel):
    """Main panel for Proxy Box Creator in EM Annotator tab"""
    bl_label = "Proxy Box Creator"
    bl_idname = "PROXYBOX_PT_main_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "EM Annotator"
    bl_options = {'DEFAULT_CLOSED'}
    
    @classmethod
    def poll(cls, context):
        # Only show when EM Tools is loaded
        return hasattr(context.scene, 'em_tools')
    
    def draw_header(self, context):
        layout = self.layout
        layout.label(text="", icon='MESH_CUBE')
    
    def draw(self, context):
        layout = self.layout
        settings = context.scene.em_tools.proxy_box
        
        # Mode selector
        box = layout.box()
        box.label(text="Mode:", icon='SETTINGS')
        row = box.row(align=True)
        row.prop(settings, "create_extractors", text="With Extractors", toggle=True)
        
        if not settings.create_extractors:
            box.label(text="Geometry only (no graph annotation)", icon='INFO')
        else:
            # Show combiner preview
            if settings.combiner_id:
                row = box.row()
                row.label(text=f"Combiner: {settings.combiner_id}", icon='LINKED')
            else:
                row = box.row()
                row.operator("proxybox.preview_combiner", text="Preview Combiner ID", icon='VIEWZOOM')
        
        layout.separator()
        
        # Instructions
        help_box = layout.box()
        help_box.label(text="Workflow:", icon='QUESTION')
        col = help_box.column(align=True)
        col.label(text="1. Position 3D cursor on model")
        col.label(text="2. Select source document")
        col.label(text="3. Record point position")
        col.label(text="4. Repeat for all 7 points")
        col.label(text="5. Create proxy")
        
        layout.separator()


class PROXYBOX_PT_points_panel(Panel):
    """Sub-panel for point recording"""
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
        
        # Draw each point (don't add here, let operators handle it)
        for i in range(7):
            # Get point if it exists, otherwise skip
            if i >= len(settings.points):
                # Show placeholder for uninitialized point
                box = layout.box()
                point_label = POINT_TYPE_LABELS.get(i, f"Point {i+1}")
                row = box.row()
                row.label(text=f"○ {point_label}", icon='RADIOBUT_OFF')
                row = box.row()
                row.label(text="Not initialized - record to create", icon='INFO')
                layout.separator()
                continue
            
            point = settings.points[i]
            point_label = POINT_TYPE_LABELS.get(i, f"Point {i+1}")
            
            # Point box
            box = layout.box()
            
            # Header with point name and status
            row = box.row()
            if point.is_recorded:
                row.label(text=f"✓ {point_label}", icon='CHECKMARK')
            else:
                row.label(text=f"○ {point_label}", icon='RADIOBUT_OFF')
            
            # Extractor ID if available
            if point.extractor_id:
                row.label(text=point.extractor_id, icon='SMALL_TRI_RIGHT_VEC')
            
            # Source document selection
            col = box.column(align=True)
            
            if point.source_document:
                # Show selected document
                row = col.row(align=True)
                row.label(text=f"Doc: {point.source_document_name or point.source_document}", 
                         icon='FILE_TEXT')
            else:
                # No document selected yet
                row = col.row(align=True)
                row.label(text="No document selected", icon='ERROR')
            
            # Document selection buttons
            row = col.row(align=True)
            op = row.operator("proxybox.pick_document_from_object", 
                            text="", icon='EYEDROPPER')
            op.point_index = i
            
            op = row.operator("proxybox.use_paradata_document", 
                            text="", icon='LOOP_BACK')
            op.point_index = i
            
            # Position display
            if point.is_recorded:
                col = box.column(align=True)
                pos = point.position
                col.label(text=f"X: {pos[0]:.4f}", icon='BLANK1')
                col.label(text=f"Y: {pos[1]:.4f}", icon='BLANK1')
                col.label(text=f"Z: {pos[2]:.4f}", icon='BLANK1')
            
            # Action buttons
            row = box.row(align=True)
            
            op = row.operator("proxybox.record_point", text="Record", icon='TRACKING')
            op.point_index = i
            
            op = row.operator("proxybox.clear_point", text="Clear", icon='X')
            op.point_index = i
            
            layout.separator()
        
        # Clear all button
        layout.separator()
        row = layout.row()
        row.scale_y = 1.2
        row.operator("proxybox.clear_all_points", text="Clear All Points", icon='TRASH')


class PROXYBOX_PT_settings_panel(Panel):
    """Sub-panel for proxy settings and creation"""
    bl_label = "Proxy Settings"
    bl_idname = "PROXYBOX_PT_settings_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "EM Annotator"
    bl_parent_id = "PROXYBOX_PT_main_panel"
    
    def draw(self, context):
        layout = self.layout
        settings = context.scene.em_tools.proxy_box
        
        # Proxy name
        box = layout.box()
        box.label(text="Proxy Configuration:", icon='OBJECT_DATA')
        box.prop(settings, "proxy_name", text="Name")
        
        # Pivot location
        row = box.row(align=True)
        row.label(text="Pivot:")
        row.prop(settings, "pivot_location", text="")
        
        # Collection option
        box.prop(settings, "use_proxy_collection", text="Use Proxy Collection")
        
        layout.separator()
        
        # Status check
        all_recorded = len(settings.points) >= 7 and all(
            p.is_recorded for p in settings.points[:7]
        )
        all_have_docs = len(settings.points) >= 7 and all(
            p.source_document for p in settings.points[:7]
        )
        
        # Status box
        status_box = layout.box()
        status_box.label(text="Status:", icon='INFO')
        
        col = status_box.column(align=True)
        
        # Points recorded check
        recorded_count = sum(1 for p in settings.points[:7] if p.is_recorded)
        if all_recorded:
            col.label(text=f"✓ All points recorded ({recorded_count}/7)", icon='CHECKMARK')
        else:
            col.label(text=f"○ Points recorded: {recorded_count}/7", icon='ERROR')
        
        # Documents assigned check
        if settings.create_extractors:
            docs_count = sum(1 for p in settings.points[:7] if p.source_document)
            if all_have_docs:
                col.label(text=f"✓ All documents assigned ({docs_count}/7)", icon='CHECKMARK')
            else:
                col.label(text=f"○ Documents assigned: {docs_count}/7", icon='ERROR')
        
        layout.separator()
        
        # Create button
        row = layout.row()
        row.scale_y = 1.5
        
        if not all_recorded:
            row.enabled = False
            row.operator("proxybox.create_proxy", text="Record All Points First", icon='ERROR')
        elif settings.create_extractors and not all_have_docs:
            row.enabled = False
            row.operator("proxybox.create_proxy", text="Assign All Documents First", icon='ERROR')
        else:
            row.operator("proxybox.create_proxy", text="Create Proxy", icon='ADD')


# List of panel classes to register
classes = [
    PROXYBOX_PT_main_panel,
    PROXYBOX_PT_points_panel,
    PROXYBOX_PT_settings_panel,
]


def register():
    """Register all UI panel classes"""
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except ValueError as e:
            print(f"Warning: Could not register {cls.__name__}: {e}")
    
    print("✓ Proxy Box Creator UI panels registered")


def unregister():
    """Unregister all UI panel classes"""
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError as e:
            print(f"Warning: Could not unregister {cls.__name__}: {e}")
    
    print("✓ Proxy Box Creator UI panels unregistered")


if __name__ == "__main__":
    register()