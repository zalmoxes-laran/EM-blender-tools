# anastylosis_manager/operators_link.py
"""Linking operators: link to SF, confirm link, search SF node, assign SF node."""

import bpy
from bpy.props import BoolProperty, IntProperty, StringProperty
from bpy.types import Operator

from s3dgraphy import get_graph
from s3dgraphy.nodes.representation_node import RepresentationModelSpecialFindNode
from s3dgraphy.nodes.link_node import LinkNode

from .. import icons_manager


def _build_transform(obj):
    """Extract position/rotation/scale from a Blender object in the legacy RMSF format."""
    transform = {
        "position": [f"{obj.location.x}", f"{obj.location.y}", f"{obj.location.z}"],
        "scale": [f"{obj.scale.x}", f"{obj.scale.y}", f"{obj.scale.z}"]
    }
    if obj.rotation_mode == 'QUATERNION':
        quat = obj.rotation_quaternion
        euler = quat.to_euler('XYZ')
        transform["rotation"] = [f"{euler.x}", f"{euler.y}", f"{euler.z}"]
    else:
        transform["rotation"] = [f"{obj.rotation_euler.x}", f"{obj.rotation_euler.y}", f"{obj.rotation_euler.z}"]
    return transform


def _ensure_rmsf_and_link(graph, obj, item_name, sf_node, rmsf_id):
    """Create RMSF node (if missing), wire has_representation_model edge, and ensure link node."""
    rmsf_node = graph.find_node_by_id(rmsf_id)
    if not rmsf_node:
        rmsf_node = RepresentationModelSpecialFindNode(
            node_id=rmsf_id,
            name=f"RMSF for {item_name}",
            type="RM",
            transform=_build_transform(obj),
            description=f"Representation model for {sf_node.node_type} {sf_node.name}"
        )
        graph.add_node(rmsf_node)

    # Remove previous has_representation_model edges for this RMSF so relinking updates cleanly
    stale_edges = [
        edge.edge_id
        for edge in list(graph.edges)
        if edge.edge_type == "has_representation_model"
        and (edge.edge_source == rmsf_id or edge.edge_target == rmsf_id)
    ]
    for edge_id in stale_edges:
        graph.remove_edge(edge_id)

    # Create edge
    edge_id = f"{sf_node.node_id}_has_representation_model_{rmsf_id}"
    existing_edge = graph.find_edge_by_id(edge_id)
    if not existing_edge:
        graph.add_edge(
            edge_id=edge_id,
            edge_source=sf_node.node_id,
            edge_target=rmsf_id,
            edge_type="has_representation_model"
        )

    # Create a LinkNode to store the URL
    link_node_id = f"{rmsf_id}_link"
    link_node = graph.find_node_by_id(link_node_id)
    if not link_node:
        gltf_path = f"models_sf/{item_name}.gltf"
        link_node = LinkNode(
            node_id=link_node_id,
            name=f"GLTF Link for {item_name}",
            description=f"Link to exported GLTF for {sf_node.node_type} {sf_node.name}",
            url=gltf_path,
            url_type="3d_model"
        )
        graph.add_node(link_node)

        edge_id = f"{rmsf_id}_has_linked_resource_{link_node_id}"
        graph.add_edge(
            edge_id=edge_id,
            edge_source=rmsf_id,
            edge_target=link_node_id,
            edge_type="has_linked_resource"
        )


