"""
Post-processing for Surface Areale meshes.
Handles normal offset, decimation, EM naming, material assignment,
and graph linking with the correct paradata chain:

  US --has_property--> PropertyNode --has_data_provenance--> ExtractorNode
       --extracted_from--> DocumentNode --has_representation_model--> RepresentationModelNode
"""

import bpy
import bmesh
import uuid
from mathutils import Vector


# ══════════════════════════════════════════════════════════════════════
# GEOMETRY POST-PROCESSING
# ══════════════════════════════════════════════════════════════════════

def apply_normal_offset(obj, bvh_tree, offset_distance, overlap_count=0):
    """Offset each vertex along the RM surface normal (anti z-fighting).

    If overlap_count > 0, the offset is multiplied to stack overlapping
    areali at different heights. Capped at 5x to avoid excessive offset.
    """
    multiplier = min(overlap_count + 1, 5)
    effective_offset = offset_distance * multiplier
    mesh = obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    for v in bm.verts:
        location, normal, index, dist = bvh_tree.find_nearest(v.co)
        if location is not None and normal is not None:
            v.co = Vector(location) + Vector(normal) * effective_offset
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()


def count_overlapping_areali(obj, rm_obj):
    """
    Count how many existing areale proxies overlap with the given object
    on the same RM, using AABB overlap test on children of rm_obj.

    Args:
        obj: The new areale object (needs bounding box)
        rm_obj: The parent RM object

    Returns:
        int: Number of overlapping areali (0 = no overlap)
    """
    if not rm_obj:
        return 0

    new_bb = _get_world_aabb(obj)
    if not new_bb:
        return 0

    count = 0
    for child in rm_obj.children:
        if child == obj:
            continue
        if not _is_areale_proxy(child):
            continue
        child_bb = _get_world_aabb(child)
        if child_bb and _aabb_overlap(new_bb, child_bb):
            count += 1

    return count


def _get_world_aabb(obj):
    """Get axis-aligned bounding box in world space as (min_corner, max_corner)."""
    if not obj.bound_box:
        return None
    world_corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    min_c = Vector((min(c.x for c in world_corners),
                     min(c.y for c in world_corners),
                     min(c.z for c in world_corners)))
    max_c = Vector((max(c.x for c in world_corners),
                     max(c.y for c in world_corners),
                     max(c.z for c in world_corners)))
    return (min_c, max_c)


def _aabb_overlap(bb1, bb2):
    """Test if two AABBs overlap."""
    min1, max1 = bb1
    min2, max2 = bb2
    return (min1.x <= max2.x and max1.x >= min2.x and
            min1.y <= max2.y and max1.y >= min2.y and
            min1.z <= max2.z and max1.z >= min2.z)


def _is_areale_proxy(obj):
    """Heuristic: check if an object is a surface areale proxy."""
    if obj.type != 'MESH':
        return False
    for mat_slot in obj.material_slots:
        if mat_slot.material and mat_slot.material.name.startswith("M_Areale_"):
            return True
    return False


def decimate_preserving_boundary(obj, max_triangles, max_error, bvh_tree):
    """Decimate mesh while preserving boundary edges.
    Uses is_boundary on live bmesh elements (not cached indices)."""
    mesh = obj.data
    if len(mesh.polygons) <= max_triangles:
        return

    bm = bmesh.new()
    bm.from_mesh(mesh)

    # Step 1: Remove degenerate geometry
    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges[:], dist=max_error * 0.5)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()

    # Step 2: Dissolve interior edges at low angles (preserve boundary)
    # Check is_boundary AFTER dissolve_degenerate (indices may have changed)
    interior_verts = [v for v in bm.verts if not v.is_boundary]
    interior_edges = [e for e in bm.edges if not e.is_boundary]
    if interior_verts and interior_edges:
        bmesh.ops.dissolve_limit(
            bm, angle_limit=0.087,  # ~5 degrees
            verts=interior_verts,
            edges=interior_edges,
        )

    bm.to_mesh(mesh)
    bm.free()
    mesh.update()

    # Step 3: If still over limit, use Decimate modifier as final pass
    if len(mesh.polygons) > max_triangles:
        mod = obj.modifiers.new("Decimate", 'DECIMATE')
        mod.ratio = max_triangles / len(mesh.polygons)
        mod.use_collapse_triangulate = True
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.modifier_apply(modifier=mod.name)


