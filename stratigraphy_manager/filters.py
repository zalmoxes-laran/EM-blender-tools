"""
Filter system for stratigraphic units
This module contains the central filtering logic for the Stratigraphy Manager,
providing a consistent way to filter stratigraphic units based on multiple criteria.
"""

import bpy # type: ignore
from bpy.props import BoolProperty, StringProperty # type: ignore
from bpy.types import Operator # type: ignore

from ..functions import is_reconstruction_us, EM_list_clear
from .data import ensure_valid_index
from ..populate_lists import populate_stratigraphic_node

class EM_filter_lists(Operator):
    bl_idname = "em.filter_lists"
    bl_label = "Filter Lists"
    bl_description = "Apply filters to stratigraphy list"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        """
        Apply filters to stratigraphy list.

        ✅ CLEAN VERSION: Uses only scene.em_tools.stratigraphy paths
        """
        scene = context.scene
        strat = scene.em_tools.stratigraphy  # ✅ Nuovo

        # Check graph availability
        from ..functions import is_graph_available as check_graph
        graph_exists, graph = check_graph(context)

        if not graph_exists:
            self.report({'WARNING'}, "No active graph found. Please load a GraphML file first.")
            return {'CANCELLED'}

        # Get all stratigraphic nodes
        all_strat_nodes = [node for node in graph.nodes
                           if hasattr(node, 'node_type') and
                           node.node_type in ['US', 'USVs', 'USVn', 'VSF', 'SF', 'USD', 'serSU', 'serUSD', 'serUSVn', 'serUSVs']]

        # Apply filters
        filtered_items = all_strat_nodes  # Start with all nodes

        # Filter by epoch
        if scene.filter_by_epoch:
            epochs = scene.em_tools.epochs
            if epochs.list and len(epochs.list) > 0:
                active_epoch_index = epochs.list_index
                if active_epoch_index >= 0 and active_epoch_index < len(epochs.list):
                    active_epoch = epochs.list[active_epoch_index]

                    # Filter nodes
                    epoch_filtered = []
                    for node in filtered_items:
                        first_epoch = graph.get_connected_epoch_node_by_edge_type(node, "has_first_epoch")

                        # Check if created in this epoch
                        if first_epoch and first_epoch.name == active_epoch.name:
                            epoch_filtered.append(node)
                        # Check if survived in this epoch (if option enabled)
                        elif scene.include_surviving_units:
                            survived_epochs = graph.get_connected_epoch_nodes_list_by_edge_type(node, "survive_in_epoch")
                            if any(e.name == active_epoch.name for e in survived_epochs):
                                epoch_filtered.append(node)

                    filtered_items = epoch_filtered

        # Filter by activity
        if scene.filter_by_activity:
            activity_manager = scene.activity_manager
            if activity_manager.activities and len(activity_manager.activities) > 0:
                active_activity_index = activity_manager.active_index
                if active_activity_index >= 0 and active_activity_index < len(activity_manager.activities):
                    active_activity = activity_manager.activities[active_activity_index]

                    # Filter nodes that belong to this activity
                    activity_filtered = []
                    for node in filtered_items:
                        # Check if node is connected to this activity via "is_in_activity" edge
                        connected_activities = graph.get_connected_nodes_by_edge_type(node.node_id, "is_in_activity")
                        if any(activity.name == active_activity.name for activity in connected_activities):
                            activity_filtered.append(node)

                    filtered_items = activity_filtered

        # Filter reconstruction units
        if not scene.show_reconstruction_units:
            from ..functions import is_reconstruction_us
            filtered_items = [node for node in filtered_items if not is_reconstruction_us(node)]

        # ✅ Save current selection (SOLO nuovo)
        current_selected = None
        if strat.units_index >= 0 and strat.units_index < len(strat.units):
            current_selected = strat.units[strat.units_index].name

        # ✅ Clear SOLO nuova lista
        EM_list_clear(context, "em_list")

        # ✅ Rebuild (popola SOLO nuova lista)
        print(f"\nPopulating with {len(filtered_items)} filtered items")
        for i, node in enumerate(filtered_items):
            populate_stratigraphic_node(scene, node, i, graph)

        # ✅ Reset index SOLO nuovo
        if len(strat.units) == 0:
            strat.units_index = -1
            self.report({'INFO'}, "No items match the current filters")
        else:
            strat.units_index = 0

            # Restore selection if possible
            if current_selected:
                for i, item in enumerate(strat.units):
                    if item.name == current_selected:
                        strat.units_index = i
                        print(f"Restored selection to index {i}: {item.name}")
                        break

        # Sync visibility if active
        if scene.sync_list_visibility:
            bpy.ops.em.strat_sync_visibility()

        return {'FINISHED'}

