"""
Operators for the Proxy Box Creator
Handles point recording, document picking, and proxy creation.
"""

import bpy
from bpy.types import Operator
from bpy.props import IntProperty, StringProperty
from mathutils import Vector

from .utils import (
    get_document_from_paradata_manager,
    get_next_extractor_number,
    get_next_combiner_number,
    create_extractor_node,
    create_combiner_node,
    create_empty_extractor,
    calculate_box_geometry,
    create_box_mesh,
    get_object_under_mouse,
    POINT_TYPE_IDS,
    POINT_TYPE_LABELS
)


class PROXYBOX_OT_record_point(Operator):
    """Record the current 3D cursor position for a measurement point"""
    bl_idname = "proxybox.record_point"
    bl_label = "Record Point from Cursor"
    bl_options = {'REGISTER', 'UNDO'}
    
    point_index: IntProperty(
        name="Point Index",
        description="Which point to record (0-6)",
        min=0,
        max=6
    )  # type: ignore
    
    @classmethod
    def poll(cls, context):
        return context.area.type == 'VIEW_3D'
    
    def execute(self, context):
        settings = context.scene.em_tools.proxy_box
        
        # Ensure we have enough points in the collection
        while len(settings.points) <= self.point_index:
            settings.points.add()
        
        point = settings.points[self.point_index]
        
        # Record cursor position
        cursor_location = context.scene.cursor.location.copy()
        point.position = cursor_location
        point.is_recorded = True
        point.point_type = POINT_TYPE_IDS[self.point_index]
        
        # Try to get document from Paradata Manager if not already set
        if not point.source_document:
            doc_info = get_document_from_paradata_manager(context)
            if doc_info:
                point.source_document = doc_info[0]
                point.source_document_name = doc_info[1]
        
        point_label = POINT_TYPE_LABELS.get(self.point_index, f"Point {self.point_index + 1}")
        self.report({'INFO'}, f"Recorded {point_label} at {cursor_location}")
        
        return {'FINISHED'}


class PROXYBOX_OT_clear_point(Operator):
    """Clear a recorded measurement point"""
    bl_idname = "proxybox.clear_point"
    bl_label = "Clear Point"
    bl_options = {'REGISTER', 'UNDO'}
    
    point_index: IntProperty(
        name="Point Index",
        min=0,
        max=6
    )  # type: ignore
    
    def execute(self, context):
        settings = context.scene.em_tools.proxy_box
        
        if self.point_index < len(settings.points):
            point = settings.points[self.point_index]
            point.position = Vector((0, 0, 0))
            point.is_recorded = False
            point.source_document = ""
            point.source_document_name = ""
            point.extractor_id = ""
            
            point_label = POINT_TYPE_LABELS.get(self.point_index, f"Point {self.point_index + 1}")
            self.report({'INFO'}, f"Cleared {point_label}")
        
        return {'FINISHED'}


class PROXYBOX_OT_clear_all_points(Operator):
    """Clear all recorded measurement points"""
    bl_idname = "proxybox.clear_all_points"
    bl_label = "Clear All Points"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        settings = context.scene.em_tools.proxy_box
        settings.points.clear()
        settings.combiner_id = ""
        
        self.report({'INFO'}, "Cleared all points")
        return {'FINISHED'}


class PROXYBOX_OT_pick_document_from_object(Operator):
    """Pick document source by clicking on a mesh object in the viewport"""
    bl_idname = "proxybox.pick_document_from_object"
    bl_label = "Pick Document from Object"
    bl_description = "Click on a mesh object to use its associated document"
    
    point_index: IntProperty(
        name="Point Index",
        min=0,
        max=6
    )  # type: ignore
    
    def modal(self, context, event):
        context.area.tag_redraw()
        
        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            # Try to get object under mouse
            obj = get_object_under_mouse(context, event)
            
            if obj and obj.type == 'MESH':
                # Check for document_id custom property
                document_id = obj.get("document_id", None)
                
                if document_id:
                    # Save to settings
                    settings = context.scene.em_tools.proxy_box
                    
                    # Ensure point exists
                    while len(settings.points) <= self.point_index:
                        settings.points.add()
                    
                    point = settings.points[self.point_index]
                    point.source_document = document_id
                    point.source_document_name = obj.name
                    
                    self.report({'INFO'}, f"Selected document: {document_id} from {obj.name}")
                    return {'FINISHED'}
                else:
                    self.report({'WARNING'}, f"Object '{obj.name}' has no document_id property")
                    return {'CANCELLED'}
            else:
                self.report({'WARNING'}, "No mesh object under cursor")
                return {'CANCELLED'}
        
        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            self.report({'INFO'}, "Document picking cancelled")
            return {'CANCELLED'}
        
        return {'RUNNING_MODAL'}
    
    def invoke(self, context, event):
        if context.area.type == 'VIEW_3D':
            context.window_manager.modal_handler_add(self)
            context.area.header_text_set("Click on a mesh object to pick its document (Right-click or ESC to cancel)")
            return {'RUNNING_MODAL'}
        else:
            self.report({'WARNING'}, "Active area is not a 3D View")
            return {'CANCELLED'}


