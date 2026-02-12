import os as os
import bpy  # type: ignore
from bpy.props import (  # type: ignore
    BoolProperty,
    EnumProperty,
    IntProperty,
    StringProperty,
)
from bpy.types import Operator  # type: ignore
from bpy_extras.io_utils import ImportHelper  # type: ignore

from s3dgraphy import get_graph
from s3dgraphy.nodes.representation_node import RepresentationModelNode

# ✅ OPTIMIZED: Import object cache for O(1) lookups
from ..object_cache import get_object_cache

__all__ = [
    'RM_OT_detect_orphaned_epochs',
    'RM_OT_fix_orphaned_epoch',
    'RM_OT_select_orphaned_objects',
    'RM_OT_set_active_epoch',
    'RM_OT_select_all_from_active_epoch',
    'RM_OT_select_from_object',
    'RM_OT_add_tileset',
    'RM_OT_set_tileset_path',
    'RM_OT_demote_from_rm_list',
    'RM_OT_update_list',
    'RM_OT_resolve_mismatches',
    'RM_OT_show_mismatch_details',
    'RM_OT_promote_to_rm',
    'RM_OT_remove_epoch_from_rm_list',
    'RM_OT_remove_epoch_from_selected',
    'RM_OT_remove_epoch',
    'RM_OT_remove_from_epoch',
    'RM_OT_demote_from_rm',
    'RM_OT_select_from_list',
    'RM_OT_toggle_publishable',
    'RM_OT_add_epoch',
    'register_operators',
    'unregister_operators',
]


class RM_OT_detect_orphaned_epochs(Operator):
    bl_idname = "rm.detect_orphaned_epochs"
    bl_label = "Detect Orphaned Epochs"
    bl_description = "Detect and manage epochs that exist in objects but not in the current graph"

    def execute(self, context):
        scene = context.scene
        rm_settings = scene.rm_settings

        # Get all valid epochs from the scene
        valid_epochs = set()
        if hasattr(scene.em_tools, 'epochs') and len(scene.em_tools.epochs.list) > 0:
            for epoch in scene.em_tools.epochs.list:
                valid_epochs.add(epoch.name)

        # Find orphaned epochs
        orphaned_epochs = {}  # epoch_name -> list of object names

        for obj in bpy.data.objects:
            if hasattr(obj, "EM_ep_belong_ob") and len(obj.EM_ep_belong_ob) > 0:
                for ep in obj.EM_ep_belong_ob:
                    if ep.epoch != "no_epoch" and ep.epoch not in valid_epochs:
                        if ep.epoch not in orphaned_epochs:
                            orphaned_epochs[ep.epoch] = []
                        orphaned_epochs[ep.epoch].append(obj.name)

        if not orphaned_epochs:
            # Clear any existing orphaned epochs data
            rm_settings.orphaned_epochs.clear()
            rm_settings.has_orphaned_epochs = False
            self.report({'INFO'}, "No orphaned epochs found. All epochs are valid!")
            return {'FINISHED'}

        # Populate the orphaned epochs data structure
        rm_settings.orphaned_epochs.clear()
        for epoch_name, obj_names in orphaned_epochs.items():
            item = rm_settings.orphaned_epochs.add()
            item.orphaned_epoch_name = epoch_name
            item.object_count = len(obj_names)
            # Set default replacement to the first valid epoch if available
            if valid_epochs:
                item.replacement_epoch = sorted(valid_epochs)[0]

        rm_settings.has_orphaned_epochs = True

        self.report({'WARNING'}, f"Found {len(orphaned_epochs)} orphaned epoch(s). Review the mapping panel below.")

        return {'FINISHED'}


class RM_OT_fix_orphaned_epoch(Operator):
    bl_idname = "rm.fix_orphaned_epoch"
    bl_label = "Fix Orphaned Epoch"
    bl_description = "Replace or remove an orphaned epoch from all objects"

    orphaned_epoch_name: StringProperty(
        name="Orphaned Epoch",
        description="Name of the orphaned epoch to fix",
        default=""
    )  # type: ignore

    action: EnumProperty(
        name="Action",
        description="Action to perform on the orphaned epoch",
        items=[
            ('REPLACE', 'Replace with Valid Epoch', 'Replace with a valid epoch from the list'),
            ('REMOVE', 'Remove Epoch', 'Remove the orphaned epoch from all objects'),
        ],
        default='REPLACE'
    )  # type: ignore

    def get_epoch_items(self, context):
        """Generate enum items dynamically from available epochs"""
        items = []
        scene = context.scene
        if hasattr(scene.em_tools, 'epochs') and len(scene.em_tools.epochs.list) > 0:
            for i, epoch in enumerate(scene.em_tools.epochs.list):
                epoch_label = f"{epoch.name}"
                if hasattr(epoch, 'start_time') and hasattr(epoch, 'end_time'):
                    epoch_label += f" [{int(epoch.start_time)}-{int(epoch.end_time)}]"
                items.append((epoch.name, epoch_label, f"Replace with {epoch.name}"))

        if not items:
            items.append(('NONE', 'No Epochs Available', 'No valid epochs found'))

        return items

    replacement_epoch: EnumProperty(
        name="Replacement Epoch",
        description="Select the epoch to replace with",
        items=get_epoch_items
    )  # type: ignore

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=450)

    def draw(self, context):
        layout = self.layout
        layout.label(text=f"Fix orphaned epoch: '{self.orphaned_epoch_name}'", icon='ERROR')

        layout.separator()
        layout.prop(self, "action", expand=True)

        if self.action == 'REPLACE':
            layout.separator()
            layout.label(text="Select replacement epoch:")
            layout.prop(self, "replacement_epoch", text="")

    def execute(self, context):
        if self.action == 'REPLACE' and (not self.replacement_epoch or self.replacement_epoch == 'NONE'):
            self.report({'ERROR'}, "Please select a valid replacement epoch")
            return {'CANCELLED'}

        # Find all objects with the orphaned epoch
        affected_objects = []
        for obj in bpy.data.objects:
            if hasattr(obj, "EM_ep_belong_ob") and len(obj.EM_ep_belong_ob) > 0:
                for ep in obj.EM_ep_belong_ob:
                    if ep.epoch == self.orphaned_epoch_name:
                        affected_objects.append(obj)
                        break

        if not affected_objects:
            self.report({'WARNING'}, f"No objects found with epoch '{self.orphaned_epoch_name}'")
            return {'FINISHED'}

        # Get graph if available
        graph = None
        try:
            if context.scene.em_tools.active_file_index >= 0:
                graphml = context.scene.em_tools.graphml_files[context.scene.em_tools.active_file_index]
                graph = get_graph(graphml.name)
        except Exception as e:
            print(f"Warning: Could not retrieve graph: {e}")

        # Perform action
        for obj in affected_objects:
            if self.action == 'REPLACE':
                # Replace orphaned epoch with valid one
                for ep in obj.EM_ep_belong_ob:
                    if ep.epoch == self.orphaned_epoch_name:
                        ep.epoch = self.replacement_epoch

                # Update graph if available
                if graph:
                    try:
                        model_node_id = f"{obj.name}_model"

                        # Find the replacement epoch node
                        replacement_epoch_node = None
                        for node in graph.nodes:
                            if node.node_type == "EpochNode" and node.name == self.replacement_epoch:
                                replacement_epoch_node = node
                                break

                        if replacement_epoch_node:
                            # Remove old edges with orphaned epoch (if any exist)
                            edges_to_remove = []
                            for edge in graph.edges:
                                if edge.edge_source == model_node_id and edge.edge_type in ["has_first_epoch", "survive_in_epoch"]:
                                    edges_to_remove.append(edge.edge_id)

                            for edge_id in edges_to_remove:
                                try:
                                    graph.remove_edge(edge_id)
                                except:
                                    pass

                            # Add new edge
                            edge_id = f"{model_node_id}_has_first_epoch_{replacement_epoch_node.node_id}"
                            if not graph.find_edge_by_id(edge_id):
                                graph.add_edge(
                                    edge_id=edge_id,
                                    edge_source=model_node_id,
                                    edge_target=replacement_epoch_node.node_id,
                                    edge_type="has_first_epoch"
                                )
                    except Exception as e:
                        print(f"Warning: Could not update graph for {obj.name}: {e}")

            elif self.action == 'REMOVE':
                # Remove the orphaned epoch
                indices_to_remove = []
                for i, ep in enumerate(obj.EM_ep_belong_ob):
                    if ep.epoch == self.orphaned_epoch_name:
                        indices_to_remove.append(i)

                # Remove in reverse order
                for i in reversed(indices_to_remove):
                    obj.EM_ep_belong_ob.remove(i)

                # If no epochs left, add "no_epoch"
                if len(obj.EM_ep_belong_ob) == 0:
                    ep_item = obj.EM_ep_belong_ob.add()
                    ep_item.epoch = "no_epoch"

                # Update graph if available
                if graph:
                    try:
                        model_node_id = f"{obj.name}_model"

                        # Remove all edges (since we're removing the only epoch)
                        edges_to_remove = []
                        for edge in graph.edges:
                            if edge.edge_source == model_node_id and edge.edge_type in ["has_first_epoch", "survive_in_epoch"]:
                                edges_to_remove.append(edge.edge_id)

                        for edge_id in edges_to_remove:
                            try:
                                graph.remove_edge(edge_id)
                            except:
                                pass
                    except Exception as e:
                        print(f"Warning: Could not update graph for {obj.name}: {e}")

        # Update RM list
        bpy.ops.rm.update_list(from_graph=False)

        action_text = "replaced" if self.action == 'REPLACE' else "removed"
        self.report({'INFO'}, f"Orphaned epoch '{self.orphaned_epoch_name}' {action_text} from {len(affected_objects)} object(s)")
        return {'FINISHED'}


