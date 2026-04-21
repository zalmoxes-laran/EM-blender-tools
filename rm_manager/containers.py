"""RM container logic (DP-47 extension / DP-07 wrapper).

An **RM container** groups several mesh objects under a single
DocumentNode. The Document is the graph-side wrapper; the container
is the EMTools-side PropertyGroup on ``scene.rm_containers`` that
tracks which Blender mesh objects belong to it. A mesh can belong to
at most **one** container at a time (user decision, Q_C).

Ownership:
- Authoritative mesh list → ``RMContainerItem.mesh_names``.
- Mesh custom property ``em_rm_container_doc_id`` is a reverse-lookup
  convenience; ``mesh_names`` wins if they disagree.
- Blender Collections are NOT source of truth — users are free to
  keep meshes in any collection they prefer.

This module exposes:

- :func:`sync_rm_containers` — validates mesh existence, removes
  missing entries, raises sanitisation warnings, and on first open
  bundles un-linked legacy RMs into an automatic "Legacy RMs" container.
- :func:`find_container_for_mesh` — reverse lookup.
- :func:`add_mesh_to_container` / :func:`remove_mesh_from_container` —
  mutate both the PropertyGroup list and the scene graph
  (``has_representation_model`` edge from Document to RM node).
- :func:`unregister_container` — drops the container + removes all
  ``has_representation_model`` edges from the linked Document to the
  contained meshes' RM nodes (the DocumentNode itself stays).
"""

from __future__ import annotations

from typing import List, Optional, Tuple

import bpy  # type: ignore


LEGACY_CONTAINER_LABEL = "Legacy RMs"


def _active_graph(context):
    """Return (graph_info, graph) tuple, or (None, None) when there is
    no active graph (no graphml loaded).
    """
    em_tools = context.scene.em_tools
    if em_tools.active_file_index < 0 \
            or em_tools.active_file_index >= len(em_tools.graphml_files):
        return None, None
    try:
        from s3dgraphy import get_graph
        gi = em_tools.graphml_files[em_tools.active_file_index]
        return gi, get_graph(gi.name)
    except Exception:
        return None, None


def _resolve_doc_name(graph, doc_node_id: str) -> str:
    """Return the DocumentNode's display name (e.g. ``D.01``) or empty
    string if the node is missing.
    """
    if not doc_node_id or graph is None:
        return ""
    try:
        n = graph.find_node_by_id(doc_node_id)
        return (getattr(n, "name", "") or "") if n is not None else ""
    except Exception:
        return ""


def find_container_for_mesh(scene, mesh_name: str) -> Optional[int]:
    """Return the index of the container that holds ``mesh_name``, or
    ``None`` when the mesh is not in any container.
    """
    if not mesh_name:
        return None
    for idx, container in enumerate(scene.rm_containers):
        for entry in container.mesh_names:
            if entry.name == mesh_name:
                return idx
    return None


def _ensure_rm_node_for_mesh(scene, graph, mesh_obj) -> Optional[str]:
    """Return the node_id of the RepresentationModelNode that
    represents this mesh in the graph. Resolution order:

    1. The mesh's ``em_rm_node_id`` custom property (if still valid).
    2. The matching entry in ``scene.rm_list`` (legacy RM Manager
       already tracks an RM node_id per mesh).
    3. Create a fresh RepresentationModelNode.

    The resolved id is written back to the mesh's ``em_rm_node_id`` so
    subsequent calls hit case 1.
    """
    if graph is None or mesh_obj is None:
        return None
    # Case 1: custom property on the mesh.
    existing = mesh_obj.get("em_rm_node_id", "")
    if existing:
        try:
            if graph.find_node_by_id(existing) is not None:
                return existing
        except Exception:
            pass
    # Case 2: existing rm_list entry with a node_id.
    try:
        for rm_item in scene.rm_list:
            if rm_item.name == mesh_obj.name and rm_item.node_id:
                try:
                    if graph.find_node_by_id(rm_item.node_id) is not None:
                        mesh_obj["em_rm_node_id"] = rm_item.node_id
                        return rm_item.node_id
                except Exception:
                    pass
    except Exception:
        pass
    # Case 3: create a fresh RepresentationModelNode.
    try:
        from s3dgraphy.exporter.graphml.utils import generate_uuid
        from s3dgraphy.nodes.representation_node import RepresentationModelNode
    except Exception:
        return None
    rm_id = generate_uuid()
    rm_node = RepresentationModelNode(
        node_id=rm_id,
        name=mesh_obj.name,
        type="RM",
        description="",
    )
    graph.add_node(rm_node)
    mesh_obj["em_rm_node_id"] = rm_id
    return rm_id


