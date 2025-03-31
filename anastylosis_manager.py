import bpy
from bpy.props import (
    StringProperty, 
    BoolProperty,
    CollectionProperty,
    IntProperty,
    EnumProperty,
    PointerProperty,
    FloatVectorProperty,
)
from bpy.types import (
    Panel,
    Operator,
    PropertyGroup,
    UIList,
)

from .s3Dgraphy import get_graph
from .s3Dgraphy.nodes.representation_node import RepresentationModelSpecialFindNode
from .s3Dgraphy.nodes.stratigraphic_node import SpecialFindUnit, VirtualSpecialFindUnit
from .s3Dgraphy.nodes.link_node import LinkNode

# PropertyGroup for representing a SpecialFind association
class AnastylisisItem(PropertyGroup):
    """Properties for SpecialFind models in the anastylosis list"""
    name: StringProperty(
        name="Name",
        description="Name of the 3D model",
        default="Unnamed"
    )
    sf_node_id: StringProperty(
        name="SF Node ID",
        description="ID of the SpecialFind node this model is associated with",
        default=""
    )
    sf_node_name: StringProperty(
        name="SF Node Name",
        description="Name of the SpecialFind node",
        default=""
    )
    is_virtual: BoolProperty(
        name="Is Virtual",
        description="Whether this is a virtual reconstruction (VSF) or a real fragment (SF)",
        default=False
    )
    is_publishable: BoolProperty(
        name="Publishable",
        description="Whether this anastylosis model is publishable",
        default=True
    )
    node_id: StringProperty(
        name="Node ID",
        description="ID of the RMSF node in the graph",
        default=""
    )
    object_exists: BoolProperty(
        name="Object Exists",
        description="Whether the object exists in the scene",
        default=False
    )