class RM_OT_select_orphaned_objects(Operator):
    bl_idname = "rm.select_orphaned_objects"
    bl_label = "Select Objects with Orphaned Epoch"
    bl_description = "Select all objects that have this orphaned epoch"

    orphaned_epoch_name: StringProperty(
        name="Orphaned Epoch",
        description="Name of the orphaned epoch",
        default=""
    )  # type: ignore

    def execute(self, context):
        # Deselect all
        bpy.ops.object.select_all(action='DESELECT')

        # Select objects with the orphaned epoch
        selected_count = 0
        for obj in bpy.data.objects:
            if hasattr(obj, "EM_ep_belong_ob") and len(obj.EM_ep_belong_ob) > 0:
                for ep in obj.EM_ep_belong_ob:
                    if ep.epoch == self.orphaned_epoch_name:
                        obj.select_set(True)
                        selected_count += 1
                        break

        # Set first as active
        if selected_count > 0:
            for obj in context.selected_objects:
                context.view_layer.objects.active = obj
                break

        self.report({'INFO'}, f"Selected {selected_count} object(s) with orphaned epoch '{self.orphaned_epoch_name}'")
        return {'FINISHED'}


class RM_OT_set_active_epoch(Operator):
    bl_idname = "rm.set_active_epoch"
    bl_label = "Set Active Epoch"
    bl_description = "Set the active epoch for RM management"

    epoch_index: IntProperty(
        name="Epoch Index",
        description="Index of the epoch to set as active",
        default=0
    )  # type: ignore

    def execute(self, context):
        scene = context.scene
        epochs = scene.em_tools.epochs

        # Validate index
        if self.epoch_index < 0 or self.epoch_index >= len(epochs.list):
            self.report({'ERROR'}, "Invalid epoch index")
            return {'CANCELLED'}

        # Set the active epoch
        epochs.list_index = self.epoch_index
        epoch = epochs.list[self.epoch_index]

        self.report({'INFO'}, f"Active epoch set to: {epoch.name}")
        return {'FINISHED'}


class RM_OT_select_all_from_active_epoch(Operator):
    bl_idname = "rm.select_all_from_active_epoch"
    bl_label = "Select All from Active Epoch"
    bl_description = "Select all RM objects in the 3D view that belong to the currently active epoch"

    def execute(self, context):
        scene = context.scene
        epochs = scene.em_tools.epochs

        # Check if there's an active epoch
        if epochs.list_index < 0 or epochs.list_index >= len(epochs.list):
            self.report({'ERROR'}, "No active epoch selected")
            return {'CANCELLED'}

        active_epoch = epochs.list[epochs.list_index]

        # Deselect all objects first
        bpy.ops.object.select_all(action='DESELECT')

        # Count selected objects
        selected_count = 0

        # Iterate through all objects in the scene
        for obj in bpy.data.objects:
            # Check if object has epoch properties
            if hasattr(obj, "EM_ep_belong_ob") and len(obj.EM_ep_belong_ob) > 0:
                # Check if the active epoch is in this object's epochs
                for ep in obj.EM_ep_belong_ob:
                    if ep.epoch == active_epoch.name:
                        # Select this object
                        obj.select_set(True)
                        selected_count += 1
                        break

        # Set the first selected object as active if any were selected
        if selected_count > 0:
            for obj in context.selected_objects:
                context.view_layer.objects.active = obj
                break

            self.report({'INFO'}, f"Selected {selected_count} object(s) from epoch '{active_epoch.name}'")
            return {'FINISHED'}
        else:
            self.report({'WARNING'}, f"No objects found for epoch '{active_epoch.name}'")
            return {'FINISHED'}

class RM_OT_select_from_object(Operator):
    bl_idname = "rm.select_from_object"
    bl_label = "Select RM List Item"
    bl_description = "Select the corresponding row in the RM list for the active object"
    
    def execute(self, context):
        active_obj = context.active_object
        if not active_obj:
            self.report({'ERROR'}, "No active object selected")
            return {'CANCELLED'}
        
        # Find the item in the RM list with the matching name
        scene = context.scene
        rm_list = scene.rm_list
        found = False
        
        for i, item in enumerate(rm_list):
            if item.name == active_obj.name:
                scene.rm_list_index = i
                found = True
                self.report({'INFO'}, f"Selected RM list item for {active_obj.name}")
                break
        
        if not found:
            # Try adding the object to the list if it has epochs
            if hasattr(active_obj, "EM_ep_belong_ob") and len(active_obj.EM_ep_belong_ob) > 0:
                # Update the list first to make sure all objects are included
                bpy.ops.rm.update_list(from_graph=False)
                
                # Try finding it again
                for i, item in enumerate(rm_list):
                    if item.name == active_obj.name:
                        scene.rm_list_index = i
                        found = True
                        self.report({'INFO'}, f"Added and selected RM list item for {active_obj.name}")
                        break
            
            if not found:
                self.report({'WARNING'}, f"Object {active_obj.name} not found in RM list. Try adding it to an epoch first.")
        
        return {'FINISHED'}

class RM_OT_add_tileset(Operator):
    bl_idname = "rm.add_tileset"
    bl_label = "Add Cesium Tileset"
    bl_description = "Add an empty Cesium tileset object to the current epoch"
    
    tileset_name: StringProperty(
        name="Tileset Name",
        description="Name of the tileset object",
        default="Tileset"
    ) # type: ignore
    
    tileset_path: StringProperty(
        name="Tileset Path",
        description="Path to the Cesium tileset zip file (relative or absolute)",
        default="",
        subtype='FILE_PATH',
        options={'PATH_SUPPORTS_BLEND_RELATIVE'} if bpy.app.version >= (4, 5, 0) else set()
    ) # type: ignore
    
    def invoke(self, context, event):
        # Open a dialog to get the tileset name and path
        return context.window_manager.invoke_props_dialog(self)
    
    def draw(self, dialog):
        layout = self.layout
        layout.prop(self, "tileset_name")
        layout.prop(self, "tileset_path")
    
    def execute(self, context):
        scene = context.scene
        epochs = scene.em_tools.epochs
        
        # Check if an epoch is selected
        if epochs.list_index < 0 or epochs.list_index >= len(epochs.list):
            self.report({'ERROR'}, "No active epoch selected")
            return {'CANCELLED'}
        
        active_epoch = epochs.list[epochs.list_index]
        
        # Create an empty object
        bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, 0))
        obj = context.object
        
        # Ensure the name is unique
        base_name = self.tileset_name
        if not base_name:
            base_name = "Tileset"
            
        # Find a unique name by adding a number if needed
        index = 1
        obj_name = base_name
        while obj_name in bpy.data.objects:
            obj_name = f"{base_name}_{index}"
            index += 1
            
        obj.name = obj_name
        
        # Add the tileset_path custom property
        obj["tileset_path"] = self.tileset_path
        
        # Add it to the current epoch
        ep_item = obj.EM_ep_belong_ob.add()
        ep_item.epoch = active_epoch.name
        
        # Update the RM list
        bpy.ops.rm.update_list(from_graph=True)
        
        # Update the graph if available
        graph = None
        if context.scene.em_tools.active_file_index >= 0:
            graphml = context.scene.em_tools.graphml_files[context.scene.em_tools.active_file_index]
            graph = get_graph(graphml.name)
            
            if graph:
                # Create a RM node in the graph
                from s3dgraphy.nodes.representation_node import RepresentationModelNode

                # Ottieni il nome base del tileset senza estensione
                tileset_filename = os.path.basename(self.tileset_path)
                tileset_name = os.path.splitext(tileset_filename)[0]
                model_node_id = f"{obj.name}_model"

                model_node = RepresentationModelNode(
                    node_id=model_node_id,
                    name=f"Model for {obj.name}",
                    type="RM"
                )

                # Set url after initialization
                model_node.url = f"tilesets/{tileset_name}/tileset.json"

                # Add tileset marker attribute
                model_node.attributes['is_tileset'] = True
                model_node.attributes['tileset_path'] = self.tileset_path
                model_node.attributes['is_publishable'] = True
                
                # Add the node to the graph
                graph.add_node(model_node)
                
                # Find the epoch node
                epoch_node = None
                for node in graph.nodes:
                    if node.node_type == "EpochNode" and node.name == active_epoch.name:
                        epoch_node = node
                        break
                
                if epoch_node:
                    # Add the edge connecting the model to the epoch
                    edge_id = f"{model_node_id}_has_first_epoch_{epoch_node.node_id}"
                    if not graph.find_edge_by_id(edge_id):
                        graph.add_edge(
                            edge_id=edge_id,
                            edge_source=model_node_id,
                            edge_target=epoch_node.node_id,
                            edge_type="has_first_epoch"
                        )
        
        # Find and select the item in the RM list
        for i, item in enumerate(scene.rm_list):
            if item.name == obj.name:
                scene.rm_list_index = i
                break
        
        self.report({'INFO'}, f"Added tileset '{obj.name}' to epoch '{active_epoch.name}'")
        return {'FINISHED'}