def _has_edge(graph, source_id: str, target_id: str,
               edge_type: str) -> bool:
    for e in graph.edges:
        if (e.edge_source == source_id
                and e.edge_target == target_id
                and e.edge_type == edge_type):
            return True
    return False


def add_mesh_to_container(context, container, mesh_obj) -> Tuple[bool, str]:
    """Add ``mesh_obj`` to ``container``. Returns ``(ok, reason)``.

    Creates the RepresentationModelNode for the mesh if needed, adds
    the ``has_representation_model`` edge from the linked Document to
    the RM node, sets the mesh's reverse-lookup custom property, and
    appends the mesh name to the container's list.

    Skips (with reason) when the mesh is already in another container
    (Q_C: a mesh belongs to at most one container).
    """
    if mesh_obj is None or mesh_obj.type != 'MESH':
        return False, "Not a mesh"
    scene = context.scene
    existing_idx = find_container_for_mesh(scene, mesh_obj.name)
    if existing_idx is not None:
        existing = scene.rm_containers[existing_idx]
        if existing == container:
            return False, f"Mesh {mesh_obj.name!r} already in this container"
        return False, (
            f"Mesh {mesh_obj.name!r} already belongs to container "
            f"{existing.label!r} — remove it from there first")
    # Graph side (only when the container is linked to a Document).
    _graph_info, graph = _active_graph(context)
    if graph is not None and container.doc_node_id:
        rm_id = _ensure_rm_node_for_mesh(scene, graph, mesh_obj)
        if rm_id and not _has_edge(
                graph, container.doc_node_id, rm_id,
                "has_representation_model"):
            try:
                graph.add_edge(
                    edge_id=(f"{container.doc_node_id}_"
                             f"has_representation_model_{rm_id}"),
                    edge_source=container.doc_node_id,
                    edge_target=rm_id,
                    edge_type="has_representation_model",
                )
            except Exception as e:
                return False, f"Failed to add edge: {e}"
        mesh_obj["em_rm_container_doc_id"] = container.doc_node_id
    # Property-group side.
    entry = container.mesh_names.add()
    entry.name = mesh_obj.name
    return True, ""


def remove_mesh_from_container(context, container, mesh_name: str,
                                 drop_edge: bool = True) -> bool:
    """Remove ``mesh_name`` from ``container``. When ``drop_edge`` is
    True and the container is linked to a Document, also remove the
    ``has_representation_model`` edge from the Document to the mesh's
    RM node. Returns True on success.
    """
    # Property-group side.
    hit_idx = None
    for i, entry in enumerate(container.mesh_names):
        if entry.name == mesh_name:
            hit_idx = i
            break
    if hit_idx is None:
        return False
    container.mesh_names.remove(hit_idx)
    # Graph side.
    if drop_edge and container.doc_node_id:
        _graph_info, graph = _active_graph(context)
        mesh_obj = bpy.data.objects.get(mesh_name)
        rm_id = mesh_obj.get("em_rm_node_id", "") if mesh_obj else ""
        if graph is not None and rm_id:
            edge_id = (f"{container.doc_node_id}_"
                       f"has_representation_model_{rm_id}")
            for i, e in enumerate(list(graph.edges)):
                if (e.edge_id == edge_id
                        or (e.edge_source == container.doc_node_id
                            and e.edge_target == rm_id
                            and e.edge_type == "has_representation_model")):
                    try:
                        graph.remove_edge(e.edge_id)
                    except Exception:
                        pass
                    break
        if mesh_obj is not None \
                and mesh_obj.get("em_rm_container_doc_id", "") \
                == container.doc_node_id:
            try:
                del mesh_obj["em_rm_container_doc_id"]
            except KeyError:
                pass
    return True


