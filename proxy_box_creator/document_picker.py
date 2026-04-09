"""
Document picker popup for Proxy Box Creator
Provides a compact search interface for selecting source documents
"""

import bpy
from bpy.types import Operator
from bpy.props import StringProperty, IntProperty


class PROXYBOX_OT_search_document(Operator):
    """Search and pick a document from the graph"""
    bl_idname = "proxybox.search_document"
    bl_label = "Pick Document"
    bl_description = "Search for a document by name (e.g., D.10)"
    bl_options = {'REGISTER', 'INTERNAL'}
    
    point_index: IntProperty(
        name="Point Index",
        description="Which point this document is for",
        min=0,
        max=6
    )  # type: ignore
    
    search_query: StringProperty(
        name="Search",
        description="Search for document by name",
        default=""
    )  # type: ignore
    
    @classmethod
    def poll(cls, context):
        em_tools = context.scene.em_tools
        return em_tools.active_file_index >= 0
    
    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=400)
    
    def draw(self, context):
        layout = self.layout
        
        # Search box
        layout.prop(self, "search_query", text="", icon='VIEWZOOM')
        
        layout.separator()
        
        # Get the active graph
        from s3dgraphy import get_graph
        
        em_tools = context.scene.em_tools
        if em_tools.active_file_index < 0:
            layout.label(text="No active graph", icon='ERROR')
            return
        
        graph_info = em_tools.graphml_files[em_tools.active_file_index]
        graph = get_graph(graph_info.name)  # ← Use .name instead of .graph_id
        
        if not graph:
            layout.label(text="Graph not loaded", icon='ERROR')
            return
        
        # Filter documents by search query
        documents = []
        for node in graph.nodes:  # ← graph.nodes is a LIST, not a dict
            if hasattr(node, 'node_type') and node.node_type == "document":
                # Get both UUID (node_id) and human-readable name
                node_id = node.node_id if hasattr(node, 'node_id') else ""     # UUID (internal)
                node_name = node.name if hasattr(node, 'name') else ""         # Name (display)
                
                # Search in both node_id and name
                search_lower = self.search_query.lower()
                
                if (not self.search_query or 
                    search_lower in node_id.lower() or 
                    search_lower in node_name.lower()):
                    # Store BOTH: we'll use name for operations, but keep id for reference
                    documents.append((node_id, node_name))
        
        # Sort by node_id
        documents.sort(key=lambda x: x[0])
        
        # Display results
        if documents:
            box = layout.box()
            box.label(text=f"Found {len(documents)} documents:", icon='FILE_TEXT')
            
            # Limit display to first 20 results
            for doc_id, doc_name in documents[:20]:
                row = box.row()
                # Show only the document NAME in the button, not the ID
                op = row.operator("proxybox.assign_document", 
                                  text=doc_name,  # ← Only show name
                                  icon='CHECKMARK')
                op.point_index = self.point_index
                op.document_id = doc_id
                op.document_name = doc_name
            
            if len(documents) > 20:
                box.label(text=f"...and {len(documents) - 20} more. Refine your search.", 
                          icon='INFO')
        else:
            layout.label(text="No documents found", icon='INFO')
            if self.search_query:
                layout.label(text="Try a different search term")
    
    def execute(self, context):
        # This operator only shows a dialog, no execution needed
        return {'FINISHED'}


class PROXYBOX_OT_assign_document(Operator):
    """Assign a document to a measurement point"""
    bl_idname = "proxybox.assign_document"
    bl_label = "Assign Document"
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}
    
    point_index: IntProperty(
        name="Point Index",
        min=0,
        max=6
    )  # type: ignore
    
    document_id: StringProperty(
        name="Document ID",
        description="Internal node_id (UUID)",
        default=""
    )  # type: ignore
    
    document_name: StringProperty(
        name="Document Name",
        description="Human-readable document name",
        default=""
    )  # type: ignore
    
    def execute(self, context):
        settings = context.scene.em_tools.proxy_box
        
        # Ensure point exists
        while len(settings.points) <= self.point_index:
            settings.points.add()
        
        point = settings.points[self.point_index]
        
        # CRITICAL: Store the NAME (not UUID) for pattern matching
        point.source_document = self.document_name      # ← Store NAME for calculations
        point.source_document_name = self.document_name  # ← Store NAME for display
        
        self.report({'INFO'}, f"Assigned {self.document_name} to point {self.point_index + 1}")
        
        return {'FINISHED'}