class ANASTYLOSIS_OT_link_to_sf(Operator):
    """Link object to the currently active SpecialFind in Stratigraphy Manager (kept for backward compatibility)."""
    bl_idname = "anastylosis.link_to_sf"
    bl_label = "Link to Active SpecialFind"
    bl_description = "Link this object to the currently active SpecialFind in Stratigraphy Manager"

    anastylosis_index: IntProperty(
        name="Anastylosis Index",
        description="Index of the anastylosis item in the list",
        default=-1
    )

    def execute(self, context):
        scene = context.scene
        anastylosis = scene.em_tools.anastylosis

        if self.anastylosis_index < 0:
            self.anastylosis_index = anastylosis.list_index

        if self.anastylosis_index < 0 or self.anastylosis_index >= len(anastylosis.list):
            self.report({'ERROR'}, "No anastylosis model selected")
            return {'CANCELLED'}

        item = anastylosis.list[self.anastylosis_index]

        obj = bpy.data.objects.get(item.name)
        if not obj:
            self.report({'ERROR'}, f"Object {item.name} not found in scene")
            return {'CANCELLED'}

        strat = scene.em_tools.stratigraphy
        if strat.units_index < 0 or strat.units_index >= len(strat.units):
            self.report({'ERROR'}, "No active stratigraphy unit selected")
            return {'CANCELLED'}

        active_strat_item = strat.units[strat.units_index]

        graph = None
        if context.scene.em_tools.active_file_index >= 0:
            graphml = context.scene.em_tools.graphml_files[context.scene.em_tools.active_file_index]
            graph = get_graph(graphml.name)

        if not graph:
            self.report({'ERROR'}, "No active graph available")
            return {'CANCELLED'}

        sf_node = graph.find_node_by_id(active_strat_item.id_node)
        if not sf_node:
            self.report({'ERROR'}, f"SpecialFind node {active_strat_item.id_node} not found in graph")
            return {'CANCELLED'}

        if sf_node.node_type not in ["SF", "VSF"]:
            self.report({'ERROR'}, f"Active node is not a SpecialFind (type: {sf_node.node_type})")
            return {'CANCELLED'}

        rmsf_id = f"{item.name}_rmsf"
        _ensure_rmsf_and_link(graph, obj, item.name, sf_node, rmsf_id)

        item.sf_node_id = sf_node.node_id
        item.sf_node_name = sf_node.name
        item.is_virtual = sf_node.node_type == "VSF"
        item.node_id = rmsf_id

        bpy.ops.anastylosis.update_list(from_graph=True)

        self.report({'INFO'}, f"Linked {item.name} to {sf_node.node_type} {sf_node.name}")
        return {'FINISHED'}


