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

        layout.prop(self, "search_query", text="", icon='VIEWZOOM')
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


classes = (
    ANASTYLOSIS_OT_link_to_sf,
    ANASTYLOSIS_OT_confirm_link,
    ANASTYLOSIS_OT_search_sf_node,
    ANASTYLOSIS_OT_assign_sf_node,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
