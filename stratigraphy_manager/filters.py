"""
Filter system for stratigraphic units
This module contains the central filtering logic for the Stratigraphy Manager,
providing a consistent way to filter stratigraphic units based on multiple criteria.
"""

import bpy
from bpy.props import BoolProperty
from bpy.types import Operator

from ..functions import is_reconstruction_us
from .data import ensure_valid_index
from ..populate_lists import populate_stratigraphic_node, EM_list_clear

class EM_filter_lists(Operator):
    bl_idname = "em.filter_lists"
    bl_label = "Filter Lists"
    bl_description = "Apply filters to stratigraphy list"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        scene = context.scene
        em_tools = scene.em_tools
        
        # Check if there's an active graph
        from ..functions import is_graph_available as check_graph
        graph_exists, graph = check_graph(context)

        if not graph_exists:
            self.report({'WARNING'}, "No active graph found. Please load a GraphML file first.")
            return {'CANCELLED'}
        
        # Temporary list to store all filtered elements
        filtered_items = []
        
        # Get stratigraphic nodes from the graph
        strat_nodes = [node for node in graph.nodes if hasattr(node, 'node_type') and 
                      node.node_type in ['US', 'USVs', 'USVn', 'VSF', 'SF', 'USD', 'serSU', 'serUSVn', 'serUSVs']]
        
        # Debug: Print active epoch
        active_epoch_name = None
        if scene.filter_by_epoch and scene.epoch_list_index >= 0 and len(scene.epoch_list) > 0:
            active_epoch_name = scene.epoch_list[scene.epoch_list_index].name
            print(f"Active epoch: {active_epoch_name}")
        
        # Debug: Print active activity
        active_activity_name = None  
        if scene.filter_by_activity and scene.activity_manager.active_index >= 0 and len(scene.activity_manager.activities) > 0:
            active_activity_name = scene.activity_manager.activities[scene.activity_manager.active_index].name
            print(f"Active activity: {active_activity_name}")
        
        for node in strat_nodes:
            print(f"\nEvaluating node: {node.name} (UUID: {node.node_id})")
            include_node = True
            
            # Apply epoch filter if active
            if scene.filter_by_epoch and active_epoch_name:
                include_node = False 

                # Find edges connecting this node to epochs
                created_in_epoch = False
                survives_in_epoch = False
                
                # Find all epochs connected to this node
                connected_epochs = []
                
                # Search directly by node ID in edges
                for edge in graph.edges:
                    if edge.edge_source == node.node_id:
                        target_node = graph.find_node_by_id(edge.edge_target)
                        
                        if target_node and hasattr(target_node, 'node_type') and target_node.node_type == "epoch":
                            if edge.edge_type == "has_first_epoch":
                                connected_epochs.append({"name": target_node.name, "type": "created"})
                                if target_node.name == active_epoch_name:
                                    created_in_epoch = True
                                    print(f"  Node was created in active epoch: {active_epoch_name}")
                                    
                            elif edge.edge_type == "survive_in_epoch":
                                connected_epochs.append({"name": target_node.name, "type": "survives"})
                                if target_node.name == active_epoch_name:
                                    survives_in_epoch = True
                                    print(f"  Node survives in active epoch: {active_epoch_name}")
                
                # Debug: show all epochs connected to this node
                if connected_epochs:
                    print(f"  Connected epochs: {connected_epochs}")
                else:
                    print(f"  No epochs connected to this node")
                
                # Include the node if it was created in this epoch or survives in this epoch (when option is enabled)
                include_node = created_in_epoch or (survives_in_epoch and scene.include_surviving_units)
                
                if include_node:
                    print(f"  Node INCLUDED for epoch filter")
                else:
                    print(f"  Node EXCLUDED for epoch filter")
            
            # Apply activity filter if active and if the node is still included
            if scene.filter_by_activity and include_node and active_activity_name:
                in_activity = False
                
                # Look for connections with the active activity
                for edge in graph.edges:
                    if edge.edge_source == node.node_id and edge.edge_type == "is_in_activity":
                        activity_node = graph.find_node_by_id(edge.edge_target)
                        if activity_node and hasattr(activity_node, 'name') and activity_node.name == active_activity_name:
                            in_activity = True
                            print(f"  Node is in active activity: {active_activity_name}")
                            break
                
                include_node = in_activity
                
                if include_node:
                    print(f"  Node INCLUDED for activity filter")
                else:
                    print(f"  Node EXCLUDED for activity filter")
            
            # Apply reconstruction filter if the node is a reconstruction unit
            if include_node and is_reconstruction_us(node):
                include_node = scene.show_reconstruction_units
                if include_node:
                    print(f"  Reconstruction node INCLUDED")
                else:
                    print(f"  Reconstruction node EXCLUDED")
            
            # If the node passes all filters, add it to the list
            if include_node:
                filtered_items.append(node)
                print(f"  FINAL RESULT: Node {node.name} INCLUDED in filtered list")
            else:
                print(f"  FINAL RESULT: Node {node.name} EXCLUDED from filtered list")
        
        # Update the em_list with filtered elements
        # Save the currently selected element (if present)
        current_selected = None
        if scene.em_list_index >= 0 and scene.em_list_index < len(scene.em_list):
            try:
                current_selected = scene.em_list[scene.em_list_index].name
                print(f"Current selection: {current_selected}")
            except IndexError:
                print(f"IndexError: index {scene.em_list_index} out of range for list with {len(scene.em_list)} items")
                current_selected = None
        
        # Clear the current list
        EM_list_clear(context, "em_list")
        
        # Rebuild the list with filtered elements
        print(f"\nPopulating em_list with {len(filtered_items)} filtered items")
        for i, node in enumerate(filtered_items):
            # Use the existing function to populate the list
            populate_stratigraphic_node(scene, node, i, graph)
          
        
        # IMPORTANT: Reset the index safely
        if len(scene.em_list) == 0:
            scene.em_list_index = -1
            self.report({'INFO'}, "No items match the current filters")
        else:
            # First set to 0, then try to restore the selection
            scene.em_list_index = 0
            
            # Restore the selection if possible
            if current_selected:
                for i, item in enumerate(scene.em_list):
                    if item.name == current_selected:
                        scene.em_list_index = i
                        print(f"Restored selection to index {i}: {item.name}")
                        break
        
        # If visibility sync is active, update the visibility of objects
        if scene.sync_list_visibility:
            bpy.ops.em.strat_sync_visibility()
        
        return {'FINISHED'}

