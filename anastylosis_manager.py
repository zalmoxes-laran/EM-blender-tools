import re
import os
import subprocess
import bpy
from bpy.props import (
    StringProperty,
    BoolProperty,
    CollectionProperty,
    IntProperty,
    EnumProperty,
    PointerProperty,
    FloatVectorProperty,
)
from bpy.types import (
    Panel,
    Operator,
    PropertyGroup,
    UIList,
)

from s3dgraphy import get_graph
from s3dgraphy.nodes.representation_node import RepresentationModelSpecialFindNode
from s3dgraphy.nodes.stratigraphic_node import SpecialFindUnit, VirtualSpecialFindUnit
from s3dgraphy.nodes.link_node import LinkNode
from . import icons_manager


# --- LOD Helper ---

LOD_MIN_LEVEL = 0
LOD_MAX_LEVEL = 4
LOD_SUFFIX_RE = re.compile(r"^(.+)_LOD(\d+)$")
LOD_FALLBACK_WARNING = "Some Levels of Detail were not found. Fallback applied to the nearest available LOD."


def _split_lod_name(name):
    """Return (base_name, lod_level) if name ends with _LOD#, else (None, None)."""
    m = LOD_SUFFIX_RE.match(name or "")
    if not m:
        return None, None
    return m.group(1), int(m.group(2))


def _resolve_lod_with_fallback(available_levels, requested_level, min_level=LOD_MIN_LEVEL, max_level=LOD_MAX_LEVEL):
    """Clamp request to [min,max] and fallback to highest available <= request."""
    if not available_levels:
        return None

    req = max(min_level, min(max_level, int(requested_level)))
    levels_in_range = sorted({lvl for lvl in available_levels if min_level <= lvl <= max_level})
    if not levels_in_range:
        return None

    lower_or_equal = [lvl for lvl in levels_in_range if lvl <= req]
    if lower_or_equal:
        return max(lower_or_equal)

    # If no lower level exists, use the minimum available in range.
    return min(levels_in_range)


def _rename_object_to_lod(obj, target_lod):
    """Rename object suffix to _LODn only if the object already follows that convention."""
    base_name, _ = _split_lod_name(obj.name)
    if base_name is None:
        return
    obj.name = f"{base_name}_LOD{target_lod}"


def _switch_linked_mesh_lod(obj, requested_lod):
    """Switch linked mesh data to requested LOD with fallback to max available <= request."""
    if not obj or obj.type != 'MESH' or not obj.data or not obj.data.library:
        return False, None, None, "Object has no linked mesh library"

    mesh_name = obj.data.name
    base_name, _ = _split_lod_name(mesh_name)
    if base_name is None:
        return False, None, None, f"Mesh '{mesh_name}' has no _LODn suffix"

    lib_path = bpy.path.abspath(obj.data.library.filepath)
    target_mesh_name = None
    resolved_lod = None

    with bpy.data.libraries.load(lib_path, link=True) as (data_from, data_to):
        available_levels = []
        for name in data_from.meshes:
            m = LOD_SUFFIX_RE.match(name)
            if m and m.group(1) == base_name:
                available_levels.append(int(m.group(2)))

        resolved_lod = _resolve_lod_with_fallback(available_levels, requested_lod)
        if resolved_lod is None:
            return False, None, None, f"No LOD levels found for base '{base_name}' in library"

        target_mesh_name = f"{base_name}_LOD{resolved_lod}"
        data_to.meshes = [target_mesh_name]

    target_mesh = bpy.data.meshes.get(target_mesh_name)
    if target_mesh is None:
        return False, None, None, f"Mesh '{target_mesh_name}' could not be loaded from library"

    obj.data = target_mesh
    _rename_object_to_lod(obj, resolved_lod)
    return True, resolved_lod, target_mesh_name, None

def detect_lod_variants(obj_name):
    """Given an object name, find all its LOD variants in the scene.
    Recognizes pattern: BaseName_LOD0, BaseName_LOD1, etc.
    Returns list of tuples (lod_level, obj_name) sorted by LOD level.
    """
    # Try to extract base name by removing _LODN suffix (greedy match)
    match = re.match(r'^(.+)_LOD(\d+)$', obj_name)
    if match:
        base_name = match.group(1)
    else:
        # Object doesn't have LOD suffix — use full name as base
        base_name = obj_name

    variants = []
    pattern = re.compile(r'^' + re.escape(base_name) + r'_LOD(\d+)$')

    for obj in bpy.data.objects:
        m = pattern.match(obj.name)
        if m:
            lod_level = int(m.group(1))
            variants.append((lod_level, obj.name))

    variants.sort(key=lambda x: x[0])
    return variants


# --- Graph helper ---

def _remove_item_from_graph(graph, item):
    """Remove RMSF node, its link node, and all connected edges from the graph.
    Shared logic used by both single-remove and batch-remove operators.
    """
    if not graph or not item.node_id:
        return

    rmsf_node = graph.find_node_by_id(item.node_id)
    if rmsf_node:
        # Find all connected edges
        edges_to_remove = []
        for edge in graph.edges:
            if edge.edge_source == item.node_id or edge.edge_target == item.node_id:
                edges_to_remove.append(edge.edge_id)

        # Remove edges
        for edge_id in edges_to_remove:
            graph.remove_edge(edge_id)

        # Remove node
        graph.remove_node(item.node_id)

        # Also remove the link node if it exists
        link_node_id = f"{item.node_id}_link"
        link_node = graph.find_node_by_id(link_node_id)
        if link_node:
            # Find and remove edges to the link node
            link_edges = [
                edge.edge_id for edge in graph.edges
                if edge.edge_source == link_node_id or edge.edge_target == link_node_id
            ]
            for edge_id in link_edges:
                graph.remove_edge(edge_id)

            # Remove the link node
            graph.remove_node(link_node_id)


# PropertyGroup for representing a SpecialFind association
class AnastylisisItem(PropertyGroup):
    """Properties for SpecialFind models in the anastylosis list"""
    name: StringProperty(
        name="Name",
        description="Name of the 3D model",
        default="Unnamed"
    )
    sf_node_id: StringProperty(
        name="SF Node ID",
        description="ID of the SpecialFind node this model is associated with",
        default=""
    )
    sf_node_name: StringProperty(
        name="SF Node Name",
        description="Name of the SpecialFind node",
        default=""
    )
    is_virtual: BoolProperty(
        name="Is Virtual",
        description="Whether this is a virtual reconstruction (VSF) or a real fragment (SF)",
        default=False
    )
    is_publishable: BoolProperty(
        name="Publishable",
        description="Whether this anastylosis model is publishable",
        default=True
    )
    node_id: StringProperty(
        name="Node ID",
        description="ID of the RMSF node in the graph",
        default=""
    )
    object_exists: BoolProperty(
        name="Object Exists",
        description="Whether the object exists in the scene",
        default=False
    )
    # LOD properties
    active_lod: IntProperty(
        name="Active LOD",
        description="Currently active LOD level for this object",
        default=0,
        min=0
    )
    has_lod_variants: BoolProperty(
        name="Has LOD Variants",
        description="Whether this object has LOD variants in the scene",
        default=False
    )
    lod_count: IntProperty(
        name="LOD Count",
        description="Number of LOD variants available",
        default=0,
        min=0
    )