class ANASTYLOSIS_OT_confirm_link(Operator):
    """Confirm SF/VSF link selection (kept for backward compatibility)."""
    bl_idname = "anastylosis.confirm_link"
    bl_label = "Confirm Link"
    bl_description = "Confirm linking object to this SpecialFind node"

    sf_node_index: IntProperty(
        name="SF Node Index",
        description="Index of the SF node in the temporary list",
        default=-1
    )

    def execute(self, context):
        scene = context.scene
        anastylosis = scene.em_tools.anastylosis

        if self.sf_node_index < 0 or self.sf_node_index >= len(anastylosis.sf_nodes):
            self.report({'ERROR'}, "Invalid SpecialFind node selection")
            return {'CANCELLED'}

        sf_item = anastylosis.sf_nodes[self.sf_node_index]

        obj_name = anastylosis.temp_obj_name
        rmsf_id = anastylosis.temp_rmsf_id

        obj = bpy.data.objects.get(obj_name)
        if not obj:
            self.report({'ERROR'}, f"Object {obj_name} not found in scene")
            return {'CANCELLED'}

        graph = None
        if context.scene.em_tools.active_file_index >= 0:
            graphml = context.scene.em_tools.graphml_files[context.scene.em_tools.active_file_index]
            graph = get_graph(graphml.name)

        if not graph:
            self.report({'ERROR'}, "No active graph available")
            return {'CANCELLED'}

        sf_node = graph.find_node_by_id(sf_item.node_id)
        if not sf_node:
            self.report({'ERROR'}, f"SpecialFind node {sf_item.node_id} not found in graph")
            return {'CANCELLED'}

        # NOTE: preserve legacy description label (SpecialFind {obj_name}) when creating the RMSF
        rmsf_node = graph.find_node_by_id(rmsf_id)
        if not rmsf_node:
            rmsf_node = RepresentationModelSpecialFindNode(
                node_id=rmsf_id,
                name=f"RMSF for {obj_name}",
                type="RM",
                transform=_build_transform(obj),
                description=f"Representation model for SpecialFind {obj_name}"
            )
            graph.add_node(rmsf_node)

        stale_edges = [
            edge.edge_id
            for edge in list(graph.edges)
            if edge.edge_type == "has_representation_model"
            and (edge.edge_source == rmsf_id or edge.edge_target == rmsf_id)
        ]
        for edge_id in stale_edges:
            graph.remove_edge(edge_id)

        edge_id = f"{sf_item.node_id}_has_representation_model_{rmsf_id}"
        existing_edge = graph.find_edge_by_id(edge_id)
        if not existing_edge:
            graph.add_edge(
                edge_id=edge_id,
                edge_source=sf_item.node_id,
                edge_target=rmsf_id,
                edge_type="has_representation_model"
            )

        link_node_id = f"{rmsf_id}_link"
        link_node = graph.find_node_by_id(link_node_id)
        if not link_node:
            gltf_path = f"models_sf/{obj_name}.gltf"
            link_node = LinkNode(
                node_id=link_node_id,
                name=f"GLTF Link for {obj_name}",
                description=f"Link to exported GLTF for SpecialFind {obj_name}",
                url=gltf_path,
                url_type="3d_model"
            )
            graph.add_node(link_node)

            edge_id = f"{rmsf_id}_has_linked_resource_{link_node_id}"
            graph.add_edge(
                edge_id=edge_id,
                edge_source=rmsf_id,
                edge_target=link_node_id,
                edge_type="has_linked_resource"
            )

        for item in anastylosis.list:
            if item.name == obj_name:
                item.sf_node_id = sf_item.node_id
                item.sf_node_name = sf_item.name
                item.is_virtual = "Virtual" in sf_item.description
                break

        bpy.ops.anastylosis.update_list(from_graph=True)

        self.report({'INFO'}, f"Linked {obj_name} to SpecialFind {sf_item.name}")
        return {'FINISHED'}