class EM_reset_filters(Operator):
    bl_idname = "em.reset_filters"
    bl_label = "Reset Filters"
    bl_description = "Reset all filters and reload the complete list"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        scene = context.scene
        
        # Important: remember the current state of filters
        previous_epoch_filter = scene.filter_by_epoch
        previous_activity_filter = scene.filter_by_activity
        
        # Temporarily disable update callback
        # by setting a flag that will be checked in callbacks
        if hasattr(filter_list_update, "is_running"):
            filter_list_update.is_running = True
        
        try:
            # Disable filters without triggering new updates
            scene.filter_by_epoch = False
            scene.filter_by_activity = False
            
            # Reload ONLY the em_list, not other lists!
            em_tools = scene.em_tools
            if em_tools.active_file_index >= 0:
                graphml = em_tools.graphml_files[em_tools.active_file_index]
                from ..functions import get_graph
                graph = get_graph(graphml.name)
                
                if graph:
                    # Clear ONLY the em_list
                    EM_list_clear(context, "em_list")
                    
                    # Extract only stratigraphic nodes from the graph
                    strat_nodes = [node for node in graph.nodes if hasattr(node, 'node_type') and 
                                  node.node_type in ['US', 'USVs', 'USVn', 'VSF', 'SF', 'USD', 'serSU', 'serUSVn', 'serUSVs']]
                    
                    # Repopulate ONLY the em_list
                    for i, node in enumerate(strat_nodes):
                        populate_stratigraphic_node(scene, node, i, graph)
                    
                    # Ensure the index is valid
                    if len(scene.em_list) > 0:
                        scene.em_list_index = 0
                    else:
                        scene.em_list_index = -1
                    
                    self.report({'INFO'}, "Filters reset, showing all items")
                else:
                    self.report({'WARNING'}, "No active graph found")
        finally:
            # Restore the possibility of updates
            if hasattr(filter_list_update, "is_running"):
                filter_list_update.is_running = False
        
        return {'FINISHED'}

class EM_toggle_include_surviving(Operator):
    bl_idname = "em.toggle_include_surviving"
    bl_label = "Toggle Include Surviving Units"
    bl_description = "Toggle whether to include units that survive in the current epoch"
    bl_options = {"REGISTER", "UNDO"}
    
    def execute(self, context):
        scene = context.scene
        # Invert the current value
        scene.include_surviving_units = not scene.include_surviving_units
        
        print(f"Toggled include_surviving_units to: {scene.include_surviving_units}")
        
        # Call the filter update function
        if scene.filter_by_epoch:
            bpy.ops.em.filter_lists()
        
        return {'FINISHED'}

