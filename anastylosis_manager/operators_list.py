# anastylosis_manager/operators_list.py
"""List-management operators: update, select, add, remove, cleanup."""

import bpy
from bpy.props import BoolProperty, IntProperty, StringProperty
from bpy.types import Operator

from s3dgraphy import get_graph
from s3dgraphy.nodes.representation_node import RepresentationModelSpecialFindNode

from .lod_utils import detect_lod_variants, _get_active_lod
from .graph_utils import (
    _remove_item_from_graph,
    analyze_visibility_requirements,
    apply_visibility_changes,
)


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
                    item.has_lod_variants = len(variants) >= 1
                    item.lod_count = len(variants)
                    item.active_lod = _get_active_lod(item.name)

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
                    item.has_lod_variants = len(variants) >= 1
                    item.lod_count = len(variants)
                    item.active_lod = _get_active_lod(item.name)

            # ── Sanitise stale rows ────────────────────────────────
            # Drop entries whose name maps neither to an RMSF graph
            # node (well-formed, possibly orphan of an SF link — still
            # a valid RMSF the user can complete here) NOR to a scene
            # mesh. Those entries are leftovers from past iterations
            # (manual property tinkering, partial imports, etc.) and
            # would otherwise keep coming back on every refresh.
            graph_rmsf_obj_names = set()
            if graph:
                for node in graph.nodes:
                    if getattr(node, 'node_type', '') != "representation_model_sf":
                        continue
                    nname = getattr(node, 'name', '') or ''
                    obj_name = nname.replace("RMSF for ", "").strip()
                    if obj_name:
                        graph_rmsf_obj_names.add(obj_name)
            i = len(anastylosis_list) - 1
            removed = 0
            while i >= 0:
                row = anastylosis_list[i]
                in_graph = (graph is not None
                             and row.name in graph_rmsf_obj_names)
                in_scene = row.name in bpy.data.objects
                if not in_graph and not in_scene:
                    anastylosis_list.remove(i)
                    removed += 1
                i -= 1

            # Restore index if possible
            anastylosis.list_index = min(current_index, len(anastylosis_list)-1) if anastylosis_list else 0

            # Report
            stale_msg = f" — pruned {removed} stale" if removed else ""
            if self.from_graph:
                self.report({'INFO'},
                            f"Updated anastylosis list from graph: "
                            f"{len(anastylosis_list)} models"
                            f"{stale_msg}")
            else:
                self.report({'INFO'},
                            f"Updated anastylosis list from scene: "
                            f"{len(anastylosis_list)} models"
                            f"{stale_msg}")

            return {'FINISHED'}

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.report({'ERROR'}, f"Error updating anastylosis list: {str(e)}")
            return {'CANCELLED'}


class ANASTYLOSIS_OT_select_from_list(Operator):
    bl_idname = "anastylosis.select_from_list"
    bl_label = "Select Object"
    bl_description = "Select this object in the 3D view"

    anastylosis_index: IntProperty(
        name="Anastylosis Index",
        description="Index of the anastylosis item in the list",
        default=-1
    )

    changes_description: StringProperty(default="")  # type: ignore

    def invoke(self, context, event):
        scene = context.scene
        anastylosis = scene.em_tools.anastylosis
        index = self.anastylosis_index if self.anastylosis_index >= 0 else anastylosis.list_index

        if index < 0 or index >= len(anastylosis.list):
            self.report({'ERROR'}, "No anastylosis model selected")
            return {'CANCELLED'}

        anastylosis.list_index = index
        self.anastylosis_index = index

        item = anastylosis.list[index]
        obj = bpy.data.objects.get(item.name)
        if not obj:
            self.report({'ERROR'}, f"Object {item.name} not found in scene")
            return {'CANCELLED'}

        analysis = analyze_visibility_requirements(context, [obj])
        if analysis['total_changes'] == 0:
            return self.execute(context)

        parts = []
        if analysis['needs_unhide']:
            parts.append("unhide object")
        if analysis['needs_unprotect']:
            parts.append("unlock selection")
        if analysis['needs_collection_activation']:
            col_count = len(analysis['needs_collection_activation'])
            parts.append(f"activate {col_count} collection{'s' if col_count > 1 else ''}")
        self.changes_description = ", ".join(parts)

        return context.window_manager.invoke_props_dialog(self, width=350)

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        anastylosis = scene.em_tools.anastylosis
        index = self.anastylosis_index if self.anastylosis_index >= 0 else anastylosis.list_index
        if index < 0 or index >= len(anastylosis.list):
            return
        item = anastylosis.list[index]

        layout.label(text=f"To select '{item.name}':", icon='INFO')
        layout.label(text=f"  {self.changes_description}")
        layout.separator()
        layout.label(text="Press OK to proceed, or cancel to abort.")

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

        apply_visibility_changes(context, [obj])

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