class RM_OT_set_tileset_path(Operator, ImportHelper):
    bl_idname = "rm.set_tileset_path"
    bl_label = "Set Tileset Path"
    bl_description = "Set the path to the Cesium tileset zip file"
    
    filter_glob: StringProperty(
        default="*.zip",
        options={'HIDDEN'}
    ) # type: ignore
    
    object_name: StringProperty(
        name="Object Name",
        description="Name of the object to update",
        default=""
    ) # type: ignore
    
    def execute(self, context):
        obj = get_object_cache().get_object(self.object_name)
        if not obj:
            self.report({'ERROR'}, f"Object {self.object_name} not found")
            return {'CANCELLED'}
        
        # Converti automaticamente in percorso relativo (come fa Blender)
        tileset_path = bpy.path.relpath(self.filepath)
        
        # Update the tileset_path property
        obj["tileset_path"] = tileset_path
        
        # Update the url in the graph if available
        try:
            graph = None
            if context.scene.em_tools.active_file_index >= 0:
                graphml = context.scene.em_tools.graphml_files[context.scene.em_tools.active_file_index]
                graph = get_graph(graphml.name)
                
                if graph:
                    model_node_id = f"{obj.name}_model"
                    model_node = graph.find_node_by_id(model_node_id)
                    
                    if model_node:
                        model_node.url = f"tilesets/{os.path.basename(self.filepath)}"
                        model_node.attributes['tileset_path'] = tileset_path
                        print(f"Updated tileset path in graph node: {model_node.node_id}")
        except Exception as e:
            print(f"Error updating graph node: {e}")
        
        self.report({'INFO'}, f"Updated tileset path: {tileset_path}")
        return {'FINISHED'}

class RM_OT_demote_from_rm_list(Operator):
    bl_idname = "rm.demote_from_rm_list"
    bl_label = "Demote RM"
    bl_description = "Remove this object from all epochs and the graph"
    
    rm_index: IntProperty(
        name="RM Index",
        description="Index of the RM item in the list",
        default=-1
    ) # type: ignore
    
    def execute(self, context):
        scene = context.scene
        
        # Check if we have a valid index
        if self.rm_index < 0 or self.rm_index >= len(scene.rm_list):
            self.report({'ERROR'}, "Invalid RM index")
            return {'CANCELLED'}
            
        # Get the RM item and the corresponding object
        rm_item = scene.rm_list[self.rm_index]
        obj = get_object_cache().get_object(rm_item.name)
        
        if not obj:
            self.report({'ERROR'}, f"Object {rm_item.name} not found in scene")
            return {'CANCELLED'}
            
        # First select the object to make it visible in the viewport
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        context.view_layer.objects.active = obj
        
        # Make sure we can see the object (unhide if hidden)
        was_hidden = obj.hide_viewport
        if was_hidden:
            obj.hide_viewport = False
            
        # Get the graph
        graph = None
        if context.scene.em_tools.active_file_index >= 0:
            graphml = context.scene.em_tools.graphml_files[context.scene.em_tools.active_file_index]
            from s3dgraphy import get_graph
            graph = get_graph(graphml.name)
            
        # Remove all epochs from the object
        while len(obj.EM_ep_belong_ob) > 0:
            obj.EM_ep_belong_ob.remove(0)
            
        # Remove from graph if available
        if graph:
            model_node_id = f"{obj.name}_model"
            model_node = graph.find_node_by_id(model_node_id)
            
            if model_node:
                # Find and remove all edges associated with the node
                edges_to_remove = []
                for edge in graph.edges:
                    if edge.edge_source == model_node_id or edge.edge_target == model_node_id:
                        edges_to_remove.append(edge.edge_id)
                
                # Remove the edges
                for edge_id in edges_to_remove:
                    graph.remove_edge(edge_id)
                
                # Remove the node
                graph.remove_node(model_node_id)
                
        # Remove from the list
        scene.rm_list.remove(self.rm_index)
        
        # Update the list index if needed
        if scene.rm_list_index >= len(scene.rm_list):
            scene.rm_list_index = max(0, len(scene.rm_list) - 1)
        
        # Restore visibility state
        obj.hide_viewport = was_hidden
        
        self.report({'INFO'}, f"Removed {obj.name} from RM models")
        return {'FINISHED'}

class RM_OT_update_list(Operator):
    bl_idname = "rm.update_list"
    bl_label = "Update RM List"
    bl_description = "Synchronize the RM list. Use 'from Scene' if you manually changed object properties, or 'from Graph' after importing/modifying the GraphML file."
    
    from_graph: BoolProperty(
        name="Update from Graph",
        description="Update the list using graph data. If False, uses only scene objects.",
        default=True
    ) # type: ignore
    
    def execute(self, context):
        try:
            scene = context.scene
            rm_list = scene.rm_list
            
            # Salva l'indice corrente per ripristinarlo dopo l'aggiornamento
            current_index = scene.rm_list_index
            
            # Dizionario per tracciare gli oggetti già presenti nella lista
            existing_objects = {}
            for i, item in enumerate(rm_list):
                if hasattr(item, 'name'):
                    existing_objects[item.name] = {
                        "index": i,
                        "epochs": [epoch.name for epoch in item.epochs] if hasattr(item, 'epochs') else [],
                        "is_publishable": item.is_publishable if hasattr(item, 'is_publishable') else True
                    }
            
            # Ottieni il grafo attivo se stiamo aggiornando dal grafo
            graph = None
            if self.from_graph and hasattr(context.scene, 'em_tools'):
                if (hasattr(context.scene.em_tools, 'graphml_files') and
                    len(context.scene.em_tools.graphml_files) > 0 and
                    context.scene.em_tools.active_file_index >= 0):
                    
                    graphml = context.scene.em_tools.graphml_files[context.scene.em_tools.active_file_index]
                    from s3dgraphy import get_graph
                    graph = get_graph(graphml.name)
            
            # Crea dizionario per ordinare le epoche per tempo di inizio
            epoch_start_times = {}
            if graph:
                for node in graph.nodes:
                    if node.node_type == "EpochNode":
                        epoch_start_times[node.name] = getattr(node, 'start_time', float('inf'))
            else:
                # Se non abbiamo il grafo, usa le epoche dalla scena
                for epoch in scene.em_tools.epochs.list:
                    epoch_start_times[epoch.name] = epoch.start_time
            
            # Se non stiamo usando il grafo o non è disponibile, usiamo gli oggetti di scena
            scene_objects = [obj for obj in bpy.data.objects if 
                            (obj.type == 'MESH' or "tileset_path" in obj) and 
                            hasattr(obj, "EM_ep_belong_ob") and 
                            len(obj.EM_ep_belong_ob) > 0]
            
            processed_objects = set()
            
            for obj in scene_objects:
                processed_objects.add(obj.name)
                
                # Ottieni le epoche dell'oggetto, escludendo "no_epoch"
                scene_epochs = [ep.epoch for ep in obj.EM_ep_belong_ob if ep.epoch != "no_epoch"]
                
                # Se non ci sono epoche, passa al prossimo oggetto
                if not scene_epochs:
                    continue
                
                # Determine if this is a tileset object
                is_tileset = "tileset_path" in obj
                
                # Se l'oggetto è già nella lista, aggiorna
                if obj.name in existing_objects:
                    item_index = existing_objects[obj.name]["index"]
                    item = rm_list[item_index]
                    
                    # Pulisci le epoche precedenti
                    while len(item.epochs) > 0:
                        item.epochs.remove(0)
                    
                    # Ordina le epoche per tempo di inizio
                    ordered_epochs = []
                    for epoch_name in scene_epochs:
                        start_time = epoch_start_times.get(epoch_name, float('inf'))
                        ordered_epochs.append({
                            "name": epoch_name,
                            "start_time": start_time
                        })
                    
                    # Ordina per tempo di inizio
                    ordered_epochs.sort(key=lambda x: x['start_time'])
                    
                    # Aggiungi le epoche all'item
                    for i, epoch_data in enumerate(ordered_epochs):
                        epoch_item = item.epochs.add()
                        epoch_item.name = epoch_data['name']
                        # La prima epoca è quella con il tempo di inizio più basso
                        epoch_item.is_first_epoch = (i == 0)
                    
                    # Aggiorna la prima epoch
                    if len(item.epochs) > 0:
                        item.first_epoch = item.epochs[0].name
                    else:
                        item.first_epoch = "no_epoch"
                    
                    # Debug print
                    #print(f"Prima epoch aggiornata: {item.first_epoch}")
                
                else:
                    # Crea un nuovo elemento per l'oggetto
                    item = rm_list.add()
                    item.name = obj.name
                    item.node_id = f"{obj.name}_model"
                    item.object_exists = True
                    
                    # Ordina le epoche per tempo di inizio
                    ordered_epochs = []
                    for epoch_name in scene_epochs:
                        start_time = epoch_start_times.get(epoch_name, float('inf'))
                        ordered_epochs.append({
                            "name": epoch_name,
                            "start_time": start_time
                        })
                    
                    # Ordina per tempo di inizio
                    ordered_epochs.sort(key=lambda x: x['start_time'])
                    
                    # Aggiungi le epoche all'item
                    for i, epoch_data in enumerate(ordered_epochs):
                        epoch_item = item.epochs.add()
                        epoch_item.name = epoch_data['name']
                        # La prima epoca è quella con il tempo di inizio più basso
                        epoch_item.is_first_epoch = (i == 0)
                    
                    # Imposta la prima epoch
                    if len(item.epochs) > 0:
                        item.first_epoch = item.epochs[0].name
                    else:
                        item.first_epoch = "no_epoch"
                    
                    # Verifica pubblicabilità dal grafo
                    if graph:
                        rm_node = graph.find_node_by_id(item.node_id)
                        if rm_node and hasattr(rm_node, 'attributes'):
                            item.is_publishable = rm_node.attributes.get('is_publishable', True)
                        else:
                            item.is_publishable = True
                            
                    # For tileset objects, make sure they're always publishable by default
                    if is_tileset:
                        item.is_publishable = True
            
            # Rimuovi gli oggetti non più presenti
            for i in range(len(rm_list) - 1, -1, -1):
                if rm_list[i].name not in processed_objects:
                    rm_list.remove(i)
            
            # Gestisci l'aggiornamento dal grafo
            if self.from_graph and graph:
                rm_nodes = [node for node in graph.nodes if node.node_type == "representation_model"]
                
                for node in rm_nodes:
                    # Estrai il nome dell'oggetto dal node_id
                    obj_name = node.name.replace("Model for ", "").strip()
                    
                    # Verifica se l'oggetto esiste nella scena
                    obj_exists = obj_name in bpy.data.objects
                    
                    # Trova o crea l'elemento nella lista
                    existing_item = None
                    for item in rm_list:
                        if item.name == obj_name:
                            existing_item = item
                            break
                    
                    # Se l'oggetto non esiste nella lista, crealo
                    if not existing_item:
                        new_item = rm_list.add()
                        new_item.name = obj_name
                        new_item.node_id = node.node_id
                        new_item.object_exists = obj_exists
                        
                        # Imposta la pubblicabilità 
                        new_item.is_publishable = node.attributes.get('is_publishable', True)
                        
                        # Trova le epoche associate
                        associated_epochs = []
                        for edge in graph.edges:
                            if edge.edge_source == node.node_id and edge.edge_type in ["has_first_epoch", "has_representation_model", "survive_in_epoch"]:
                                epoch_node = graph.find_node_by_id(edge.edge_target)
                                if epoch_node and epoch_node.node_type == "EpochNode":
                                    associated_epochs.append({
                                        "name": epoch_node.name,
                                        "node": epoch_node,
                                        "start_time": getattr(epoch_node, 'start_time', float('inf')),
                                        "edge_type": edge.edge_type
                                    })
                        
                        # Ordina le epoche
                        associated_epochs.sort(key=lambda x: x['start_time'])
                        
                        # Aggiungi le epoche all'item
                        for i, epoch_data in enumerate(associated_epochs):
                            epoch_item = new_item.epochs.add()
                            epoch_item.name = epoch_data['name']
                            epoch_item.is_first_epoch = (epoch_data['edge_type'] == "has_first_epoch" or i == 0)
                        
                        # Imposta la prima epoch
                        if associated_epochs:
                            new_item.first_epoch = associated_epochs[0]['name']
                        else:
                            new_item.first_epoch = "no_epoch"
            
            # Ripristina l'indice se possibile
            scene.rm_list_index = min(current_index, len(rm_list)-1) if rm_list else 0
            
            # Report
            if self.from_graph:
                self.report({'INFO'}, f"Updated RM list from graph: {len(rm_list)} models")
            else:
                self.report({'INFO'}, f"Updated RM list from scene objects: {len(rm_list)} models")
            
            return {'FINISHED'}
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.report({'ERROR'}, f"Error updating RM list: {str(e)}")
            return {'CANCELLED'}

