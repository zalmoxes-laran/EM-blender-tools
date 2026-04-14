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

def apply_normal_offset(obj, bvh_tree, offset_distance):
    """Offset each vertex along the RM surface normal (anti z-fighting)."""
    mesh = obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    for v in bm.verts:
        location, normal, index, dist = bvh_tree.find_nearest(v.co)
        if location is not None and normal is not None:
            v.co = Vector(location) + Vector(normal) * offset_distance
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()


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
    """Create and assign a semi-transparent material based on the US type."""
    colors = {
        'UL': (0.9, 0.6, 0.2), 'TSU': (0.8, 0.2, 0.2),
        'US_NEG': (0.3, 0.3, 0.3), 'US': (0.4, 0.6, 0.9),
        'GENERIC': (0.7, 0.7, 0.7),
    }
    color = colors.get(us_type, (0.7, 0.7, 0.7))
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
    """Find a DocumentNode connected to the RM via has_representation_model."""
    rm_node = find_rm_node_in_graph(scene, graph, rm_obj)
    if not rm_node:
        return None
    # Document --has_representation_model--> RM (so RM is the target)
    for edge in graph.edges:
        if (edge.edge_target == rm_node.node_id and
                edge.edge_type == "has_representation_model"):
            source = graph.find_node_by_id(edge.edge_source)
            if source and hasattr(source, 'node_type') and source.node_type == 'document':
                return source
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
# GRAPH CHAIN CREATION
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

    if settings.us_type == 'GENERIC':
        return None, "Generic proxy — link manually later"

    # ── 1. Find RepresentationModelNode (create if missing from graph) ─
    rm_node = find_rm_node_in_graph(scene, graph, rm_obj, create_if_missing=True)
    if not rm_node:
        return None, f"RM node not found and could not be created for {rm_obj.name}"

    # ── 2. Find or create DocumentNode ────────────────────────────────
    doc_node = find_rm_document(scene, graph, rm_obj)

    if not doc_node:
        if settings.create_new_document and settings.new_doc_name:
            doc_node = _create_document_node(graph, settings)
            # Edge: Document --has_representation_model--> RM
            _ensure_edge(graph, doc_node.node_id, rm_node.node_id,
                         "has_representation_model")
            messages.append(f"Created document: {doc_node.name}")
        elif not settings.create_new_document and settings.existing_document:
            doc_node = _find_node_by_name(graph, settings.existing_document, 'document')
            if doc_node:
                _ensure_edge(graph, doc_node.node_id, rm_node.node_id,
                             "has_representation_model")
                messages.append(f"Linked document: {doc_node.name}")

    if not doc_node:
        return None, "No document — cannot create paradata chain"

    # ── 3. Find or create US node ─────────────────────────────────────
    us_node = None
    if settings.create_new_us and settings.new_us_name:
        us_node = _create_us_node(graph, settings)
        messages.append(f"Created US: {us_node.name}")
        if settings.new_us_epoch:
            _link_us_to_epoch(graph, us_node, settings.new_us_epoch)
        if settings.link_to_existing_us:
            _link_us_stratigraphically(graph, us_node, settings.link_to_existing_us)
    elif settings.linked_us_name:
        us_node = _find_node_by_name(graph, settings.linked_us_name)

    if not us_node:
        return None, "No US node created or found"

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
    _refresh_lists(context, graph, doc_node=doc_node, extractor_node=extractor,
                   us_node=us_node, prop_node=prop_node,
                   us_is_new=settings.create_new_us)

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


def _create_us_node(graph, settings):
    """Create a new stratigraphic node based on the selected US type."""
    from s3dgraphy.nodes import (
        StratigraphicUnit, TransformationStratigraphicUnit, WorkingUnit
    )
    type_map = {
        'UL': WorkingUnit,
        'TSU': TransformationStratigraphicUnit,
        'US_NEG': StratigraphicUnit,
        'US': StratigraphicUnit,
    }
    node_class = type_map.get(settings.us_type, StratigraphicUnit)
    us_node = node_class(node_id=str(uuid.uuid4()), name=settings.new_us_name)
    graph.add_node(us_node)
    return us_node


def _link_us_to_epoch(graph, us_node, epoch_name):
    """Link US to an epoch via has_first_epoch."""
    for node in graph.nodes:
        if hasattr(node, 'name') and node.name == epoch_name:
            _ensure_edge(graph, us_node.node_id, node.node_id, "has_first_epoch")
            return True
    return False


def _link_us_stratigraphically(graph, us_node, target_us_name):
    """Create is_after relationship between two US nodes."""
    for node in graph.nodes:
        if hasattr(node, 'name') and node.name == target_us_name:
            _ensure_edge(graph, us_node.node_id, node.node_id, "is_after")
            return True
    return False


def _create_document_node(graph, settings):
    """Create a new DocumentNode. Returns existing node if name already taken."""
    # Check if a document with this name already exists
    existing = _find_node_by_name(graph, settings.new_doc_name, 'document')
    if existing:
        print(f"[SurfaceAreale] Document '{settings.new_doc_name}' already exists, reusing it")
        return existing

    from s3dgraphy.nodes import DocumentNode
    doc_node = DocumentNode(
        node_id=str(uuid.uuid4()),
        name=settings.new_doc_name,
        description=f"Document created by Surface Areale tool"
    )
    if settings.new_doc_date:
        doc_node.attributes['date'] = settings.new_doc_date
    graph.add_node(doc_node)
    return doc_node


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
