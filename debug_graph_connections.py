"""
Debug operator to inspect graph connections for survive_in_epoch edges
"""

import bpy
from bpy.types import Operator

from .us_types import US_PROPER_TYPES


class EM_OT_debug_graph_connections(Operator):
    """Debug: Inspect graph connections for survive_in_epoch"""
    bl_idname = "em.debug_graph_connections"
    bl_label = "Debug Graph Connections"
    bl_description = "Inspect graph connections for survive_in_epoch edges"
    bl_options = {'REGISTER'}

    def execute(self, context):
        from .functions import is_graph_available

        graph_exists, graph = is_graph_available(context)

        if not graph_exists:
            self.report({'ERROR'}, "No graph available")
            return {'CANCELLED'}

        print("\n" + "="*80)
        print("GRAPH CONNECTION DEBUG REPORT")
        print("="*80)

        # 1. Count edge types
        print("\n### EDGE TYPE COUNTS ###")
        edge_types = {}
        for edge in graph.edges:
            edge_type = edge.edge_type
            edge_types[edge_type] = edge_types.get(edge_type, 0) + 1

        for edge_type, count in sorted(edge_types.items()):
            print(f"  {edge_type}: {count}")

        # 2. List all survive_in_epoch connections
        print("\n### ALL survive_in_epoch CONNECTIONS ###")
        survive_edges = [e for e in graph.edges if e.edge_type == "survive_in_epoch"]
        print(f"Total survive_in_epoch edges: {len(survive_edges)}")

        for edge in survive_edges[:20]:  # Limit to first 20
            source_node = graph.find_node_by_id(edge.edge_source)
            target_node = graph.find_node_by_id(edge.edge_target)
            source_name = source_node.name if source_node else edge.edge_source
            target_name = target_node.name if target_node else edge.edge_target
            print(f"  {edge.edge_id}: {source_name} -> {target_name}")

        if len(survive_edges) > 20:
            print(f"  ... and {len(survive_edges) - 20} more")

        # 3. Test a specific node
        print("\n### TESTING SPECIFIC NODES ###")

        # Get all stratigraphic nodes
        strat_nodes = [node for node in graph.nodes
                       if hasattr(node, 'node_type') and
                       node.node_type in US_PROPER_TYPES]

        if strat_nodes:
            # Test first 5 nodes
            for test_node in strat_nodes[:5]:
                print(f"\nNode: {test_node.name} (ID: {test_node.node_id})")

                # Find has_first_epoch
                first_epoch = graph.get_connected_epoch_node_by_edge_type(test_node, "has_first_epoch")
                print(f"  First epoch: {first_epoch.name if first_epoch else 'NONE'}")

                # Find survive_in_epoch - MANUAL SEARCH
                print(f"  Survive in epochs (manual search):")
                manual_survived = []
                for edge in graph.edges:
                    if edge.edge_type == "survive_in_epoch":
                        if edge.edge_source == test_node.node_id:
                            target = graph.find_node_by_id(edge.edge_target)
                            if target:
                                manual_survived.append(target.name)
                                print(f"    - {target.name} (source->target)")
                        elif edge.edge_target == test_node.node_id:
                            source = graph.find_node_by_id(edge.edge_source)
                            if source:
                                manual_survived.append(source.name)
                                print(f"    - {source.name} (target<-source)")

                if not manual_survived:
                    print(f"    NONE FOUND")

                # Find survive_in_epoch - USING FUNCTION
                print(f"  Survive in epochs (using get_connected_epoch_nodes_list_by_edge_type):")
                survived_epochs = graph.get_connected_epoch_nodes_list_by_edge_type(test_node, "survive_in_epoch")
                if survived_epochs:
                    for epoch in survived_epochs:
                        print(f"    - {epoch.name}")
                else:
                    print(f"    NONE FOUND")

        # 4. Check epoch nodes
        print("\n### EPOCH NODES ###")

        # First check with "EpochNode"
        epoch_nodes_capital = [node for node in graph.nodes
                               if hasattr(node, 'node_type') and node.node_type == 'EpochNode']
        print(f"Nodes with node_type='EpochNode': {len(epoch_nodes_capital)}")

        # Then check with "EpochNode"
        epoch_nodes_lower = [node for node in graph.nodes
                            if hasattr(node, 'node_type') and node.node_type == 'EpochNode']
        print(f"Nodes with node_type='EpochNode': {len(epoch_nodes_lower)}")

        # Check all unique node types
        all_types = set()
        for node in graph.nodes:
            if hasattr(node, 'node_type'):
                all_types.add(node.node_type)

        print(f"\nAll node types in graph: {sorted(all_types)}")

        # List all epoch nodes (regardless of type)
        epoch_nodes = epoch_nodes_capital if epoch_nodes_capital else epoch_nodes_lower
        print(f"\nEpoch nodes found:")
        for epoch in epoch_nodes:
            print(f"  {epoch.name} (ID: {epoch.node_id}, type: '{epoch.node_type}')")

        print("\n" + "="*80)
        print("END REPORT")
        print("="*80 + "\n")

        self.report({'INFO'}, "Debug report printed to console")
        return {'FINISHED'}


def register():
    bpy.utils.register_class(EM_OT_debug_graph_connections)


def unregister():
    bpy.utils.unregister_class(EM_OT_debug_graph_connections)