class RM_OT_resolve_mismatches(Operator):
    bl_idname = "rm.resolve_mismatches"
    bl_label = "Resolve Epoch Mismatches"
    bl_description = "Resolve mismatches between scene objects and graph epochs"
    
    use_graph_epochs: BoolProperty(
        name="Use Graph Epochs",
        description="If True, use epochs from graph. If False, use epochs from scene objects",
        default=True
    ) # type: ignore
    
    def execute(self, context):
        scene = context.scene
        rm_list = scene.rm_list
        
        # Ottieni il grafo attivo
        graph = None
        if context.scene.em_tools.active_file_index >= 0:
            graphml = context.scene.em_tools.graphml_files[context.scene.em_tools.active_file_index]
            graph = get_graph(graphml.name)
        
        if not graph and self.use_graph_epochs:
            self.report({'ERROR'}, "No active graph available")
            return {'CANCELLED'}
        
        resolved_count = 0
        
        # Itera su tutti gli elementi della lista
        for i, item in enumerate(rm_list):
            if item.epoch_mismatch:
                obj = get_object_cache().get_object(item.name)
                if not obj:
                    continue
                
                if self.use_graph_epochs:
                    # Usa le epoche dal grafo
                    # Rimuovi tutte le epoche dall'oggetto tranne no_epoch
                    j = 0
                    while j < len(obj.EM_ep_belong_ob):
                        if obj.EM_ep_belong_ob[j].epoch != "no_epoch":
                            obj.EM_ep_belong_ob.remove(j)
                        else:
                            j += 1
                    
                    # Aggiungi le epoche dalla lista RM
                    for epoch_item in item.epochs:
                        ep_item = obj.EM_ep_belong_ob.add()
                        ep_item.epoch = epoch_item.name
                else:
                    # Usa le epoche dall'oggetto
                    obj_epochs = [ep.epoch for ep in obj.EM_ep_belong_ob if ep.epoch != "no_epoch"]
                    
                    # Aggiorna il grafo con le epoche dell'oggetto
                    model_node_id = f"{obj.name}_model"
                    model_node = graph.find_node_by_id(model_node_id)
                    
                    if model_node:
                        # Rimuovi tutti gli edge esistenti
                        edges_to_remove = []
                        for edge in graph.edges:
                            if edge.edge_source == model_node_id and edge.edge_type == "has_representation_model":
                                edges_to_remove.append(edge.edge_id)
                        
                        # Rimuovi gli edge
                        for edge_id in edges_to_remove:
                            graph.remove_edge(edge_id)
                        
                        # Aggiungi i nuovi edge
                        for epoch_name in obj_epochs:
                            epoch_node = None
                            for node in graph.nodes:
                                if node.node_type == "EpochNode" and node.name == epoch_name:
                                    epoch_node = node
                                    break
                            
                            if epoch_node:
                                edge_id = f"{epoch_node.node_id}_has_representation_model_{model_node_id}"
                                if not graph.find_edge_by_id(edge_id):
                                    graph.add_edge(
                                        edge_id=edge_id,
                                        #edge_source=model_node_id,
                                        #edge_target=epoch_node.node_id,
                                        edge_source=epoch_node.node_id,
                                        edge_target=model_node_id,
                                        edge_type="has_representation_model"
                                    )
                
                # Marca come risolto
                item.epoch_mismatch = False
                resolved_count += 1
        
        # Aggiorna la lista RM
        bpy.ops.rm.update_list(from_graph=self.use_graph_epochs)
        
        action = "graph" if self.use_graph_epochs else "scene objects"
        self.report({'INFO'}, f"Resolved {resolved_count} mismatches using epochs from {action}")
        return {'FINISHED'}

class RM_OT_show_mismatch_details(Operator):
    bl_idname = "rm.show_mismatch_details"
    bl_label = "Show Mismatch Details"
    bl_description = "Show details about epoch mismatches for selected object"
    
    def execute(self, context):
        scene = context.scene
        
        if scene.rm_list_index < 0 or not scene.rm_list:
            self.report({'ERROR'}, "No RM model selected")
            return {'CANCELLED'}
        
        item = scene.rm_list[scene.rm_list_index]
        
        if not item.epoch_mismatch:
            self.report({'INFO'}, "No mismatch detected for this object")
            return {'FINISHED'}
        
        obj = get_object_cache().get_object(item.name)
        if not obj:
            self.report({'ERROR'}, "Object not found in scene")
            return {'CANCELLED'}
        
        # Get epochs from object
        obj_epochs = [ep.epoch for ep in obj.EM_ep_belong_ob if ep.epoch != "no_epoch"]
        
        # Get epochs from RM list
        list_epochs = [ep.name for ep in item.epochs]
        
        # Find differences
        obj_only = set(obj_epochs) - set(list_epochs)
        list_only = set(list_epochs) - set(obj_epochs)
        
        # Show dialog with details
        def draw(self, context):
            layout = self.layout
            layout.label(text=f"Mismatch details for {item.name}:")
            
            box = layout.box()
            box.label(text="Epochs in object but not in graph:")
            if obj_only:
                for epoch in sorted(obj_only):
                    box.label(text=f"- {epoch}")
            else:
                box.label(text="None")
            
            box = layout.box()
            box.label(text="Epochs in graph but not in object:")
            if list_only:
                for epoch in sorted(list_only):
                    box.label(text=f"- {epoch}")
            else:
                box.label(text="None")
        
        bpy.context.window_manager.popup_menu(draw, title="Epoch Mismatch Details", icon='INFO')
        
        return {'FINISHED'}