class ANASTYLOSIS_OT_search_sf_node(Operator):
    """Search and select an SF/VSF node to link to this object"""
    bl_idname = "anastylosis.search_sf_node"
    bl_label = "Link to SpecialFind"
    bl_description = "Search for an SF or VSF node to link this object to"
    bl_options = {'REGISTER', 'INTERNAL'}

    anastylosis_index: IntProperty(
        name="Anastylosis Index",
        description="Index of the anastylosis item in the list",
        default=-1
    ) # type: ignore

    search_query: StringProperty(
        name="Search",
        description="Search for SF/VSF node by name",
        default=""
    ) # type: ignore

    @classmethod
    def poll(cls, context):
        em_tools = context.scene.em_tools
        return em_tools.active_file_index >= 0

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=400)

    def draw(self, context):
        layout = self.layout

        # Search field + create-new entry point on a single row, so
        # users can either pick an existing SF/VSF or fall through to
        # the shared add-US dialog (with its US Type pre-set to
        # SpecialFind for this entry point).
        head = layout.row(align=True)
        head.prop(self, "search_query", text="", icon='VIEWZOOM')
        op = head.operator(
            "anastylosis.create_new_sf",
            text="+ New SF", icon='ADD')
        op.anastylosis_index = self.anastylosis_index
        layout.separator()

        em_tools = context.scene.em_tools
        if em_tools.active_file_index < 0:
            layout.label(text="No active graph", icon='ERROR')
            return

        graph_info = em_tools.graphml_files[em_tools.active_file_index]
        graph = get_graph(graph_info.name)

        if not graph:
            layout.label(text="Graph not loaded", icon='ERROR')
            return

        sf_nodes = []
        for node in graph.nodes:
            if hasattr(node, 'node_type') and node.node_type in ["SF", "VSF"]:
                node_id = node.node_id if hasattr(node, 'node_id') else ""
                node_name = node.name if hasattr(node, 'name') else ""

                search_lower = self.search_query.lower()
                if (not self.search_query or
                    search_lower in node_id.lower() or
                    search_lower in node_name.lower()):
                    sf_nodes.append(node)

        sf_nodes.sort(key=lambda x: x.name)

        if sf_nodes:
            box = layout.box()
            icon_val = icons_manager.get_icon_value("show_all_proxies")
            box.label(text=f"Found {len(sf_nodes)} SF/VSF nodes:", icon='MESH_ICOSPHERE')

            for node in sf_nodes[:20]:
                row = box.row(align=True)
                type_label = "VSF" if node.node_type == "VSF" else "SF"

                if icon_val:
                    op = row.operator("anastylosis.assign_sf_node",
                                      text=f"{node.name} ({type_label})",
                                      icon_value=icon_val)
                else:
                    sf_icon = 'OUTLINER_OB_EMPTY' if node.node_type == "VSF" else 'MESH_ICOSPHERE'
                    op = row.operator("anastylosis.assign_sf_node",
                                      text=f"{node.name} ({type_label})",
                                      icon=sf_icon)
                op.anastylosis_index = self.anastylosis_index
                op.sf_node_id = node.node_id
                op.sf_node_name = node.name
                op.is_virtual = (node.node_type == "VSF")

            if len(sf_nodes) > 20:
                box.label(text=f"...and {len(sf_nodes) - 20} more. Refine your search.",
                          icon='INFO')
        else:
            layout.label(text="No SF/VSF nodes found", icon='INFO')
            if self.search_query:
                layout.label(text="Try a different search term")

    def execute(self, context):
        # This operator only shows a dialog, no execution needed
        return {'FINISHED'}


class ANASTYLOSIS_OT_assign_sf_node(Operator):
    """Assign an SF/VSF node to an anastylosis item"""
    bl_idname = "anastylosis.assign_sf_node"
    bl_label = "Assign SF Node"
    bl_description = "Link this anastylosis object to the selected SpecialFind node"
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    anastylosis_index: IntProperty(
        name="Anastylosis Index",
        default=-1
    ) # type: ignore

    sf_node_id: StringProperty(
        name="SF Node ID",
        default=""
    ) # type: ignore

    sf_node_name: StringProperty(
        name="SF Node Name",
        default=""
    ) # type: ignore

    is_virtual: BoolProperty(
        name="Is Virtual",
        default=False
    ) # type: ignore

    def execute(self, context):
        scene = context.scene
        anastylosis = scene.em_tools.anastylosis

        if self.anastylosis_index < 0:
            self.anastylosis_index = anastylosis.list_index

        if self.anastylosis_index < 0 or self.anastylosis_index >= len(anastylosis.list):
            self.report({'ERROR'}, "No anastylosis model selected")
            return {'CANCELLED'}

        item = anastylosis.list[self.anastylosis_index]

        obj = bpy.data.objects.get(item.name)
        if not obj:
            self.report({'ERROR'}, f"Object {item.name} not found in scene")
            return {'CANCELLED'}

        graph = None
        if context.scene.em_tools.active_file_index >= 0:
            graphml = context.scene.em_tools.graphml_files[context.scene.em_tools.active_file_index]
            graph = get_graph(graphml.name)

        if not graph:
            self.report({'ERROR'}, "No active graph available")
            return {'CANCELLED'}

        sf_node = graph.find_node_by_id(self.sf_node_id)
        if not sf_node:
            self.report({'ERROR'}, f"SpecialFind node {self.sf_node_id} not found in graph")
            return {'CANCELLED'}

        if sf_node.node_type not in ["SF", "VSF"]:
            self.report({'ERROR'}, f"Node is not a SpecialFind (type: {sf_node.node_type})")
            return {'CANCELLED'}

        rmsf_id = f"{item.name}_rmsf"
        _ensure_rmsf_and_link(graph, obj, item.name, sf_node, rmsf_id)

        item.sf_node_id = sf_node.node_id
        item.sf_node_name = sf_node.name
        item.is_virtual = sf_node.node_type == "VSF"
        item.node_id = rmsf_id

        bpy.ops.anastylosis.update_list(from_graph=True)

        self.report({'INFO'}, f"Linked {item.name} to {sf_node.node_type} {sf_node.name}")
        return {'FINISHED'}


