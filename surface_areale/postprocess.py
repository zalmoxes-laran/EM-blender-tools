"""
Post-processing for Surface Areale meshes.
Handles normal offset, decimation, EM naming, material assignment,
and graph linking.
"""

import bpy
import bmesh
import uuid
from mathutils import Vector
from mathutils.bvhtree import BVHTree


def apply_normal_offset(obj, bvh_tree, offset_distance):
    """
    Offset each vertex of the areale mesh along the RM surface normal.
    Prevents z-fighting with the underlying RM.
    """
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
    """
    Decimate the areale mesh while preserving boundary edges.
    """
    mesh = obj.data

    current_tris = len(mesh.polygons)
    if current_tris <= max_triangles:
        return

    bm = bmesh.new()
    bm.from_mesh(mesh)

    boundary_verts = set()
    for edge in bm.edges:
        if edge.is_boundary:
            boundary_verts.add(edge.verts[0].index)
            boundary_verts.add(edge.verts[1].index)

    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges[:], dist=max_error * 0.5)

    bmesh.ops.dissolve_limit(
        bm,
        angle_limit=0.087,
        verts=[v for v in bm.verts if v.index not in boundary_verts],
        edges=[e for e in bm.edges if not e.is_boundary],
    )

    bm.to_mesh(mesh)
    bm.free()
    mesh.update()

    if len(mesh.polygons) > max_triangles:
        mod = obj.modifiers.new("Decimate", 'DECIMATE')
        mod.ratio = max_triangles / len(mesh.polygons)
        mod.use_collapse_triangulate = True
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.modifier_apply(modifier=mod.name)


def assign_em_naming(obj, graph, us_node_name, settings, context):
    """Apply EM naming convention to the areale object."""
    try:
        from ..operators.addon_prefix_helpers import node_name_to_proxy_name
        if us_node_name and graph:
            proxy_name = node_name_to_proxy_name(us_node_name, context, graph)
            obj.name = proxy_name
        elif us_node_name:
            obj.name = us_node_name
    except Exception as e:
        print(f"[SurfaceAreale] Warning: could not apply EM naming: {e}")
        if us_node_name:
            obj.name = us_node_name


def assign_em_material(obj, us_type, alpha=0.5):
    """
    Create and assign a material based on the US type.
    """
    colors = {
        'UL': (0.9, 0.6, 0.2),
        'TSU': (0.8, 0.2, 0.2),
        'US_NEG': (0.3, 0.3, 0.3),
        'US': (0.4, 0.6, 0.9),
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

        nodes = mat.node_tree.nodes
        principled = None
        for node in nodes:
            if node.type == 'BSDF_PRINCIPLED':
                principled = node
                break

        if principled:
            principled.inputs['Base Color'].default_value = (*color, 1.0)
            principled.inputs['Alpha'].default_value = alpha
            principled.inputs['Roughness'].default_value = 0.8
            try:
                principled.inputs['Specular IOR Level'].default_value = 0.0
            except KeyError:
                pass

    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)