class EM_reset_filters(Operator):
    bl_idname = "em.reset_filters"
    bl_label = "Reset Filters"
    bl_description = "Reset all filters and reload the complete list"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        """
        Reset all filters and reload the complete list.

        ✅ CLEAN VERSION: Uses only scene.em_tools.stratigraphy paths
        """
        scene = context.scene
        strat = scene.em_tools.stratigraphy  # ✅ Nuovo

        # Disable filter update callbacks while resetting toggles.
        from . import operators as strat_ops
        old_bypass = strat_ops._em_bypass_filter_update
        strat_ops._em_bypass_filter_update = True

        try:
            # Disable filters
            scene.filter_by_epoch = False
            scene.filter_by_activity = False

            # Reset containment filter
            strat.filter_by_containment = False
            strat.containment_filter_node_id = ""

            # Get graph
            from ..functions import is_graph_available
            graph_exists, graph = is_graph_available(context)

            if graph_exists:
                # ✅ Clear SOLO nuova lista
                EM_list_clear(context, "em_list")

                # Get all stratigraphic nodes
                strat_nodes = [node for node in graph.nodes
                               if hasattr(node, 'node_type') and
                               node.node_type in ['US', 'USVs', 'USVn', 'VSF', 'SF', 'USD', 'serSU', 'serUSD', 'serUSVn', 'serUSVs']]

                # ✅ Repopulate SOLO nuova lista
                for i, node in enumerate(strat_nodes):
                    populate_stratigraphic_node(scene, node, i, graph)

                # ✅ Ensure index SOLO nuovo
                if len(strat.units) > 0:
                    strat.units_index = 0
                else:
                    strat.units_index = -1

                # Optional behavior: re-enable visibility for all proxies.
                if scene.reset_filters_show_all_proxies and hasattr(bpy.ops.em, "strat_show_all_proxies"):
                    bpy.ops.em.strat_show_all_proxies()
                    self.report({'INFO'}, "Filters reset, list restored and all proxies shown")
                else:
                    self.report({'INFO'}, "Filters reset, list restored (visibility preserved)")
            else:
                self.report({'WARNING'}, "No active graph found")
        finally:
            strat_ops._em_bypass_filter_update = old_bypass

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


class EM_filter_by_containment(Operator):
    bl_idname = "em.filter_by_containment"
    bl_label = "Filter by Containment"
    bl_description = "Show only the container US and the elements it contains"
    bl_options = {"REGISTER", "UNDO"}

    container_node_id: StringProperty(
        name="Container Node ID",
        description="Node ID of the container US to filter by"
    )  # type: ignore

    def execute(self, context):
        scene = context.scene
        strat = scene.em_tools.stratigraphy

        from ..functions import is_graph_available as check_graph
        graph_exists, graph = check_graph(context)

        if not graph_exists:
            self.report({'WARNING'}, "No active graph found.")
            return {'CANCELLED'}

        container_id = self.container_node_id

        # Disable other filters to avoid conflicts
        from . import operators as strat_ops
        old_bypass = strat_ops._em_bypass_filter_update
        strat_ops._em_bypass_filter_update = True
        try:
            scene.filter_by_epoch = False
            scene.filter_by_activity = False
        finally:
            strat_ops._em_bypass_filter_update = old_bypass

        # Find all children of this container via is_part_of edges
        child_node_ids = set()
        for edge in graph.edges:
            if edge.edge_type == "is_part_of" and edge.edge_target == container_id:
                child_node_ids.add(edge.edge_source)

        # Get all matching nodes (container + children)
        matching_nodes = []
        for node in graph.nodes:
            if not hasattr(node, 'node_type'):
                continue
            if node.node_id == container_id or node.node_id in child_node_ids:
                matching_nodes.append(node)

        # Rebuild list with filtered items
        from ..functions import EM_list_clear
        EM_list_clear(context, "em_list")

        for i, node in enumerate(matching_nodes):
            populate_stratigraphic_node(scene, node, i, graph)

        # Set filter state
        strat.filter_by_containment = True
        strat.containment_filter_node_id = container_id

        # Select the container row
        if len(strat.units) > 0:
            strat.units_index = 0

        self.report({'INFO'}, f"Showing container and {len(child_node_ids)} contained elements")
        return {'FINISHED'}


class EM_select_parent_us(Operator):
    bl_idname = "em.select_parent_us"
    bl_label = "Select Parent US"
    bl_description = "Select the container US that contains this element"
    bl_options = {"REGISTER", "UNDO"}

    parent_node_id: StringProperty(
        name="Parent Node ID",
        description="Node ID of the parent US to select"
    )  # type: ignore

    def execute(self, context):
        scene = context.scene
        strat = scene.em_tools.stratigraphy

        # Find the parent in the current list
        for i, item in enumerate(strat.units):
            if item.id_node == self.parent_node_id:
                strat.units_index = i
                self.report({'INFO'}, f"Selected container: {item.name}")
                return {'FINISHED'}

        self.report({'WARNING'}, "Parent US not found in current list")
        return {'CANCELLED'}


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

        # Reset containment filter when epoch/activity filters are toggled
        strat = scene.em_tools.stratigraphy
        if strat.filter_by_containment:
            strat.filter_by_containment = False
            strat.containment_filter_node_id = ""
            print("Containment filter reset due to epoch/activity filter change")

        # Check if there's a valid graph before proceeding
        from ..functions import is_graph_available as check_graph
        graph_exists, _ = check_graph(context)
        
        if graph_exists:
            # Only apply filtering if at least one filter is active
            if scene.filter_by_epoch or scene.filter_by_activity:
                try:
                    # IMPORTANTE: Verifica che l'operatore esista prima di chiamarlo
                    if hasattr(bpy.ops, 'em') and hasattr(bpy.ops.em, 'filter_lists'):
                        bpy.ops.em.filter_lists()
                    else:
                        print("Warning: em.filter_lists operator not available")
                except Exception as e:
                    print(f"Error applying filters: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                # If all filters are off, use our reset operator
                try:
                    # IMPORTANTE: Verifica che l'operatore esista prima di chiamarlo
                    if hasattr(bpy.ops, 'em') and hasattr(bpy.ops.em, 'reset_filters'):
                        bpy.ops.em.reset_filters()
                    else:
                        print("Warning: em.reset_filters operator not available")
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
        EM_filter_by_containment,
        EM_select_parent_us,
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
        EM_select_parent_us,
        EM_filter_by_containment,
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