class ANASTYLOSIS_OT_create_new_sf(Operator):
    """Open the shared add-US dialog with the type locked to SpecialFind
    and, on confirm, link the freshly-created SF to the target RMSF row.

    Wraps :class:`STRAT_OT_add_us` so the user reuses the same form the
    Stratigraphy Manager exposes (one source of truth for US creation).
    The ``lock_us_type=True`` flag keeps the type dropdown read-only at
    the dialog level — the user can still edit name / epoch / activity
    but can't accidentally turn the new unit into a regular US.
    """
    bl_idname = "anastylosis.create_new_sf"
    bl_label = "Create new SpecialFind"
    bl_description = (
        "Open the shared Add-US dialog with the type locked to "
        "SpecialFind, then link the new SF to this RMSF row")
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    anastylosis_index: IntProperty(default=-1)  # type: ignore

    @classmethod
    def poll(cls, context):
        return context.scene.em_tools.active_file_index >= 0

    def execute(self, context):
        scene = context.scene
        anastylosis = scene.em_tools.anastylosis
        idx = (self.anastylosis_index
               if self.anastylosis_index >= 0
               else anastylosis.list_index)
        if idx < 0 or idx >= len(anastylosis.list):
            self.report({'ERROR'}, "No anastylosis model selected")
            return {'CANCELLED'}

        # Snapshot the current SF count so we can detect the brand-new
        # one regardless of any units_index re-shuffle done by the
        # add-US operator.
        strat = scene.em_tools.stratigraphy
        before_ids = {u.id_node for u in strat.units}

        try:
            result = bpy.ops.strat.add_us(
                'INVOKE_DEFAULT',
                us_type='SF',
                lock_us_type=True,
            )
        except Exception as e:
            self.report({'ERROR'}, f"Could not open Add-US dialog: {e}")
            return {'CANCELLED'}
        if 'FINISHED' not in result:
            # User cancelled — nothing to do.
            return {'CANCELLED'}

        # Find the new SF: the strat list now has exactly one extra
        # entry whose id wasn't there before.
        new_unit = None
        for u in strat.units:
            if u.id_node not in before_ids:
                new_unit = u
                break
        if new_unit is None:
            self.report({'WARNING'},
                        "Add-US dialog finished but no new SF found "
                        "in the stratigraphy list.")
            return {'CANCELLED'}

        em_tools = scene.em_tools
        graph_info = em_tools.graphml_files[em_tools.active_file_index]
        graph = get_graph(graph_info.name)
        if graph is None:
            self.report({'ERROR'}, "Graph not loaded")
            return {'CANCELLED'}
        sf_node = graph.find_node_by_id(new_unit.id_node)
        if sf_node is None:
            self.report({'ERROR'},
                        f"New SF node {new_unit.id_node!r} not found "
                        "in graph after creation.")
            return {'CANCELLED'}

        # Wire the SF to the target RMSF row (mirrors assign_sf_node).
        item = anastylosis.list[idx]
        obj = bpy.data.objects.get(item.name)
        if obj is None:
            self.report({'ERROR'},
                        f"RMSF object {item.name!r} not found in scene")
            return {'CANCELLED'}
        rmsf_id = item.node_id or f"{item.name}_rmsf"
        _ensure_rmsf_and_link(graph, obj, item.name, sf_node, rmsf_id)

        item.sf_node_id = sf_node.node_id
        item.sf_node_name = sf_node.name
        item.is_virtual = sf_node.node_type == "VSF"
        item.node_id = rmsf_id

        bpy.ops.anastylosis.update_list(from_graph=True)
        self.report(
            {'INFO'},
            f"Created SF {sf_node.name} and linked to RMSF {item.name}")
        return {'FINISHED'}