def assign_em_naming(obj, graph, us_node_name, context):
    """Apply EM naming convention (graph prefix) to the areale object."""
    try:
        from ..operators.addon_prefix_helpers import node_name_to_proxy_name
        if us_node_name and graph:
            obj.name = node_name_to_proxy_name(us_node_name, context, graph)
        elif us_node_name:
            obj.name = us_node_name
    except Exception as e:
        print(f"[SurfaceAreale] Naming warning: {e}")
        if us_node_name:
            obj.name = us_node_name


def assign_em_material(obj, us_type, alpha=0.5):
    """Create and assign a semi-transparent material based on the US type.

    Colour sourced from ``em_visual_rules.json`` via
    :func:`us_types.get_us_color` — the same source the Stratigraphy
    Manager's ``emset.emmaterial`` operator uses. If the JSON has no
    entry for ``us_type`` (shouldn't happen now that USN is registered
    but keep a safety net) fall back to a neutral grey.
    """
    from ..us_types import get_us_color
    rgba = get_us_color(us_type)
    if rgba and len(rgba) >= 3:
        color = tuple(rgba[:3])
    else:
        color = (0.7, 0.7, 0.7)
    mat_name = f"M_Areale_{us_type}"
    mat = bpy.data.materials.get(mat_name)
    if not mat:
        mat = bpy.data.materials.new(name=mat_name)
        mat.use_nodes = True
        try:
            mat.blend_method = 'BLEND'
        except AttributeError:
            pass
        for node in mat.node_tree.nodes:
            if node.type == 'BSDF_PRINCIPLED':
                node.inputs['Base Color'].default_value = (*color, 1.0)
                node.inputs['Alpha'].default_value = alpha
                node.inputs['Roughness'].default_value = 0.8
                try:
                    node.inputs['Specular IOR Level'].default_value = 0.0
                except KeyError:
                    pass
                break
    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)


# ══════════════════════════════════════════════════════════════════════
# RM / DOCUMENT LOOKUP HELPERS
# ══════════════════════════════════════════════════════════════════════

def is_mesh_an_rm(obj, scene):
    """Check if a Blender object is a registered RM via scene.rm_list."""
    if not obj:
        return False, None
    for item in scene.rm_list:
        if item.name == obj.name:
            return True, item
    return False, None


def find_rm_node_in_graph(scene, graph, rm_obj, create_if_missing=False):
    """
    Find the RepresentationModelNode in the graph for the given Blender object.
    If create_if_missing=True and the RM exists in scene.rm_list but not in the
    graph, creates the node in the graph (with UUID) and links it to its epochs.

    Note: This function is called from the UI draw() method — keep it silent
    (no print statements) to avoid log spam.
    """
    rm_name = rm_obj.name

    # Strategy 1: Use rm_list node_id
    for item in scene.rm_list:
        if item.name == rm_name and item.node_id:
            node = graph.find_node_by_id(item.node_id)
            if node:
                return node

    # Strategy 2: Search graph nodes by exact name
    for node in graph.nodes:
        if (hasattr(node, 'node_type') and
                node.node_type == 'representation_model' and
                hasattr(node, 'name') and node.name == rm_name):
            return node

    # Strategy 3: Search by partial name match (LOD variants)
    for node in graph.nodes:
        if (hasattr(node, 'node_type') and
                node.node_type == 'representation_model' and
                hasattr(node, 'name') and isinstance(node.name, str)):
            if rm_name in node.name or node.name in rm_name:
                return node

    # Strategy 4: Create the RM node if it's in rm_list but missing from graph
    if create_if_missing:
        for item in scene.rm_list:
            if item.name == rm_name:
                rm_node = _create_rm_node_in_graph(graph, item, scene)
                if rm_node:
                    print(f"[SurfaceAreale] Created missing RM node in graph: {rm_node.name} (id={rm_node.node_id})")
                    # Update the rm_list item with the new stable UUID
                    item.node_id = rm_node.node_id
                    return rm_node

    return None


