"""Create Proxy from the seven recorded points (DP-47 / DP-07 flow).

The flow is always paradata-driven: Step 1 has already anchored the
proxy on a DocumentNode, Step 2 has recorded 7 points each carrying a
source document and an extractor id. This operator materialises the
graph side (extractors + combiner + PropertyNode hook into the active
US) and the scene side (extractor empties + combiner empty + proxy
mesh), all prefixed with the graph_code per DP-46.
"""

from __future__ import annotations

import bpy  # type: ignore
from bpy.types import Operator  # type: ignore
from mathutils import Vector  # type: ignore


def _resolve_target_us(context):
    """Return the target Stratigraphic Unit item used by this run.

    Prefers ``settings.target_us_name`` (ProxyBox's own picker);
    falls back to the Stratigraphy Manager's ``units[units_index]``
    when it's empty. Returns the ``EMListItem`` or ``None``.
    """
    scene = context.scene
    em_tools = scene.em_tools
    strat = em_tools.stratigraphy
    settings = em_tools.proxy_box
    if settings.target_us_name:
        for u in strat.units:
            if u.name == settings.target_us_name:
                return u
        return None
    if (strat.units
            and 0 <= strat.units_index < len(strat.units)):
        return strat.units[strat.units_index]
    return None


class PROXYBOX_OT_create_proxy_enhanced(Operator):
    """Create the proxy box mesh plus the full paradata chain."""
    bl_idname = "proxybox.create_proxy_enhanced"
    bl_label = "Create Proxy"
    bl_description = (
        "Create the proxy box mesh, the 7 extractor empties, the "
        "combiner empty, and the graph-side paradata chain anchored "
        "on the Step-1 Document and hooked into the active US."
    )
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        settings = context.scene.em_tools.proxy_box
        if len(settings.points) < 7:
            return False
        if not all(p.is_recorded for p in settings.points[:7]):
            return False
        if not all(p.source_document for p in settings.points[:7]):
            return False
        if not all(p.extractor_id for p in settings.points[:7]):
            return False
        return True

    def execute(self, context):
        scene = context.scene
        em_tools = scene.em_tools
        settings = em_tools.proxy_box
        points = [Vector(p.position) for p in settings.points[:7]]

        # ── Active US resolution ────────────────────────────────────
        us_item = _resolve_target_us(context)
        if us_item is None or not us_item.name:
            self.report(
                {'ERROR'},
                "No Active Stratigraphic Unit — pick one in the "
                "Proxy Box panel or select it in the Stratigraphy "
                "Manager.")
            return {'CANCELLED'}
        proxy_name = us_item.name

        # ── Graph access + write-lock pre-flight ────────────────────
        from s3dgraphy import get_graph
        if em_tools.active_file_index < 0:
            self.report({'ERROR'},
                        "No active graph file. Load a GraphML first.")
            return {'CANCELLED'}
        graph_info = em_tools.graphml_files[em_tools.active_file_index]
        graph = get_graph(graph_info.name)
        if not graph:
            self.report({'ERROR'}, "Graph not loaded")
            return {'CANCELLED'}

        from ..functions import normalize_path
        from ..graphml_lock import abort_if_graphml_locked
        target_path = normalize_path(graph_info.graphml_path or "")
        if target_path and not abort_if_graphml_locked(self, target_path):
            return {'CANCELLED'}

        graph_code = getattr(graph_info, "graph_code", "") or ""

        # ── 1. Extractors in graph + empties in scene ────────────────
        extractors_collection = self._ensure_extractors_collection(context)
        extractor_objects = []
        for point in settings.points[:7]:
            ok = self._create_extractor_in_graph(
                graph,
                point.source_document,
                point.extractor_id,
                point.point_type,
                point.position,
            )
            if ok:
                empty = self._create_extractor_empty(
                    context, point.extractor_id, point.position,
                    extractors_collection, graph_code=graph_code,
                )
                extractor_objects.append(empty)
            else:
                self.report({'WARNING'},
                            f"Failed to create extractor: "
                            f"{point.extractor_id}")

        # ── 2. Combiner ──────────────────────────────────────────────
        combiner_id = self._create_combiner(
            context, graph, extractor_objects, proxy_name,
            graph_code=graph_code)
        if combiner_id:
            settings.combiner_id = combiner_id
            self.report({'INFO'}, f"Created combiner: {combiner_id}")
            linked = self._link_combiner_to_us(
                context, graph, combiner_id, us_item)
            if linked:
                self.report(
                    {'INFO'},
                    f"Linked combiner to US {us_item.name!r} via "
                    f"PropertyNode 'proxy_geometry'")
            else:
                self.report(
                    {'WARNING'},
                    f"Combiner created but not linked to US "
                    f"{us_item.name!r} — check that the US has a "
                    f"valid id_node.")

        # ── 3. Proxy geometry ────────────────────────────────────────
        proxy_obj = self._create_proxy_geometry(
            context, points, proxy_name, settings)
        if not proxy_obj:
            self.report({'ERROR'}, "Failed to create proxy geometry")
            return {'CANCELLED'}
        if graph_code and not proxy_obj.name.startswith(f"{graph_code}."):
            proxy_obj.name = f"{graph_code}.{proxy_obj.name}"
        if combiner_id:
            proxy_obj["em_combiner_id"] = combiner_id

        self.report({'INFO'}, f"Proxy created: {proxy_obj.name}")
        return {'FINISHED'}

    # ── scene / graph builders ──────────────────────────────────────

    def _ensure_extractors_collection(self, context):
        scene = context.scene
        if "Extractors" in bpy.data.collections:
            return bpy.data.collections["Extractors"]
        extractors_col = bpy.data.collections.new("Extractors")
        scene.collection.children.link(extractors_col)
        return extractors_col

    def _create_extractor_in_graph(self, graph, doc_name, extractor_id,
                                    point_type, position):
        """Create an ExtractorNode under ``doc_name`` and the edge
        ``Document --has_extractor--> Extractor``. ``doc_name`` is the
        display name (e.g. ``D.10``); the DocumentNode is looked up
        by ``node.name`` to keep the pattern consistent with how the
        old flow wrote them.
        """
        try:
            import uuid
            from s3dgraphy.nodes import ExtractorNode
            extractor = ExtractorNode(
                node_id=str(uuid.uuid4()),
                name=extractor_id,
                description=f"Extractor for {point_type} point",
            )
            extractor.attributes['point_type'] = point_type
            extractor.attributes['x'] = position.x
            extractor.attributes['y'] = position.y
            extractor.attributes['z'] = position.z
            extractor.attributes['purpose'] = "proxy_box_creator"
            extractor.attributes['description'] = (
                f"Extractor for {point_type} point")
            graph.add_node(extractor)

            doc_node = None
            for node in graph.nodes:
                if (hasattr(node, 'name')
                        and node.name == doc_name
                        and getattr(node, 'node_type', '') == 'document'):
                    doc_node = node
                    break
            if not doc_node:
                print(f"✗ Error: Could not find document with name: "
                      f"{doc_name}")
                return False
            edge_id = f"{doc_node.node_id}_extracts_{extractor.node_id}"
            graph.add_edge(
                edge_id=edge_id,
                edge_source=doc_node.node_id,
                edge_target=extractor.node_id,
                edge_type="has_extractor",
            )
            return True
        except Exception as e:
            print(f"Error creating extractor in graph: {e}")
            return False

    def _create_extractor_empty(self, context, extractor_id, position,
                                 collection, graph_code=""):
        """Create an empty in the scene for the extractor. Name =
        ``{graph_code}.{extractor_id}`` (DP-46) so scene-side elements
        round-trip across graph imports.
        """
        obj_name = (f"{graph_code}.{extractor_id}"
                    if graph_code else extractor_id)
        empty = bpy.data.objects.new(obj_name, None)
        empty.location = position
        empty.empty_display_type = 'SPHERE'
        empty.empty_display_size = 0.1
        collection.objects.link(empty)
        empty["em_extractor_id"] = extractor_id
        empty["em_node_type"] = "extractor"
        empty["em_graph_code"] = graph_code
        return empty

    def _create_combiner(self, context, graph, extractor_objects,
                          proxy_name, graph_code=""):
        """Create a combiner node and empty; link every extractor to
        the combiner via ``is_combined_in``.
        """
        try:
            from s3dgraphy.nodes import CombinerNode
            max_num = 0
            for node in graph.nodes:
                if not hasattr(node, 'node_type') \
                        or not hasattr(node, 'name'):
                    continue
                if node.node_type != "combiner":
                    continue
                if not isinstance(node.name, str):
                    continue
                if node.name.startswith('C.'):
                    try:
                        n = int(node.name.split('.')[1])
                        max_num = max(max_num, n)
                    except (ValueError, IndexError):
                        continue
            combiner_id = f"C.{max_num + 1}"
            combiner = CombinerNode(
                node_id=combiner_id,
                name=f"Proxy_{proxy_name}",
            )
            combiner.attributes['purpose'] = "proxy_box_creator"
            combiner.attributes['description'] = (
                "Combiner for proxy box measurement points")
            graph.add_node(combiner)
            for ext_obj in extractor_objects:
                extractor_id = ext_obj.get("em_extractor_id", "")
                if extractor_id:
                    edge_id = (f"{extractor_id}_combines_to_"
                               f"{combiner_id}")
                    graph.add_edge(
                        edge_id=edge_id,
                        edge_source=extractor_id,
                        edge_target=combiner_id,
                        edge_type="is_combined_in",
                    )

            empty_name = (f"{graph_code}.{combiner_id}"
                          if graph_code else combiner_id)
            combiner_empty = bpy.data.objects.new(empty_name, None)
            if extractor_objects:
                centroid = (sum(
                    (obj.location for obj in extractor_objects),
                    Vector()) / len(extractor_objects))
                combiner_empty.location = centroid
            combiner_empty.empty_display_type = 'CUBE'
            combiner_empty.empty_display_size = 0.3
            self._ensure_extractors_collection(context) \
                .objects.link(combiner_empty)
            combiner_empty["em_combiner_id"] = combiner_id
            combiner_empty["em_node_type"] = "combiner"
            combiner_empty["em_graph_code"] = graph_code
            return combiner_id
        except Exception as e:
            print(f"Error creating combiner: {e}")
            return None

    def _link_combiner_to_us(self, context, graph, combiner_id, us_item):
        """Hook the Combiner into the target US's paradata chain:

            US --has_property--> PropertyNode("proxy_geometry")
            PropertyNode --has_data_provenance--> Combiner

        Reuses an existing ``proxy_geometry`` PropertyNode on the US
        when present — re-running the Proxy Box Creator on the same US
        adds another has_data_provenance edge to the shared PN instead
        of duplicating intermediaries.
        """
        us_node_id = getattr(us_item, "id_node", "") or ""
        if not us_node_id:
            return False
        us_node = graph.find_node_by_id(us_node_id)
        if us_node is None:
            return False
        pn_node = None
        for edge in graph.edges:
            if (edge.edge_source == us_node_id
                    and edge.edge_type == "has_property"):
                candidate = graph.find_node_by_id(edge.edge_target)
                if candidate is None:
                    continue
                cname = getattr(candidate, "name", "") or ""
                ctype = (getattr(candidate, "data", None) or {}).get(
                    "property_type", "")
                if cname == "proxy_geometry" \
                        or ctype == "proxy_geometry":
                    pn_node = candidate
                    break
        if pn_node is None:
            import uuid
            from s3dgraphy.nodes.property_node import PropertyNode
            pn_node = PropertyNode(
                node_id=str(uuid.uuid4()),
                name="proxy_geometry",
                property_type="proxy_geometry",
                value="",
                description="7-point proxy box geometry declared "
                            "from measurement points.",
            )
            graph.add_node(pn_node)
            graph.add_edge(
                edge_id=(f"{us_node_id}_has_property_"
                         f"{pn_node.node_id}"),
                edge_source=us_node_id,
                edge_target=pn_node.node_id,
                edge_type="has_property",
            )
        prov_edge_id = (f"{pn_node.node_id}_has_data_provenance_"
                        f"{combiner_id}")
        if not any(e.edge_id == prov_edge_id for e in graph.edges):
            graph.add_edge(
                edge_id=prov_edge_id,
                edge_source=pn_node.node_id,
                edge_target=combiner_id,
                edge_type="has_data_provenance",
            )
        return True

    def _create_proxy_geometry(self, context, points, proxy_name,
                                settings):
        """Build the proxy box mesh and move it into the Proxy
        collection when requested.
        """
        from .utils import calculate_box_geometry, create_box_mesh
        try:
            geometry = calculate_box_geometry(points)
        except Exception as e:
            print(f"Error calculating geometry: {e}")
            return None
        try:
            proxy_obj = create_box_mesh(
                proxy_name, geometry, settings.pivot_location)
        except Exception as e:
            print(f"Error creating mesh: {e}")
            return None
        if settings.use_proxy_collection:
            proxy_col = bpy.data.collections.get("Proxy")
            if proxy_col is None:
                proxy_col = bpy.data.collections.new("Proxy")
                context.scene.collection.children.link(proxy_col)
            for col in proxy_obj.users_collection:
                col.objects.unlink(proxy_obj)
            proxy_col.objects.link(proxy_obj)
        return proxy_obj


classes = [PROXYBOX_OT_create_proxy_enhanced]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