# UI List for showing the anastylosis models
class ANASTYLOSIS_UL_List(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        try:
            if self.layout_type in {'DEFAULT', 'COMPACT'}:
                # Get the object
                obj = bpy.data.objects.get(item.name)

                # Determine appropriate icon
                if hasattr(item, 'object_exists') and item.object_exists:
                    icon_value=icons_manager.get_icon_value("show_all_special_finds")
                    # Layout
                    row = layout.row(align=True)
                    # Name of the model
                    row.prop(item, "name", text="", emboss=False, icon_value=icon_value)
                else:
                    obj_icon = 'ERROR'
                    row = layout.row(align=True)
                    row.prop(item, "name", text="", emboss=False, icon=obj_icon)

                # Associated SF/VSF node
                if hasattr(item, 'sf_node_name') and item.sf_node_name:

                    if item.is_virtual:
                        icon_value=icons_manager.get_icon_value("show_all_proxies")
                        row.label(text=item.sf_node_name, icon_value=icon_value)
                    else:
                        icon_value=icons_manager.get_icon_value("show_all_proxies")
                        row.label(text=item.sf_node_name, icon_value=icon_value)

                else:
                    row.label(text="[Not Connected]", icon='QUESTION')

                # LOD dropdown (if there are LOD variants)
                lod_variants = detect_lod_variants(item.name)
                if len(lod_variants) >= 1:
                    sub = row.row(align=True)
                    sub.scale_x = 0.6
                    sub.menu("ANASTYLOSIS_MT_lod_selector", text=f"L{item.active_lod}", icon='MOD_DECIM')


                # Search SF/VSF button (replaces old link_to_sf)
                op = row.operator("anastylosis.search_sf_node", text="", icon='VIEWZOOM', emboss=False)
                op.anastylosis_index = index

                # Selection object (inline)
                op = row.operator("anastylosis.select_from_list", text="", icon='RESTRICT_SELECT_OFF', emboss=False)
                op.anastylosis_index = index

                # Publish flag with custom icons
                if hasattr(item, 'is_publishable'):
                    pub_icon = icons_manager.get_icon_value("em_publish") if item.is_publishable else icons_manager.get_icon_value("em_no_publish")
                    if pub_icon:
                        row.prop(item, "is_publishable", text="", icon_value=pub_icon)
                    else:
                        row.prop(item, "is_publishable", text="", icon='EXPORT' if item.is_publishable else 'CANCEL')



                # Trash bin for removing
                op = row.operator("anastylosis.remove_from_list", text="", icon='TRASH', emboss=False)
                op.anastylosis_index = index

            elif self.layout_type in {'GRID'}:
                layout.alignment = 'CENTER'
                layout.label(text="", icon='OBJECT_DATA')

        except Exception as e:
            # In case of error, show basic element
            row = layout.row()
            row.label(text=f"Error: {str(e)}", icon='ERROR')

# Operator to update the anastylosis list
class ANASTYLOSIS_OT_update_list(Operator):
    bl_idname = "anastylosis.update_list"
    bl_label = "Update Anastylosis List"
    bl_description = "Update the list of anastylosis models from the graph and scene objects"

    from_graph: BoolProperty(
        name="Update from Graph",
        description="Update the list using graph data. If False, uses only scene objects.",
        default=True
    ) # type: ignore

    def execute(self, context):
        try:
            scene = context.scene
            anastylosis = scene.em_tools.anastylosis
            anastylosis_list = anastylosis.list

            # Save current index to restore after update
            current_index = anastylosis.list_index

            # Track objects already in the list
            existing_objects = {}
            for i, item in enumerate(anastylosis_list):
                if hasattr(item, 'name'):
                    existing_objects[item.name] = {
                        "index": i,
                        "sf_node_id": item.sf_node_id,
                        "is_publishable": item.is_publishable if hasattr(item, 'is_publishable') else True
                    }

            # Get active graph if updating from graph
            graph = None
            if self.from_graph and hasattr(context.scene, 'em_tools'):
                if (hasattr(context.scene.em_tools, 'graphml_files') and
                    len(context.scene.em_tools.graphml_files) > 0 and
                    context.scene.em_tools.active_file_index >= 0):

                    graphml = context.scene.em_tools.graphml_files[context.scene.em_tools.active_file_index]
                    graph = get_graph(graphml.name)

            # If we have a graph, process all RMSF nodes
            if graph:
                # Find all RMSF nodes
                rmsf_nodes = [node for node in graph.nodes if node.node_type == "representation_model_sf"]

                for node in rmsf_nodes:
                    # Extract object name from node_id (assuming node_id format is "{obj_name}_rmsf")
                    obj_name = node.name.replace("RMSF for ", "").strip()

                    # Check if object exists in scene
                    obj_exists = obj_name in bpy.data.objects

                    # Find connected SF/VSF node
                    sf_node = None
                    sf_node_id = ""
                    sf_node_name = ""
                    is_virtual = False

                    # Find edges connecting to SF/VSF nodes
                    for edge in graph.edges:
                        if edge.edge_source == node.node_id and edge.edge_type == "has_representation_model":
                            target_node = graph.find_node_by_id(edge.edge_target)
                            if target_node and target_node.node_type in ["SF", "VSF"]:
                                sf_node = target_node
                                sf_node_id = target_node.node_id
                                sf_node_name = target_node.name
                                is_virtual = target_node.node_type == "VSF"
                                break
                        elif edge.edge_target == node.node_id and edge.edge_type == "has_representation_model":
                            source_node = graph.find_node_by_id(edge.edge_source)
                            if source_node and source_node.node_type in ["SF", "VSF"]:
                                sf_node = source_node
                                sf_node_id = source_node.node_id
                                sf_node_name = source_node.name
                                is_virtual = source_node.node_type == "VSF"
                                break

                    # Check if this object is already in the list
                    if obj_name in existing_objects:
                        # Update existing item
                        index = existing_objects[obj_name]["index"]
                        item = anastylosis_list[index]
                        item.sf_node_id = sf_node_id
                        item.sf_node_name = sf_node_name
                        item.is_virtual = is_virtual
                        item.node_id = node.node_id
                        item.object_exists = obj_exists
                    else:
                        # Create new item
                        item = anastylosis_list.add()
                        item.name = obj_name
                        item.sf_node_id = sf_node_id
                        item.sf_node_name = sf_node_name
                        item.is_virtual = is_virtual
                        item.node_id = node.node_id
                        item.object_exists = obj_exists
                        item.is_publishable = node.attributes.get('is_publishable', True) if hasattr(node, 'attributes') else True

                    # Detect LOD variants
                    variants = detect_lod_variants(item.name)
                    item.has_lod_variants = len(variants) > 1
                    item.lod_count = len(variants)
                    m = re.match(r'^.+_LOD(\d+)$', item.name)
                    item.active_lod = int(m.group(1)) if m else 0

            # Process all selected objects from scene if needed
            if not self.from_graph or not graph:
                # Get all selected mesh objects
                selected_objects = [obj for obj in context.selected_objects if obj.type == 'MESH']

                for obj in selected_objects:
                    # Skip if already processed from graph
                    if obj.name in existing_objects:
                        continue

                    # Create new item for this object
                    item = anastylosis_list.add()
                    item.name = obj.name
                    item.object_exists = True
                    item.is_publishable = True

                    # Set up node ID following same convention as other modules
                    item.node_id = f"{obj.name}_rmsf"

                    # Detect LOD variants
                    variants = detect_lod_variants(item.name)
                    item.has_lod_variants = len(variants) > 1
                    item.lod_count = len(variants)
                    m = re.match(r'^.+_LOD(\d+)$', item.name)
                    item.active_lod = int(m.group(1)) if m else 0

            # Restore index if possible
            anastylosis.list_index = min(current_index, len(anastylosis_list)-1) if anastylosis_list else 0

            # Report
            if self.from_graph:
                self.report({'INFO'}, f"Updated anastylosis list from graph: {len(anastylosis_list)} models")
            else:
                self.report({'INFO'}, f"Updated anastylosis list from scene: {len(anastylosis_list)} models")

            return {'FINISHED'}

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.report({'ERROR'}, f"Error updating anastylosis list: {str(e)}")
            return {'CANCELLED'}

# Operator to link an object to a SF/VSF node (kept for backward compatibility)
class ANASTYLOSIS_OT_link_to_sf(Operator):
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

        # Get item from anastylosis list
        if self.anastylosis_index < 0:
            self.anastylosis_index = anastylosis.list_index

        if self.anastylosis_index < 0 or self.anastylosis_index >= len(anastylosis.list):
            self.report({'ERROR'}, "No anastylosis model selected")
            return {'CANCELLED'}

        item = anastylosis.list[self.anastylosis_index]

        # Get object
        obj = bpy.data.objects.get(item.name)
        if not obj:
            self.report({'ERROR'}, f"Object {item.name} not found in scene")
            return {'CANCELLED'}

        # Get active stratigraphy item
        strat = scene.em_tools.stratigraphy
        if strat.units_index < 0 or strat.units_index >= len(strat.units):
            self.report({'ERROR'}, "No active stratigraphy unit selected")
            return {'CANCELLED'}

        active_strat_item = strat.units[strat.units_index]

        # Get graph
        graph = None
        if context.scene.em_tools.active_file_index >= 0:
            graphml = context.scene.em_tools.graphml_files[context.scene.em_tools.active_file_index]
            graph = get_graph(graphml.name)

        if not graph:
            self.report({'ERROR'}, "No active graph available")
            return {'CANCELLED'}

        # Get SF node
        sf_node = graph.find_node_by_id(active_strat_item.id_node)
        if not sf_node:
            self.report({'ERROR'}, f"SpecialFind node {active_strat_item.id_node} not found in graph")
            return {'CANCELLED'}

        # Check if it's actually a SF or VSF
        if sf_node.node_type not in ["SF", "VSF"]:
            self.report({'ERROR'}, f"Active node is not a SpecialFind (type: {sf_node.node_type})")
            return {'CANCELLED'}

        # Proceed with linking
        # Get or create RMSF node
        rmsf_id = f"{item.name}_rmsf"
        rmsf_node = graph.find_node_by_id(rmsf_id)

        if not rmsf_node:
            # Get object transform
            transform = {
                "position": [f"{obj.location.x}", f"{obj.location.y}", f"{obj.location.z}"],
                "scale": [f"{obj.scale.x}", f"{obj.scale.y}", f"{obj.scale.z}"]
            }

            # Handle rotation based on rotation mode
            if obj.rotation_mode == 'QUATERNION':
                quat = obj.rotation_quaternion
                euler = quat.to_euler('XYZ')
                transform["rotation"] = [f"{euler.x}", f"{euler.y}", f"{euler.z}"]
            else:
                transform["rotation"] = [f"{obj.rotation_euler.x}", f"{obj.rotation_euler.y}", f"{obj.rotation_euler.z}"]

            # Create RMSF node
            rmsf_node = RepresentationModelSpecialFindNode(
                node_id=rmsf_id,
                name=f"RMSF for {item.name}",
                type="RM",
                transform=transform,
                description=f"Representation model for {sf_node.node_type} {sf_node.name}"
            )

            # Add node to graph
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

        # Create or update edge
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
            # Create new LinkNode
            gltf_path = f"models_sf/{item.name}.gltf"
            link_node = LinkNode(
                node_id=link_node_id,
                name=f"GLTF Link for {item.name}",
                description=f"Link to exported GLTF for {sf_node.node_type} {sf_node.name}",
                url=gltf_path,
                url_type="3d_model"
            )
            graph.add_node(link_node)

            # Create edge between RMSF and LinkNode
            edge_id = f"{rmsf_id}_has_linked_resource_{link_node_id}"
            graph.add_edge(
                edge_id=edge_id,
                edge_source=rmsf_id,
                edge_target=link_node_id,
                edge_type="has_linked_resource"
            )

        # Update the anastylosis list
        item.sf_node_id = sf_node.node_id
        item.sf_node_name = sf_node.name
        item.is_virtual = sf_node.node_type == "VSF"
        item.node_id = rmsf_id

        # Refresh the list
        bpy.ops.anastylosis.update_list(from_graph=True)

        self.report({'INFO'}, f"Linked {item.name} to {sf_node.node_type} {sf_node.name}")
        return {'FINISHED'}

# Operator to confirm SF/VSF link selection (kept for backward compatibility)
class ANASTYLOSIS_OT_confirm_link(Operator):
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

        # Check if we have valid selection
        if self.sf_node_index < 0 or self.sf_node_index >= len(anastylosis.sf_nodes):
            self.report({'ERROR'}, "Invalid SpecialFind node selection")
            return {'CANCELLED'}

        # Get the selected SF node
        sf_item = anastylosis.sf_nodes[self.sf_node_index]

        # Get object name and RMSF ID from temp properties
        obj_name = anastylosis.temp_obj_name
        rmsf_id = anastylosis.temp_rmsf_id

        # Get object
        obj = bpy.data.objects.get(obj_name)
        if not obj:
            self.report({'ERROR'}, f"Object {obj_name} not found in scene")
            return {'CANCELLED'}

        # Get graph
        graph = None
        if context.scene.em_tools.active_file_index >= 0:
            graphml = context.scene.em_tools.graphml_files[context.scene.em_tools.active_file_index]
            graph = get_graph(graphml.name)

        if not graph:
            self.report({'ERROR'}, "No active graph available")
            return {'CANCELLED'}

        # Get or create RMSF node
        rmsf_node = graph.find_node_by_id(rmsf_id)
        if not rmsf_node:
            # Get object transform
            transform = {
                "position": [f"{obj.location.x}", f"{obj.location.y}", f"{obj.location.z}"],
                "scale": [f"{obj.scale.x}", f"{obj.scale.y}", f"{obj.scale.z}"]
            }

            # Handle rotation based on rotation mode
            if obj.rotation_mode == 'QUATERNION':
                quat = obj.rotation_quaternion
                euler = quat.to_euler('XYZ')
                transform["rotation"] = [f"{euler.x}", f"{euler.y}", f"{euler.z}"]
            else:
                transform["rotation"] = [f"{obj.rotation_euler.x}", f"{obj.rotation_euler.y}", f"{obj.rotation_euler.z}"]

            # Create RMSF node
            rmsf_node = RepresentationModelSpecialFindNode(
                node_id=rmsf_id,
                name=f"RMSF for {obj_name}",
                type="RM",
                transform=transform,
                description=f"Representation model for SpecialFind {obj_name}"
            )

            # Add node to graph
            graph.add_node(rmsf_node)

        # Get SF node
        sf_node = graph.find_node_by_id(sf_item.node_id)
        if not sf_node:
            self.report({'ERROR'}, f"SpecialFind node {sf_item.node_id} not found in graph")
            return {'CANCELLED'}

        # Remove previous has_representation_model edges for this RMSF so relinking updates cleanly
        stale_edges = [
            edge.edge_id
            for edge in list(graph.edges)
            if edge.edge_type == "has_representation_model"
            and (edge.edge_source == rmsf_id or edge.edge_target == rmsf_id)
        ]
        for edge_id in stale_edges:
            graph.remove_edge(edge_id)

        # Create or update edge
        edge_id = f"{sf_item.node_id}_has_representation_model_{rmsf_id}"
        existing_edge = graph.find_edge_by_id(edge_id)

        if not existing_edge:
            graph.add_edge(
                edge_id=edge_id,
                edge_source=sf_item.node_id,
                edge_target=rmsf_id,
                edge_type="has_representation_model"
            )

        # Create a LinkNode to store the URL
        link_node_id = f"{rmsf_id}_link"
        link_node = graph.find_node_by_id(link_node_id)

        if not link_node:
            # Create new LinkNode
            gltf_path = f"models_sf/{obj_name}.gltf"
            link_node = LinkNode(
                node_id=link_node_id,
                name=f"GLTF Link for {obj_name}",
                description=f"Link to exported GLTF for SpecialFind {obj_name}",
                url=gltf_path,
                url_type="3d_model"
            )
            graph.add_node(link_node)

            # Create edge between RMSF and LinkNode
            edge_id = f"{rmsf_id}_has_linked_resource_{link_node_id}"
            graph.add_edge(
                edge_id=edge_id,
                edge_source=rmsf_id,
                edge_target=link_node_id,
                edge_type="has_linked_resource"
            )

        # Update the anastylosis list
        for item in anastylosis.list:
            if item.name == obj_name:
                item.sf_node_id = sf_item.node_id
                item.sf_node_name = sf_item.name
                item.is_virtual = "Virtual" in sf_item.description
                break

        # Refresh the list
        bpy.ops.anastylosis.update_list(from_graph=True)

        self.report({'INFO'}, f"Linked {obj_name} to SpecialFind {sf_item.name}")
        return {'FINISHED'}

# Operator to select object from list
class ANASTYLOSIS_OT_select_from_list(Operator):
    bl_idname = "anastylosis.select_from_list"
    bl_label = "Select Object"
    bl_description = "Select this object in the 3D view"

    anastylosis_index: IntProperty(
        name="Anastylosis Index",
        description="Index of the anastylosis item in the list",
        default=-1
    )

    def execute(self, context):
        scene = context.scene
        anastylosis = scene.em_tools.anastylosis

        # Get item from list
        if self.anastylosis_index < 0:
            self.anastylosis_index = anastylosis.list_index

        if self.anastylosis_index < 0 or self.anastylosis_index >= len(anastylosis.list):
            self.report({'ERROR'}, "No anastylosis model selected")
            return {'CANCELLED'}

        item = anastylosis.list[self.anastylosis_index]

        # Get object
        obj = bpy.data.objects.get(item.name)
        if not obj:
            self.report({'ERROR'}, f"Object {item.name} not found in scene")
            return {'CANCELLED'}

        # Deselect all objects
        bpy.ops.object.select_all(action='DESELECT')

        # Select the object
        obj.select_set(True)
        context.view_layer.objects.active = obj

        # Zoom to object if settings allow
        if hasattr(anastylosis, 'settings') and anastylosis.settings and anastylosis.settings.zoom_to_selected:
            win = context.window
            scr = win.screen if win else None
            if scr:
                for area in scr.areas:
                    if area.type == 'VIEW_3D':
                        region = next((r for r in area.regions if r.type == 'WINDOW'), None)
                        space = area.spaces.active if hasattr(area, "spaces") else None
                        if region:
                            # Blender 4.5+ context override syntax requires window/screen/area/region
                            with context.temp_override(
                                window=win,
                                screen=scr,
                                area=area,
                                region=region,
                                space_data=space,
                                scene=scene,
                                view_layer=context.view_layer
                            ):
                                bpy.ops.view3d.view_selected()
                        break

        self.report({'INFO'}, f"Selected object: {item.name}")
        return {'FINISHED'}

# Operator to remove from list
class ANASTYLOSIS_OT_remove_from_list(Operator):
    bl_idname = "anastylosis.remove_from_list"
    bl_label = "Remove from Anastylosis"
    bl_description = "Remove this object from anastylosis list and unlink from SpecialFind node"

    anastylosis_index: IntProperty(
        name="Anastylosis Index",
        description="Index of the anastylosis item in the list",
        default=-1
    )

    def execute(self, context):
        scene = context.scene
        anastylosis = scene.em_tools.anastylosis

        # Get item from list
        if self.anastylosis_index < 0:
            self.anastylosis_index = anastylosis.list_index

        if self.anastylosis_index < 0 or self.anastylosis_index >= len(anastylosis.list):
            self.report({'ERROR'}, "No anastylosis model selected")
            return {'CANCELLED'}

        item = anastylosis.list[self.anastylosis_index]

        # Get graph
        graph = None
        if context.scene.em_tools.active_file_index >= 0:
            graphml = context.scene.em_tools.graphml_files[context.scene.em_tools.active_file_index]
            graph = get_graph(graphml.name)

        # Remove from graph using shared helper
        _remove_item_from_graph(graph, item)

        # Remove from list
        item_name = item.name
        anastylosis.list.remove(self.anastylosis_index)

        # Update index if needed
        if anastylosis.list_index >= len(anastylosis.list):
            anastylosis.list_index = max(0, len(anastylosis.list) - 1)

        self.report({'INFO'}, f"Removed {item_name} from anastylosis list")
        return {'FINISHED'}

# Operator to add selected objects to the list
class ANASTYLOSIS_OT_add_selected(Operator):
    bl_idname = "anastylosis.add_selected"
    bl_label = "Add Selected Objects"
    bl_description = "Add selected mesh objects to the anastylosis list"

    def execute(self, context):
        scene = context.scene
        anastylosis = scene.em_tools.anastylosis

        # Get all selected mesh objects
        selected_objects = [obj for obj in context.selected_objects if obj.type == 'MESH']

        if not selected_objects:
            self.report({'ERROR'}, "No mesh objects selected")
            return {'CANCELLED'}

        # Keep track of objects added
        added_count = 0

        # Get graph (optional)
        graph = None
        if context.scene.em_tools.active_file_index >= 0:
            graphml = context.scene.em_tools.graphml_files[context.scene.em_tools.active_file_index]
            graph = get_graph(graphml.name)

        # Find existing objects in the list
        existing_objects = {item.name for item in anastylosis.list}

        for obj in selected_objects:
            # Skip if already in list
            if obj.name in existing_objects:
                continue

            # Create new item
            item = anastylosis.list.add()
            item.name = obj.name
            item.object_exists = True
            item.is_publishable = True
            item.node_id = f"{obj.name}_rmsf"

            # Detect LOD variants
            variants = detect_lod_variants(item.name)
            item.has_lod_variants = len(variants) > 1
            item.lod_count = len(variants)
            m = re.match(r'^.+_LOD(\d+)$', item.name)
            item.active_lod = int(m.group(1)) if m else 0

            # If we have a graph, create RMSF node
            if graph:
                # Check if node already exists
                existing_node = graph.find_node_by_id(item.node_id)
                if not existing_node:
                    # Get object transform
                    transform = {
                        "position": [f"{obj.location.x}", f"{obj.location.y}", f"{obj.location.z}"],
                        "scale": [f"{obj.scale.x}", f"{obj.scale.y}", f"{obj.scale.z}"]
                    }

                    # Handle rotation based on rotation mode
                    if obj.rotation_mode == 'QUATERNION':
                        quat = obj.rotation_quaternion
                        euler = quat.to_euler('XYZ')
                        transform["rotation"] = [f"{euler.x}", f"{euler.y}", f"{euler.z}"]
                    else:
                        transform["rotation"] = [f"{obj.rotation_euler.x}", f"{obj.rotation_euler.y}", f"{obj.rotation_euler.z}"]

                    # Create RMSF node
                    rmsf_node = RepresentationModelSpecialFindNode(
                        node_id=item.node_id,
                        name=f"RMSF for {obj.name}",
                        type="RM",
                        transform=transform,
                        description=f"Representation model for SpecialFind {obj.name}"
                    )

                    # Add node to graph
                    graph.add_node(rmsf_node)

            added_count += 1

        # Update list if objects added
        if added_count > 0:
            bpy.ops.anastylosis.update_list(from_graph=graph is not None)

        self.report({'INFO'}, f"Added {added_count} objects to anastylosis list")
        return {'FINISHED'}

# Operator to remove selected objects from list (batch)
class ANASTYLOSIS_OT_remove_selected(Operator):
    bl_idname = "anastylosis.remove_selected"
    bl_label = "Remove Selected from Anastylosis"
    bl_description = "Remove all selected objects from the anastylosis list and unlink from graph"

    def execute(self, context):
        scene = context.scene
        anastylosis = scene.em_tools.anastylosis
        selected_names = {obj.name for obj in context.selected_objects}

        # Find indices to remove (from bottom to top to not invalidate indices)
        indices_to_remove = []
        for i, item in enumerate(anastylosis.list):
            if item.name in selected_names:
                indices_to_remove.append(i)

        if not indices_to_remove:
            self.report({'WARNING'}, "No selected objects found in the anastylosis list")
            return {'CANCELLED'}

        # Get graph
        graph = None
        if context.scene.em_tools.active_file_index >= 0:
            graphml = context.scene.em_tools.graphml_files[context.scene.em_tools.active_file_index]
            graph = get_graph(graphml.name)

        # Remove from graph and list (reverse order)
        removed_count = 0
        for idx in reversed(indices_to_remove):
            item = anastylosis.list[idx]
            # Remove from graph using shared helper
            _remove_item_from_graph(graph, item)
            anastylosis.list.remove(idx)
            removed_count += 1

        # Update index
        if anastylosis.list_index >= len(anastylosis.list):
            anastylosis.list_index = max(0, len(anastylosis.list) - 1)

        self.report({'INFO'}, f"Removed {removed_count} objects from anastylosis list")
        return {'FINISHED'}


class ANASTYLOSIS_OT_cleanup_missing_objects(Operator):
    bl_idname = "anastylosis.cleanup_missing_objects"
    bl_label = "Clean Missing Anastylosis Rows"
    bl_description = "Remove anastylosis rows whose objects no longer exist in scene"

    def execute(self, context):
        scene = context.scene
        anastylosis = scene.em_tools.anastylosis

        graph = None
        if context.scene.em_tools.active_file_index >= 0:
            graphml = context.scene.em_tools.graphml_files[context.scene.em_tools.active_file_index]
            graph = get_graph(graphml.name)

        removed = 0
        for idx in range(len(anastylosis.list) - 1, -1, -1):
            item = anastylosis.list[idx]
            if bpy.data.objects.get(item.name) is None:
                _remove_item_from_graph(graph, item)
                anastylosis.list.remove(idx)
                removed += 1

        if anastylosis.list_index >= len(anastylosis.list):
            anastylosis.list_index = max(0, len(anastylosis.list) - 1)

        self.report({'INFO'}, f"Cleaned {removed} missing object row(s) from anastylosis list")
        return {'FINISHED'}

# Operator to select in list from active 3D object
class ANASTYLOSIS_OT_select_from_object(Operator):
    bl_idname = "anastylosis.select_from_object"
    bl_label = "Select in List from Active Object"
    bl_description = "Find and select the active 3D object in the anastylosis list"

    def execute(self, context):
        obj = context.active_object
        if not obj:
            self.report({'ERROR'}, "No active object")
            return {'CANCELLED'}

        anastylosis = context.scene.em_tools.anastylosis
        for i, item in enumerate(anastylosis.list):
            if item.name == obj.name:
                anastylosis.list_index = i
                self.report({'INFO'}, f"Selected {obj.name} in list (index {i})")
                return {'FINISHED'}

        self.report({'WARNING'}, f"Object '{obj.name}' not found in anastylosis list")
        return {'CANCELLED'}

# Search popup for SF/VSF nodes (replaces link_to_sf in the UI)
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

        # Search box
        layout.prop(self, "search_query", text="", icon='VIEWZOOM')
        layout.separator()

        # Get the active graph
        em_tools = context.scene.em_tools
        if em_tools.active_file_index < 0:
            layout.label(text="No active graph", icon='ERROR')
            return

        graph_info = em_tools.graphml_files[em_tools.active_file_index]
        graph = get_graph(graph_info.name)

        if not graph:
            layout.label(text="Graph not loaded", icon='ERROR')
            return

        # Filter SF and VSF nodes by search query
        sf_nodes = []
        for node in graph.nodes:
            if hasattr(node, 'node_type') and node.node_type in ["SF", "VSF"]:
                node_id = node.node_id if hasattr(node, 'node_id') else ""
                node_name = node.name if hasattr(node, 'name') else ""

                # Search in both node_id and name
                search_lower = self.search_query.lower()
                if (not self.search_query or
                    search_lower in node_id.lower() or
                    search_lower in node_name.lower()):
                    sf_nodes.append(node)

        # Sort by name
        sf_nodes.sort(key=lambda x: x.name)

        # Display results
        if sf_nodes:
            box = layout.box()
            icon_val = icons_manager.get_icon_value("show_all_proxies")
            box.label(text=f"Found {len(sf_nodes)} SF/VSF nodes:", icon='MESH_ICOSPHERE')

            # Limit display to first 20 results
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

# Operator to assign an SF/VSF node to an anastylosis item (called from search popup)
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

        # Get item from anastylosis list
        if self.anastylosis_index < 0:
            self.anastylosis_index = anastylosis.list_index

        if self.anastylosis_index < 0 or self.anastylosis_index >= len(anastylosis.list):
            self.report({'ERROR'}, "No anastylosis model selected")
            return {'CANCELLED'}

        item = anastylosis.list[self.anastylosis_index]

        # Get object
        obj = bpy.data.objects.get(item.name)
        if not obj:
            self.report({'ERROR'}, f"Object {item.name} not found in scene")
            return {'CANCELLED'}

        # Get graph
        graph = None
        if context.scene.em_tools.active_file_index >= 0:
            graphml = context.scene.em_tools.graphml_files[context.scene.em_tools.active_file_index]
            graph = get_graph(graphml.name)

        if not graph:
            self.report({'ERROR'}, "No active graph available")
            return {'CANCELLED'}

        # Find the SF node in the graph
        sf_node = graph.find_node_by_id(self.sf_node_id)
        if not sf_node:
            self.report({'ERROR'}, f"SpecialFind node {self.sf_node_id} not found in graph")
            return {'CANCELLED'}

        # Check if it's actually a SF or VSF
        if sf_node.node_type not in ["SF", "VSF"]:
            self.report({'ERROR'}, f"Node is not a SpecialFind (type: {sf_node.node_type})")
            return {'CANCELLED'}

        # Get or create RMSF node
        rmsf_id = f"{item.name}_rmsf"
        rmsf_node = graph.find_node_by_id(rmsf_id)

        if not rmsf_node:
            # Get object transform
            transform = {
                "position": [f"{obj.location.x}", f"{obj.location.y}", f"{obj.location.z}"],
                "scale": [f"{obj.scale.x}", f"{obj.scale.y}", f"{obj.scale.z}"]
            }

            # Handle rotation based on rotation mode
            if obj.rotation_mode == 'QUATERNION':
                quat = obj.rotation_quaternion
                euler = quat.to_euler('XYZ')
                transform["rotation"] = [f"{euler.x}", f"{euler.y}", f"{euler.z}"]
            else:
                transform["rotation"] = [f"{obj.rotation_euler.x}", f"{obj.rotation_euler.y}", f"{obj.rotation_euler.z}"]

            # Create RMSF node
            rmsf_node = RepresentationModelSpecialFindNode(
                node_id=rmsf_id,
                name=f"RMSF for {item.name}",
                type="RM",
                transform=transform,
                description=f"Representation model for {sf_node.node_type} {sf_node.name}"
            )

            # Add node to graph
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
            gltf_path = f"models_sf/{item.name}.gltf"
            link_node = LinkNode(
                node_id=link_node_id,
                name=f"GLTF Link for {item.name}",
                description=f"Link to exported GLTF for {sf_node.node_type} {sf_node.name}",
                url=gltf_path,
                url_type="3d_model"
            )
            graph.add_node(link_node)

            # Create edge between RMSF and LinkNode
            edge_id = f"{rmsf_id}_has_linked_resource_{link_node_id}"
            graph.add_edge(
                edge_id=edge_id,
                edge_source=rmsf_id,
                edge_target=link_node_id,
                edge_type="has_linked_resource"
            )

        # Update the anastylosis list item
        item.sf_node_id = sf_node.node_id
        item.sf_node_name = sf_node.name
        item.is_virtual = sf_node.node_type == "VSF"
        item.node_id = rmsf_id

        # Refresh the list
        bpy.ops.anastylosis.update_list(from_graph=True)

        self.report({'INFO'}, f"Linked {item.name} to {sf_node.node_type} {sf_node.name}")
        return {'FINISHED'}

# Operator to switch LOD level for a single item
class ANASTYLOSIS_OT_switch_lod(Operator):
    bl_idname = "anastylosis.switch_lod"
    bl_label = "Switch LOD"
    bl_description = "Switch this item to a different Level of Detail"

    anastylosis_index: IntProperty(
        name="Anastylosis Index",
        default=-1
    ) # type: ignore

    target_lod: IntProperty(
        name="Target LOD",
        default=0
    ) # type: ignore

    def execute(self, context):
        anastylosis = context.scene.em_tools.anastylosis

        if self.anastylosis_index < 0 or self.anastylosis_index >= len(anastylosis.list):
            self.report({'ERROR'}, "Invalid anastylosis index")
            return {'CANCELLED'}

        item = anastylosis.list[self.anastylosis_index]

        obj = bpy.data.objects.get(item.name)
        requested_lod = max(LOD_MIN_LEVEL, min(LOD_MAX_LEVEL, int(self.target_lod)))

        if not obj:
            self.report({'ERROR'}, f"Object '{item.name}' not found in scene")
            return {'CANCELLED'}

        # Linked mesh workflow: swap mesh datablock from library and fallback automatically.
        if obj.type == 'MESH' and obj.data and obj.data.library:
            ok, resolved_lod, target_mesh_name, err = _switch_linked_mesh_lod(obj, requested_lod)
            if not ok:
                self.report({'ERROR'}, err or "LOD switch failed")
                return {'CANCELLED'}
            if resolved_lod != requested_lod:
                self.report({'WARNING'}, LOD_FALLBACK_WARNING)

            item.name = obj.name
            item.active_lod = resolved_lod
            item.object_exists = True
            self.report({'INFO'}, f"Set LOD {resolved_lod} ({target_mesh_name})")
            return {'FINISHED'}

        # Local-scene workflow: switch visibility to an existing object variant in scene.
        variants = detect_lod_variants(item.name)
        if not variants:
            self.report({'ERROR'}, "No LOD variants found in scene")
            return {'CANCELLED'}

        by_level = {lod_level: lod_name for lod_level, lod_name in variants}
        resolved_lod = _resolve_lod_with_fallback(by_level.keys(), requested_lod)
        if resolved_lod is None or resolved_lod not in by_level:
            self.report({'ERROR'}, f"No usable LOD in range {LOD_MIN_LEVEL}-{LOD_MAX_LEVEL}")
            return {'CANCELLED'}

        target_name = by_level[resolved_lod]
        if resolved_lod != requested_lod:
            self.report({'WARNING'}, LOD_FALLBACK_WARNING)
        if target_name == item.name:
            item.active_lod = resolved_lod
            self.report({'INFO'}, f"Already at LOD {resolved_lod}")
            return {'FINISHED'}

        old_obj = obj
        new_obj = bpy.data.objects.get(target_name)
        if old_obj:
            old_obj.hide_viewport = True
            old_obj.hide_render = True
        if new_obj:
            new_obj.hide_viewport = False
            new_obj.hide_render = False

        item.name = target_name
        item.active_lod = resolved_lod
        item.object_exists = new_obj is not None

        self.report({'INFO'}, f"Set LOD {resolved_lod} ({target_name})")
        return {'FINISHED'}

# Operator for batch LOD switching across all items
class ANASTYLOSIS_OT_batch_switch_lod(Operator):
    bl_idname = "anastylosis.batch_switch_lod"
    bl_label = "Batch Switch LOD"
    bl_description = "Switch LOD level for all items that have LOD variants"

    direction: IntProperty(
        name="Direction",
        description="+1 for higher LOD number, -1 for lower",
        default=1
    ) # type: ignore

    def execute(self, context):
        anastylosis = context.scene.em_tools.anastylosis
        switched = 0
        fallback_applied = False

        for item in anastylosis.list:
            obj = bpy.data.objects.get(item.name)
            if not obj or obj.type != 'MESH':
                continue

            target_lod = max(LOD_MIN_LEVEL, min(LOD_MAX_LEVEL, item.active_lod + self.direction))

            if obj.data and obj.data.library:
                ok, resolved_lod, _target_mesh_name, _err = _switch_linked_mesh_lod(obj, target_lod)
                if ok:
                    if resolved_lod != target_lod:
                        fallback_applied = True
                    item.name = obj.name
                    item.active_lod = resolved_lod
                    item.object_exists = True
                    switched += 1
                continue

            variants = detect_lod_variants(item.name)
            if len(variants) <= 1:
                continue

            by_level = {lod_level: lod_name for lod_level, lod_name in variants}
            resolved_lod = _resolve_lod_with_fallback(by_level.keys(), target_lod)
            if resolved_lod is None or resolved_lod not in by_level:
                continue
            if resolved_lod != target_lod:
                fallback_applied = True

            target_name = by_level[resolved_lod]
            if target_name == item.name:
                item.active_lod = resolved_lod
                continue

            old_obj = obj
            new_obj = bpy.data.objects.get(target_name)
            if old_obj:
                old_obj.hide_viewport = True
                old_obj.hide_render = True
            if new_obj:
                new_obj.hide_viewport = False
                new_obj.hide_render = False
            item.name = target_name
            item.active_lod = resolved_lod
            item.object_exists = new_obj is not None
            switched += 1

        direction_text = "higher" if self.direction > 0 else "lower"
        if fallback_applied:
            self.report({'WARNING'}, LOD_FALLBACK_WARNING)
        self.report({'INFO'}, f"Switched {switched} items to {direction_text} LOD")
        return {'FINISHED'}

# Menu for LOD level selection (per-item dropdown in UIList)
class ANASTYLOSIS_MT_lod_selector(bpy.types.Menu):
    bl_label = "Select LOD Level"
    bl_idname = "ANASTYLOSIS_MT_lod_selector"

    def draw(self, context):
        layout = self.layout
        anastylosis = context.scene.em_tools.anastylosis
        if anastylosis.list_index < 0 or anastylosis.list_index >= len(anastylosis.list):
            return
        item = anastylosis.list[anastylosis.list_index]
        for lod_level in range(LOD_MIN_LEVEL, LOD_MAX_LEVEL + 1):
            is_active = (item.active_lod == lod_level)
            op = layout.operator("anastylosis.switch_lod",
                                 text=f"LOD {lod_level}" + (" (active)" if is_active else ""),
                                 icon='CHECKMARK' if is_active else 'NONE')
            op.anastylosis_index = anastylosis.list_index
            op.target_lod = lod_level


# Menu for batch LOD switch on selected 3D objects
class ANASTYLOSIS_MT_batch_lod_selected(bpy.types.Menu):
    bl_label = "Batch LOD for Selected"
    bl_idname = "ANASTYLOSIS_MT_batch_lod_selected"

    def draw(self, context):
        layout = self.layout
        for level in range(LOD_MIN_LEVEL, LOD_MAX_LEVEL + 1):
            op = layout.operator("anastylosis.batch_lod_selected", text=f"Set LOD {level}")
            op.target_lod = level


# Operator for batch LOD switch on selected 3D objects
class ANASTYLOSIS_OT_batch_lod_selected(Operator):
    bl_idname = "anastylosis.batch_lod_selected"
    bl_label = "Batch LOD for Selected Objects"
    bl_description = "Switch LOD level for all selected objects that have LOD variants"

    target_lod: IntProperty(
        name="Target LOD",
        default=0
    ) # type: ignore

    def execute(self, context):
        switched = 0
        skipped = 0
        fallback_applied = False
        anastylosis = context.scene.em_tools.anastylosis
        requested_lod = max(LOD_MIN_LEVEL, min(LOD_MAX_LEVEL, int(self.target_lod)))

        for obj in context.selected_objects:
            # Find this object in the anastylosis list
            item_idx = None
            for i, item in enumerate(anastylosis.list):
                if item.name == obj.name:
                    item_idx = i
                    break
            if item_idx is None:
                continue

            item = anastylosis.list[item_idx]
            if obj.type == 'MESH' and obj.data and obj.data.library:
                ok, resolved_lod, _target_mesh_name, _err = _switch_linked_mesh_lod(obj, requested_lod)
                if not ok:
                    skipped += 1
                    continue
                if resolved_lod != requested_lod:
                    fallback_applied = True
                item.name = obj.name
                item.active_lod = resolved_lod
                item.object_exists = True
                switched += 1
                continue

            variants = detect_lod_variants(item.name)
            if not variants:
                skipped += 1
                continue

            by_level = {lod_level: lod_name for lod_level, lod_name in variants}
            resolved_lod = _resolve_lod_with_fallback(by_level.keys(), requested_lod)
            if resolved_lod is None or resolved_lod not in by_level:
                skipped += 1
                continue
            if resolved_lod != requested_lod:
                fallback_applied = True

            target_name = by_level[resolved_lod]
            if target_name == item.name:
                item.active_lod = resolved_lod
                continue

            old_obj = bpy.data.objects.get(item.name)
            new_obj = bpy.data.objects.get(target_name)
            if old_obj:
                old_obj.hide_viewport = True
                old_obj.hide_render = True
            if new_obj:
                new_obj.hide_viewport = False
                new_obj.hide_render = False
            item.name = target_name
            item.active_lod = resolved_lod
            item.object_exists = new_obj is not None
            switched += 1

        if fallback_applied:
            self.report({'WARNING'}, LOD_FALLBACK_WARNING)
        msg = f"Switched {switched} objects to LOD {requested_lod}"
        if skipped > 0:
            msg += f" ({skipped} skipped - LOD not available)"
        self.report({'INFO'}, msg)
        return {'FINISHED'}


class ANASTYLOSIS_OT_open_linked_file(Operator):
    """Open linked .blend file for this anastylosis object in a new Blender instance"""
    bl_idname = "anastylosis.open_linked_file"
    bl_label = "Open Linked File"
    bl_options = {"REGISTER", "UNDO"}

    anastylosis_index: IntProperty(
        name="Anastylosis Index",
        default=-1
    )  # type: ignore

    def execute(self, context):
        anastylosis = context.scene.em_tools.anastylosis
        index = self.anastylosis_index if self.anastylosis_index >= 0 else anastylosis.list_index
        if index < 0 or index >= len(anastylosis.list):
            self.report({'ERROR'}, "No anastylosis item selected")
            return {'CANCELLED'}

        item = anastylosis.list[index]
        obj = bpy.data.objects.get(item.name)
        if not obj:
            self.report({'ERROR'}, f"Object '{item.name}' not found in scene")
            return {'CANCELLED'}

        linked_file = None
        if obj.library:
            linked_file = obj.library.filepath
        elif obj.data and obj.data.library:
            linked_file = obj.data.library.filepath

        if not linked_file:
            self.report({'ERROR'}, f"Object '{obj.name}' is not linked from an external .blend")
            return {'CANCELLED'}

        linked_file = bpy.path.abspath(linked_file)
        if not os.path.exists(linked_file):
            self.report({'ERROR'}, f"Linked file not found: {linked_file}")
            return {'CANCELLED'}

        try:
            subprocess.Popen([bpy.app.binary_path, linked_file])
        except Exception as e:
            self.report({'ERROR'}, f"Failed to open linked file: {str(e)}")
            return {'CANCELLED'}

        self.report({'INFO'}, f"Opened linked file: {linked_file}")
        return {'FINISHED'}


# Settings for Anastylosis Manager
class AnastylisisSettings(PropertyGroup):
    zoom_to_selected: BoolProperty(
        name="Zoom to Selected",
        description="Zoom to the selected object when clicked in the list",
        default=True
    )

    show_settings: BoolProperty(
        name="Show Settings",
        description="Show or hide the settings section",
        default=False
    )

# Temporary item for SF node selection
class AnastylosisSFNodeItem(PropertyGroup):
    node_id: StringProperty(name="Node ID")
    name: StringProperty(name="Name")
    description: StringProperty(name="Description")

# Main Anastylosis Manager Panel
class VIEW3D_PT_Anastylosis_Manager(Panel):
    bl_label = "Anastylosis Manager"
    bl_idname = "VIEW3D_PT_Anastylosis_Manager"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'EM Annotator'
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        em_tools = context.scene.em_tools
        # Show only if we're in advanced EM mode
        return em_tools.mode_em_advanced

    def draw_header(self, context):
        layout = self.layout
        icon_id = icons_manager.get_icon_value("show_all_special_finds")
        if icon_id:
            layout.label(text="", icon_value=icon_id)
        else:
            layout.label(text="", icon='MESH_ICOSPHERE')

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        from .functions import is_graph_available

        # Check if a graph is available
        graph_available, graph = is_graph_available(context)

        '''
        # Update controls
        row = layout.row(align=True)
        row.operator("anastylosis.update_list", text="Update from Scene", icon='FILE_REFRESH').from_graph = False

        # Check if a graph is available
        if graph_available:
            row.operator("anastylosis.update_list", text="Update from Graph", icon='NODE_MATERIAL').from_graph = True
        '''

        # Operations on selected objects (only shown when objects are selected)
        selected_objects = context.selected_objects
        if selected_objects:
            sel_count = len(selected_objects)
            box = layout.box()
            row = box.row(align=True)
            row.label(text=f"Sel: {sel_count} obj{'s' if sel_count != 1 else ''}", icon='OBJECT_DATA')
            row.operator("anastylosis.select_from_object", text="", icon='VIEWZOOM')
            row.operator("anastylosis.add_selected", text="", icon='ADD')
            sub = row.row(align=True)
            sub.alert = True
            sub.operator("anastylosis.remove_selected", text="", icon='TRASH')
            # Batch LOD dropdown (only if at least one selected object has LOD variants)
            has_lod_objects = any(len(detect_lod_variants(obj.name)) >= 1 for obj in selected_objects)
            if has_lod_objects:
                sub = row.row(align=True)
                sub.menu("ANASTYLOSIS_MT_batch_lod_selected", text="", icon='MOD_DECIM')

        row = layout.row(align=True)
        row.operator("anastylosis.cleanup_missing_objects", text="", icon='TRASH')

        # List of anastylosis models
        row = layout.row()
        anastylosis = scene.em_tools.anastylosis
        row.template_list(
            "ANASTYLOSIS_UL_List", "anastylosis_list",
            anastylosis, "list",
            anastylosis, "list_index"
        )

        # Show connection info if an item is selected
        if anastylosis.list_index >= 0 and len(anastylosis.list) > 0:
            item = anastylosis.list[anastylosis.list_index]

            if item.sf_node_id:
                box = layout.box()
                row = box.row()
                sf_icon = 'OUTLINER_OB_EMPTY' if item.is_virtual else 'MESH_ICOSPHERE'
                row.label(text=f"Connected to: {item.sf_node_name}", icon=sf_icon)
            else:
                box = layout.box()
                row = box.row()
                row.label(text="Not connected to any SpecialFind", icon='INFO')

            # LOD Management (if the selected item has LOD variants)
            lod_variants = detect_lod_variants(item.name)

            if len(lod_variants) >= 1:
                box = layout.box()
                row = box.row(align=True)
                op = row.operator("anastylosis.open_linked_file", text="", icon='FILE_FOLDER')
                op.anastylosis_index = anastylosis.list_index
                row.label(text="LOD:")
                for lod_level in range(LOD_MIN_LEVEL, LOD_MAX_LEVEL + 1):
                    sub = row.row(align=True)
                    sub.scale_x = 0.7
                    op = sub.operator(
                        "anastylosis.switch_lod",
                        text=str(lod_level),
                        depress=(item.active_lod == lod_level)
                    )
                    op.anastylosis_index = anastylosis.list_index
                    op.target_lod = lod_level

                # Batch LOD switch for all items
                box.separator()
                row = box.row(align=True)
                row.label(text="Batch LOD switch:", icon='PRESET')
                op = row.operator("anastylosis.batch_switch_lod", text="", icon='TRIA_LEFT')
                op.direction = -1
                op = row.operator("anastylosis.batch_switch_lod", text="", icon='TRIA_RIGHT')
                op.direction = 1

        # Settings (collapsible)
        box = layout.box()
        row = box.row()
        row.prop(anastylosis.settings, "show_settings",
                icon="TRIA_DOWN" if anastylosis.settings.show_settings else "TRIA_RIGHT",
                text="Settings",
                emboss=False)

        if anastylosis.settings.show_settings:
            row = box.row()
            row.prop(anastylosis.settings, "zoom_to_selected")


# Handler to update list when a graph is loaded
@bpy.app.handlers.persistent
def update_anastylosis_list_on_graph_load(dummy):
    """Update anastylosis list when a graph is loaded"""

    # Ensure we're in a context where we can access scene
    if not bpy.context or not hasattr(bpy.context, 'scene'):
        return

    scene = bpy.context.scene

    # Check if graph is available
    if (hasattr(scene, 'em_tools') and
        hasattr(scene.em_tools, 'graphml_files') and
        len(scene.em_tools.graphml_files) > 0 and
        scene.em_tools.active_file_index >= 0):

        try:
            # BLENDER 4.5 COMPATIBLE: Timer callback must return None or float
            def timer_callback():
                bpy.ops.anastylosis.update_list(from_graph=True)
                return None  # Required for Blender 4.5+

            bpy.app.timers.register(timer_callback, first_interval=0.5)
        except Exception as e:
            print(f"Error updating anastylosis list on graph load: {e}")

# Registration classes
classes = [
    ANASTYLOSIS_UL_List,
    ANASTYLOSIS_MT_lod_selector,
    ANASTYLOSIS_MT_batch_lod_selected,
    ANASTYLOSIS_OT_update_list,
    ANASTYLOSIS_OT_link_to_sf,
    ANASTYLOSIS_OT_select_from_list,
    ANASTYLOSIS_OT_remove_from_list,
    ANASTYLOSIS_OT_add_selected,
    ANASTYLOSIS_OT_confirm_link,
    ANASTYLOSIS_OT_remove_selected,
    ANASTYLOSIS_OT_cleanup_missing_objects,
    ANASTYLOSIS_OT_select_from_object,
    ANASTYLOSIS_OT_search_sf_node,
    ANASTYLOSIS_OT_assign_sf_node,
    ANASTYLOSIS_OT_open_linked_file,
    ANASTYLOSIS_OT_switch_lod,
    ANASTYLOSIS_OT_batch_switch_lod,
    ANASTYLOSIS_OT_batch_lod_selected,
    VIEW3D_PT_Anastylosis_Manager,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    # Register handler
    if update_anastylosis_list_on_graph_load not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(update_anastylosis_list_on_graph_load)

def unregister():
    # Remove handler
    if update_anastylosis_list_on_graph_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(update_anastylosis_list_on_graph_load)

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