class EM_toggle_show_reconstruction(Operator):
    bl_idname = "em.toggle_show_reconstruction"
    bl_label = "Toggle Show Reconstruction"
    bl_description = "Toggle showing reconstruction units"
    bl_options = {"REGISTER", "UNDO"}
    
    def execute(self, context):
        scene = context.scene
        # Invert the current value
        scene.show_reconstruction_units = not scene.show_reconstruction_units
        
        print(f"Toggled show_reconstruction_units to: {scene.show_reconstruction_units}")
        
        # Call the filter update function
        if scene.filter_by_epoch:
            bpy.ops.em.filter_lists()
        
        return {'FINISHED'}

class EM_help_popup(Operator):
    bl_idname = "em.help_popup"
    bl_label = "Help Information"
    bl_description = "Show help information"
    
    title: bpy.props.StringProperty(default="Help") 
    text: bpy.props.StringProperty(default="") 
    url: bpy.props.StringProperty(default="https://docs.extendedmatrix.org") 
    
    def execute(self, context):
        def draw(self, context):
            layout = self.layout
            
            # Split the text into lines and display it
            if self.text:
                for line in self.text.split('\n'):
                    layout.label(text=line)
            else:
                # Default text if not specified
                layout.label(text="Survival Filter:")
                layout.label(text="- When enabled: Shows all units that exist in this epoch")
                layout.label(text="- When disabled: Shows only units created in this epoch")
            
            layout.separator()
            
            # Button to open documentation
            op = layout.operator("wm.url_open", text="Open Documentation")
            op.url = self.url
        
        bpy.context.window_manager.popup_menu(draw, title=self.title)
        return {'FINISHED'}

def filter_list_update(self, context):
    """
    Update callback for filter toggle buttons.
    This function is called whenever a filter button is toggled.
    Acts as a central dispatching point for filter updates.
    """
    scene = context.scene
    
    # PREVENT RECURSIVE CALLS: Check if we're already inside this function
    if hasattr(filter_list_update, "is_running") and filter_list_update.is_running:
        print("Preventing recursive filter_list_update call")
        return
    
    # Set flag to prevent recursion
    filter_list_update.is_running = True
    
    try:
        # Check which filter was toggled (self.name can be "filter_by_epoch" or "filter_by_activity")
        filter_name = getattr(self, "name", None)
        filter_value = getattr(scene, filter_name, False) if filter_name else False
        
        print(f"\n--- Filter toggle: {filter_name} = {filter_value} ---")
        
        # Check if there's a valid graph before proceeding
        from ..functions import is_graph_available as check_graph
        graph_exists, _ = check_graph(context)
        
        if graph_exists:
            # Only apply filtering if at least one filter is active
            if scene.filter_by_epoch or scene.filter_by_activity:
                try:
                    bpy.ops.em.filter_lists()
                except Exception as e:
                    print(f"Error applying filters: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                # If all filters are off, use our reset operator
                try:
                    bpy.ops.em.reset_filters()
                except Exception as e:
                    print(f"Error resetting filters: {e}")
                    import traceback
                    traceback.print_exc()
        else:
            # Show message to load a graph first
            bpy.context.window_manager.popup_menu(
                lambda self, context: self.layout.label(text="Please load a graph before filtering"),
                title="No Graph Available",
                icon='ERROR'
            )
            
            # Reset the filter that was just toggled
            if filter_name:
                # Disable temporary to prevent another callback
                old_is_running = getattr(filter_list_update, "is_running", False)
                filter_list_update.is_running = True
                
                setattr(scene, filter_name, False)
                print(f"Reset {filter_name} to False since no graph is available")
                
                # Restore previous state
                filter_list_update.is_running = old_is_running
    
    finally:
        # Reset the flag to allow future calls
        filter_list_update.is_running = False

def register_filters():
    """Register filter-related operators and properties."""
    classes = [
        EM_filter_lists,
        EM_reset_filters,
        EM_toggle_include_surviving,
        EM_toggle_show_reconstruction,
        EM_help_popup,
    ]
    
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except ValueError:
            # Class might already be registered
            pass

def unregister_filters():
    """Unregister filter-related operators and properties."""
    classes = [
        EM_help_popup,
        EM_toggle_show_reconstruction,
        EM_toggle_include_surviving,
        EM_reset_filters,
        EM_filter_lists,
    ]
    
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except ValueError:
            # Class might already be unregistered
            pass