class RM_OT_promote_to_rm(Operator):
    bl_idname = "rm.promote_to_rm"
    bl_label = "Add to Active Epoch"
    bl_description = "Add selected objects to the currently active epoch. Objects can belong to multiple epochs."
    
    mode: EnumProperty(
        name="Mode",
        description="Method of adding objects to epoch",
        items=[
            ('SELECTED', 'Selected Objects', 'Add all selected objects to the epoch'),
            ('RM_LIST', 'RM List Object', 'Add the object from RM list to the epoch')
        ],
        default='SELECTED'
    ) # type: ignore
    
    def execute(self, context):
        scene = context.scene
        
        # Determina gli oggetti da processare
        if self.mode == 'RM_LIST':
            # Usa l'oggetto dalla lista RM
            if scene.rm_list_index < 0 or not scene.rm_list:
                self.report({'ERROR'}, "No RM model selected")
                return {'CANCELLED'}
            rm_item = scene.rm_list[scene.rm_list_index]
            obj = get_object_cache().get_object(rm_item.name)
            if not obj:
                self.report({'ERROR'}, f"Object not found in scene: {rm_item.name}")
                return {'CANCELLED'}
            selected_objects = [obj]
        else:
            selected_objects = []

            for obj in context.selected_objects:
                if obj.type == 'MESH' or obj.type == 'CURVE' or (obj.type == 'EMPTY' and obj.instance_type != 'COLLECTION'):
                    selected_objects.append(obj)
                elif obj.type == 'EMPTY' and obj.instance_type == 'COLLECTION' and obj.instance_collection:
                    # Aggiungi tutti gli oggetti mesh della collezione istanziata
                    for child in obj.instance_collection.objects:
                        if child.type == 'MESH':
                            selected_objects.append(child)

            if not selected_objects:
                self.report({'ERROR'}, "No mesh objects or valid collections selected")
                return {'CANCELLED'}

        epochs = scene.em_tools.epochs
        # Verifica che ci sia un'epoca attiva
        if epochs.list_index < 0 or not epochs.list:
            self.report({'ERROR'}, "No active epoch")
            return {'CANCELLED'}
        
        active_epoch = epochs.list[epochs.list_index]
        
        # Ottieni il grafo attivo (opzionale)
        graph = None
        try:
            if context.scene.em_tools.active_file_index >= 0:
                graphml = context.scene.em_tools.graphml_files[context.scene.em_tools.active_file_index]
                graph = get_graph(graphml.name)
        except Exception as e:
            print(f"Warning: Could not retrieve graph: {e}")
            graph = None
        
        # Processa ogni oggetto
        for obj in selected_objects:
            # Trova le epoche esistenti dell'oggetto
            existing_epochs = [ep.epoch for ep in obj.EM_ep_belong_ob if ep.epoch != "no_epoch"]
            
            # Filtra le epoche esistenti per evitare duplicati
            filtered_epochs = list(set(existing_epochs))
            
            # Ordina le epoche 
            sorted_epochs = filtered_epochs.copy()
            
            # Aggiungi l'epoch attiva nell'ordine corretto
            if active_epoch.name not in sorted_epochs:
                sorted_epochs.append(active_epoch.name)
            
            # Rimuovi "no_epoch" se presente
            if "no_epoch" in sorted_epochs:
                sorted_epochs.remove("no_epoch")
            
            # Aggiorna gli EP_belong_ob dell'oggetto
            obj.EM_ep_belong_ob.clear()
            for epoch_name in sorted_epochs:
                ep_item = obj.EM_ep_belong_ob.add()
                ep_item.epoch = epoch_name
            
            # Aggiorna il grafo se disponibile (opzionale)
            if graph:
                try:
                    model_node_id = f"{obj.name}_model"
                    
                    # Rimuovi vecchi edge
                    edges_to_remove = []
                    for edge in graph.edges:
                        if edge.edge_source == model_node_id and edge.edge_type in ["has_first_epoch", "has_representation_model", "survive_in_epoch"]:
                            edges_to_remove.append(edge.edge_id)
                    
                    for edge_id in edges_to_remove:
                        graph.remove_edge(edge_id)
                    
                    # Aggiungi nuovi edge
                    for i, epoch_name in enumerate(sorted_epochs):
                        epoch_node = None
                        for node in graph.nodes:
                            if node.node_type == "EpochNode" and node.name == epoch_name:
                                epoch_node = node
                                break
                        
                        if epoch_node:
                            edge_type = "has_first_epoch" if i == 0 else "survive_in_epoch"
                            if edge_type == "has_first_epoch":
                                edge_id = f"{model_node_id}_has_first_epoch_{epoch_node.node_id}"
                            else:
                                edge_id = f"{model_node_id}_survive_in_epoch_{epoch_node.node_id}"    
                            graph.add_edge(
                                edge_id=edge_id,
                                edge_source=model_node_id,
                                edge_target=epoch_node.node_id,
                                edge_type=edge_type
                            )
                except Exception as e:
                    print(f"Warning: Could not update graph: {e}")
        
        # Aggiorna la lista RM
        bpy.ops.rm.update_list(from_graph=True)
        
        self.report({'INFO'}, f"Added epoch '{active_epoch.name}' to {len(selected_objects)} object(s)")
        return {'FINISHED'}

class RM_OT_remove_epoch_from_rm_list(Operator):
    bl_idname = "rm.remove_epoch_from_rm_list"
    bl_label = "Remove Epoch"
    bl_description = "Remove the epoch from the RM list item"
    
    def execute(self, context):
        scene = context.scene
        
        # Verifica che ci sia un RM selezionato
        if scene.rm_list_index < 0 or scene.rm_list_index >= len(scene.rm_list):
            self.report({'ERROR'}, "No RM model selected")
            return {'CANCELLED'}
        
        # Ottieni l'item RM corrente
        rm_item = scene.rm_list[scene.rm_list_index]
        
        # Verifica che ci sia un'epoch selezionata
        if rm_item.active_epoch_index < 0 or rm_item.active_epoch_index >= len(rm_item.epochs):
            self.report({'ERROR'}, "No epoch selected")
            return {'CANCELLED'}
        
        # Ottieni l'epoch da rimuovere
        epoch_to_remove = rm_item.epochs[rm_item.active_epoch_index]
        epoch_name = epoch_to_remove.name
        
        # Ottieni il grafo attivo (opzionale)
        graph = None
        try:
            if context.scene.em_tools.active_file_index >= 0:
                graphml = context.scene.em_tools.graphml_files[context.scene.em_tools.active_file_index]
                graph = get_graph(graphml.name)
        except Exception as e:
            print(f"Warning: Could not retrieve graph: {e}")
            graph = None
        
        # Trova l'oggetto Blender
        obj = get_object_cache().get_object(rm_item.name)
        if not obj:
            self.report({'ERROR'}, f"Object not found in scene: {rm_item.name}")
            return {'CANCELLED'}
        
        # Rimuovi l'epoch dall'oggetto
        epochs_to_remove = []
        for i, ep in enumerate(obj.EM_ep_belong_ob):
            if ep.epoch == epoch_name:
                epochs_to_remove.append(i)
        
        # Rimuovi le epoche in ordine inverso
        for i in reversed(epochs_to_remove):
            obj.EM_ep_belong_ob.remove(i)
        
        # Se non ci sono più epoche, aggiungi "no_epoch"
        if len(obj.EM_ep_belong_ob) == 0:
            ep_item = obj.EM_ep_belong_ob.add()
            ep_item.epoch = "no_epoch"
        
        # Rimuovi l'epoch dalla lista RM
        rm_item.epochs.remove(rm_item.active_epoch_index)
        
        # Aggiorna l'indice se necessario
        if rm_item.active_epoch_index >= len(rm_item.epochs):
            rm_item.active_epoch_index = max(0, len(rm_item.epochs) - 1)
        
        # Aggiorna la prima epoch
        if len(rm_item.epochs) > 0:
            for i, epoch_item in enumerate(rm_item.epochs):
                epoch_item.is_first_epoch = (i == 0)
            rm_item.first_epoch = rm_item.epochs[0].name
        else:
            rm_item.first_epoch = "no_epoch"
        
        # Aggiorna il grafo se disponibile
        if graph:
            try:
                model_node_id = f"{obj.name}_model"
                
                # Rimuovi gli edge per quest'epoch
                edges_to_remove = []
                for edge in graph.edges:
                    if (edge.edge_source == model_node_id and 
                        edge.edge_type in ["has_first_epoch", "has_representation_model", "survive_in_epoch"]):
                        epoch_node = graph.find_node_by_id(edge.edge_target)
                        if epoch_node and epoch_node.name == epoch_name:
                            edges_to_remove.append(edge.edge_id)
                
                for edge_id in edges_to_remove:
                    graph.remove_edge(edge_id)
            except Exception as e:
                print(f"Warning: Could not update graph: {e}")
        
        # Aggiorna la lista RM
        bpy.ops.rm.update_list(from_graph=True)
        
        self.report({'INFO'}, f"Removed epoch '{epoch_name}' from {rm_item.name}")
        return {'FINISHED'}