class ANASTYLOSIS_OT_search_doc_node(Operator):
    """Search and pick a Document to link to this RMSF.

    Opens the standard document picker dialog (search the catalog or
    create a brand-new master Document via the shared
    ``docmanager.create_master_document`` flow). On confirm the doc is
    written into the RMSF item; the corresponding graph edge can be
    materialised by downstream knowledge-extraction tools.
    """
    bl_idname = "anastylosis.search_doc_node"
    bl_label = "Link to Document"
    bl_description = (
        "Search for an existing Document or create a new master to "
        "associate with this RMSF. Required for knowledge-extraction "
        "tools (Surface Areas, Proxy Box, measurement extractors) "
        "that read paradata from the RMSF"
    )
    bl_options = {'REGISTER', 'INTERNAL'}

    anastylosis_index: IntProperty(default=-1)  # type: ignore
    target_doc_name: StringProperty(default="")  # type: ignore

    @classmethod
    def poll(cls, context):
        return context.scene.em_tools.active_file_index >= 0

    def invoke(self, context, event):
        self.target_doc_name = ""
        return context.window_manager.invoke_props_dialog(self, width=420)

    def draw(self, context):
        layout = self.layout
        layout.label(text="Pick a Document for this RMSF:",
                     icon='FILE_TEXT')
        layout.separator()
        from ..master_document_helpers import (
            draw_document_picker_with_create_button)
        draw_document_picker_with_create_button(
            layout, context.scene,
            target_owner=self,
            target_prop_name="target_doc_name",
            create_new_operator="docmanager.create_master_document",
            create_new_label="+ Add New Document...",
        )

    def execute(self, context):
        scene = context.scene
        em_tools = scene.em_tools
        anastylosis = em_tools.anastylosis
        idx = (self.anastylosis_index
               if self.anastylosis_index >= 0
               else anastylosis.list_index)
        if idx < 0 or idx >= len(anastylosis.list):
            self.report({'ERROR'}, "No anastylosis model selected")
            return {'CANCELLED'}

        if em_tools.active_file_index < 0:
            self.report({'ERROR'}, "No active graph")
            return {'CANCELLED'}
        graph_info = em_tools.graphml_files[em_tools.active_file_index]
        graph = get_graph(graph_info.name)
        if graph is None:
            self.report({'ERROR'}, "Graph not loaded")
            return {'CANCELLED'}

        # Resolve the picked document. Two paths feed it:
        #   1. The user typed/picked from the search field —
        #      ``target_doc_name`` carries the chosen display name.
        #   2. The user clicked "+ Add New Document..." inside the
        #      picker — the ``docmanager.create_master_document``
        #      operator drops the new node id on the
        #      ``last_created_master_doc_id`` sentinel before
        #      returning. We honour that here so the new doc is
        #      auto-associated without a second click.
        doc_node = None
        if self.target_doc_name:
            for node in graph.nodes:
                if (getattr(node, 'node_type', '') == 'document'
                        and getattr(node, 'name', '')
                        == self.target_doc_name):
                    doc_node = node
                    break
        if doc_node is None:
            new_doc_id = em_tools.get("last_created_master_doc_id", "")
            if new_doc_id:
                doc_node = graph.find_node_by_id(new_doc_id)

        if doc_node is None:
            self.report({'INFO'}, "No document picked")
            return {'CANCELLED'}

        # Reset the sentinel so it can't leak into the next dialog.
        try:
            em_tools["last_created_master_doc_id"] = ""
        except Exception:
            pass

        return bpy.ops.anastylosis.assign_doc_node(
            'EXEC_DEFAULT',
            anastylosis_index=idx,
            doc_node_id=doc_node.node_id,
            doc_node_name=doc_node.name,
        )