class PROXYBOX_OT_use_paradata_document(Operator):
    """Use the document currently selected in Paradata Manager"""
    bl_idname = "proxybox.use_paradata_document"
    bl_label = "Use Paradata Selection"
    bl_description = "Use the document selected in the Paradata Manager"
    
    point_index: IntProperty(
        name="Point Index",
        min=0,
        max=6
    )  # type: ignore
    
    def execute(self, context):
        doc_info = get_document_from_paradata_manager(context)
        
        if doc_info:
            settings = context.scene.em_tools.proxy_box
            
            # Ensure point exists
            while len(settings.points) <= self.point_index:
                settings.points.add()
            
            point = settings.points[self.point_index]
            point.source_document = doc_info[0]
            point.source_document_name = doc_info[1]
            
            self.report({'INFO'}, f"Using document from Paradata Manager: {doc_info[1]}")
        else:
            self.report({'WARNING'}, "No document selected in Paradata Manager")
            return {'CANCELLED'}
        
        return {'FINISHED'}


class PROXYBOX_OT_create_proxy(Operator):
    """Create the proxy box from recorded measurement points"""
    bl_idname = "proxybox.create_proxy"
    bl_label = "Create Proxy"
    bl_description = "Create the proxy box mesh and optional extractors/combiner"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        settings = context.scene.em_tools.proxy_box
        # Check that all 7 points are recorded
        if len(settings.points) < 7:
            return False
        return all(point.is_recorded for point in settings.points[:7])
    
    def execute(self, context):
        settings = context.scene.em_tools.proxy_box
        scene = context.scene
        
        # Collect all points
        points = [Vector(point.position) for point in settings.points[:7]]
        
        # Create extractors and combiner if in annotation mode
        extractor_ids = []
        
        if settings.create_extractors:
            # Get the active graph
            from s3dgraphy.utils.graph_registry import get_graph
            
            em_tools = scene.em_tools
            if em_tools.active_file_index < 0:
                self.report({'ERROR'}, "No active graph file. Load a GraphML first.")
                return {'CANCELLED'}
            
            graphml = em_tools.graphml_files[em_tools.active_file_index]
            graph = get_graph(graphml.name)
            
            if not graph:
                self.report({'ERROR'}, "Could not get active graph")
                return {'CANCELLED'}
            
            # Create extractors for each point
            for i, point_settings in enumerate(settings.points[:7]):
                if not point_settings.source_document:
                    self.report({'ERROR'}, f"Point {i+1} ({POINT_TYPE_LABELS[i]}) has no source document")
                    return {'CANCELLED'}
                
                # Get next extractor number for this document
                extractor_num = get_next_extractor_number(graph, point_settings.source_document)
                
                # Create extractor node
                extractor_id = create_extractor_node(
                    graph,
                    point_settings.source_document,
                    extractor_num,
                    Vector(point_settings.position),
                    point_settings.point_type
                )
                
                if not extractor_id:
                    self.report({'ERROR'}, f"Failed to create extractor for point {i+1}")
                    return {'CANCELLED'}
                
                extractor_ids.append(extractor_id)
                point_settings.extractor_id = extractor_id
                
                # Create Empty object for visualization
                create_empty_extractor(context, extractor_id, Vector(point_settings.position))
            
            # Create combiner
            combiner_num = get_next_combiner_number(graph)
            combiner_id = create_combiner_node(graph, combiner_num, extractor_ids)
            
            if not combiner_id:
                self.report({'ERROR'}, "Failed to create combiner")
                return {'CANCELLED'}
            
            settings.combiner_id = combiner_id
            
            self.report({'INFO'}, f"Created {len(extractor_ids)} extractors and combiner {combiner_id}")
        
        # Calculate box geometry
        try:
            geometry = calculate_box_geometry(points)
        except Exception as e:
            self.report({'ERROR'}, f"Failed to calculate geometry: {e}")
            return {'CANCELLED'}
        
        # Create the mesh
        try:
            proxy_obj = create_box_mesh(
                settings.proxy_name,
                geometry,
                settings.pivot_location
            )
        except Exception as e:
            self.report({'ERROR'}, f"Failed to create mesh: {e}")
            return {'CANCELLED'}
        
        # Add to appropriate collection
        if settings.use_proxy_collection:
            # Create or get Proxy collection
            if "Proxy" not in bpy.data.collections:
                proxy_collection = bpy.data.collections.new("Proxy")
                scene.collection.children.link(proxy_collection)
            else:
                proxy_collection = bpy.data.collections["Proxy"]
            
            # Link to Proxy collection
            proxy_collection.objects.link(proxy_obj)
        else:
            # Link to active collection
            context.collection.objects.link(proxy_obj)
        
        # Store metadata in custom properties
        proxy_obj["is_proxy"] = True
        proxy_obj["proxy_type"] = "box"
        proxy_obj["length"] = geometry['dimensions'][0]
        proxy_obj["width"] = geometry['dimensions'][1]
        proxy_obj["height"] = geometry['dimensions'][2]
        
        if settings.create_extractors:
            proxy_obj["combiner_id"] = settings.combiner_id
            proxy_obj["extractor_ids"] = ",".join(extractor_ids)
        
        # Select the new object
        bpy.ops.object.select_all(action='DESELECT')
        proxy_obj.select_set(True)
        context.view_layer.objects.active = proxy_obj
        
        self.report({'INFO'}, f"Created proxy '{settings.proxy_name}' with dimensions: " +
                    f"{geometry['dimensions'][0]:.2f} × {geometry['dimensions'][1]:.2f} × {geometry['dimensions'][2]:.2f}")
        
        return {'FINISHED'}