# UI List for showing the anastylosis models
class ANASTYLOSIS_UL_List(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        try:
            if self.layout_type in {'DEFAULT', 'COMPACT'}:
                # Get the object
                obj = bpy.data.objects.get(item.name)
                
                # Determine appropriate icon
                if hasattr(item, 'object_exists') and item.object_exists:
                    obj_icon = 'OBJECT_DATA'
                else:
                    obj_icon = 'ERROR'
                
                # Layout
                row = layout.row(align=True)
                
                # Name of the model
                row.prop(item, "name", text="", emboss=False, icon=obj_icon)
                
                # Associated SF/VSF node
                if hasattr(item, 'sf_node_name') and item.sf_node_name:
                    sf_icon = 'OUTLINER_OB_EMPTY' if item.is_virtual else 'MESH_ICOSPHERE'
                    row.label(text=item.sf_node_name, icon=sf_icon)
                else:
                    row.label(text="[Not Connected]", icon='QUESTION')
                
                # Link/Select buttons
                op = row.operator("anastylosis.link_to_sf", text="", icon='LINKED', emboss=False)
                op.anastylosis_index = index
                
                op = row.operator("anastylosis.select_from_list", text="", icon='RESTRICT_SELECT_OFF', emboss=False)
                op.anastylosis_index = index
                
                # Publish flag
                if hasattr(item, 'is_publishable'):
                    row.prop(item, "is_publishable", text="", icon='EXPORT' if item.is_publishable else 'CANCEL')
                
                # Trash bin for removing
                op = row.operator("anastylosis.remove_from_list", text="", icon='TRASH', emboss=False)
                op.anastylosis_index = index
                
            elif self.layout_type in {'GRID'}:
                layout.alignment = 'CENTER'
                layout.label(text="", icon='OBJECT_DATA')
                
        except Exception as e:
            # In case of error, show basic element
            row = layout.row()
            row.label(text=f"Error: {str(e)}", icon='ERROR')

# Operator to update the anastylosis list
class ANASTYLOSIS_OT_update_list(Operator):
    bl_idname = "anastylosis.update_list"
    bl_label = "Update Anastylosis List"
    bl_description = "Update the list of anastylosis models from the graph and scene objects"
    
    from_graph: BoolProperty(
        name="Update from Graph",
        description="Update the list using graph data. If False, uses only scene objects.",
        default=True
    )
    
    def execute(self, context):
        try:
            scene = context.scene
            anastylosis_list = scene.anastylosis_list
            
            # Save current index to restore after update
            current_index = scene.anastylosis_list_index
            
            # Track objects already in the list
            existing_objects = {}
            for i, item in enumerate(anastylosis_list):
                if hasattr(item, 'name'):
                    existing_objects[item.name] = {
                        "index": i,
                        "sf_node_id": item.sf_node_id,
                        "is_publishable": item.is_publishable if hasattr(item, 'is_publishable') else True
                    }
            
            # Get active graph if updating from graph
            graph = None
            if self.from_graph and hasattr(context.scene, 'em_tools'):
                if (hasattr(context.scene.em_tools, 'graphml_files') and
                    len(context.scene.em_tools.graphml_files) > 0 and
                    context.scene.em_tools.active_file_index >= 0):
                    
                    graphml = context.scene.em_tools.graphml_files[context.scene.em_tools.active_file_index]
                    graph = get_graph(graphml.name)
            
            # If we have a graph, process all RMSF nodes
            if graph:
                # Find all RMSF nodes
                rmsf_nodes = [node for node in graph.nodes if node.node_type == "representation_model_sf"]
                
                for node in rmsf_nodes:
                    # Extract object name from node_id (assuming node_id format is "{obj_name}_rmsf")
                    obj_name = node.name.replace("RMSF for ", "").strip()
                    
                    # Check if object exists in scene
                    obj_exists = obj_name in bpy.data.objects
                    
                    # Find connected SF/VSF node
                    sf_node = None
                    sf_node_id = ""
                    sf_node_name = ""
                    is_virtual = False
                    
                    # Find edges connecting to SF/VSF nodes
                    for edge in graph.edges:
                        if edge.edge_source == node.node_id and edge.edge_type == "has_representation_model":
                            target_node = graph.find_node_by_id(edge.edge_target)
                            if target_node and target_node.node_type in ["SF", "VSF"]:
                                sf_node = target_node
                                sf_node_id = target_node.node_id
                                sf_node_name = target_node.name
                                is_virtual = target_node.node_type == "VSF"
                                break
                        elif edge.edge_target == node.node_id and edge.edge_type == "has_representation_model":
                            source_node = graph.find_node_by_id(edge.edge_source)
                            if source_node and source_node.node_type in ["SF", "VSF"]:
                                sf_node = source_node
                                sf_node_id = source_node.node_id
                                sf_node_name = source_node.name
                                is_virtual = source_node.node_type == "VSF"
                                break
                    
                    # Check if this object is already in the list
                    if obj_name in existing_objects:
                        # Update existing item
                        index = existing_objects[obj_name]["index"]
                        item = anastylosis_list[index]
                        item.sf_node_id = sf_node_id
                        item.sf_node_name = sf_node_name
                        item.is_virtual = is_virtual
                        item.node_id = node.node_id
                        item.object_exists = obj_exists
                    else:
                        # Create new item
                        item = anastylosis_list.add()
                        item.name = obj_name
                        item.sf_node_id = sf_node_id
                        item.sf_node_name = sf_node_name
                        item.is_virtual = is_virtual
                        item.node_id = node.node_id
                        item.object_exists = obj_exists
                        item.is_publishable = node.attributes.get('is_publishable', True) if hasattr(node, 'attributes') else True
            
            # Process all selected objects from scene if needed
            if not self.from_graph or not graph:
                # Get all selected mesh objects
                selected_objects = [obj for obj in context.selected_objects if obj.type == 'MESH']
                
                for obj in selected_objects:
                    # Skip if already processed from graph
                    if obj.name in existing_objects:
                        continue
                    
                    # Create new item for this object
                    item = anastylosis_list.add()
                    item.name = obj.name
                    item.object_exists = True
                    item.is_publishable = True
                    
                    # Set up node ID following same convention as other modules
                    item.node_id = f"{obj.name}_rmsf"
            
            # Restore index if possible
            scene.anastylosis_list_index = min(current_index, len(anastylosis_list)-1) if anastylosis_list else 0
            
            # Report
            if self.from_graph:
                self.report({'INFO'}, f"Updated anastylosis list from graph: {len(anastylosis_list)} models")
            else:
                self.report({'INFO'}, f"Updated anastylosis list from scene: {len(anastylosis_list)} models")
            
            return {'FINISHED'}
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.report({'ERROR'}, f"Error updating anastylosis list: {str(e)}")
            return {'CANCELLED'}

# Operator to link an object to a SF/VSF node
class ANASTYLOSIS_OT_link_to_sf(Operator):
    bl_idname = "anastylosis.link_to_sf"
    bl_label = "Link to Active SpecialFind"
    bl_description = "Link this object to the currently active SpecialFind in Stratigraphy Manager"
    
    anastylosis_index: IntProperty(
        name="Anastylosis Index",
        description="Index of the anastylosis item in the list",
        default=-1
    )
    
    def execute(self, context):
        scene = context.scene
        
        # Get item from anastylosis list
        if self.anastylosis_index < 0:
            self.anastylosis_index = scene.anastylosis_list_index
            
        if self.anastylosis_index < 0 or self.anastylosis_index >= len(scene.anastylosis_list):
            self.report({'ERROR'}, "No anastylosis model selected")
            return {'CANCELLED'}
            
        item = scene.anastylosis_list[self.anastylosis_index]
        
        # Get object
        obj = bpy.data.objects.get(item.name)
        if not obj:
            self.report({'ERROR'}, f"Object {item.name} not found in scene")
            return {'CANCELLED'}
        
        # Get active stratigraphy item
        if scene.em_list_index < 0 or scene.em_list_index >= len(scene.em_list):
            self.report({'ERROR'}, "No active stratigraphy unit selected")
            return {'CANCELLED'}
            
        active_strat_item = scene.em_list[scene.em_list_index]
        
        # Get graph
        graph = None
        if context.scene.em_tools.active_file_index >= 0:
            graphml = context.scene.em_tools.graphml_files[context.scene.em_tools.active_file_index]
            graph = get_graph(graphml.name)
            
        if not graph:
            self.report({'ERROR'}, "No active graph available")
            return {'CANCELLED'}
        
        # Get SF node
        sf_node = graph.find_node_by_id(active_strat_item.id_node)
        if not sf_node:
            self.report({'ERROR'}, f"SpecialFind node {active_strat_item.id_node} not found in graph")
            return {'CANCELLED'}
            
        # Check if it's actually a SF or VSF
        if sf_node.node_type not in ["SF", "VSF"]:
            self.report({'ERROR'}, f"Active node is not a SpecialFind (type: {sf_node.node_type})")
            return {'CANCELLED'}
        
        # Proceed with linking
        # Get or create RMSF node
        rmsf_id = f"{item.name}_rmsf"
        rmsf_node = graph.find_node_by_id(rmsf_id)
        
        if not rmsf_node:
            # Get object transform
            transform = {
                "position": [f"{obj.location.x}", f"{obj.location.y}", f"{obj.location.z}"],
                "scale": [f"{obj.scale.x}", f"{obj.scale.y}", f"{obj.scale.z}"]
            }
            
            # Handle rotation based on rotation mode
            if obj.rotation_mode == 'QUATERNION':
                quat = obj.rotation_quaternion
                euler = quat.to_euler('XYZ')
                transform["rotation"] = [f"{euler.x}", f"{euler.y}", f"{euler.z}"]
            else:
                transform["rotation"] = [f"{obj.rotation_euler.x}", f"{obj.rotation_euler.y}", f"{obj.rotation_euler.z}"]
            
            # Create RMSF node
            rmsf_node = RepresentationModelSpecialFindNode(
                node_id=rmsf_id,
                name=f"RMSF for {item.name}",
                type="RM",
                transform=transform,
                description=f"Representation model for {sf_node.node_type} {sf_node.name}"
            )
            
            # Add node to graph
            graph.add_node(rmsf_node)
        
        # Create or update edge
        edge_id = f"{sf_node.node_id}_has_representation_model_{rmsf_id}"
        existing_edge = graph.find_edge_by_id(edge_id)
        
        if not existing_edge:
            graph.add_edge(
                edge_id=edge_id,
                edge_source=sf_node.node_id,
                edge_target=rmsf_id,
                edge_type="has_representation_model"
            )
        
        # Create a LinkNode to store the URL
        link_node_id = f"{rmsf_id}_link"
        link_node = graph.find_node_by_id(link_node_id)
        
        if not link_node:
            # Create new LinkNode
            gltf_path = f"models_sf/{item.name}.gltf"
            link_node = LinkNode(
                node_id=link_node_id,
                name=f"GLTF Link for {item.name}",
                description=f"Link to exported GLTF for {sf_node.node_type} {sf_node.name}",
                url=gltf_path,
                url_type="3d_model"
            )
            graph.add_node(link_node)
            
            # Create edge between RMSF and LinkNode
            edge_id = f"{rmsf_id}_has_linked_resource_{link_node_id}"
            graph.add_edge(
                edge_id=edge_id,
                edge_source=rmsf_id,
                edge_target=link_node_id,
                edge_type="has_linked_resource"
            )
        
        # Update the anastylosis list
        item.sf_node_id = sf_node.node_id
        item.sf_node_name = sf_node.name
        item.is_virtual = sf_node.node_type == "VSF"
        item.node_id = rmsf_id
        
        # Refresh the list
        bpy.ops.anastylosis.update_list(from_graph=True)
        
        self.report({'INFO'}, f"Linked {item.name} to {sf_node.node_type} {sf_node.name}")
        return {'FINISHED'}
    
# Operator to confirm SF/VSF link selection
class ANASTYLOSIS_OT_confirm_link(Operator):
    bl_idname = "anastylosis.confirm_link"
    bl_label = "Confirm Link"
    bl_description = "Confirm linking object to this SpecialFind node"
    
    sf_node_index: IntProperty(
        name="SF Node Index",
        description="Index of the SF node in the temporary list",
        default=-1
    )
    
    def execute(self, context):
        scene = context.scene
        
        # Check if we have valid selection
        if self.sf_node_index < 0 or self.sf_node_index >= len(scene.anastylosis_sf_nodes):
            self.report({'ERROR'}, "Invalid SpecialFind node selection")
            return {'CANCELLED'}
        
        # Get the selected SF node
        sf_item = scene.anastylosis_sf_nodes[self.sf_node_index]
        
        # Get object name and RMSF ID from temp properties
        obj_name = scene.anastylosis_temp_obj_name
        rmsf_id = scene.anastylosis_temp_rmsf_id
        
        # Get object
        obj = bpy.data.objects.get(obj_name)
        if not obj:
            self.report({'ERROR'}, f"Object {obj_name} not found in scene")
            return {'CANCELLED'}
        
        # Get graph
        graph = None
        if context.scene.em_tools.active_file_index >= 0:
            graphml = context.scene.em_tools.graphml_files[context.scene.em_tools.active_file_index]
            graph = get_graph(graphml.name)
            
        if not graph:
            self.report({'ERROR'}, "No active graph available")
            return {'CANCELLED'}
        
        # Get or create RMSF node
        rmsf_node = graph.find_node_by_id(rmsf_id)
        if not rmsf_node:
            # Get object transform
            transform = {
                "position": [f"{obj.location.x}", f"{obj.location.y}", f"{obj.location.z}"],
                "scale": [f"{obj.scale.x}", f"{obj.scale.y}", f"{obj.scale.z}"]
            }
            
            # Handle rotation based on rotation mode
            if obj.rotation_mode == 'QUATERNION':
                quat = obj.rotation_quaternion
                euler = quat.to_euler('XYZ')
                transform["rotation"] = [f"{euler.x}", f"{euler.y}", f"{euler.z}"]
            else:
                transform["rotation"] = [f"{obj.rotation_euler.x}", f"{obj.rotation_euler.y}", f"{obj.rotation_euler.z}"]
            
            # Create RMSF node
            rmsf_node = RepresentationModelSpecialFindNode(
                node_id=rmsf_id,
                name=f"RMSF for {obj_name}",
                type="RM",
                transform=transform,
                description=f"Representation model for SpecialFind {obj_name}"
            )
            
            # Add node to graph
            graph.add_node(rmsf_node)
        
        # Get SF node
        sf_node = graph.find_node_by_id(sf_item.node_id)
        if not sf_node:
            self.report({'ERROR'}, f"SpecialFind node {sf_item.node_id} not found in graph")
            return {'CANCELLED'}
        
        # Create or update edge
        edge_id = f"{sf_item.node_id}_has_representation_model_{rmsf_id}"
        existing_edge = graph.find_edge_by_id(edge_id)
        
        if not existing_edge:
            graph.add_edge(
                edge_id=edge_id,
                edge_source=sf_item.node_id,
                edge_target=rmsf_id,
                edge_type="has_representation_model"
            )
        
        # Create a LinkNode to store the URL
        link_node_id = f"{rmsf_id}_link"
        link_node = graph.find_node_by_id(link_node_id)
        
        if not link_node:
            # Create new LinkNode
            gltf_path = f"models_sf/{obj_name}.gltf"
            link_node = LinkNode(
                node_id=link_node_id,
                name=f"GLTF Link for {obj_name}",
                description=f"Link to exported GLTF for SpecialFind {obj_name}",
                url=gltf_path,
                url_type="3d_model"
            )
            graph.add_node(link_node)
            
            # Create edge between RMSF and LinkNode
            edge_id = f"{rmsf_id}_has_linked_resource_{link_node_id}"
            graph.add_edge(
                edge_id=edge_id,
                edge_source=rmsf_id,
                edge_target=link_node_id,
                edge_type="has_linked_resource"
            )
        
        # Update the anastylosis list
        for item in scene.anastylosis_list:
            if item.name == obj_name:
                item.sf_node_id = sf_item.node_id
                item.sf_node_name = sf_item.name
                item.is_virtual = "Virtual" in sf_item.description
                break
        
        # Refresh the list
        bpy.ops.anastylosis.update_list(from_graph=True)
        
        self.report({'INFO'}, f"Linked {obj_name} to SpecialFind {sf_item.name}")
        return {'FINISHED'}

# Operator to select object from list
class ANASTYLOSIS_OT_select_from_list(Operator):
    bl_idname = "anastylosis.select_from_list"
    bl_label = "Select Object"
    bl_description = "Select this object in the 3D view"
    
    anastylosis_index: IntProperty(
        name="Anastylosis Index",
        description="Index of the anastylosis item in the list",
        default=-1
    )
    
    def execute(self, context):
        scene = context.scene
        
        # Get item from list
        if self.anastylosis_index < 0:
            self.anastylosis_index = scene.anastylosis_list_index
            
        if self.anastylosis_index < 0 or self.anastylosis_index >= len(scene.anastylosis_list):
            self.report({'ERROR'}, "No anastylosis model selected")
            return {'CANCELLED'}
            
        item = scene.anastylosis_list[self.anastylosis_index]
        
        # Get object
        obj = bpy.data.objects.get(item.name)
        if not obj:
            self.report({'ERROR'}, f"Object {item.name} not found in scene")
            return {'CANCELLED'}
        
        # Deselect all objects
        bpy.ops.object.select_all(action='DESELECT')
        
        # Select the object
        obj.select_set(True)
        context.view_layer.objects.active = obj
        
        # Zoom to object if settings allow
        if hasattr(scene, 'anastylosis_settings') and scene.anastylosis_settings.zoom_to_selected:
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    # Create proper override
                    override = context.copy()
                    override['area'] = area
                    bpy.ops.view3d.view_selected(override)
                    break
        
        self.report({'INFO'}, f"Selected object: {item.name}")
        return {'FINISHED'}

# Operator to remove from list
class ANASTYLOSIS_OT_remove_from_list(Operator):
    bl_idname = "anastylosis.remove_from_list"
    bl_label = "Remove from Anastylosis"
    bl_description = "Remove this object from anastylosis list and unlink from SpecialFind node"
    
    anastylosis_index: IntProperty(
        name="Anastylosis Index",
        description="Index of the anastylosis item in the list",
        default=-1
    )
    
    def execute(self, context):
        scene = context.scene
        
        # Get item from list
        if self.anastylosis_index < 0:
            self.anastylosis_index = scene.anastylosis_list_index
            
        if self.anastylosis_index < 0 or self.anastylosis_index >= len(scene.anastylosis_list):
            self.report({'ERROR'}, "No anastylosis model selected")
            return {'CANCELLED'}
            
        item = scene.anastylosis_list[self.anastylosis_index]
        
        # Get graph
        graph = None
        if context.scene.em_tools.active_file_index >= 0:
            graphml = context.scene.em_tools.graphml_files[context.scene.em_tools.active_file_index]
            graph = get_graph(graphml.name)
        
        # If we have a graph, remove nodes and edges
        if graph:
            # Find and remove RMSF node
            rmsf_node = graph.find_node_by_id(item.node_id)
            if rmsf_node:
                # Find all connected edges
                edges_to_remove = []
                for edge in graph.edges:
                    if edge.edge_source == item.node_id or edge.edge_target == item.node_id:
                        edges_to_remove.append(edge.edge_id)
                
                # Remove edges
                for edge_id in edges_to_remove:
                    graph.remove_edge(edge_id)
                
                # Remove node
                graph.remove_node(item.node_id)
                
                # Also remove the link node if it exists
                link_node_id = f"{item.node_id}_link"
                link_node = graph.find_node_by_id(link_node_id)
                if link_node:
                    # Find and remove edges to the link node
                    for edge in graph.edges:
                        if edge.edge_source == link_node_id or edge.edge_target == link_node_id:
                            graph.remove_edge(edge.edge_id)
                    
                    # Remove the link node
                    graph.remove_node(link_node_id)
        
        # Remove from list
        scene.anastylosis_list.remove(self.anastylosis_index)
        
        # Update index if needed
        if scene.anastylosis_list_index >= len(scene.anastylosis_list):
            scene.anastylosis_list_index = max(0, len(scene.anastylosis_list) - 1)
        
        self.report({'INFO'}, f"Removed {item.name} from anastylosis list")
        return {'FINISHED'}

# Operator to add selected objects to the list
class ANASTYLOSIS_OT_add_selected(Operator):
    bl_idname = "anastylosis.add_selected"
    bl_label = "Add Selected Objects"
    bl_description = "Add selected mesh objects to the anastylosis list"
    
    def execute(self, context):
        scene = context.scene
        
        # Get all selected mesh objects
        selected_objects = [obj for obj in context.selected_objects if obj.type == 'MESH']
        
        if not selected_objects:
            self.report({'ERROR'}, "No mesh objects selected")
            return {'CANCELLED'}
        
        # Keep track of objects added
        added_count = 0
        
        # Get graph (optional)
        graph = None
        if context.scene.em_tools.active_file_index >= 0:
            graphml = context.scene.em_tools.graphml_files[context.scene.em_tools.active_file_index]
            graph = get_graph(graphml.name)
        
        # Find existing objects in the list
        existing_objects = {item.name for item in scene.anastylosis_list}
        
        for obj in selected_objects:
            # Skip if already in list
            if obj.name in existing_objects:
                continue
                
            # Create new item
            item = scene.anastylosis_list.add()
            item.name = obj.name
            item.object_exists = True
            item.is_publishable = True
            item.node_id = f"{obj.name}_rmsf"
            
            # If we have a graph, create RMSF node
            if graph:
                # Check if node already exists
                existing_node = graph.find_node_by_id(item.node_id)
                if not existing_node:
                    # Get object transform
                    transform = {
                        "position": [f"{obj.location.x}", f"{obj.location.y}", f"{obj.location.z}"],
                        "scale": [f"{obj.scale.x}", f"{obj.scale.y}", f"{obj.scale.z}"]
                    }
                    
                    # Handle rotation based on rotation mode
                    if obj.rotation_mode == 'QUATERNION':
                        quat = obj.rotation_quaternion
                        euler = quat.to_euler('XYZ')
                        transform["rotation"] = [f"{euler.x}", f"{euler.y}", f"{euler.z}"]
                    else:
                        transform["rotation"] = [f"{obj.rotation_euler.x}", f"{obj.rotation_euler.y}", f"{obj.rotation_euler.z}"]
                    
                    # Create RMSF node
                    rmsf_node = RepresentationModelSpecialFindNode(
                        node_id=item.node_id,
                        name=f"RMSF for {obj.name}",
                        type="RM",
                        transform=transform,
                        description=f"Representation model for SpecialFind {obj.name}"
                    )
                    
                    # Add node to graph
                    graph.add_node(rmsf_node)
            
            added_count += 1
        
        # Update list if objects added
        if added_count > 0:
            bpy.ops.anastylosis.update_list(from_graph=graph is not None)
            
        self.report({'INFO'}, f"Added {added_count} objects to anastylosis list")
        return {'FINISHED'}

# Settings for Anastylosis Manager
class AnastylisisSettings(PropertyGroup):
    zoom_to_selected: BoolProperty(
        name="Zoom to Selected",
        description="Zoom to the selected object when clicked in the list",
        default=True
    )
    
    show_settings: BoolProperty(
        name="Show Settings",
        description="Show or hide the settings section",
        default=False
    )

# Temporary item for SF node selection
class AnastylosisSFNodeItem(PropertyGroup):
    node_id: StringProperty(name="Node ID")
    name: StringProperty(name="Name")
    description: StringProperty(name="Description")

# Main Anastylosis Manager Panel
class VIEW3D_PT_Anastylosis_Manager(Panel):
    bl_label = "Anastylosis Manager"
    bl_idname = "VIEW3D_PT_Anastylosis_Manager"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'EM'
    bl_options = {'DEFAULT_CLOSED'}
        
    @classmethod
    def poll(cls, context):
        em_tools = context.scene.em_tools
        # Show only if we're in advanced EM mode
        return em_tools.mode_switch
    
    def draw(self, context):
        layout = self.layout
        scene = context.scene

        from .functions import is_graph_available
        
        # Check if a graph is available
        graph_available, graph = is_graph_available(context)

        # Update controls
        row = layout.row(align=True)
        row.operator("anastylosis.update_list", text="Update from Scene", icon='FILE_REFRESH').from_graph = False

        # Check if a graph is available
        if graph_available:
            row.operator("anastylosis.update_list", text="Update from Graph", icon='NODE_MATERIAL').from_graph = True

        # Main action buttons
        box = layout.box()
        box.label(text="Operations on selected objects:")
        row = box.row(align=True)
        row.operator("anastylosis.add_selected", icon='ADD')
        
        # List of anastylosis models
        row = layout.row()
        row.template_list(
            "ANASTYLOSIS_UL_List", "anastylosis_list",
            scene, "anastylosis_list",
            scene, "anastylosis_list_index"
        )
        
        # Show connection info if an item is selected
        if scene.anastylosis_list_index >= 0 and len(scene.anastylosis_list) > 0:
            item = scene.anastylosis_list[scene.anastylosis_list_index]
            
            if item.sf_node_id:
                box = layout.box()
                row = box.row()
                sf_icon = 'OUTLINER_OB_EMPTY' if item.is_virtual else 'MESH_ICOSPHERE'
                row.label(text=f"Connected to: {item.sf_node_name}", icon=sf_icon)
                
                # Add button to unlink
                #row = box.row()
                #op = row.operator("anastylosis.remove_from_list", text="Unlink from SpecialFind", icon='TRASH')
                #op.anastylosis_index = scene.anastylosis_list_index
            else:
                box = layout.box()
                row = box.row()
                row.label(text="Not connected to any SpecialFind", icon='INFO')
                
                #row = box.row()
                #op = row.operator("anastylosis.link_to_sf", text="Link to SpecialFind", icon='LINKED')
                #op.anastylosis_index = scene.anastylosis_list_index
                
        
        # Settings (collapsible)
        box = layout.box()
        row = box.row()
        row.prop(scene.anastylosis_settings, "show_settings", 
                icon="TRIA_DOWN" if scene.anastylosis_settings.show_settings else "TRIA_RIGHT",
                text="Settings", 
                emboss=False)
                
        if scene.anastylosis_settings.show_settings:
            row = box.row()
            row.prop(scene.anastylosis_settings, "zoom_to_selected")


# Handler to update list when a graph is loaded
@bpy.app.handlers.persistent
def update_anastylosis_list_on_graph_load(dummy):
    """Update anastylosis list when a graph is loaded"""
    
    # Ensure we're in a context where we can access scene
    if not bpy.context or not hasattr(bpy.context, 'scene'):
        return
        
    scene = bpy.context.scene
    
    # Check if graph is available
    if (hasattr(scene, 'em_tools') and 
        hasattr(scene.em_tools, 'graphml_files') and 
        len(scene.em_tools.graphml_files) > 0 and 
        scene.em_tools.active_file_index >= 0):
        
        try:
            # Run in a timer to ensure proper context
            bpy.app.timers.register(
                lambda: bpy.ops.anastylosis.update_list(from_graph=True), 
                first_interval=0.5
            )
        except Exception as e:
            print(f"Error updating anastylosis list on graph load: {e}")

# Registration classes
classes = [
    AnastylisisItem,
    ANASTYLOSIS_UL_List,
    ANASTYLOSIS_OT_update_list,
    ANASTYLOSIS_OT_link_to_sf,
    ANASTYLOSIS_OT_select_from_list,
    ANASTYLOSIS_OT_remove_from_list,
    ANASTYLOSIS_OT_add_selected,
    AnastylisisSettings,
    AnastylosisSFNodeItem,
    ANASTYLOSIS_OT_confirm_link,
    VIEW3D_PT_Anastylosis_Manager,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    
    # Register properties
    bpy.types.Scene.anastylosis_list = bpy.props.CollectionProperty(type=AnastylisisItem)
    bpy.types.Scene.anastylosis_list_index = bpy.props.IntProperty(name="Index for anastylosis list", default=0)
    bpy.types.Scene.anastylosis_settings = bpy.props.PointerProperty(type=AnastylisisSettings)
    
    # Temporary properties for SF node selection
    bpy.types.Scene.anastylosis_sf_nodes = bpy.props.CollectionProperty(type=AnastylosisSFNodeItem)
    bpy.types.Scene.anastylosis_temp_obj_name = bpy.props.StringProperty()
    bpy.types.Scene.anastylosis_temp_rmsf_id = bpy.props.StringProperty()
    
    # Register handler
    bpy.app.handlers.load_post.append(update_anastylosis_list_on_graph_load)

def unregister():
    # Remove handler
    if update_anastylosis_list_on_graph_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(update_anastylosis_list_on_graph_load)
    
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    
    # Remove properties
    del bpy.types.Scene.anastylosis_list
    del bpy.types.Scene.anastylosis_list_index
    del bpy.types.Scene.anastylosis_settings
    del bpy.types.Scene.anastylosis_sf_nodes
    del bpy.types.Scene.anastylosis_temp_obj_name
    del bpy.types.Scene.anastylosis_temp_rmsf_id
