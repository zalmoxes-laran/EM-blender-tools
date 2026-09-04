"""Helpers for the epoch <-> representation-model edges.

Those edges are written as ``epoch --has_representation_model--> model``
(see :func:`graph_updaters.update_representation_models` and
``RM_OT_add_epoch_to_rm``), but several readers used to look for them the
other way round (``edge_source == model_node_id``).  A removal that scans
the wrong direction silently finds nothing: the epoch disappeared from the
UI while the edge stayed in the graph and kept being exported, so the
Heriverse JSON showed models under epochs the user had already detached.

Everything here matches an edge by *either* endpoint, so graphs written
with either convention are handled, and keeps the pure-graph logic out of
the operators (no ``bpy`` import here).
"""

# Edge types that bind a representation model to an epoch.
EPOCH_EDGE_TYPES = ("has_first_epoch", "has_representation_model",
                    "survive_in_epoch")


def _is_epoch_node(node):
    return node is not None and getattr(node, "node_type", None) == "EpochNode"


def iter_epoch_edges(graph, model_node_id, edge_types=EPOCH_EDGE_TYPES):
    """Yield ``(edge, epoch_node)`` for every epoch edge of *model_node_id*.

    The edge is matched whatever its direction, as long as one endpoint is
    the model and the other one is an EpochNode.
    """
    for edge in list(graph.edges):
        if edge.edge_type not in edge_types:
            continue
        if edge.edge_source == model_node_id:
            other_id = edge.edge_target
        elif edge.edge_target == model_node_id:
            other_id = edge.edge_source
        else:
            continue
        epoch_node = graph.find_node_by_id(other_id)
        if _is_epoch_node(epoch_node):
            yield edge, epoch_node


def epoch_names_for_model(graph, model_node_id, edge_types=EPOCH_EDGE_TYPES):
    """Names of the epochs the model is bound to, without duplicates."""
    names = []
    for _edge, epoch_node in iter_epoch_edges(graph, model_node_id, edge_types):
        if epoch_node.name not in names:
            names.append(epoch_node.name)
    return names


def remove_epoch_edges(graph, model_node_id, epoch_names=None,
                       edge_types=EPOCH_EDGE_TYPES):
    """Drop the model's epoch edges; ``epoch_names=None`` drops them all.

    Returns the number of edges actually removed.
    """
    wanted = None if epoch_names is None else set(epoch_names)
    to_remove = [
        edge.edge_id
        for edge, epoch_node in iter_epoch_edges(graph, model_node_id, edge_types)
        if wanted is None or epoch_node.name in wanted
    ]
    for edge_id in to_remove:
        graph.remove_edge(edge_id)
    return len(to_remove)


def sync_epoch_edges(graph, model_node_id, epoch_names,
                     edge_type="has_representation_model"):
    """Make the model's edges of *edge_type* mirror *epoch_names* exactly.

    Adds what is missing and removes what is no longer wanted, so an epoch
    detached in Blender does not survive in the graph (and in the export).
    Returns ``(added, removed)``.
    """
    wanted = [name for name in epoch_names if name and name != "no_epoch"]

    epoch_nodes_by_name = {
        node.name: node
        for node in graph.nodes
        if getattr(node, "node_type", None) == "EpochNode"
    }

    removed = 0
    for edge, epoch_node in list(iter_epoch_edges(graph, model_node_id,
                                                  (edge_type,))):
        if epoch_node.name not in wanted:
            graph.remove_edge(edge.edge_id)
            removed += 1

    added = 0
    for name in wanted:
        epoch_node = epoch_nodes_by_name.get(name)
        if epoch_node is None:
            continue
        edge_id = f"{epoch_node.node_id}_{edge_type}_{model_node_id}"
        if graph.find_edge_by_id(edge_id):
            continue
        # An edge may already exist under a different id (legacy direction
        # or a uuid-based id): only add when the pair is really missing.
        already = any(
            node.name == name
            for _e, node in iter_epoch_edges(graph, model_node_id, (edge_type,))
        )
        if already:
            continue
        graph.add_edge(
            edge_id=edge_id,
            edge_source=epoch_node.node_id,
            edge_target=model_node_id,
            edge_type=edge_type,
        )
        added += 1

    return added, removed