class RM_OT_remove_epoch_from_selected(Operator):
    bl_idname = "rm.remove_epoch_from_selected"
    bl_label = "Remove from Active Epoch"
    bl_description = "Remove the currently active epoch from selected objects. Objects remain in other epochs."
    
    def execute(self, context):
        scene = context.scene
        epochs = scene.em_tools.epochs
        
        # Verifica che ci sia un'epoch attiva
        if epochs.list_index < 0 or not epochs.list:
            self.report({'ERROR'}, "No active epoch")
            return {'CANCELLED'}
        
        active_epoch = epochs.list[epochs.list_index]
        
        # Ottieni gli oggetti selezionati
        selected_objects = [obj for obj in context.selected_objects if obj.type == 'MESH' or obj.type == 'EMPTY']
        
        if not selected_objects:
            self.report({'ERROR'}, "No mesh objects selected")
            return {'CANCELLED'}
        
        # Ottieni il grafo attivo (opzionale)
        graph = None
        try:
            if context.scene.em_tools.active_file_index >= 0:
                graphml = context.scene.em_tools.graphml_files[context.scene.em_tools.active_file_index]
                graph = get_graph(graphml.name)
        except Exception as e:
            print(f"Warning: Could not retrieve graph: {e}")
            graph = None
        
        # Numero di oggetti modificati
        modified_count = 0
        
        for obj in selected_objects:
            # Trova le epoche esistenti dell'oggetto
            existing_epochs = [ep.epoch for ep in obj.EM_ep_belong_ob if ep.epoch != "no_epoch"]
            
            # Rimuovi l'epoch attiva se presente
            if active_epoch.name in existing_epochs:
                # Rimuovi l'epoch
                epochs_to_remove = []
                for i, ep in enumerate(obj.EM_ep_belong_ob):
                    if ep.epoch == active_epoch.name:
                        epochs_to_remove.append(i)
                
                # Rimuovi le epoche in ordine inverso
                for i in reversed(epochs_to_remove):
                    obj.EM_ep_belong_ob.remove(i)
                    modified_count += 1
            
            # Se non ci sono più epoche, aggiungi "no_epoch"
            if len(obj.EM_ep_belong_ob) == 0:
                ep_item = obj.EM_ep_belong_ob.add()
                ep_item.epoch = "no_epoch"
            
            # Aggiorna il grafo se disponibile
            if graph:
                try:
                    model_node_id = f"{obj.name}_model"
                    
                    # Rimuovi gli edge per quest'epoch
                    edges_to_remove = []
                    for edge in graph.edges:
                        if (edge.edge_source == model_node_id and 
                            edge.edge_type in ["has_first_epoch", "has_representation_model", "survive_in_epoch"]):
                            epoch_node = graph.find_node_by_id(edge.edge_target)
                            if epoch_node and epoch_node.name == active_epoch.name:
                                edges_to_remove.append(edge.edge_id)
                    
                    for edge_id in edges_to_remove:
                        graph.remove_edge(edge_id)
                except Exception as e:
                    print(f"Warning: Could not update graph: {e}")
        
        # Aggiorna la lista RM
        bpy.ops.rm.update_list(from_graph=True)
        
        self.report({'INFO'}, f"Removed epoch '{active_epoch.name}' from {modified_count} object(s)")
        return {'FINISHED'}

class RM_OT_remove_epoch(Operator):
    bl_idname = "rm.remove_epoch"
    bl_label = "Remove Epoch"
    bl_description = "Remove the epoch association from this RM model"
    
    epoch_name: StringProperty() # type: ignore
    rm_index: IntProperty(
        name="RM Index",
        description="Index of the RM item in the list",
        default=-1
    ) # type: ignore
    remove_from_selected: BoolProperty(
        name="Remove from Selected Objects",
        description="If True, remove epoch from selected objects instead of from RM list",
        default=False
    ) # type: ignore
    
    def execute(self, context):
        scene = context.scene
        
        if self.remove_from_selected:
            # Rimuovi dall'oggetto selezionato in scena
            selected_objects = [obj for obj in context.selected_objects if obj.type == 'MESH']
            
            if not selected_objects:
                self.report({'ERROR'}, "No mesh objects selected")
                return {'CANCELLED'}
            
            # Numero di oggetti modificati
            modified_count = 0
            
            for obj in selected_objects:
                # Rimuovi l'epoch se presente
                epochs_to_remove = []
                for i, ep in enumerate(obj.EM_ep_belong_ob):
                    if ep.epoch == self.epoch_name:
                        epochs_to_remove.append(i)
                
                # Rimuovi le epoche in ordine inverso
                for i in reversed(epochs_to_remove):
                    obj.EM_ep_belong_ob.remove(i)
                    modified_count += 1
                
                # Se non ci sono più epoche, aggiungi "no_epoch"
                if len(obj.EM_ep_belong_ob) == 0:
                    ep_item = obj.EM_ep_belong_ob.add()
                    ep_item.epoch = "no_epoch"
            
            # Aggiorna la lista RM
            bpy.ops.rm.update_list(from_graph=True)
            
            self.report({'INFO'}, f"Removed epoch '{self.epoch_name}' from {modified_count} object(s)")
            return {'FINISHED'}
        
        else:
            # Rimuovi dalla lista RM
            if self.rm_index < 0:
                self.rm_index = scene.rm_list_index
            
            if self.rm_index < 0 or self.rm_index >= len(scene.rm_list):
                self.report({'ERROR'}, "No RM item selected")
                return {'CANCELLED'}
            
            rm_item = scene.rm_list[self.rm_index]
            
            # Ottieni il grafo attivo (opzionale)
            graph = None
            try:
                if context.scene.em_tools.active_file_index >= 0:
                    graphml = context.scene.em_tools.graphml_files[context.scene.em_tools.active_file_index]
                    graph = get_graph(graphml.name)
            except Exception as e:
                print(f"Warning: Could not retrieve graph: {e}")
                graph = None
            
            # Trova l'oggetto Blender
            obj = get_object_cache().get_object(rm_item.name)
            if not obj:
                self.report({'ERROR'}, f"Object not found in scene: {rm_item.name}")
                return {'CANCELLED'}
            
            # Rimuovi l'epoch
            epochs_to_remove = []
            for i, ep in enumerate(obj.EM_ep_belong_ob):
                if ep.epoch == self.epoch_name:
                    epochs_to_remove.append(i)
            
            # Rimuovi le epoche in ordine inverso
            for i in reversed(epochs_to_remove):
                obj.EM_ep_belong_ob.remove(i)
            
            # Se non ci sono più epoche, aggiungi "no_epoch"
            if len(obj.EM_ep_belong_ob) == 0:
                ep_item = obj.EM_ep_belong_ob.add()
                ep_item.epoch = "no_epoch"
            
            # Aggiorna il grafo se disponibile
            if graph:
                try:
                    model_node_id = f"{obj.name}_model"
                    
                    # Rimuovi gli edge per quest'epoch
                    edges_to_remove = []
                    for edge in graph.edges:
                        if (edge.edge_source == model_node_id and 
                            edge.edge_type in ["has_first_epoch", "has_representation_model", "survive_in_epoch"]):
                            epoch_node = graph.find_node_by_id(edge.edge_target)
                            if epoch_node and epoch_node.name == self.epoch_name:
                                edges_to_remove.append(edge.edge_id)
                    
                    for edge_id in edges_to_remove:
                        graph.remove_edge(edge_id)
                except Exception as e:
                    print(f"Warning: Could not update graph: {e}")
            
            # Aggiorna la lista RM
            bpy.ops.rm.update_list(from_graph=True)
            
            self.report({'INFO'}, f"Removed epoch '{self.epoch_name}' from {rm_item.name}")
            return {'FINISHED'}