class PROXYBOX_OT_copy_document_to_all(Operator):
    """Copy the document from one point to all other points"""
    bl_idname = "proxybox.copy_document_to_all"
    bl_label = "Copy to All Points"
    bl_description = "Copy this document to all measurement points"
    bl_options = {'REGISTER', 'UNDO'}
    
    point_index: IntProperty(
        name="Source Point Index",
        min=0,
        max=6
    )  # type: ignore
    
    def execute(self, context):
        settings = context.scene.em_tools.proxy_box
        
        if self.point_index >= len(settings.points):
            self.report({'ERROR'}, "Invalid point index")
            return {'CANCELLED'}
        
        source_point = settings.points[self.point_index]
        
        if not source_point.source_document:
            self.report({'WARNING'}, "Source point has no document assigned")
            return {'CANCELLED'}
        
        # Copy to all points
        count = 0
        for i in range(7):
            if i != self.point_index:
                # Ensure point exists
                while len(settings.points) <= i:
                    settings.points.add()
                
                point = settings.points[i]
                point.source_document = source_point.source_document
                point.source_document_name = source_point.source_document_name
                count += 1
        
        self.report({'INFO'}, f"Copied document {source_point.source_document} to {count} points")
        
        return {'FINISHED'}


class PROXYBOX_OT_calculate_extractor_id(Operator):
    """Calculate the next available extractor ID for this point"""
    bl_idname = "proxybox.calculate_extractor_id"
    bl_label = "Calculate Extractor ID"
    bl_description = "Auto-calculate the next extractor ID (e.g., D.10.11)"
    bl_options = {'REGISTER', 'UNDO'}
    
    point_index: IntProperty(
        name="Point Index",
        min=0,
        max=6
    )  # type: ignore
    
    @classmethod
    def poll(cls, context):
        em_tools = context.scene.em_tools
        return em_tools.active_file_index >= 0
    
    def execute(self, context):
        settings = context.scene.em_tools.proxy_box
        
        if self.point_index >= len(settings.points):
            self.report({'ERROR'}, "Invalid point index")
            return {'CANCELLED'}
        
        point = settings.points[self.point_index]
        
        if not point.source_document:
            self.report({'WARNING'}, "Assign a document first")
            return {'CANCELLED'}
        
        # Get the active graph
        from s3dgraphy import get_graph
        
        em_tools = context.scene.em_tools
        graph_info = em_tools.graphml_files[em_tools.active_file_index]
        graph = get_graph(graph_info.name)  # ← Use .name instead of .graph_id
        
        if not graph:
            self.report({'ERROR'}, "Graph not loaded")
            return {'CANCELLED'}
        
        # Find the next available extractor number for this document
        doc_id = point.source_document
        max_num = 0
        
        # STEP 1: Check existing extractors in the GRAPH
        for node in graph.nodes:
            # Skip nodes without proper attributes
            if not hasattr(node, 'node_type'):
                continue
            
            # Only look at extractor nodes
            if node.node_type != "extractor":
                continue
            
            # Use node.name (not node_id UUID) for the pattern matching
            if not hasattr(node, 'name'):
                continue
            
            node_name = node.name
            
            # Skip if name is not a string
            if not isinstance(node_name, str):
                continue
            
            # Check for extractor names like "D.10.11" that belong to this document
            if node_name.startswith(doc_id + "."):
                parts = node_name.split('.')
                if len(parts) >= 2:
                    try:
                        # Get the last number (e.g., 11 from "D.10.11")
                        sub_num = int(parts[-1])
                        max_num = max(max_num, sub_num)
                    except ValueError:
                        continue
        
        # STEP 2: Check extractors already assigned to OTHER points in THIS proxy
        # (they don't exist in the graph yet, but will be created)
        for i, other_point in enumerate(settings.points[:7]):
            # Skip the current point
            if i == self.point_index:
                continue
            
            # Skip points without extractor IDs
            if not other_point.extractor_id:
                continue
            
            # Skip if different document
            if other_point.source_document != doc_id:
                continue
            
            # Parse the extractor ID
            if other_point.extractor_id.startswith(doc_id + "."):
                parts = other_point.extractor_id.split('.')
                if len(parts) >= 2:
                    try:
                        sub_num = int(parts[-1])
                        max_num = max(max_num, sub_num)
                    except ValueError:
                        continue
        
        next_num = max_num + 1
        extractor_id = f"{doc_id}.{next_num:02d}"
        
        point.extractor_id = extractor_id
        
        self.report({'INFO'}, f"Calculated extractor ID: {extractor_id}")
        
        return {'FINISHED'}


# List of classes to register
classes = [
    PROXYBOX_OT_search_document,
    PROXYBOX_OT_assign_document,
    PROXYBOX_OT_copy_document_to_all,
    PROXYBOX_OT_calculate_extractor_id,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()