def link_areale_to_graph(context, areale_obj, rm_obj, settings):
    """
    Link the areale to the stratigraphic graph.
    Creates US node, extractor, document connections.

    Returns:
        Tuple (us_node, success_message) or (None, error_message)
    """
    from s3dgraphy import get_graph

    em_tools = context.scene.em_tools
    if em_tools.active_file_index < 0:
        return None, "No active graph file"

    graph_info = em_tools.graphml_files[em_tools.active_file_index]
    graph = get_graph(graph_info.name)

    if not graph:
        return None, "Graph not loaded"

    us_node = None
    messages = []

    if settings.us_type == 'GENERIC':
        return None, "Generic proxy — link manually later"

    # ── 1. Find or create US node ─────────────────────────────────────
    if settings.create_new_us and settings.new_us_name:
        us_node = _create_us_node(graph, settings)
        messages.append(f"Created US: {us_node.name}")
        if us_node and settings.new_us_epoch:
            if _link_us_to_epoch(graph, us_node, settings.new_us_epoch):
                messages.append(f"Linked to epoch: {settings.new_us_epoch}")
        if us_node and settings.link_to_existing_us:
            _link_us_stratigraphically(graph, us_node, settings.link_to_existing_us)
    elif settings.linked_us_name:
        for node in graph.nodes:
            if hasattr(node, 'name') and node.name == settings.linked_us_name:
                us_node = node
                break

    if not us_node:
        return None, "No US node created or found"

    # ── 2. Set geometry attribute on US ───────────────────────────────
    us_node.attributes['geometry'] = areale_obj.name
    messages.append(f"Set geometry={areale_obj.name} on {us_node.name}")

    # ── 3. Find or create Document ────────────────────────────────────
    doc_node = None

    # First: check if already detected (linked_document field)
    if settings.linked_document:
        doc_node = _find_node_by_name(graph, settings.linked_document, 'document')

    # Second: auto-detect from RM graph connections
    if not doc_node:
        doc_node = _find_rm_document(graph, rm_obj)

    # Third: create or pick based on user choice
    if not doc_node:
        if settings.create_new_document and settings.new_doc_name:
            doc_node = _create_document_node(graph, settings)
            _link_document_to_rm(graph, doc_node, rm_obj)
            messages.append(f"Created document: {doc_node.name}")
        elif not settings.create_new_document and settings.existing_document:
            doc_node = _find_node_by_name(graph, settings.existing_document, 'document')
            if doc_node:
                _link_document_to_rm(graph, doc_node, rm_obj)
                messages.append(f"Linked existing document: {doc_node.name}")

    if not doc_node:
        messages.append("WARNING: No document — extractor not created")
        assign_em_naming(areale_obj, graph, us_node.name, settings, context)
        return us_node, "; ".join(messages)

    # ── 4. Create Extractor node ──────────────────────────────────────
    from s3dgraphy.nodes import ExtractorNode

    extractor = ExtractorNode(
        node_id=str(uuid.uuid4()),
        name=f"E.{us_node.name}",
        description=f"3D drawing on surface for {us_node.name}"
    )
    extractor.attributes['purpose'] = '3D drawing on surface'
    extractor.attributes['source_rm'] = rm_obj.name
    graph.add_node(extractor)
    messages.append(f"Created extractor: {extractor.name}")

    # Edge: Document → Extractor (has_extractor)
    graph.add_edge(
        edge_id=f"{doc_node.node_id}_has_extractor_{extractor.node_id}",
        edge_source=doc_node.node_id,
        edge_target=extractor.node_id,
        edge_type="has_extractor"
    )

    # Edge: Extractor → US (is_combined_in or a property link)
    # The extractor provides the geometry for the US, link via has_property or
    # a direct edge. Use "has_documentation" from US → Document as the semantic link.
    # For now, connect US → Document via has_documentation if not already connected.
    _ensure_us_has_documentation(graph, us_node, doc_node)

    # ── 5. Apply EM naming ────────────────────────────────────────────
    assign_em_naming(areale_obj, graph, us_node.name, settings, context)

    # ── 6. Refresh UI lists so new nodes appear immediately ───────────
    _refresh_lists_after_creation(context, graph, doc_node, extractor, us_node)

    return us_node, "; ".join(messages)


# ══════════════════════════════════════════════════════════════════════
# INTERNAL HELPERS
# ══════════════════════════════════════════════════════════════════════

def _find_node_by_name(graph, name, node_type=None):
    """Find a graph node by its name, optionally filtering by node_type."""
    for node in graph.nodes:
        if not hasattr(node, 'name') or node.name != name:
            continue
        if node_type and hasattr(node, 'node_type') and node.node_type != node_type:
            continue
        return node
    return None


def _create_us_node(graph, settings):
    """Create a new stratigraphic node based on the US type."""
    from s3dgraphy.nodes import (
        StratigraphicUnit,
        TransformationStratigraphicUnit,
        WorkingUnit,
    )

    node_id = str(uuid.uuid4())
    name = settings.new_us_name

    type_map = {
        'UL': WorkingUnit,
        'TSU': TransformationStratigraphicUnit,
        'US_NEG': StratigraphicUnit,
        'US': StratigraphicUnit,
    }

    node_class = type_map.get(settings.us_type, StratigraphicUnit)
    us_node = node_class(node_id=node_id, name=name)
    graph.add_node(us_node)

    return us_node


def _link_us_to_epoch(graph, us_node, epoch_name):
    """Link US node to an epoch via has_first_epoch."""
    for node in graph.nodes:
        if hasattr(node, 'name') and node.name == epoch_name:
            graph.add_edge(
                edge_id=f"{us_node.node_id}_has_first_epoch_{node.node_id}",
                edge_source=us_node.node_id,
                edge_target=node.node_id,
                edge_type="has_first_epoch"
            )
            return True
    return False


def _link_us_stratigraphically(graph, us_node, target_us_name):
    """Create a stratigraphic relationship between two US nodes."""
    for node in graph.nodes:
        if hasattr(node, 'name') and node.name == target_us_name:
            graph.add_edge(
                edge_id=f"{us_node.node_id}_is_after_{node.node_id}",
                edge_source=us_node.node_id,
                edge_target=node.node_id,
                edge_type="is_after"
            )
            return True
    return False


