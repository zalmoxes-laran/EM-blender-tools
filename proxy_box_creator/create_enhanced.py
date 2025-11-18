"""
Enhanced proxy creation operator with full paradata support
Creates extractors and combiner nodes in the Extractors collection
"""

import bpy
from bpy.types import Operator
from mathutils import Vector


class PROXYBOX_OT_create_proxy_enhanced(Operator):
    """Create proxy box with optional extractors and combiner"""
    bl_idname = "proxybox.create_proxy_enhanced"
    bl_label = "Create Proxy"
    bl_description = "Create the proxy box mesh and optional extractors/combiner"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        settings = context.scene.em_tools.proxy_box
        
        # Check that all 7 points are recorded
        if len(settings.points) < 7:
            return False
        
        if not all(point.is_recorded for point in settings.points[:7]):
            return False
        
        # If in paradata mode, check documents and extractors
        if settings.create_extractors:
            if not all(point.source_document for point in settings.points[:7]):
                return False
            if not all(point.extractor_id for point in settings.points[:7]):
                return False
        
        return True
    
    def execute(self, context):
        settings = context.scene.em_tools.proxy_box
        scene = context.scene
        
        # Collect all points
        points = [Vector(point.position) for point in settings.points[:7]]
        
        # ═══════════════════════════════════════════════════════
        # STEP 1: Create Extractors (if enabled)
        # ═══════════════════════════════════════════════════════
        extractor_objects = []
        
        if settings.create_extractors:
            self.report({'INFO'}, "Creating extractors in graph...")
            
            # Get the active graph
            from s3dgraphy import get_graph
            
            em_tools = scene.em_tools
            if em_tools.active_file_index < 0:
                self.report({'ERROR'}, "No active graph file. Load a GraphML first.")
                return {'CANCELLED'}
            
            graph_info = em_tools.graphml_files[em_tools.active_file_index]
            graph = get_graph(graph_info.name)  # ← Use .name instead of .graph_id
            
            if not graph:
                self.report({'ERROR'}, "Graph not loaded")
                return {'CANCELLED'}
            
            # Get or create Extractors collection
            extractors_collection = self._ensure_extractors_collection(context)
            
            # Create extractor nodes in graph and empties in scene
            for i, point in enumerate(settings.points[:7]):
                extractor_id = point.extractor_id
                doc_id = point.source_document
                
                # Create node in graph
                success = self._create_extractor_in_graph(
                    graph, doc_id, extractor_id, point.point_type, point.position
                )
                
                if success:
                    # Create empty in scene
                    empty = self._create_extractor_empty(
                        context, extractor_id, point.position, extractors_collection
                    )
                    extractor_objects.append(empty)
                    self.report({'INFO'}, f"Created extractor: {extractor_id}")
                else:
                    self.report({'WARNING'}, f"Failed to create extractor: {extractor_id}")
            
            # ═══════════════════════════════════════════════════════
            # STEP 2: Create Combiner
            # ═══════════════════════════════════════════════════════
            combiner_id = self._create_combiner(context, graph, extractor_objects)
            
            if combiner_id:
                settings.combiner_id = combiner_id
                self.report({'INFO'}, f"Created combiner: {combiner_id}")
        
        # ═══════════════════════════════════════════════════════
        # STEP 3: Create Proxy Geometry
        # ═══════════════════════════════════════════════════════
        proxy_obj = self._create_proxy_geometry(context, points, settings)
        
        if not proxy_obj:
            self.report({'ERROR'}, "Failed to create proxy geometry")
            return {'CANCELLED'}
        
        # Link combiner to proxy if created
        if settings.create_extractors and settings.combiner_id:
            # Store reference in custom property
            proxy_obj["em_combiner_id"] = settings.combiner_id
        
        self.report({'INFO'}, f"Proxy created: {proxy_obj.name}")
        
        return {'FINISHED'}
    
    def _ensure_extractors_collection(self, context):
        """Get or create the Extractors collection in scene root"""
        scene = context.scene
        
        # Check if collection exists
        if "Extractors" in bpy.data.collections:
            extractors_col = bpy.data.collections["Extractors"]
        else:
            # Create new collection
            extractors_col = bpy.data.collections.new("Extractors")
            scene.collection.children.link(extractors_col)
        
        return extractors_col
    
    def _create_extractor_in_graph(self, graph, doc_id, extractor_id, point_type, position):
        """Create an extractor node in the graph"""
        try:
            import uuid
            from s3dgraphy.nodes import ExtractorNode
            
            # Create the extractor node
            # node_id = UUID (internal use)
            # name = human-readable ID (e.g., "D.10.11")
            extractor = ExtractorNode(
                node_id=str(uuid.uuid4()),  # ← UUID for internal graph operations
                name=extractor_id,          # ← Human-readable name (e.g., "D.10.11")
                description=f"Extractor for {point_type} point"
            )
            
            # Add metadata
            extractor.attributes['point_type'] = point_type
            extractor.attributes['x'] = position.x
            extractor.attributes['y'] = position.y
            extractor.attributes['z'] = position.z
            extractor.attributes['purpose'] = "proxy_box_creator"
            extractor.attributes['description'] = f"Extractor for {point_type} point"
            
            # Add to graph
            graph.add_node(extractor)
            
            # Create edge from document to extractor
            # CRITICAL: Find document by NAME (not UUID)
            doc_node = None
            for node in graph.nodes:
                if hasattr(node, 'name') and node.name == doc_id:
                    doc_node = node
                    break
            
            if not doc_node:
                print(f"✗ Error: Could not find document node with name: {doc_id}")
                return False
            
            edge_id = f"{doc_node.node_id}_extracts_{extractor.node_id}"
            graph.add_edge(
                edge_id=edge_id,
                edge_source=doc_node.node_id,  # Use UUID for edge
                edge_target=extractor.node_id,  # Use UUID for edge
                edge_type="has_extractor"
            )
            
            return True
            
        except Exception as e:
            print(f"Error creating extractor in graph: {e}")
            return False
    
    def _create_extractor_empty(self, context, extractor_id, position, collection):
        """Create an empty object for the extractor"""
        # Create empty
        empty = bpy.data.objects.new(extractor_id, None)
        empty.location = position
        empty.empty_display_type = 'SPHERE'
        empty.empty_display_size = 0.1
        
        # Link to collection
        collection.objects.link(empty)
        
        # Store metadata
        empty["em_extractor_id"] = extractor_id
        empty["em_node_type"] = "extractor"
        
        return empty
    
    def _create_combiner(self, context, graph, extractor_objects):
        """Create a combiner node that connects all extractors"""
        try:
            from s3dgraphy.nodes import CombinerNode
            
            # Get next combiner number
            max_num = 0
            for node in graph.nodes:
                # Skip nodes without proper attributes
                if not hasattr(node, 'node_type') or not hasattr(node, 'name'):
                    continue
                
                # Skip non-combiner nodes
                if node.node_type != "combiner":
                    continue
                
                node_name = node.name
                
                # Skip if name is not a string (defensive)
                if not isinstance(node_name, str):
                    continue
                
                # Check for combiner names like "C.10"
                if node_name.startswith('C.'):
                    try:
                        num = int(node_name.split('.')[1])
                        max_num = max(max_num, num)
                    except (ValueError, IndexError):
                        continue
            
            combiner_id = f"C.{max_num + 1}"
            
            # Create combiner node
            combiner = CombinerNode(
                node_id=combiner_id,
                name=f"Proxy_{context.scene.em_tools.proxy_box.proxy_name}"
            )
            
            combiner.attributes['purpose'] = "proxy_box_creator"
            combiner.attributes['description'] = "Combiner for proxy box measurement points"
            
            # Add to graph
            graph.add_node(combiner)
            
            # Create edges from extractors to combiner
            for ext_obj in extractor_objects:
                extractor_id = ext_obj.get("em_extractor_id", "")
                if extractor_id:
                    edge_id = f"{extractor_id}_combines_to_{combiner_id}"
                    graph.add_edge(
                        edge_id=edge_id,
                        edge_source=extractor_id,
                        edge_target=combiner_id,
                        edge_type="is_combined_in"
                    )
            
            # Create combiner empty in Extractors collection
            combiner_empty = bpy.data.objects.new(combiner_id, None)
            
            # Position at centroid of extractors
            if extractor_objects:
                centroid = sum((obj.location for obj in extractor_objects), Vector()) / len(extractor_objects)
                combiner_empty.location = centroid
            
            combiner_empty.empty_display_type = 'CUBE'
            combiner_empty.empty_display_size = 0.3
            
            # Link to Extractors collection
            extractors_collection = self._ensure_extractors_collection(context)
            extractors_collection.objects.link(combiner_empty)
            
            # Store metadata
            combiner_empty["em_combiner_id"] = combiner_id
            combiner_empty["em_node_type"] = "combiner"
            
            return combiner_id
            
        except Exception as e:
            print(f"Error creating combiner: {e}")
            return None
    
    def _create_proxy_geometry(self, context, points, settings):
        """Create the actual proxy box geometry"""
        from .utils import calculate_box_geometry, create_box_mesh
        
        # Calculate box geometry
        try:
            geometry = calculate_box_geometry(points)
        except Exception as e:
            print(f"Error calculating geometry: {e}")
            return None
        
        # Create mesh
        try:
            proxy_obj = create_box_mesh(
                settings.proxy_name,      # name (string)
                geometry,                 # geometry (dict)
                settings.pivot_location   # pivot_location (string)
            )
        except Exception as e:
            print(f"Error creating mesh: {e}")
            return None
        
        # Move to Proxy collection if enabled
        if settings.use_proxy_collection:
            if "Proxy" not in bpy.data.collections:
                proxy_col = bpy.data.collections.new("Proxy")
                context.scene.collection.children.link(proxy_col)
            else:
                proxy_col = bpy.data.collections["Proxy"]
            
            # Unlink from current collections
            for col in proxy_obj.users_collection:
                col.objects.unlink(proxy_obj)
            
            # Link to Proxy collection
            proxy_col.objects.link(proxy_obj)
        
        return proxy_obj


# List of classes to register
classes = [
    PROXYBOX_OT_create_proxy_enhanced,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()