def unregister_container(context, container_index: int) -> bool:
    """Drop a container from ``scene.rm_containers``. Also removes all
    ``has_representation_model`` edges from the linked Document to the
    mesh RM nodes contained here (Q_B). The DocumentNode itself stays.
    """
    scene = context.scene
    if container_index < 0 or container_index >= len(scene.rm_containers):
        return False
    container = scene.rm_containers[container_index]
    # Rip out each mesh's edge + custom prop first.
    mesh_names = [e.name for e in container.mesh_names]
    for mn in mesh_names:
        remove_mesh_from_container(context, container, mn, drop_edge=True)
    scene.rm_containers.remove(container_index)
    if scene.rm_containers_index >= len(scene.rm_containers):
        scene.rm_containers_index = max(0, len(scene.rm_containers) - 1)
    return True


def _add_warning(scene, container_label: str, mesh_name: str):
    w = scene.rm_container_warnings.add()
    w.container_label = container_label
    w.mesh_name = mesh_name


def bootstrap_legacy_container_if_needed(context) -> None:
    """Cheap one-time guard run on panel draw.

    When ``scene.rm_containers`` is empty AND there is pre-existing
    content in ``scene.rm_list``, bundle every still-existing RM
    entry into a single unlinked "Legacy RMs" container so the
    two-level UI always has at least one container to show.

    This is O(1) in the common case: once any container exists, the
    first check short-circuits and no mesh iteration happens — safe
    to call on every draw.
    """
    scene = context.scene
    if len(scene.rm_containers) != 0:
        return
    if len(scene.rm_list) == 0:
        return
    legacy = scene.rm_containers.add()
    legacy.label = LEGACY_CONTAINER_LABEL
    legacy.doc_node_id = ""
    legacy.doc_name = ""
    for rm in scene.rm_list:
        if rm.name and rm.name in bpy.data.objects:
            entry = legacy.mesh_names.add()
            entry.name = rm.name
    scene.rm_containers_index = 0


def sync_rm_containers(context) -> None:
    """Full sanitisation pass — explicitly user-triggered via the
    ``rmcontainer.sync`` operator. NOT called on panel draw (it walks
    every mesh in every container and would slow the UI down).

    - For each container, drop mesh entries whose Blender object has
      been deleted. Each drop emits a :class:`RMContainerWarning` so
      the user is told which mesh went missing.
    - Refresh cached ``doc_name`` for each container from the graph.
    - Runs :func:`bootstrap_legacy_container_if_needed` at the end so
      a manual sync also seeds the Legacy container when nothing has
      been imported yet.
    """
    scene = context.scene
    _graph_info, graph = _active_graph(context)

    # 1. Validate & refresh existing containers.
    for container in scene.rm_containers:
        # Drop missing meshes
        i = len(container.mesh_names) - 1
        while i >= 0:
            mn = container.mesh_names[i].name
            if mn and mn not in bpy.data.objects:
                _add_warning(scene, container.label or container.doc_name
                             or "<unnamed>", mn)
                container.mesh_names.remove(i)
            i -= 1
        # Refresh doc_name cache
        if container.doc_node_id:
            fresh = _resolve_doc_name(graph, container.doc_node_id)
            if fresh:
                container.doc_name = fresh

    # 2. Legacy bootstrap (no-op when containers already exist).
    bootstrap_legacy_container_if_needed(context)


def active_container(scene):
    """Return the currently-active :class:`RMContainerItem` or None."""
    if not scene.rm_containers:
        return None
    idx = scene.rm_containers_index
    if idx < 0 or idx >= len(scene.rm_containers):
        return None
    return scene.rm_containers[idx]


def mesh_names_of_active_container(scene) -> List[str]:
    """Convenience: list of mesh names in the active container, or an
    empty list when no container is active.
    """
    ac = active_container(scene)
    if ac is None:
        return []
    return [entry.name for entry in ac.mesh_names]