def _document_already_linked(graph, doc_node_id, exclude_rmsf_id=None):
    """Return ``(owner_kind, owner_node_id, owner_name)`` for the first
    RM / RMDoc / RMSF the given document is already linked to via the
    canonical edges, or ``None`` when the document is free.

    Hard-refuse policy: a Document can be the SOURCE of at most one
    ``has_representation_model`` (RM) and at most one
    ``has_representation_model_doc`` (RMDoc / RMSF). We allow the
    caller to exclude the RMSF that is being (re-)linked itself —
    re-binding the same doc to the same RMSF must always succeed.
    """
    if graph is None or not doc_node_id:
        return None
    type_map = {
        "representation_model": "RM",
        "representation_model_doc": "RMDoc",
        "representation_model_sf": "RMSF",
    }
    for edge in graph.edges:
        if edge.edge_source != doc_node_id:
            continue
        if edge.edge_type not in (
                "has_representation_model",
                "has_representation_model_doc"):
            continue
        if exclude_rmsf_id and edge.edge_target == exclude_rmsf_id:
            continue
        target = graph.find_node_by_id(edge.edge_target)
        if target is None:
            continue
        kind = type_map.get(getattr(target, 'node_type', ''))
        if kind is None:
            continue
        return (kind, target.node_id, getattr(target, 'name', '') or '')
    return None


