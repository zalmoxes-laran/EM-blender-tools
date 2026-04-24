# anastylosis_manager/graph_utils.py
"""Graph-side helpers: RMSF/link removal and visibility analysis for selection."""


def _remove_item_from_graph(graph, item):
    """Remove RMSF node, its link node, and all connected edges from the graph.
    Shared logic used by both single-remove and batch-remove operators.
    """
    if not graph or not item.node_id:
        return

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
            link_edges = [
                edge.edge_id for edge in graph.edges
                if edge.edge_source == link_node_id or edge.edge_target == link_node_id
            ]
            for edge_id in link_edges:
                graph.remove_edge(edge_id)

            # Remove the link node
            graph.remove_node(link_node_id)


def analyze_visibility_requirements(context, objects):
    """Analyze which visibility/collection changes are needed to select objects."""
    from ..stratigraphy_manager.operators import find_layer_collection

    needs_unhide = []
    needs_unprotect = []
    needs_collection_activation = set()
    not_in_view_layer = []
    already_visible = []

    for obj in objects:
        obj_needs_changes = False
        obj_in_view_layer = False

        for collection in obj.users_collection:
            layer_col = find_layer_collection(context.view_layer.layer_collection, collection.name)
            if layer_col:
                if layer_col.exclude:
                    needs_collection_activation.add(collection.name)
                    obj_needs_changes = True
                else:
                    obj_in_view_layer = True
                if collection.hide_viewport:
                    needs_collection_activation.add(collection.name)
                    obj_needs_changes = True

        if not obj_in_view_layer and obj.users_collection:
            not_in_view_layer.append(obj.name)
            obj_needs_changes = True

        if obj.hide_viewport or obj.hide_get():
            needs_unhide.append(obj.name)
            obj_needs_changes = True

        if obj.hide_select:
            needs_unprotect.append(obj.name)
            obj_needs_changes = True

        if not obj_needs_changes:
            already_visible.append(obj.name)

    return {
        'needs_unhide': needs_unhide,
        'needs_unprotect': needs_unprotect,
        'needs_collection_activation': list(needs_collection_activation),
        'not_in_view_layer': not_in_view_layer,
        'already_visible': already_visible,
        'total_changes': len(needs_unhide) + len(needs_unprotect) + len(needs_collection_activation),
    }


def apply_visibility_changes(context, objects):
    """Apply visibility/collection changes to make objects selectable."""
    from ..stratigraphy_manager.operators import activate_collection_fully

    for obj in objects:
        if obj.hide_viewport:
            obj.hide_viewport = False
        if obj.hide_get():
            obj.hide_set(False)
        if obj.hide_select:
            obj.hide_select = False
        for collection in obj.users_collection:
            activate_collection_fully(context, collection)
