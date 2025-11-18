"""
Redesigned UI for Proxy Box Creator
Based on the clean, compact design of alignment_orientation_tool
"""

import bpy
from bpy.types import Panel
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
        return hasattr(context.scene, 'em_tools')
    
    def draw_header(self, context):
        layout = self.layout
        layout.label(text="", icon='MESH_CUBE')
    
    def draw(self, context):
        layout = self.layout
        settings = context.scene.em_tools.proxy_box
        
        # Mode selector (compatto come alignment tool)
        box = layout.box()
        box.label(text="Mode:", icon='SETTINGS')
        row = box.row(align=True)
        row.prop(settings, "create_extractors", text="With Extractors", toggle=True)
        
        if settings.create_extractors and settings.combiner_id:
            box.row().operator("proxybox.preview_combiner", text="Preview Combiner ID", icon='VIEWZOOM')
        
        layout.separator()
        
        # Instructions (stile compatto)
        box = layout.box()
        box.label(text="Workflow:", icon='QUESTION')
        box.label(text="1. Position 3D cursor on model")
        box.label(text="2. Select source document")
        box.label(text="3. Record point position")
        box.label(text="4. Repeat for all 7 points")
        box.label(text="5. Create proxy")
        
        layout.separator()


class PROXYBOX_PT_points_panel(Panel):
    """Compact panel for point recording - Redesigned"""
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
        scene = context.scene
        
        # Per ogni punto, mostra una singola riga compatta
        for i in range(7):
            point_label = POINT_TYPE_LABELS.get(i, f"Point {i+1}")
            
            # Crea la riga principale
            row = layout.row()
            row.label(text=f"{point_label}:")
            
            # Se il punto esiste ed è registrato, mostra le coordinate
            if i < len(settings.points) and settings.points[i].is_recorded:
                point = settings.points[i]
                pos = point.position
                
                # Colonna per le coordinate (formato compatto)
                col = row.column(align=True)
                col.label(text=f"({pos[0]:.2f}, {pos[1]:.2f}, {pos[2]:.2f})")
            else:
                # Mostra "Not initialized"
                col = row.column(align=True)
                col.label(text="(0.00, 0.00, 0.00)")
            
            # Bottone Record (sempre presente, stile alignment tool)
            op = row.operator("proxybox.record_point", text="Record", icon='MOUSE_LMB')
            op.point_index = i
        
        # Bottone Clear All (unico, alla fine)
        layout.operator("proxybox.clear_all_points", icon='X')
        
        layout.separator()


class PROXYBOX_PT_settings_panel(Panel):
    """Compact settings panel - Redesigned"""
    bl_label = "Proxy Settings"
    bl_idname = "PROXYBOX_PT_settings_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "EM Annotator"
    bl_parent_id = "PROXYBOX_PT_main_panel"
    
    def draw(self, context):
        layout = self.layout
        settings = context.scene.em_tools.proxy_box
        
        # Verifica se tutti i punti sono registrati
        all_recorded = len(settings.points) >= 7 and all(
            p.is_recorded for p in settings.points[:7]
        )
        all_have_docs = len(settings.points) >= 7 and all(
            p.source_document for p in settings.points[:7]
        )
        
        # Mostra le impostazioni SOLO se i punti sono pronti
        if all_recorded or (len(settings.points) > 0 and any(p.is_recorded for p in settings.points)):
            box = layout.box()
            box.label(text="Proxy Configuration:", icon='OBJECT_DATA')
            
            col = box.column(align=True)
            col.prop(settings, "proxy_name", text="Name")
            col.prop(settings, "pivot_location", text="Pivot")
            col.prop(settings, "use_proxy_collection", text="Use Proxy Collection")
            
            layout.separator()
        
        # Status box (più compatto)
        box = layout.box()
        box.label(text="Status:", icon='INFO')
        
        col = box.column(align=True)
        
        # Points recorded
        recorded_count = sum(1 for p in settings.points[:7] if p.is_recorded)
        if all_recorded:
            col.label(text=f"✓ Points recorded: {recorded_count}/7", icon='CHECKMARK')
        else:
            col.label(text=f"○ Points recorded: {recorded_count}/7", icon='ERROR')
        
        # Documents assigned (solo se modalità extractors)
        if settings.create_extractors:
            docs_count = sum(1 for p in settings.points[:7] if p.source_document)
            if all_have_docs:
                col.label(text=f"✓ Documents assigned: {docs_count}/7", icon='CHECKMARK')
            else:
                col.label(text=f"○ Documents assigned: {docs_count}/7", icon='ERROR')
        
        layout.separator()
        
        # Create button (stile alignment tool - grande e centrale)
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


# Classes to register
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
    
    print("✓ Proxy Box Creator UI panels registered (redesigned)")


def unregister():
    """Unregister all UI panel classes"""
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError as e:
            print(f"Warning: Could not unregister {cls.__name__}: {e}")
    
    print("✓ Proxy Box Creator UI panels unregistered (redesigned)")


if __name__ == "__main__":
    register()