def _create_rm_node_in_graph(graph, rm_item, scene):
    """
    Create a RepresentationModelNode in the graph for an RM that exists in
    scene.rm_list but is missing from the graph. Uses a stable UUID.
    Links it to its epochs via has_first_epoch / survive_in_epoch.
    """
    from s3dgraphy.nodes import RepresentationModelNode

    node_id = str(uuid.uuid4())  # Stable UUID, not name-based
    rm_node = RepresentationModelNode(
        node_id=node_id,
        name=rm_item.name,
        type="RM"
    )
    graph.add_node(rm_node)

    # Link to epochs from the rm_item
    if rm_item.epochs:
        for i, epoch_item in enumerate(rm_item.epochs):
            epoch_name = epoch_item.name
            # Find the epoch node in the graph
            for node in graph.nodes:
                if (hasattr(node, 'node_type') and node.node_type == 'EpochNode'
                        and hasattr(node, 'name') and node.name == epoch_name):
                    edge_type = "has_first_epoch" if i == 0 else "survive_in_epoch"
                    graph.add_edge(
                        edge_id=f"{node_id}_{edge_type}_{node.node_id}",
                        edge_source=node_id,
                        edge_target=node.node_id,
                        edge_type=edge_type
                    )
                    break

    return rm_node


def find_rm_document(scene, graph, rm_obj):
    """Find a DocumentNode linked to this RM.

    Two linkage paths are supported:

    1. **Graph edge** ``Document --has_representation_model--> RM``.
       This is the canonical link used when the paradata chain has
       been materialised in the graph.

    2. **RM container** (``scene.rm_containers``) with
       ``doc_node_id`` pointing at the document. Containers are the
       DP-47 extension used by the RM Manager to group meshes under a
       document without necessarily creating the ``has_representation_model``
       edge up-front. Without this fallback the Surface Areas
       extraction-chain UI would show "No Document linked" even when
       the Document Manager catalog reports the link correctly.
    """
    rm_node = find_rm_node_in_graph(scene, graph, rm_obj)
    if rm_node:
        for edge in graph.edges:
            if (edge.edge_target == rm_node.node_id and
                    edge.edge_type == "has_representation_model"):
                source = graph.find_node_by_id(edge.edge_source)
                if (source and hasattr(source, 'node_type')
                        and source.node_type == 'document'):
                    return source

    # Fallback: scene.rm_containers — find any container that holds
    # this mesh and resolve its doc_node_id back to a DocumentNode.
    try:
        rm_containers = getattr(scene, 'rm_containers', None)
        if rm_containers:
            rm_name = rm_obj.name
            for container in rm_containers:
                if not container.doc_node_id:
                    continue
                if not any(e.name == rm_name for e in container.mesh_names):
                    continue
                doc_node = graph.find_node_by_id(container.doc_node_id)
                if (doc_node and hasattr(doc_node, 'node_type')
                        and doc_node.node_type == 'document'):
                    return doc_node
    except Exception:
        pass

    return None


def _find_node_by_name(graph, name, node_type=None):
    """Find a graph node by name, optionally filtering by node_type."""
    for node in graph.nodes:
        if not hasattr(node, 'name') or node.name != name:
            continue
        if node_type and hasattr(node, 'node_type') and node.node_type != node_type:
            continue
        return node
    return None


# ══════════════════════════════════════════════════════════════════════
# SIMPLE LINKING (1.5 — no paradata, just naming + US association)
# ══════════════════════════════════════════════════════════════════════

def link_areale_simple(context, areale_obj, rm_obj, settings):
    """
    1.5 mode: link the areale proxy to an existing US node.
    No paradata chain (Property/Extractor/Document) is created.
    Only applies EM naming (graph prefix + US name) and parents to RM.

    Returns: (us_node, message_string) or (None, error_string)
    """
    from s3dgraphy import get_graph

    scene = context.scene
    em_tools = scene.em_tools

    if em_tools.active_file_index < 0:
        return None, "No active graph file"

    graph_info = em_tools.graphml_files[em_tools.active_file_index]
    graph = get_graph(graph_info.name)
    if not graph:
        return None, "Graph not loaded"

    # ── Find existing US node ─────────────────────────────────────────
    us_node = None
    if settings.linked_us_name:
        us_node = _find_node_by_name(graph, settings.linked_us_name)

    if not us_node:
        return None, f"US node '{settings.linked_us_name}' not found in graph"

    # ── Apply EM naming (rename proxy to prefixed US name) ────────────
    assign_em_naming(areale_obj, graph, us_node.name, context)

    # ── Parent to RM object ───────────────────────────────────────────
    areale_obj.parent = rm_obj
    areale_obj.matrix_parent_inverse = rm_obj.matrix_world.inverted()

    return us_node, f"Proxy '{areale_obj.name}' linked to {us_node.name}"


# ══════════════════════════════════════════════════════════════════════
# FULL PARADATA CHAIN (experimental — future 1.6)
# ══════════════════════════════════════════════════════════════════════