class ANASTYLOSIS_OT_assign_doc_node(Operator):
    """Write the picked Document onto the RMSF row and create the
    corresponding ``DocumentNode --has_representation_model_doc--> RMSF``
    edge in the graph. Re-linking drops any pre-existing edge of the
    same type targeting this RMSF so the user can swap docs cleanly.

    Used both by ``search_doc_node`` (after the picker dialog confirms)
    and by any future flow that wants to attach a doc programmatically.
    """
    bl_idname = "anastylosis.assign_doc_node"
    bl_label = "Assign Document to RMSF"
    bl_description = (
        "Link this RMSF to the given Document and create the "
        "has_representation_model_doc edge in the graph")
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    anastylosis_index: IntProperty(default=-1)  # type: ignore
    doc_node_id: StringProperty(default="")  # type: ignore
    doc_node_name: StringProperty(default="")  # type: ignore

    def execute(self, context):
        scene = context.scene
        anastylosis = scene.em_tools.anastylosis
        idx = (self.anastylosis_index
               if self.anastylosis_index >= 0
               else anastylosis.list_index)
        if idx < 0 or idx >= len(anastylosis.list):
            self.report({'ERROR'}, "No anastylosis model selected")
            return {'CANCELLED'}
        if not self.doc_node_id:
            self.report({'ERROR'}, "No Document id provided")
            return {'CANCELLED'}

        em_tools = scene.em_tools
        if em_tools.active_file_index < 0:
            self.report({'ERROR'}, "No active graph")
            return {'CANCELLED'}
        graph_info = em_tools.graphml_files[em_tools.active_file_index]
        graph = get_graph(graph_info.name)
        if graph is None:
            self.report({'ERROR'}, "Graph not loaded")
            return {'CANCELLED'}

        doc_node = graph.find_node_by_id(self.doc_node_id)
        if doc_node is None:
            self.report({'ERROR'},
                        f"Document {self.doc_node_id!r} not found in graph")
            return {'CANCELLED'}

        item = anastylosis.list[idx]

        # ── Heal a stale RMSF row: the panel item carries a node_id
        # that no longer matches a graph node (e.g. the user removed
        # the RMSF node manually, or loaded a graph that lacks it).
        # If we have an SF link, recreate the RMSF + edge via the
        # shared helper so the rest of the flow can proceed; otherwise
        # bail with a clear message.
        rmsf_id = item.node_id
        if rmsf_id and graph.find_node_by_id(rmsf_id) is None:
            obj = bpy.data.objects.get(item.name)
            sf_node = (graph.find_node_by_id(item.sf_node_id)
                       if item.sf_node_id else None)
            if obj is not None and sf_node is not None:
                _ensure_rmsf_and_link(
                    graph, obj, item.name, sf_node, rmsf_id)
            else:
                self.report(
                    {'ERROR'},
                    f"RMSF graph node {rmsf_id!r} is missing and the "
                    "row has no SF link to recreate it from. Re-link "
                    "this row to a SpecialFind first.")
                return {'CANCELLED'}
        elif not rmsf_id:
            # Row never linked to any SF yet — without a target id we
            # cannot anchor the doc edge.
            self.report(
                {'ERROR'},
                "Link this row to a SpecialFind first — the RMSF node "
                "is created on SF assignment, and the doc edge needs "
                "it as the target.")
            return {'CANCELLED'}

        # ── Hard-refuse if the picked Document is already attached to
        # another RM / RMDoc / RMSF. The user has to clear the existing
        # link first or pick a different document.
        owner = _document_already_linked(
            graph, self.doc_node_id, exclude_rmsf_id=rmsf_id)
        if owner is not None:
            kind, _oid, oname = owner
            self.report(
                {'ERROR'},
                f"Document is already linked to {kind} "
                f"{oname or '(unnamed)'}. Clear that link first or "
                f"pick another document.")
            return {'CANCELLED'}

        # Drop pre-existing has_representation_model_doc edges that
        # target the same RMSF — the user is re-linking to a new doc.
        stale = [
            e.edge_id for e in list(graph.edges)
            if e.edge_type == "has_representation_model_doc"
            and e.edge_target == rmsf_id]
        for eid in stale:
            graph.remove_edge(eid)

        edge_id = (f"{self.doc_node_id}_has_representation_model_doc_"
                   f"{rmsf_id}")
        if not graph.find_edge_by_id(edge_id):
            graph.add_edge(
                edge_id=edge_id,
                edge_source=self.doc_node_id,
                edge_target=rmsf_id,
                edge_type="has_representation_model_doc",
            )

        item.doc_node_id = self.doc_node_id
        item.doc_node_name = (self.doc_node_name
                              or doc_node.name
                              or self.doc_node_id)

        self.report(
            {'INFO'},
            f"RMSF {item.name} linked to Document "
            f"{item.doc_node_name}")
        return {'FINISHED'}


class ANASTYLOSIS_OT_clear_doc_node(Operator):
    """Detach the Document from this RMSF row (leaves the SF link
    intact and does not touch the graph).
    """
    bl_idname = "anastylosis.clear_doc_node"
    bl_label = "Clear Document"
    bl_description = "Remove the Document association from this RMSF row"
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    anastylosis_index: IntProperty(default=-1)  # type: ignore

    def execute(self, context):
        anastylosis = context.scene.em_tools.anastylosis
        idx = (self.anastylosis_index
               if self.anastylosis_index >= 0
               else anastylosis.list_index)
        if idx < 0 or idx >= len(anastylosis.list):
            return {'CANCELLED'}
        item = anastylosis.list[idx]
        item.doc_node_id = ""
        item.doc_node_name = ""
        return {'FINISHED'}


classes = (
    ANASTYLOSIS_OT_link_to_sf,
    ANASTYLOSIS_OT_confirm_link,
    ANASTYLOSIS_OT_search_sf_node,
    ANASTYLOSIS_OT_assign_sf_node,
    ANASTYLOSIS_OT_create_new_sf,
    ANASTYLOSIS_OT_search_doc_node,
    ANASTYLOSIS_OT_assign_doc_node,
    ANASTYLOSIS_OT_clear_doc_node,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