class ANASTYLOSIS_OT_remove_from_list(Operator):
    bl_idname = "anastylosis.remove_from_list"
    bl_label = "Remove from Anastylosis"
    bl_description = "Remove this object from anastylosis list and unlink from SpecialFind node"

    anastylosis_index: IntProperty(
        name="Anastylosis Index",
        description="Index of the anastylosis item in the list",
        default=-1
    )

    def invoke(self, context, event):
        # Destructive: unlinks the object from its SpecialFind node in
        # the graph. Confirm before letting it through.
        return context.window_manager.invoke_confirm(self, event)

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
            item.has_lod_variants = len(variants) >= 1
            item.lod_count = len(variants)
            item.active_lod = _get_active_lod(item.name)

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


class ANASTYLOSIS_OT_remove_selected(Operator):
    bl_idname = "anastylosis.remove_selected"
    bl_label = "Remove Selected from Anastylosis"
    bl_description = "Remove all selected objects from the anastylosis list and unlink from graph"

    def invoke(self, context, event):
        # Bulk destructive operation: confirm before unlinking every
        # selected object from its SpecialFind.
        return context.window_manager.invoke_confirm(self, event)

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


classes = (
    ANASTYLOSIS_OT_update_list,
    ANASTYLOSIS_OT_select_from_list,
    ANASTYLOSIS_OT_remove_from_list,
    ANASTYLOSIS_OT_add_selected,
    ANASTYLOSIS_OT_remove_selected,
    ANASTYLOSIS_OT_cleanup_missing_objects,
    ANASTYLOSIS_OT_select_from_object,
    None,  # placeholder; replaced after class definitions below
)


class ANASTYLOSIS_OT_jump_to_document(Operator):
    """Highlight the linked Document in the Document Manager catalog.

    Mirrors :class:`RMDOC_OT_jump_to_document`: sets
    ``scene.doc_list_index`` to the matching row so the user can move
    from the RMSF detail panel to the catalog with a single click.
    """
    bl_idname = "anastylosis.jump_to_document"
    bl_label = "Show in Document Manager"
    bl_description = (
        "Highlight this RMSF's linked Document in the Document Manager "
        "catalog")

    doc_node_id: StringProperty()  # type: ignore

    def execute(self, context):
        scene = context.scene
        if not self.doc_node_id:
            self.report({'WARNING'}, "No linked document")
            return {'CANCELLED'}
        doc_list = getattr(scene, 'doc_list', None)
        if doc_list is None:
            return {'CANCELLED'}
        for i, item in enumerate(doc_list):
            if item.node_id == self.doc_node_id:
                scene.doc_list_index = i
                self.report({'INFO'},
                            f"Jumped to document {item.name}")
                return {'FINISHED'}
        self.report({'WARNING'},
                    "Linked document not found in catalog")
        return {'CANCELLED'}


class ANASTYLOSIS_OT_select_sf_proxy(Operator):
    """Select the SF proxy object in the viewport for this RMSF row.

    Looks up a scene object whose name matches the linked SF node
    name, optionally prefixed by the active graph code (the same
    naming convention used by Stratigraphy Manager / Document
    Manager). When no proxy is found, the operator reports the miss
    so the future "create primitive proxy" tool has a clear hook.
    """
    bl_idname = "anastylosis.select_sf_proxy"
    bl_label = "Select SF Proxy"
    bl_description = (
        "Select the SpecialFind's proxy object in the 3D viewport. "
        "If no proxy exists yet, you'll need to create one (a future "
        "tool will generate a simplified primitive automatically)")

    anastylosis_index: IntProperty(default=-1)  # type: ignore

    def execute(self, context):
        scene = context.scene
        anastylosis = scene.em_tools.anastylosis
        idx = (self.anastylosis_index
               if self.anastylosis_index >= 0
               else anastylosis.list_index)
        if idx < 0 or idx >= len(anastylosis.list):
            self.report({'ERROR'}, "No anastylosis model selected")
            return {'CANCELLED'}
        item = anastylosis.list[idx]
        if not item.sf_node_name:
            self.report({'WARNING'}, "No SF linked to this RMSF")
            return {'CANCELLED'}

        # Try direct name match first, then with graph prefix.
        target = bpy.data.objects.get(item.sf_node_name)
        if target is None:
            try:
                from ..operators.addon_prefix_helpers import (
                    node_name_to_proxy_name)
                from ..functions import is_graph_available
                ok, graph = is_graph_available(context)
                if ok and graph is not None:
                    prefixed = node_name_to_proxy_name(
                        item.sf_node_name, context=context, graph=graph)
                    target = bpy.data.objects.get(prefixed)
            except Exception:
                pass

        if target is None:
            self.report(
                {'WARNING'},
                f"SF proxy {item.sf_node_name!r} not found in the "
                "scene. Create the proxy (manually or with the future "
                "primitive-from-mesh tool) before retrying.")
            return {'CANCELLED'}

        try:
            bpy.ops.object.select_all(action='DESELECT')
        except RuntimeError:
            pass
        target.select_set(True)
        context.view_layer.objects.active = target
        self.report({'INFO'}, f"Selected SF proxy {target.name}")
        return {'FINISHED'}


# Patch the placeholder above with the freshly-defined class so the
# registration tuple stays a single source of truth.
classes = tuple(c for c in classes if c is not None) + (
    ANASTYLOSIS_OT_jump_to_document,
    ANASTYLOSIS_OT_select_sf_proxy,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