def link_areale_to_graph(context, areale_obj, rm_obj, settings):
    """
    Create the full paradata chain in the graph:
    US --has_property--> PropertyNode --has_data_provenance--> ExtractorNode
         --extracted_from--> DocumentNode --has_representation_model--> RM

    Returns: (us_node, message_string) or (None, error_string)
    """
    from s3dgraphy import get_graph

    scene = context.scene
    em_tools = scene.em_tools

    if em_tools.active_file_index < 0:
        return None, "No active graph file"

    graph_info = em_tools.graphml_files[em_tools.active_file_index]
    graph = get_graph(graph_info.name)
    if not graph:
        return None, "Graph not loaded"

    messages = []

    # ── 1. Find RepresentationModelNode (create if missing from graph) ─
    rm_node = find_rm_node_in_graph(scene, graph, rm_obj, create_if_missing=True)
    if not rm_node:
        return None, f"RM node not found and could not be created for {rm_obj.name}"

    # ── 2. Find or link DocumentNode ──────────────────────────────────
    # DP-07 unified flow: documents are always created via the shared
    # Master-Document dialog (either the one the user had already open
    # or the wrapper ``emtools.surface_areale_create_doc`` which
    # auto-picks the result). So here we just resolve ``existing_document``
    # — the inline "create doc" branch is gone.
    doc_node = find_rm_document(scene, graph, rm_obj)
    if not doc_node and settings.existing_document:
        doc_node = _find_node_by_name(
            graph, settings.existing_document, 'document')
        if doc_node:
            _ensure_edge(graph, doc_node.node_id, rm_node.node_id,
                         "has_representation_model")
            messages.append(f"Linked document: {doc_node.name}")

    if not doc_node:
        return None, "No document — cannot create paradata chain"

    # ── 3. Find the target US ─────────────────────────────────────────
    # The Surface Areas panel only exposes the ``linked_us_name``
    # picker (with a ``+`` button that launches the shared
    # ``strat.add_us`` dialog). New-US creation happens upfront via
    # that dialog — by the time we reach this postprocess step, the
    # US already exists in the graph and the Stratigraphy Manager's
    # list.
    us_node = None
    if settings.linked_us_name:
        us_node = _find_node_by_name(graph, settings.linked_us_name)
    if not us_node:
        return None, (
            "No US picked. Use the '+' next to the Existing US "
            "picker to create a new one via the shared dialog.")

    # ── 4. Create PropertyNode ────────────────────────────────────────
    from s3dgraphy.nodes import PropertyNode

    prop_node = PropertyNode(
        node_id=str(uuid.uuid4()),
        name=settings.property_name,       # default: "geometry"
        description=f"Geometry property for {us_node.name}",
        value=areale_obj.name,             # the proxy object name
        property_type="string"
    )
    graph.add_node(prop_node)
    messages.append(f"Created property: {prop_node.name}={prop_node.value}")

    # ── 5. Create ExtractorNode ───────────────────────────────────────
    from s3dgraphy.nodes import ExtractorNode

    # Extractor name follows pattern: {document_name}.{next_number}
    # e.g. D.10016.1, D.10016.2, etc. (same pattern as proxy_box_creator)
    extractor_name = _get_next_extractor_name(graph, doc_node.name)

    extractor = ExtractorNode(
        node_id=str(uuid.uuid4()),
        name=extractor_name,
        description=settings.extractor_name  # default: "3D drawing on surface"
    )
    extractor.attributes['purpose'] = settings.extractor_name
    extractor.attributes['source_rm'] = rm_obj.name
    graph.add_node(extractor)
    messages.append(f"Created extractor: {extractor.name}")

    # ── 6. Create the 4 edges ─────────────────────────────────────────

    # Edge 1: US --has_property--> PropertyNode
    graph.add_edge(
        edge_id=f"{us_node.node_id}_has_property_{prop_node.node_id}",
        edge_source=us_node.node_id,
        edge_target=prop_node.node_id,
        edge_type="has_property"
    )

    # Edge 2: PropertyNode --has_data_provenance--> ExtractorNode
    graph.add_edge(
        edge_id=f"{prop_node.node_id}_has_data_provenance_{extractor.node_id}",
        edge_source=prop_node.node_id,
        edge_target=extractor.node_id,
        edge_type="has_data_provenance"
    )

    # Edge 3: ExtractorNode --extracted_from--> DocumentNode
    graph.add_edge(
        edge_id=f"{extractor.node_id}_extracted_from_{doc_node.node_id}",
        edge_source=extractor.node_id,
        edge_target=doc_node.node_id,
        edge_type="extracted_from"
    )

    # Edge 4: DocumentNode --has_representation_model--> RM (ensure exists)
    _ensure_edge(graph, doc_node.node_id, rm_node.node_id,
                 "has_representation_model")

    # ── 7. Apply EM naming (rename proxy to US name) ────────────────
    assign_em_naming(areale_obj, graph, us_node.name, context)
    # Update PropertyNode value with the final proxy name
    prop_node.value = areale_obj.name

    # ── 8. Refresh UI lists ───────────────────────────────────────────
    # ``us_is_new=False`` is correct now: Surface Areas never creates
    # a US inline — the user either picks an existing one or hits the
    # "+" button which goes through the shared dialog (which populates
    # the Stratigraphy Manager list itself).
    _refresh_lists(context, graph, doc_node=doc_node, extractor_node=extractor,
                   us_node=us_node, prop_node=prop_node,
                   us_is_new=False)

    return us_node, "; ".join(messages)