class RM_OT_remove_from_epoch(Operator):
    bl_idname = "rm.remove_from_epoch"
    bl_label = "Remove from Active Epoch"
    bl_description = "Remove the selected RM model from the active epoch"
    
    rm_index: IntProperty(
        name="RM Index",
        description="Index of the RM item in the list",
        default=-1
    ) # type: ignore
    
    def execute(self, context):
        scene = context.scene
        epochs = scene.em_tools.epochs
        
        # Usa l'indice fornito se valido, altrimenti l'indice selezionato nella lista
        index = self.rm_index if self.rm_index >= 0 else scene.rm_list_index
        
        # Verifica che ci sia un elemento RM selezionato
        if index < 0 or index >= len(scene.rm_list):
            self.report({'ERROR'}, "No RM model selected")
            return {'CANCELLED'}
        
        # Verifica che ci sia un'epoca attiva
        if epochs.list_index < 0 or not epochs.list:
            self.report({'ERROR'}, "No active epoch")
            return {'CANCELLED'}
        
        # Ottiene l'elemento RM e l'epoca attiva
        rm_item = scene.rm_list[index]
        active_epoch = epochs.list[epochs.list_index]
        
        # Ottieni il grafo attivo
        graph = None
        if context.scene.em_tools.active_file_index >= 0:
            graphml = context.scene.em_tools.graphml_files[context.scene.em_tools.active_file_index]
            graph = get_graph(graphml.name)
        
        # Trova l'oggetto Blender
        obj = get_object_cache().get_object(rm_item.name)
        if not obj:
            self.report({'ERROR'}, f"Object not found in scene: {rm_item.name}")
            return {'CANCELLED'}
        
        # Rimuovi l'epoca dall'oggetto
        epochs_removed = False
        for i in range(len(obj.EM_ep_belong_ob) - 1, -1, -1):
            if obj.EM_ep_belong_ob[i].epoch == active_epoch.name:
                obj.EM_ep_belong_ob.remove(i)
                epochs_removed = True
        
        # Se non ci sono più epoche, aggiungi "no_epoch"
        if len(obj.EM_ep_belong_ob) == 0:
            no_epoch_item = obj.EM_ep_belong_ob.add()
            no_epoch_item.epoch = "no_epoch"
        
        # Gestisci il grafo se disponibile
        if graph:
            # Identificativo del nodo RM
            model_node_id = f"{obj.name}_model"
            rm_node = graph.find_node_by_id(model_node_id)
            
            if rm_node:
                # Trova e rimuovi gli edge con l'epoca attiva
                edges_to_remove = []
                for edge in graph.edges:
                    if (edge.edge_source == model_node_id and 
                        edge.edge_type in ["has_first_epoch", "has_representation_model", "survive_in_epoch"]):
                        # Trova il nodo dell'epoca
                        epoch_node = graph.find_node_by_id(edge.edge_target)
                        if epoch_node and epoch_node.name == active_epoch.name:
                            edges_to_remove.append(edge.edge_id)
                
                # Rimuovi gli edge
                for edge_id in edges_to_remove:
                    graph.remove_edge(edge_id)
        
        # Aggiorna la lista RM
        # Rimuovi l'epoch dalla lista delle epoche dell'item
        for i in range(len(rm_item.epochs) - 1, -1, -1):
            if rm_item.epochs[i].name == active_epoch.name:
                rm_item.epochs.remove(i)
        
        # Se non ci sono più epoche, imposta a "no_epoch"
        if len(rm_item.epochs) == 0:
            rm_item.first_epoch = "no_epoch"
        else:
            # Rivaluta la prima epoch
            for i, epoch_item in enumerate(rm_item.epochs):
                epoch_item.is_first_epoch = (i == 0)
            rm_item.first_epoch = rm_item.epochs[0].name
        
        # Aggiorna la lista RM
        bpy.ops.rm.update_list(from_graph=graph is not None)
        
        # Messaggio di successo
        if epochs_removed:
            self.report({'INFO'}, f"Removed epoch '{active_epoch.name}' from {rm_item.name}")
            return {'FINISHED'}
        else:
            self.report({'WARNING'}, f"No epoch '{active_epoch.name}' found for {rm_item.name}")
            return {'FINISHED'}

class RM_OT_demote_from_rm(Operator):
    bl_idname = "rm.demote_from_rm"
    bl_label = "Remove from ALL Epochs"
    bl_description = "DANGER: Remove selected objects completely from ALL epochs and the graph."
    
    def execute(self, context):
        scene = context.scene
        selected_objects = [obj for obj in context.selected_objects if obj.type == 'MESH' or obj.type == 'EMPTY']
        
        if not selected_objects:
            self.report({'ERROR'}, "No mesh objects selected")
            return {'CANCELLED'}
        
        # Ottieni il grafo attivo
        graph = None
        if context.scene.em_tools.active_file_index >= 0:
            graphml = context.scene.em_tools.graphml_files[context.scene.em_tools.active_file_index]
            graph = get_graph(graphml.name)
        
        # Conta quanti oggetti sono stati rimossi
        removed_count = 0

        # Rimuovi gli elementi dalla lista RM prima
        objects_to_remove = [obj.name for obj in selected_objects]
        for i in range(len(scene.rm_list) - 1, -1, -1):
            if scene.rm_list[i].name in objects_to_remove:
                scene.rm_list.remove(i)


        for obj in selected_objects:
            # Rimuovi tutte le epoche dall'oggetto
            while len(obj.EM_ep_belong_ob) > 0:
                obj.EM_ep_belong_ob.remove(0)
            
            # Aggiungi "no_epoch"
            #ep_item = obj.EM_ep_belong_ob.add()
            #ep_item.epoch = "no_epoch"
            
            removed_count += 1
            
            # Se il grafo è disponibile, rimuovi anche il nodo e gli edge dal grafo
            if graph:
                model_node_id = f"{obj.name}_model"
                model_node = graph.find_node_by_id(model_node_id)
                
                if model_node:
                    # Trova e rimuovi tutti gli edge associati al nodo
                    edges_to_remove = []
                    for edge in graph.edges:
                        if edge.edge_source == model_node_id or edge.edge_target == model_node_id:
                            edges_to_remove.append(edge.edge_id)
                    
                    # Rimuovi gli edge
                    for edge_id in edges_to_remove:
                        graph.remove_edge(edge_id)
                    
                    # Rimuovi il nodo
                    graph.remove_node(model_node_id)
        
        # Aggiorna la lista RM
        #bpy.ops.rm.update_list(from_graph=graph is not None)

        # Aggiorna l'indice della lista RM se necessario
        if scene.rm_list_index >= len(scene.rm_list):
            scene.rm_list_index = max(0, len(scene.rm_list) - 1)


        self.report({'INFO'}, f"Demoted {removed_count} objects from RM models")
        return {'FINISHED'}

class RM_OT_select_from_list(Operator):
    bl_idname = "rm.select_from_list"
    bl_label = "Select RM Object"
    bl_description = "Select the RM object in the 3D view"
    
    rm_index: IntProperty(
        name="RM Index",
        description="Index of the RM item in the list",
        default=-1
    ) # type: ignore
    
    def execute(self, context):
        try:
            scene = context.scene
            
            # Use provided index if valid, otherwise the selected index in the list
            index = self.rm_index if self.rm_index >= 0 else scene.rm_list_index
            
            # Verify we have a valid index
            if index >= 0 and index < len(scene.rm_list):
                item = scene.rm_list[index]
                
                # Deselect all objects
                bpy.ops.object.select_all(action='DESELECT')
                
                # If the object exists, select it
                obj = get_object_cache().get_object(item.name)
                if obj:
                    # ✅ Make object visible
                    if obj.hide_viewport:
                        obj.hide_viewport = False
                    if obj.hide_get():
                        obj.hide_set(False)

                    # ✅ Make object selectable
                    if obj.hide_select:
                        obj.hide_select = False

                    # ✅ Activate all parent collections
                    from ..stratigraphy_manager.operators import activate_collection_fully
                    for collection in obj.users_collection:
                        activate_collection_fully(context, collection)

                    obj.select_set(True)
                    # Set as active object
                    context.view_layer.objects.active = obj
                    
                    # Zoom to object if the option is enabled
                    if hasattr(scene, 'rm_settings') and scene.rm_settings.zoom_to_selected:
                        # Find a 3D view area
                        win = context.window
                        scr = win.screen if win else None
                        if scr:
                            for area in scr.areas:
                                if area.type == 'VIEW_3D':
                                    region = next((r for r in area.regions if r.type == 'WINDOW'), None)
                                    space = area.spaces.active if hasattr(area, "spaces") else None
                                    if region:
                                        # ✅ Blender 4.5+ context override syntax
                                        with context.temp_override(
                                            window=win,
                                            screen=scr,
                                            area=area,
                                            region=region,
                                            space_data=space,
                                            scene=scene,
                                            view_layer=context.view_layer
                                        ):
                                            bpy.ops.view3d.view_selected()
                                    break
                    
                    self.report({'INFO'}, f"Selected object: {item.name}")
                    return {'FINISHED'}
                else:
                    self.report({'ERROR'}, f"Object not found in scene: {item.name}")
                    return {'CANCELLED'}
            
            self.report({'ERROR'}, "No item selected in the list")
            return {'CANCELLED'}
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.report({'ERROR'}, f"Error selecting object: {str(e)}")
            return {'CANCELLED'}

class RM_OT_toggle_publishable(Operator):
    bl_idname = "rm.toggle_publishable"
    bl_label = "Toggle Publishable"
    bl_description = "Toggle the publishable status of the selected RM model"
    
    rm_index: IntProperty(
        name="RM Index",
        description="Index of the RM item in the list",
        default=-1
    ) # type: ignore
    
    def execute(self, context):
        scene = context.scene
        epochs = scene.em_tools.epochs
        
        # Usa l'indice fornito se valido, altrimenti l'indice selezionato nella lista
        index = self.rm_index if self.rm_index >= 0 else scene.rm_list_index
        
        if index >= 0 and index < len(scene.rm_list):
            item = scene.rm_list[index]
            item.is_publishable = not item.is_publishable
            
            # Aggiorna l'attributo nel nodo RM del grafo se necessario
            graph = None
            if context.scene.em_tools.active_file_index >= 0:
                graphml = context.scene.em_tools.graphml_files[context.scene.em_tools.active_file_index]
                graph = get_graph(graphml.name)
            
            if graph:
                rm_node = graph.find_node_by_id(item.node_id)
                if rm_node:
                    # Aggiorna l'attributo del nodo
                    rm_node.attributes['is_publishable'] = item.is_publishable
            
            self.report({'INFO'}, f"Set {item.name} publishable status to {item.is_publishable}")
            return {'FINISHED'}
        
        self.report({'ERROR'}, "No item selected in the list")
        return {'CANCELLED'}