class PROXYBOX_OT_preview_combiner(Operator):
    """Preview the combiner ID that will be created"""
    bl_idname = "proxybox.preview_combiner"
    bl_label = "Preview Combiner"
    bl_description = "Calculate and show the combiner ID that will be used"
    
    def execute(self, context):
        settings = context.scene.em_tools.proxy_box
        
        if not settings.create_extractors:
            self.report({'INFO'}, "Extractor creation is disabled")
            return {'CANCELLED'}
        
        # Get the active graph
        from s3dgraphy.utils.graph_registry import get_graph
        
        em_tools = context.scene.em_tools
        if em_tools.active_file_index < 0:
            self.report({'WARNING'}, "No active graph file")
            return {'CANCELLED'}
        
        graphml = em_tools.graphml_files[em_tools.active_file_index]
        graph = get_graph(graphml.name)
        
        if not graph:
            self.report({'WARNING'}, "Could not get active graph")
            return {'CANCELLED'}
        
        # Calculate combiner number
        combiner_num = get_next_combiner_number(graph)
        combiner_id = f"C.{combiner_num}"
        
        settings.combiner_id = combiner_id
        
        self.report({'INFO'}, f"Next combiner will be: {combiner_id}")
        return {'FINISHED'}


# List of operator classes to register
classes = [
    PROXYBOX_OT_record_point,
    PROXYBOX_OT_clear_point,
    PROXYBOX_OT_clear_all_points,
    PROXYBOX_OT_pick_document_from_object,
    PROXYBOX_OT_use_paradata_document,
    PROXYBOX_OT_create_proxy,
    PROXYBOX_OT_preview_combiner,
]


def register():
    """Register all operator classes"""
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except ValueError as e:
            print(f"Warning: Could not register {cls.__name__}: {e}")
    
    print("✓ Proxy Box Creator operators registered")


def unregister():
    """Unregister all operator classes"""
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError as e:
            print(f"Warning: Could not unregister {cls.__name__}: {e}")
    
    print("✓ Proxy Box Creator operators unregistered")


if __name__ == "__main__":
    register()