# ══════════════════════════════════════════════════════════════════════
# INTERNAL HELPERS
# ══════════════════════════════════════════════════════════════════════

def _ensure_edge(graph, source_id, target_id, edge_type):
    """Create an edge only if it doesn't already exist."""
    for edge in graph.edges:
        if (edge.edge_source == source_id and
                edge.edge_target == target_id and
                edge.edge_type == edge_type):
            return  # Already exists
    graph.add_edge(
        edge_id=f"{source_id}_{edge_type}_{target_id}",
        edge_source=source_id,
        edge_target=target_id,
        edge_type=edge_type
    )


def _get_next_extractor_name(graph, doc_name):
    """
    Get the next available extractor name for a document.
    Pattern: {doc_name}.{next_number} e.g. D.10016.1, D.10016.2
    Same pattern used by proxy_box_creator/create_enhanced.py
    """
    prefix = f"{doc_name}."
    max_num = 0
    for node in graph.nodes:
        if not hasattr(node, 'node_type') or node.node_type != 'extractor':
            continue
        if not hasattr(node, 'name') or not isinstance(node.name, str):
            continue
        if node.name.startswith(prefix):
            suffix = node.name[len(prefix):]
            try:
                num = int(suffix)
                max_num = max(max_num, num)
            except ValueError:
                # Could be nested like D.10016.1.5 — try last part
                parts = suffix.split('.')
                try:
                    num = int(parts[0])
                    max_num = max(max_num, num)
                except (ValueError, IndexError):
                    continue
    return f"{doc_name}.{max_num + 1}"


# ``_create_us_node`` / ``_link_us_to_epoch`` /
# ``_link_us_stratigraphically`` — gone. The Surface Areas flow no
# longer creates US inline; the shared ``strat.add_us`` dialog
# (which delegates to :func:`us_helpers.create_us_node`) owns all of
# that.


def _refresh_lists(context, graph, doc_node=None, extractor_node=None,
                   us_node=None, prop_node=None, us_is_new=False):
    """Refresh EM UI lists so new nodes appear immediately.
    Only populates US if us_is_new=True (avoids duplicating existing US).
    Document and Extractor use populate_*_node which already checks for duplicates."""
    scene = context.scene
    try:
        from ..populate_lists import (
            populate_document_node, populate_extractor_node,
            populate_stratigraphic_node, build_instance_chains
        )

        # populate_document_node already checks for duplicates (by id_node)
        if doc_node:
            idx = len(scene.em_tools.em_sources_list)
            populate_document_node(scene, doc_node, idx, graph=graph)

        if extractor_node:
            idx = len(scene.em_tools.em_extractors_list)
            populate_extractor_node(scene, extractor_node, idx, graph=graph)

        # Only populate US if it's newly created (not an existing one selected by user)
        if us_node and us_is_new:
            idx = len(scene.em_tools.stratigraphy.units)
            chains = build_instance_chains(graph) if graph else {}
            populate_stratigraphic_node(scene, us_node, idx, graph=graph,
                                        instance_chains=chains)

        # Sync doc_list for Document Manager
        try:
            from ..document_manager.data import sync_doc_list
            sync_doc_list(scene)
        except Exception as e:
            print(f"[SurfaceAreale] doc_list sync: {e}")

    except Exception as e:
        print(f"[SurfaceAreale] List refresh failed: {e}")
        import traceback
        traceback.print_exc()
