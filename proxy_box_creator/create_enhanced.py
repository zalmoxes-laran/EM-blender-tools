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
    """Return the Stratigraphic Unit item used by this run, or None.

    ``settings.target_us_name`` is a computed property backed by
    ``strat.units[strat.units_index].name`` — so resolving it is just
    a matter of returning the active unit (no fallback path needed).
    """
    scene = context.scene
    strat = scene.em_tools.stratigraphy
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

        # ── Optional: Create new US first ───────────────────────────
        # When the Create-new-US toggle is on we materialise the new
        # unit in the graph, populate the Stratigraphy Manager list,
        # and pin it as active — so the subsequent ``_resolve_target_us``
        # step just returns the one we just made.
        if settings.create_new_us:
            ok, msg = self._create_and_activate_new_us(scene, graph)
            if not ok:
                self.report({'ERROR'}, msg)
                return {'CANCELLED'}
            self.report({'INFO'}, msg)
            # Leave the toggle off after a successful creation so the
            # next Create run defaults to "reuse existing" instead of
            # trying to make another duplicate.
            settings.create_new_us = False

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

        # ── 1. Resolve the anchor DocumentNode (UUID-based) ─────────
        # The points carry source_document_id (UUID) populated at
        # Record time; we fall back to settings.document_node_id so a
        # propagate-off run still works as long as the Step-1 anchor
        # is set. NAME-based lookup would silently bind to a stale
        # D.X from another paradata chain when duplicates exist.
        anchor_doc_id = (settings.document_node_id or "").strip()
        point_doc_ids = {
            (p.source_document_id or anchor_doc_id)
            for p in settings.points[:7]}
        if not point_doc_ids or any(not d for d in point_doc_ids):
            self.report({'ERROR'},
                        "One or more points lack a source_document_id "
                        "— re-record with the Step-1 anchor set.")
            return {'CANCELLED'}

        # ── 1b. Clone the anchor Document into a fresh instance ─────
        # Each Proxy Box run gets its OWN DocumentNode instance (same
        # display name, fresh UUID, attributes copied from the master).
        # Without this the new extractors would attach to whichever
        # pre-existing ``D.XX`` instance was picked at Step 1 — an
        # instance typically already wrapped inside another PD node-
        # group, which is exactly what the user reported. The clone
        # carries ``em_master_document=True`` so the GraphMLPatcher
        # serialises it; ``attributes['original_emid']`` points back
        # to the master UUID so downstream tools can re-link the
        # instances (same convention used by the GraphMLExporter's
        # per-group document copies).
        doc_instance_id = self._clone_document_for_pd(
            graph, anchor_doc_id, us_item_name=None)
        if not doc_instance_id:
            self.report({'ERROR'},
                        f"Could not clone Document "
                        f"{anchor_doc_id!r} for this proxy's PD "
                        f"group.")
            return {'CANCELLED'}

        # ── 2. Extractors in graph + empties in scene ────────────────
        # Extractors attach to the CLONE (doc_instance_id), not the
        # master — that's the whole point of cloning above. The
        # per-point ``source_document_id`` (which still points at the
        # master) is kept for history / debugging but not used as the
        # edge target here.
        extractors_collection = self._ensure_extractors_collection(context)
        extractor_tuples: list = []  # [(empty, uuid), ...]
        for point in settings.points[:7]:
            ok, ext_uuid, err = self._create_extractor_in_graph(
                graph,
                doc_instance_id,
                point.extractor_id,
                point.point_type,
                point.position,
            )
            if ok:
                empty = self._create_extractor_empty(
                    context, point.extractor_id, point.position,
                    extractors_collection,
                    graph_code=graph_code,
                    extractor_uuid=ext_uuid,
                )
                extractor_tuples.append((empty, ext_uuid))
            else:
                self.report({'ERROR'},
                            f"Failed to create extractor "
                            f"{point.extractor_id!r}: {err}")
                return {'CANCELLED'}

        # ── 3. Combiner ──────────────────────────────────────────────
        combiner_display, combiner_uuid, err = self._create_combiner(
            context, graph, extractor_tuples, proxy_name,
            graph_code=graph_code)
        if not combiner_uuid:
            self.report({'ERROR'},
                        f"Combiner creation failed: {err}. The "
                        f"extractors are already in the graph — "
                        f"inspect and retry or revert.")
            return {'CANCELLED'}
        settings.combiner_id = combiner_display
        self.report({'INFO'}, f"Created combiner: {combiner_display}")
        # Pass the full chain identity to ``_link_combiner_to_us`` so
        # it can wrap PN + Combiner + Extractors + Document instance
        # (the clone, not the master) in a per-US ParadataNodeGroup.
        linked, err = self._link_combiner_to_us(
            context, graph, combiner_uuid, us_item,
            doc_node_id=doc_instance_id,
            extractor_uuids=[u for _empty, u in extractor_tuples])
        if linked:
            self.report(
                {'INFO'},
                f"Linked combiner to US {us_item.name!r} via "
                f"PropertyNode 'proxy_geometry'")
        else:
            self.report(
                {'WARNING'},
                f"Combiner created but not linked to US "
                f"{us_item.name!r}: {err}")

        # ── 4. Proxy geometry ────────────────────────────────────────
        proxy_obj = self._create_proxy_geometry(
            context, points, proxy_name, settings)
        if not proxy_obj:
            self.report({'ERROR'}, "Failed to create proxy geometry")
            return {'CANCELLED'}
        if graph_code and not proxy_obj.name.startswith(f"{graph_code}."):
            proxy_obj.name = f"{graph_code}.{proxy_obj.name}"
        proxy_obj["em_combiner_id"] = combiner_display
        proxy_obj["em_combiner_uuid"] = combiner_uuid

        # ── 4. Post-create refresh (mirror listitem.toobj semantics) ─
        # The proxy mesh is now the concrete object linked to the US,
        # so the em_list icon needs to flip to LINKED and the current
        # display-mode material has to be applied to the fresh object.
        self._refresh_display_after_create(context)

        # Leave the new proxy selected so the user sees the result.
        try:
            bpy.ops.object.select_all(action='DESELECT')
            proxy_obj.select_set(True)
            context.view_layer.objects.active = proxy_obj
        except Exception:
            pass

        # ── 5. Persist the paradata chain to .graphml ───────────────
        # The chain we just built — Document → Extractors → Combiner
        # → PropertyNode → US → Epoch — lives only in memory until
        # the user saves the file. Offer (and by default do) the save
        # here, per the DP-07 "salvataggio virtuoso" principle: the
        # paradata MUST be serialised or it's lost on crash. The
        # write-lock pre-flight already ran at the top of execute,
        # so yEd isn't holding the file.
        persisted = False
        if settings.persist_after_create:
            try:
                result = bpy.ops.export.graphml_update()
                persisted = 'FINISHED' in result
            except Exception as e:
                self.report({'WARNING'},
                            f"Auto-save failed: {e}. Save manually "
                            f"via Export > Update GraphML.")

        tag = " [persisted]" if persisted else ""
        self.report({'INFO'}, f"Proxy created: {proxy_obj.name}{tag}")
        return {'FINISHED'}

    def _create_and_activate_new_us(self, scene, graph):
        """Create the new Stratigraphic Unit described by
        ``scene.em_tools.proxy_box.{new_us_type, new_us_name,
        new_us_epoch}``, wire it into the graph, populate the
        Stratigraphy Manager list, and make it the active one.

        Contract:

        - ``new_us_name`` must be non-empty and must not collide with
          an existing US in the Stratigraphy Manager.
        - ``new_us_epoch`` MUST be non-empty — every US belongs to a
          first epoch (no year needed, but the epoch anchor is part
          of the paradata contract).
        - The type factory goes through :func:`us_types.get_us_class`,
          so adding a new node_type to s3dgraphy's JSON datamodel
          propagates here automatically.

        Returns ``(ok, message)``. On success the computed
        ``target_us_name`` property reflects the new unit because
        ``strat.units_index`` is pinned to it.
        """
        settings = scene.em_tools.proxy_box
        strat = scene.em_tools.stratigraphy
        new_name = (settings.new_us_name or "").strip()
        if not new_name:
            return False, "New US name is empty"
        if not settings.new_us_epoch:
            return False, (
                "New US has no epoch — every Stratigraphic Unit needs "
                "a first-epoch anchor (pick one from the 'Epoch' "
                "dropdown before creating).")
        # Duplicates — reject rather than silently reusing an existing
        # node (the Create flow depends on the US being fresh + active).
        for u in strat.units:
            if u.name == new_name:
                return False, (
                    f"Stratigraphic Unit {new_name!r} already exists — "
                    f"toggle off 'Create new US' and pick it from the "
                    f"Active US dropdown instead.")

        from ..us_types import get_us_class
        node_class = get_us_class(settings.new_us_type)
        if node_class is None:
            return False, (
                f"Unknown US type {settings.new_us_type!r} — check the "
                f"datamodel JSON")
        try:
            import uuid
            us_node = node_class(
                node_id=str(uuid.uuid4()), name=new_name)
            graph.add_node(us_node)
        except Exception as e:
            return False, f"Failed to create US node: {e}"

        # Epoch anchoring — mandatory. We've already checked that the
        # field is non-empty; here we fail hard if the named epoch
        # doesn't exist in the graph (user picked from a stale list).
        linked = False
        for n in graph.nodes:
            if (getattr(n, 'name', '') == settings.new_us_epoch
                    and type(n).__name__ == 'EpochNode'):
                edge_id = (f"{us_node.node_id}_has_first_epoch_"
                           f"{n.node_id}")
                if not any(e.edge_id == edge_id
                           for e in graph.edges):
                    try:
                        graph.add_edge(
                            edge_id=edge_id,
                            edge_source=us_node.node_id,
                            edge_target=n.node_id,
                            edge_type="has_first_epoch",
                        )
                        linked = True
                    except Exception:
                        pass
                else:
                    linked = True
                break
        if not linked:
            return False, (
                f"Epoch {settings.new_us_epoch!r} not found in graph "
                f"— refresh the epoch list and retry.")

        # Populate the Stratigraphy Manager list and pin the new US as
        # active so the computed ``target_us_name`` returns it.
        try:
            from ..populate_lists import (
                populate_stratigraphic_node, build_instance_chains)
            idx = len(strat.units)
            chains = build_instance_chains(graph)
            populate_stratigraphic_node(
                scene, us_node, idx,
                graph=graph, instance_chains=chains)
            strat.units_index = idx
        except Exception as e:
            return False, f"Failed to populate US list: {e}"

        return True, f"Created new US {new_name} (epoch: {settings.new_us_epoch})"

    def _refresh_display_after_create(self, context):
        """Mirror the post-link refresh done by ``listitem.toobj``:

        - Invalidate the object cache (name may be fresh).
        - ``update_icons(context, "em_list")`` so the Stratigraphy
          Manager's UIList icon flips to LINKED.
        - Re-apply the current ``proxy_display_mode`` so the new mesh
          gets the correct material (EM / Epochs / Properties).

        Silent best-effort — failures are reported but don't abort the
        Create flow (the geometry + graph are already in place).
        """
        try:
            from ..object_cache import invalidate_object_cache
            invalidate_object_cache()
        except Exception:
            pass
        try:
            from ..functions import update_icons
            update_icons(context, "em_list")
        except Exception as e:
            self.report({'WARNING'},
                        f"update_icons failed: {e}")
        try:
            scene = context.scene
            mode = scene.em_tools.proxy_display_mode
            if mode == "EM":
                bpy.ops.emset.emmaterial()
            elif mode in ("Epochs", "Horizons"):
                bpy.ops.emset.epochmaterial()
            elif mode == "Properties":
                if (getattr(scene, 'selected_property', None)
                        and hasattr(scene, 'property_values')
                        and len(scene.property_values) > 0):
                    bpy.ops.visual.apply_colors()
        except Exception as e:
            self.report({'WARNING'},
                        f"Display-mode refresh failed: {e}")

    # ── scene / graph builders ──────────────────────────────────────

    def _ensure_extractors_collection(self, context):
        scene = context.scene
        if "Extractors" in bpy.data.collections:
            return bpy.data.collections["Extractors"]
        extractors_col = bpy.data.collections.new("Extractors")
        scene.collection.children.link(extractors_col)
        return extractors_col

    def _create_extractor_in_graph(self, graph, doc_node_id,
                                    extractor_display,
                                    point_type, position):
        """Create an ExtractorNode under the DocumentNode with UUID
        ``doc_node_id`` and the edge ``Document --has_extractor-->
        Extractor``.

        Returns ``(ok, extractor_uuid, error_message)``. UUID-based
        lookup avoids the bug where multiple Documents share a display
        name (e.g. a legacy ``D.01`` plus a fresh one) and a
        name-based match would attach the extractor to the wrong one.
        """
        try:
            import traceback
            import uuid
            from s3dgraphy.nodes import ExtractorNode

            doc_node = graph.find_node_by_id(doc_node_id)
            if doc_node is None:
                return (False, "",
                        f"Anchor DocumentNode with id {doc_node_id!r} "
                        f"not found in graph")
            if getattr(doc_node, 'node_type', '') != 'document':
                return (False, "",
                        f"Node {doc_node_id!r} is not a DocumentNode "
                        f"(got node_type={doc_node.node_type!r})")

            ext_uuid = str(uuid.uuid4())
            extractor = ExtractorNode(
                node_id=ext_uuid,
                name=extractor_display,
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

            # Canonical EM edge: Extractor --extracted_from--> Document
            # (source=Extractor, target=Document). Matches the importer
            # and the GraphMLPatcher line-style table (dashed, 1.0);
            # using the inverse ``has_extractor`` previously rendered
            # as a solid line because it's not a canonical edge type.
            edge_id = f"{ext_uuid}_extracted_from_{doc_node.node_id}"
            graph.add_edge(
                edge_id=edge_id,
                edge_source=ext_uuid,
                edge_target=doc_node.node_id,
                edge_type="extracted_from",
            )
            return True, ext_uuid, ""
        except Exception as e:
            import traceback
            traceback.print_exc()
            return False, "", str(e)

    def _create_extractor_empty(self, context, extractor_display,
                                 position, collection,
                                 graph_code="", extractor_uuid=""):
        """Create an empty in the scene for the extractor. Name =
        ``{graph_code}.{extractor_display}`` (DP-46) so scene-side
        elements round-trip across graph imports; the UUID is stored
        separately as ``em_extractor_uuid`` so downstream lookups
        don't have to scan by name.
        """
        obj_name = (f"{graph_code}.{extractor_display}"
                    if graph_code else extractor_display)
        empty = bpy.data.objects.new(obj_name, None)
        empty.location = position
        empty.empty_display_type = 'SPHERE'
        empty.empty_display_size = 0.1
        collection.objects.link(empty)
        empty["em_extractor_id"] = extractor_display
        empty["em_extractor_uuid"] = extractor_uuid
        empty["em_node_type"] = "extractor"
        empty["em_graph_code"] = graph_code
        return empty

    def _create_combiner(self, context, graph, extractor_tuples,
                          proxy_name, graph_code=""):
        """Create a combiner node and empty; link every extractor to
        the combiner via ``is_combined_in``.

        ``extractor_tuples`` is ``[(scene_empty, extractor_uuid), ...]``
        — we need the UUIDs to wire edges in the graph (by UUID,
        matching the convention extractor-side) and the empties to
        compute the centroid for the scene empty's position.

        Returns ``(display_id, combiner_uuid, error)``. On failure
        ``combiner_uuid`` is the empty string.
        """
        try:
            import uuid
            from s3dgraphy.nodes import CombinerNode

            # Compute the next free display id (C.N) by scanning
            # existing combiner node NAMES — gap-aware enough for our
            # purposes. Zero-padded numeric suffixes (e.g. C.01100)
            # parse fine via int().
            max_num = 0
            for node in graph.nodes:
                if getattr(node, 'node_type', '') != 'combiner':
                    continue
                n_name = getattr(node, 'name', '')
                if not isinstance(n_name, str) or not n_name.startswith('C.'):
                    continue
                try:
                    suffix = n_name.split('.', 1)[1]
                    max_num = max(max_num, int(suffix))
                except (ValueError, IndexError):
                    continue
            display_id = f"C.{max_num + 1}"

            # node_id is a fresh UUID; display_id is the human label.
            # Keeping them distinct matches the convention used for
            # Documents / Extractors / Properties and keeps edges
            # correctly anchored to graph IDs.
            combiner_uuid = str(uuid.uuid4())
            combiner = CombinerNode(
                node_id=combiner_uuid,
                name=display_id,
            )
            combiner.attributes['purpose'] = "proxy_box_creator"
            combiner.attributes['description'] = (
                f"Combiner for proxy box {proxy_name!r} — aggregates "
                f"the 7 measurement-point extractors.")
            graph.add_node(combiner)

            # Canonical EM edge: Combiner --combines--> Extractor
            # (source=Combiner, target=Extractor, dashed). Again the
            # direction matches both the importer and the patcher
            # line-style table; ``is_combined_in`` (inverse) is not a
            # canonical edge type and would render as a solid line.
            for _empty, ext_uuid in extractor_tuples:
                if not ext_uuid:
                    continue
                edge_id = (f"{combiner_uuid}_combines_"
                           f"{ext_uuid}")
                graph.add_edge(
                    edge_id=edge_id,
                    edge_source=combiner_uuid,
                    edge_target=ext_uuid,
                    edge_type="combines",
                )

            empty_name = (f"{graph_code}.{display_id}"
                          if graph_code else display_id)
            combiner_empty = bpy.data.objects.new(empty_name, None)
            if extractor_tuples:
                centroid = (sum(
                    (t[0].location for t in extractor_tuples),
                    Vector()) / len(extractor_tuples))
                combiner_empty.location = centroid
            combiner_empty.empty_display_type = 'CUBE'
            combiner_empty.empty_display_size = 0.3
            self._ensure_extractors_collection(context) \
                .objects.link(combiner_empty)
            combiner_empty["em_combiner_id"] = display_id
            combiner_empty["em_combiner_uuid"] = combiner_uuid
            combiner_empty["em_node_type"] = "combiner"
            combiner_empty["em_graph_code"] = graph_code
            return display_id, combiner_uuid, ""
        except Exception as e:
            import traceback
            traceback.print_exc()
            return "", "", str(e)

    def _link_combiner_to_us(self, context, graph, combiner_uuid, us_item,
                              doc_node_id, extractor_uuids):
        """Hook the Combiner into the target US's paradata chain AND
        wrap everything in a ParadataNodeGroup named ``<US>_PD``:

            US  --has_property-->           PropertyNode("Proxy Geometry")
            PN  --has_data_provenance-->    Combiner
            Combiner --combines-->          Extractor x 7
            Extractor --extracted_from-->   Document
            US  --has_paradata_nodegroup--> <US>_PD
            [PN, Combiner, Extractors, Doc-instance] --is_in_paradata_nodegroup-->
                                            <US>_PD

        Reuses an existing ``proxy_geometry``-typed PropertyNode on
        the US when present — re-running the Proxy Box Creator on the
        same US adds another has_data_provenance edge to the shared PN.

        The PropertyNode NAME is the canonical qualia label ``Proxy
        Geometry`` (see ``em_qualia_types_additions.json`` →
        ``proxy_geometry``); no US prefix. A per-US distinction comes
        from the containing ParadataNodeGroup, not from the PN name.

        Returns ``(ok, error_message)``.
        """
        try:
            import uuid
            from s3dgraphy.nodes.property_node import PropertyNode
            from s3dgraphy.nodes.group_node import ParadataNodeGroup

            us_node_id = getattr(us_item, "id_node", "") or ""
            if not us_node_id:
                return False, (
                    f"US {us_item.name!r} has no id_node — the US list "
                    f"may be out of sync with the graph.")
            us_node = graph.find_node_by_id(us_node_id)
            if us_node is None:
                return False, (
                    f"US id {us_node_id!r} not found in graph.")
            us_display = getattr(us_node, 'name', '') or us_node_id

            # ── 1. PropertyNode (reuse or create) ─────────────────
            pn_node = None
            for edge in graph.edges:
                if (edge.edge_source == us_node_id
                        and edge.edge_type == "has_property"):
                    candidate = graph.find_node_by_id(edge.edge_target)
                    if candidate is None:
                        continue
                    ctype = (getattr(candidate, "data", None) or {}).get(
                        "property_type", "")
                    if ctype == "proxy_geometry":
                        pn_node = candidate
                        break
            if pn_node is None:
                pn_node = PropertyNode(
                    node_id=str(uuid.uuid4()),
                    name="Proxy Geometry",
                    property_type="proxy_geometry",
                    value="",
                    description="Coarse 3D bounding volume (proxy box) "
                                "declared from 7 measurement points "
                                "on the Representation Model.",
                )
                graph.add_node(pn_node)
                graph.add_edge(
                    edge_id=(f"{us_node_id}_has_property_"
                             f"{pn_node.node_id}"),
                    edge_source=us_node_id,
                    edge_target=pn_node.node_id,
                    edge_type="has_property",
                )

            # ── 2. PN → Combiner (has_data_provenance, dashed) ────
            prov_edge_id = (f"{pn_node.node_id}_has_data_provenance_"
                            f"{combiner_uuid}")
            if not any(e.edge_id == prov_edge_id for e in graph.edges):
                graph.add_edge(
                    edge_id=prov_edge_id,
                    edge_source=pn_node.node_id,
                    edge_target=combiner_uuid,
                    edge_type="has_data_provenance",
                )

            # ── 3. ParadataNodeGroup wrapping the whole chain ─────
            pd_group = self._ensure_pd_group(
                graph, us_node_id, us_display)
            pd_group_id = pd_group.node_id

            # Every paradata child --is_in_paradata_nodegroup--> PD_group.
            # Direction: source=child, target=group (per patcher's
            # line-style table: dashed).
            children = [pn_node.node_id, combiner_uuid, doc_node_id]
            children.extend([u for u in extractor_uuids if u])
            for child_id in children:
                if not child_id:
                    continue
                eid = (f"{child_id}_is_in_paradata_nodegroup_"
                       f"{pd_group_id}")
                if not any(e.edge_id == eid for e in graph.edges):
                    graph.add_edge(
                        edge_id=eid,
                        edge_source=child_id,
                        edge_target=pd_group_id,
                        edge_type="is_in_paradata_nodegroup",
                    )
            return True, ""
        except Exception as e:
            import traceback
            traceback.print_exc()
            return False, str(e)

    def _clone_document_for_pd(self, graph, master_doc_id, us_item_name):
        """Create a per-PD-group copy of the DocumentNode identified
        by ``master_doc_id`` (UUID). Returns the new node's UUID.

        Rationale: in EM graphs each PD node group that references a
        Document has its own Document instance wrapped inside the
        group (yEd BPMN convention — documents appear inside the
        group container, not shared across groups). Without this
        clone the user sees the new extractors pointing at an
        unrelated PD group's Document copy, and the Pick-from-selected
        resolution picks whichever instance yEd drew first.

        The clone:
        - Keeps the display NAME (``D.01``) identical to the master.
        - Gets a fresh UUID so edges can't collide with the master's.
        - Copies ``description`` + ``data`` (role/content_nature/
          geometry).
        - Is marked ``em_master_document=True`` so the GraphMLPatcher
          serialises it; ``original_emid`` points at the master so a
          future de-duplication step can collapse them back into one.
        """
        master = graph.find_node_by_id(master_doc_id)
        if master is None:
            return ""
        try:
            import uuid
            from s3dgraphy.nodes.document_node import DocumentNode
            clone_id = str(uuid.uuid4())
            data = dict(getattr(master, "data", {}) or {})
            clone = DocumentNode(
                node_id=clone_id,
                name=getattr(master, "name", "") or "",
                description=getattr(master, "description", "") or "",
                url=getattr(master, "url", None),
                data=data,
                role=data.get("role"),
                content_nature=data.get("content_nature"),
                geometry=data.get("geometry"),
            )
            if not hasattr(clone, "attributes") or clone.attributes is None:
                clone.attributes = {}
            # Copy the subset of master attributes that matters for
            # rendering (shape/border) — the patcher may rely on them.
            for k in ("shape", "border_style", "fill_color",
                      "URI", "label"):
                v = (getattr(master, "attributes", {}) or {}).get(k)
                if v is not None:
                    clone.attributes[k] = v
            clone.attributes["em_master_document"] = True
            clone.attributes["original_emid"] = master_doc_id
            graph.add_node(clone)
            return clone_id
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"[proxy_box] Document clone failed: {e}")
            return ""

    def _ensure_pd_group(self, graph, us_node_id, us_display):
        """Return the ``<US>_PD`` ParadataNodeGroup — reuse an existing
        one connected to the US via ``has_paradata_nodegroup`` when
        present; otherwise create a fresh one and the US→Group edge.

        The per-US PD group is the container yEd renders as a BPMN
        group; putting the Document + paradata chain inside it lets
        the GraphMLExporter emit a per-group Document instance (the
        visual "copy" that avoids sharing a Document slot with other
        PD groups, per the user's feedback).
        """
        import uuid
        from s3dgraphy.nodes.group_node import ParadataNodeGroup

        # Look for existing group via has_paradata_nodegroup edge.
        for edge in graph.edges:
            if (edge.edge_source == us_node_id
                    and edge.edge_type == "has_paradata_nodegroup"):
                candidate = graph.find_node_by_id(edge.edge_target)
                if isinstance(candidate, ParadataNodeGroup):
                    return candidate

        pd_group = ParadataNodeGroup(
            node_id=str(uuid.uuid4()),
            name=f"{us_display}_PD",
            description=f"Paradata node group for {us_display}",
        )
        graph.add_node(pd_group)
        graph.add_edge(
            edge_id=(f"{us_node_id}_has_paradata_nodegroup_"
                     f"{pd_group.node_id}"),
            edge_source=us_node_id,
            edge_target=pd_group.node_id,
            edge_type="has_paradata_nodegroup",
        )
        return pd_group

    def _create_proxy_geometry(self, context, points, proxy_name,
                                settings):
        """Build the proxy box mesh and move it into the Proxy
        collection when requested.
        """
        from .utils import calculate_box_geometry, create_box_mesh
        try:
            geometry = calculate_box_geometry(points)
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.report({'ERROR'},
                        f"Error calculating geometry: {e}")
            return None
        try:
            proxy_obj = create_box_mesh(
                proxy_name, geometry, settings.pivot_location)
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.report({'ERROR'}, f"Error creating mesh: {e}")
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