class RM_OT_add_epoch(Operator):
    bl_idname = "rm.add_epoch"
    bl_label = "Add Epoch"
    bl_description = "Add the currently active epoch to this RM model"
    
    rm_index: IntProperty(
        name="RM Index",
        description="Index of the RM item in the list",
        default=-1
    ) # type: ignore
    
    def execute(self, context):
        scene = context.scene
        
        # Usa l'indice fornito se valido, altrimenti l'indice selezionato nella lista
        index = self.rm_index if self.rm_index >= 0 else scene.rm_list_index
        
        # Verifica che ci sia un RM selezionato
        if index < 0 or index >= len(scene.rm_list):
            self.report({'ERROR'}, "No RM model selected")
            return {'CANCELLED'}
        
        # Verifica che ci sia un'epoca attiva
        if epochs.list_index < 0 or not epochs.list:
            self.report({'ERROR'}, "No active epoch")
            return {'CANCELLED'}
        
        rm_item = scene.rm_list[index]
        active_epoch = epochs.list[epochs.list_index]
        
        # Ottieni il grafo attivo
        graph = None
        if context.scene.em_tools.active_file_index >= 0:
            graphml = context.scene.em_tools.graphml_files[context.scene.em_tools.active_file_index]
            graph = get_graph(graphml.name)
        
        if not graph:
            self.report({'ERROR'}, "No active graph available")
            return {'CANCELLED'}
        
        # Trova l'oggetto Blender
        obj = get_object_cache().get_object(rm_item.name)
        if not obj:
            self.report({'ERROR'}, f"Object not found in scene: {rm_item.name}")
            return {'CANCELLED'}
        
        # Verifica se l'epoca è già associata
        for ep in obj.EM_ep_belong_ob:
            if ep.epoch == active_epoch.name:
                self.report({'WARNING'}, f"Epoch '{active_epoch.name}' already associated")
                return {'CANCELLED'}
        
        # Trova il nodo RM e il nodo epoca nel grafo
        rm_node = graph.find_node_by_id(rm_item.node_id)
        if not rm_node:
            self.report({'ERROR'}, f"RM node not found in graph: {rm_item.node_id}")
            return {'CANCELLED'}
        
        epoch_node = None
        for node in graph.nodes:
            if node.node_type == "EpochNode" and node.name == active_epoch.name:
                epoch_node = node
                break
        
        if not epoch_node:
            self.report({'ERROR'}, f"Epoch node not found in graph: {active_epoch.name}")
            return {'CANCELLED'}
        
        # Rimuovi "no_epoch" se presente
        for i, ep in enumerate(obj.EM_ep_belong_ob):
            if ep.epoch == "no_epoch":
                obj.EM_ep_belong_ob.remove(i)
                break
        
        # Aggiungi l'epoca all'oggetto
        ep_item = obj.EM_ep_belong_ob.add()
        ep_item.epoch = active_epoch.name
        
        # Crea un edge nel grafo
        edge_id = f"{epoch_node.node_id}_has_representation_model_{rm_item.node_id}"
        if not graph.find_edge_by_id(edge_id):
            graph.add_edge(
                edge_id=edge_id,
                #edge_source=rm_item.node_id,
                #edge_target=epoch_node.node_id,
                edge_source=epoch_node.node_id,
                edge_target=rm_item.node_id,
                edge_type="has_representation_model"
            )
        
        # Aggiorna la lista
        bpy.ops.rm.update_list()

        self.report({'INFO'}, f"Added epoch '{active_epoch.name}' to {rm_item.name}")
        return {'FINISHED'}


class RM_OT_refresh_orphaned_epochs(Operator):
    bl_idname = "rm.refresh_orphaned_epochs"
    bl_label = "Refresh Orphaned Epochs"
    bl_description = "Re-detect orphaned epochs"

    def execute(self, context):
        # Simply call the detect operator
        bpy.ops.rm.detect_orphaned_epochs()
        return {'FINISHED'}


class RM_OT_clear_orphaned_epochs(Operator):
    bl_idname = "rm.clear_orphaned_epochs"
    bl_label = "Clear Orphaned Epochs"
    bl_description = "Clear the orphaned epochs panel"

    def execute(self, context):
        scene = context.scene
        rm_settings = scene.rm_settings

        rm_settings.orphaned_epochs.clear()
        rm_settings.has_orphaned_epochs = False

        self.report({'INFO'}, "Orphaned epochs panel cleared")
        return {'FINISHED'}


class RM_OT_apply_epoch_mapping(Operator):
    bl_idname = "rm.apply_epoch_mapping"
    bl_label = "Apply Epoch Mapping"
    bl_description = "Apply the selected epoch mappings to all affected objects"

    def execute(self, context):
        scene = context.scene
        rm_settings = scene.rm_settings

        if not rm_settings.has_orphaned_epochs or len(rm_settings.orphaned_epochs) == 0:
            self.report({'ERROR'}, "No orphaned epochs to map")
            return {'CANCELLED'}

        # Check if graph is available
        graph = None
        if hasattr(scene, 'EMGraphData') and scene.EMGraphData.graph_loaded:
            graph = scene.EMGraphData

        # Build mapping dictionary
        mapping = {}  # orphaned_epoch_name -> replacement_epoch_name
        for orphaned_item in rm_settings.orphaned_epochs:
            if orphaned_item.replacement_epoch and orphaned_item.replacement_epoch != 'NONE':
                mapping[orphaned_item.orphaned_epoch_name] = orphaned_item.replacement_epoch

        if not mapping:
            self.report({'ERROR'}, "No valid mappings selected")
            return {'CANCELLED'}

        # Apply mappings to all objects
        total_objects_updated = 0
        edges_to_remove = []

        for obj in bpy.data.objects:
            if hasattr(obj, "EM_ep_belong_ob") and len(obj.EM_ep_belong_ob) > 0:
                for ep in obj.EM_ep_belong_ob:
                    if ep.epoch in mapping:
                        old_epoch = ep.epoch
                        new_epoch = mapping[old_epoch]
                        ep.epoch = new_epoch
                        total_objects_updated += 1

                        # Update graph edges if graph is available
                        if graph:
                            model_node_id = f"{obj.name}_model"

                            # Find replacement epoch node
                            replacement_epoch_node = None
                            for node in graph.nodes:
                                if node.node_type == "EpochNode" and node.name == new_epoch:
                                    replacement_epoch_node = node
                                    break

                            if replacement_epoch_node:
                                # Remove old edges
                                for edge in graph.edges:
                                    if edge.edge_source == model_node_id and edge.edge_type in ["has_first_epoch", "survive_in_epoch"]:
                                        if edge.edge_id not in edges_to_remove:
                                            edges_to_remove.append(edge.edge_id)

                                # Add new edge
                                edge_id = f"{model_node_id}_has_first_epoch_{replacement_epoch_node.node_id}"
                                # Check if edge already exists
                                edge_exists = False
                                for edge in graph.edges:
                                    if edge.edge_id == edge_id:
                                        edge_exists = True
                                        break

                                if not edge_exists:
                                    graph.add_edge(
                                        edge_id=edge_id,
                                        edge_source=model_node_id,
                                        edge_target=replacement_epoch_node.node_id,
                                        edge_type="has_first_epoch"
                                    )

        # Remove old edges from graph
        if graph:
            for edge_id in edges_to_remove:
                graph.remove_edge(edge_id)

        # Clear orphaned epochs data
        rm_settings.orphaned_epochs.clear()
        rm_settings.has_orphaned_epochs = False

        # Update RM list
        bpy.ops.rm.update_list(from_graph=False)

        self.report({'INFO'}, f"Applied mapping to {total_objects_updated} object(s)")
        return {'FINISHED'}


classes = [
    RM_OT_detect_orphaned_epochs,
    RM_OT_refresh_orphaned_epochs,
    RM_OT_clear_orphaned_epochs,
    RM_OT_apply_epoch_mapping,
    RM_OT_fix_orphaned_epoch,
    RM_OT_select_orphaned_objects,
    RM_OT_set_active_epoch,
    RM_OT_select_all_from_active_epoch,
    RM_OT_select_from_object,
    RM_OT_add_tileset,
    RM_OT_set_tileset_path,
    RM_OT_demote_from_rm_list,
    RM_OT_update_list,
    RM_OT_resolve_mismatches,
    RM_OT_show_mismatch_details,
    RM_OT_promote_to_rm,
    RM_OT_remove_epoch_from_rm_list,
    RM_OT_remove_epoch_from_selected,
    RM_OT_remove_epoch,
    RM_OT_remove_from_epoch,
    RM_OT_demote_from_rm,
    RM_OT_select_from_list,
    RM_OT_toggle_publishable,
    RM_OT_add_epoch,
]


def _register_class_once(cls):
    try:
        bpy.utils.register_class(cls)
    except ValueError:
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
        bpy.utils.register_class(cls)


def register_operators():
    for cls in classes:
        _register_class_once(cls)


def unregister_operators():
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