def _find_rm_document(graph, rm_obj):
    """Find a DocumentNode connected to the RM via has_representation_model."""
    # Try to find RM node by object name (with or without graph prefix)
    rm_node = _find_rm_node_in_graph(graph, rm_obj)

    if not rm_node:
        return None

    # Look for edges: Document --has_representation_model--> RM
    for edge in graph.edges:
        if (edge.edge_target == rm_node.node_id and
                edge.edge_type == "has_representation_model"):
            source = graph.find_node_by_id(edge.edge_source)
            if source and hasattr(source, 'node_type') and source.node_type == 'document':
                return source

    return None


def _find_rm_node_in_graph(graph, rm_obj):
    """Find the RM node in the graph, handling graph-prefixed names."""
    rm_name = rm_obj.name

    # Direct match
    for node in graph.nodes:
        if hasattr(node, 'name') and node.name == rm_name:
            if hasattr(node, 'node_type') and 'representation' in node.node_type.lower():
                return node

    # Try stripping graph prefix
    try:
        from ..operators.addon_prefix_helpers import proxy_name_to_node_name
        clean_name = proxy_name_to_node_name(rm_name, bpy.context, graph)
        if clean_name != rm_name:
            for node in graph.nodes:
                if hasattr(node, 'name') and node.name == clean_name:
                    return node
    except Exception:
        pass

    # Broader match: any RepresentationModelNode whose name is in the object name
    for node in graph.nodes:
        if not hasattr(node, 'node_type'):
            continue
        if 'representation' not in node.node_type.lower():
            continue
        if hasattr(node, 'name') and node.name and node.name in rm_name:
            return node

    return None


def _create_document_node(graph, settings):
    """Create a new DocumentNode."""
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


def _link_document_to_rm(graph, doc_node, rm_obj):
    """Create edge: DocumentNode --has_representation_model--> RepresentationModelNode."""
    rm_node = _find_rm_node_in_graph(graph, rm_obj)

    if not rm_node:
        print(f"[SurfaceAreale] Warning: could not find RM node for {rm_obj.name}")
        return False

    # Check if edge already exists
    for edge in graph.edges:
        if (edge.edge_source == doc_node.node_id and
                edge.edge_target == rm_node.node_id and
                edge.edge_type == "has_representation_model"):
            return True  # Already linked

    graph.add_edge(
        edge_id=f"{doc_node.node_id}_has_representation_model_{rm_node.node_id}",
        edge_source=doc_node.node_id,
        edge_target=rm_node.node_id,
        edge_type="has_representation_model"
    )
    return True


def _ensure_us_has_documentation(graph, us_node, doc_node):
    """Ensure the US node is connected to the document via has_documentation."""
    # Check if edge already exists
    for edge in graph.edges:
        if (edge.edge_source == us_node.node_id and
                edge.edge_target == doc_node.node_id and
                edge.edge_type == "has_documentation"):
            return

    graph.add_edge(
        edge_id=f"{us_node.node_id}_has_documentation_{doc_node.node_id}",
        edge_source=us_node.node_id,
        edge_target=doc_node.node_id,
        edge_type="has_documentation"
    )


def _refresh_lists_after_creation(context, graph, doc_node, extractor_node, us_node):
    """
    Refresh the EM UI lists after creating new nodes in the graph.
    This ensures new documents/extractors/US appear immediately in the UI
    without requiring a full graph re-import.
    """
    scene = context.scene

    try:
        from ..populate_lists import (
            populate_document_node,
            populate_extractor_node,
            populate_stratigraphic_node,
            build_instance_chains
        )

        # Refresh document list
        if doc_node:
            idx = len(scene.em_tools.em_sources_list)
            populate_document_node(scene, doc_node, idx, graph=graph)
            print(f"[SurfaceAreale] Populated document node: {doc_node.name}")

        # Refresh extractor list
        if extractor_node:
            idx = len(scene.em_tools.em_extractors_list)
            populate_extractor_node(scene, extractor_node, idx, graph=graph)
            print(f"[SurfaceAreale] Populated extractor node: {extractor_node.name}")

        # Refresh stratigraphic list for the new US
        if us_node:
            idx = len(scene.em_tools.stratigraphy.units)
            instance_chains = build_instance_chains(graph) if graph else {}
            populate_stratigraphic_node(scene, us_node, idx, graph=graph,
                                        instance_chains=instance_chains)
            print(f"[SurfaceAreale] Populated stratigraphic node: {us_node.name}")

        # Sync doc_list (used by 3D Document Manager)
        try:
            from ..document_manager.data import sync_doc_list
            sync_doc_list(scene)
            print("[SurfaceAreale] Synced doc_list")
        except Exception as e:
            print(f"[SurfaceAreale] Warning: doc_list sync failed: {e}")

    except Exception as e:
        print(f"[SurfaceAreale] Warning: list refresh failed: {e}")
        import traceback
        traceback.print_exc()
