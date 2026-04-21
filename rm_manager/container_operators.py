"""Operators for the RM container feature (DP-47 extension).

Exposes:

- :class:`RMCONTAINER_OT_link_existing_document` — pick a Document
  from the Document Manager list and create an (empty) container
  linked to it.
- :class:`RMCONTAINER_OT_create_and_link_new_document` — invoke the
  shared ``docmanager.create_master_document`` dialog and, once a
  Document is created, wrap it in a new container.
- :class:`RMCONTAINER_OT_add_selected_meshes` — add every selected
  MESH object to the active container (graph edges + custom props).
- :class:`RMCONTAINER_OT_remove_mesh_from_container` — remove one
  mesh from the active container (drops the edge).
- :class:`RMCONTAINER_OT_unregister` — drop a container and every
  ``has_representation_model`` edge it implied. Document stays.
- :class:`RMCONTAINER_OT_sync` — run the sanitisation pass.
- :class:`RMCONTAINER_OT_acknowledge_warnings` — clear the warnings.
"""

from __future__ import annotations

import bpy  # type: ignore
from bpy.types import Operator  # type: ignore
from bpy.props import StringProperty, IntProperty, EnumProperty  # type: ignore

from .containers import (
    active_container,
    add_mesh_to_container,
    bootstrap_legacy_container_if_needed,
    find_container_for_mesh,
    remove_mesh_from_container,
    sync_rm_containers,
    unregister_container,
)


def _active_graph(context):
    em_tools = context.scene.em_tools
    if em_tools.active_file_index < 0 \
            or em_tools.active_file_index >= len(em_tools.graphml_files):
        return None
    try:
        from s3dgraphy import get_graph
        return get_graph(
            em_tools.graphml_files[em_tools.active_file_index].name)
    except Exception:
        return None


def _container_from_doc_name(graph, doc_name: str):
    """Resolve a user-picked doc_name (e.g. ``D.01``) to its
    DocumentNode. Returns (node_id, display_name) or (None, "").
    """
    if graph is None or not doc_name:
        return None, ""
    for node in graph.nodes:
        if getattr(node, "node_type", "") != "document":
            continue
        if getattr(node, "name", "") == doc_name:
            return node.node_id, node.name
    return None, ""


class RMCONTAINER_OT_link_existing_document(Operator):
    """Pick an existing DocumentNode and create an empty RM container
    linked to it.
    """
    bl_idname = "rmcontainer.link_existing_document"
    bl_label = "Link existing document"
    bl_description = (
        "Create a new RM container linked to an existing DocumentNode. "
        "Pick a document from the Document Manager list."
    )
    bl_options = {'REGISTER', 'UNDO'}

    doc_name: StringProperty(
        name="Document",
        description="Name of the Document to wrap (e.g. D.01)",
    )  # type: ignore
    container_label: StringProperty(
        name="Container label",
        description="Display label for this container",
        default="",
    )  # type: ignore

    @classmethod
    def poll(cls, context):
        em_tools = context.scene.em_tools
        return em_tools.active_file_index >= 0

    def invoke(self, context, event):
        self.doc_name = ""
        self.container_label = ""
        return context.window_manager.invoke_props_dialog(self, width=360)

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        if hasattr(scene, "doc_list") and scene.doc_list:
            layout.prop_search(self, "doc_name", scene, "doc_list",
                                text="Document")
        else:
            layout.prop(self, "doc_name", text="Document")
        layout.prop(self, "container_label", text="Label")
        layout.label(
            text="The container will start empty. Use 'Add selected "
                 "meshes' to populate it.",
            icon='INFO',
        )

    def execute(self, context):
        graph = _active_graph(context)
        if graph is None:
            self.report({'ERROR'}, "No active graph")
            return {'CANCELLED'}
        doc_id, doc_display = _container_from_doc_name(graph, self.doc_name)
        if not doc_id:
            self.report({'ERROR'},
                        f"Document {self.doc_name!r} not found in graph")
            return {'CANCELLED'}
        scene = context.scene
        label = (self.container_label or "").strip() \
            or f"{doc_display}.container"
        # Avoid duplicates on the same document.
        for existing in scene.rm_containers:
            if existing.doc_node_id == doc_id:
                self.report(
                    {'WARNING'},
                    f"A container for {doc_display} already exists "
                    f"({existing.label!r}) — activating it.")
                scene.rm_containers_index = list(scene.rm_containers).index(
                    existing)
                return {'FINISHED'}
        container = scene.rm_containers.add()
        container.label = label
        container.doc_node_id = doc_id
        container.doc_name = doc_display
        scene.rm_containers_index = len(scene.rm_containers) - 1
        self.report({'INFO'}, f"Created container {label!r} -> {doc_display}")
        return {'FINISHED'}


class RMCONTAINER_OT_create_empty(Operator):
    """Create a new empty RM container that is NOT linked to any
    DocumentNode yet. The user can link it later via
    ``rmcontainer.link_this_to_doc`` or promote it to a document-linked
    container via the edit flow.
    """
    bl_idname = "rmcontainer.create_empty"
    bl_label = "Empty container"
    bl_description = (
        "Create a new empty RM container (no document link). You can "
        "add meshes now and link it to a document later."
    )
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        container = scene.rm_containers.add()
        # Auto-label with a running index so two empty containers are
        # visually distinguishable in the UIList.
        existing_empty = sum(
            1 for c in scene.rm_containers if not c.doc_node_id
            and (c.label.startswith("Container ") or c is container))
        container.label = f"Container {existing_empty}"
        container.doc_node_id = ""
        container.doc_name = ""
        scene.rm_containers_index = len(scene.rm_containers) - 1
        self.report({'INFO'}, f"Created empty container {container.label!r}")
        return {'FINISHED'}


class RMCONTAINER_OT_link_this_to_doc(Operator):
    """Link the active (unlinked) container to an existing DocumentNode.

    For containers that were created empty via
    ``rmcontainer.create_empty`` or that come from the legacy bootstrap
    pass. Opens a doc picker; on confirm, the container records the
    doc_node_id and — for every mesh already in the container — adds
    the ``has_representation_model`` edge from the Document to the
    mesh's RM node.
    """
    bl_idname = "rmcontainer.link_this_to_doc"
    bl_label = "Link to document"
    bl_description = (
        "Link the active container to a Document from the catalog. "
        "Adds has_representation_model edges from the Document to "
        "each mesh already inside the container."
    )
    bl_options = {'REGISTER', 'UNDO'}

    doc_name: StringProperty(
        name="Document",
        description="Name of the Document to link (e.g. D.01)",
    )  # type: ignore

    @classmethod
    def poll(cls, context):
        ac = active_container(context.scene)
        em_tools = context.scene.em_tools
        return (ac is not None
                and not ac.doc_node_id
                and em_tools.active_file_index >= 0)

    def invoke(self, context, event):
        self.doc_name = ""
        return context.window_manager.invoke_props_dialog(self, width=360)

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        if hasattr(scene, "doc_list") and scene.doc_list:
            layout.prop_search(self, "doc_name", scene, "doc_list",
                                text="Document")
        else:
            layout.prop(self, "doc_name", text="Document")
        ac = active_container(scene)
        if ac is not None and len(ac.mesh_names) > 0:
            layout.label(
                text=f"Will add has_representation_model edges from "
                     f"the document to {len(ac.mesh_names)} mesh(es).",
                icon='INFO')

    def execute(self, context):
        scene = context.scene
        ac = active_container(scene)
        if ac is None:
            self.report({'ERROR'}, "No active container")
            return {'CANCELLED'}
        if ac.doc_node_id:
            self.report({'ERROR'}, "This container is already linked")
            return {'CANCELLED'}
        graph = _active_graph(context)
        if graph is None:
            self.report({'ERROR'}, "No active graph")
            return {'CANCELLED'}
        doc_id, doc_display = _container_from_doc_name(graph, self.doc_name)
        if not doc_id:
            self.report({'ERROR'},
                        f"Document {self.doc_name!r} not found in graph")
            return {'CANCELLED'}
        # Retrofit edges for every existing mesh in the container.
        from .containers import _ensure_rm_node_for_mesh, _has_edge
        added = 0
        for entry in ac.mesh_names:
            mesh_obj = bpy.data.objects.get(entry.name)
            if mesh_obj is None:
                continue
            rm_id = _ensure_rm_node_for_mesh(scene, graph, mesh_obj)
            if rm_id and not _has_edge(
                    graph, doc_id, rm_id, "has_representation_model"):
                try:
                    graph.add_edge(
                        edge_id=(f"{doc_id}_has_representation_model_"
                                 f"{rm_id}"),
                        edge_source=doc_id,
                        edge_target=rm_id,
                        edge_type="has_representation_model",
                    )
                    added += 1
                except Exception:
                    pass
            mesh_obj["em_rm_container_doc_id"] = doc_id
        ac.doc_node_id = doc_id
        ac.doc_name = doc_display
        self.report(
            {'INFO'},
            f"Linked container {ac.label!r} to {doc_display} "
            f"(+{added} has_representation_model edge(s))")
        return {'FINISHED'}


class RMCONTAINER_OT_create_and_link_new_document(Operator):
    """Chain into the shared ``docmanager.create_master_document``
    dialog. On success, wrap the newly-created DocumentNode in a fresh
    container.
    """
    bl_idname = "rmcontainer.create_and_link_new_document"
    bl_label = "Create new document + container"
    bl_description = (
        "Open the Master Document creation dialog (name, description, "
        "epoch anchor, three-axis classification) and create a new RM "
        "container linked to the resulting document."
    )
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        em_tools = context.scene.em_tools
        return em_tools.active_file_index >= 0

    def execute(self, context):
        em_tools = context.scene.em_tools
        # Reset the result sentinel before calling the inner operator
        # so we can detect whether it actually created a document.
        em_tools["last_created_master_doc_id"] = ""
        result = bpy.ops.docmanager.create_master_document('INVOKE_DEFAULT')
        if 'FINISHED' not in result:
            # User cancelled or something failed — nothing to wrap.
            return {'CANCELLED'}
        doc_id = em_tools.get("last_created_master_doc_id", "")
        if not doc_id:
            self.report({'WARNING'},
                        "Document was not created (sentinel missing)")
            return {'CANCELLED'}
        graph = _active_graph(context)
        doc_display = ""
        if graph is not None:
            try:
                n = graph.find_node_by_id(doc_id)
                doc_display = getattr(n, "name", "") if n else ""
            except Exception:
                doc_display = ""
        scene = context.scene
        container = scene.rm_containers.add()
        container.doc_node_id = doc_id
        container.doc_name = doc_display
        container.label = f"{doc_display}.container" \
            if doc_display else "New container"
        scene.rm_containers_index = len(scene.rm_containers) - 1
        self.report({'INFO'},
                    f"Container created and linked to {doc_display or doc_id}")
        return {'FINISHED'}


class RMCONTAINER_OT_add_selected_meshes(Operator):
    """Add every selected MESH object to the active container.

    Skips meshes already in another container with a warning, so the
    Q_C invariant (one mesh ↔ one container) is enforced.
    """
    bl_idname = "rmcontainer.add_selected_meshes"
    bl_label = "Add selected meshes"
    bl_description = (
        "Add the selected MESH objects to the active RM container. "
        "Meshes already in another container are skipped."
    )
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (active_container(context.scene) is not None
                and any(o.type == 'MESH'
                        for o in context.selected_objects))

    def execute(self, context):
        container = active_container(context.scene)
        if container is None:
            self.report({'ERROR'}, "No active container")
            return {'CANCELLED'}
        selected = [o for o in context.selected_objects
                    if o.type == 'MESH']
        if not selected:
            self.report({'ERROR'}, "No mesh objects selected")
            return {'CANCELLED'}

        # Auto-promote to rm_list when an active epoch exists: any
        # selected mesh that isn't yet an RM gets added to rm_list and
        # anchored to the active epoch. This way the user can add
        # non-RM meshes to a container without an extra step, and each
        # mesh shows up in the sub-list with its epoch association.
        scene = context.scene
        em_tools = scene.em_tools
        epochs = getattr(em_tools, 'epochs', None)
        has_active_epoch = (epochs is not None
                             and len(epochs.list) > 0
                             and epochs.list_index >= 0)
        rm_names = {rm.name for rm in scene.rm_list}
        non_rm_selected = [o for o in selected if o.name not in rm_names]
        if non_rm_selected and has_active_epoch:
            # rm.promote_to_rm operates on selected_objects — the
            # current selection already matches what we want.
            try:
                bpy.ops.rm.promote_to_rm('EXEC_DEFAULT', mode='SELECTED')
            except Exception as e:
                self.report({'WARNING'},
                            f"Auto-promote to rm_list failed: {e}. "
                            f"Meshes will be added to the container "
                            f"without epoch anchoring.")
        elif non_rm_selected and not has_active_epoch:
            self.report({'WARNING'},
                        f"{len(non_rm_selected)} mesh(es) are not yet "
                        f"in rm_list and no active epoch is selected. "
                        f"They'll be added to the container but will "
                        f"have no epoch anchor until you promote them "
                        f"manually.")

        added = 0
        skipped = []
        for obj in selected:
            ok, reason = add_mesh_to_container(context, container, obj)
            if ok:
                added += 1
            elif reason:
                skipped.append(reason)
        if skipped:
            for s in skipped[:5]:
                self.report({'WARNING'}, s)
            if len(skipped) > 5:
                self.report({'WARNING'},
                            f"... and {len(skipped) - 5} more skipped")
        self.report({'INFO'},
                    f"Added {added} mesh(es) to {container.label!r} "
                    f"(skipped {len(skipped)})")
        return {'FINISHED'}


_MOVE_TARGET_ITEMS_CACHE: list = []


def _move_target_items(self, context):
    """EnumProperty items for the move-to-container target picker.
    Module-level cache keeps the strings alive across Blender's
    callback invocations.
    """
    global _MOVE_TARGET_ITEMS_CACHE
    items = [("__UNASSIGN__", "-- Unassigned (no container) --",
              "Remove from its current container without moving to any "
              "other one")]
    for i, c in enumerate(context.scene.rm_containers):
        doc = c.doc_name if c.doc_name else "—"
        items.append((
            str(i),
            f"{c.label}   [{doc}]   ({len(c.mesh_names)})",
            f"Move to container {c.label!r}",
        ))
    _MOVE_TARGET_ITEMS_CACHE = items
    return items


class RMCONTAINER_OT_move_selected_to_container(Operator):
    """Move every selected MESH object into a target container.

    Workflow: the user first narrows down the selection in the
    viewport (e.g. via ``rm.select_all_from_active_epoch`` or by
    hand), then runs this operator and picks a target. Each selected
    mesh is removed from its current container (if any) and inserted
    into the target. ``has_representation_model`` edges are updated
    end-to-end — the edge from the old container's Document is
    dropped and, when the target is linked to a Document, the new
    edge is added.

    Pick ``-- Unassigned --`` as the target to simply remove meshes
    from any container they currently belong to, without putting them
    in another one.
    """
    bl_idname = "rmcontainer.move_selected_to_container"
    bl_label = "Move selected to container"
    bl_description = (
        "Move the selected MESH objects into a target container. "
        "Removes them from whichever container they currently belong "
        "to and updates has_representation_model edges accordingly."
    )
    bl_options = {'REGISTER', 'UNDO'}

    target: EnumProperty(
        name="Target",
        description="Target container for the selected meshes",
        items=_move_target_items,
    )  # type: ignore

    @classmethod
    def poll(cls, context):
        return any(o.type == 'MESH' for o in context.selected_objects)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=420)

    def draw(self, context):
        layout = self.layout
        sel_count = sum(1 for o in context.selected_objects
                        if o.type == 'MESH')
        layout.label(
            text=f"Moving {sel_count} selected mesh(es)",
            icon='OBJECT_DATA')
        layout.prop(self, "target", text="Target")
        layout.label(
            text="Meshes are removed from their current container "
                 "(if any) before being added to the target.",
            icon='INFO')

    def execute(self, context):
        scene = context.scene
        target_container = None
        if self.target != "__UNASSIGN__":
            try:
                idx = int(self.target)
            except (TypeError, ValueError):
                idx = -1
            if 0 <= idx < len(scene.rm_containers):
                target_container = scene.rm_containers[idx]
            else:
                self.report({'ERROR'}, "Invalid target container index")
                return {'CANCELLED'}

        selected = [o for o in context.selected_objects if o.type == 'MESH']
        if not selected:
            self.report({'ERROR'}, "No mesh objects selected")
            return {'CANCELLED'}

        moved = 0
        skipped = 0
        for obj in selected:
            current_idx = find_container_for_mesh(scene, obj.name)
            current_container = (scene.rm_containers[current_idx]
                                  if current_idx is not None else None)
            if current_container is target_container:
                skipped += 1
                continue
            if current_container is not None:
                remove_mesh_from_container(
                    context, current_container, obj.name, drop_edge=True)
            if target_container is not None:
                ok, reason = add_mesh_to_container(
                    context, target_container, obj)
                if not ok:
                    self.report({'WARNING'}, reason)
                    continue
            moved += 1

        target_label = (target_container.label
                        if target_container else "(unassigned)")
        self.report(
            {'INFO'},
            f"Moved {moved} mesh(es) to {target_label!r} "
            f"(skipped {skipped} already there)")
        return {'FINISHED'}


class RMCONTAINER_OT_remove_mesh_from_container(Operator):
    """Remove a single mesh from the active container (drops the edge)."""
    bl_idname = "rmcontainer.remove_mesh_from_container"
    bl_label = "Remove mesh from container"
    bl_description = (
        "Remove this mesh from its container and drop the "
        "has_representation_model edge from the linked Document."
    )
    bl_options = {'REGISTER', 'UNDO'}

    mesh_name: StringProperty()  # type: ignore

    @classmethod
    def poll(cls, context):
        return active_container(context.scene) is not None

    def execute(self, context):
        container = active_container(context.scene)
        if container is None:
            self.report({'ERROR'}, "No active container")
            return {'CANCELLED'}
        if not self.mesh_name:
            self.report({'ERROR'}, "Missing mesh_name")
            return {'CANCELLED'}
        if not remove_mesh_from_container(context, container,
                                            self.mesh_name, drop_edge=True):
            self.report({'WARNING'},
                        f"Mesh {self.mesh_name!r} was not in this container")
            return {'CANCELLED'}
        self.report({'INFO'},
                    f"Removed {self.mesh_name!r} from {container.label!r}")
        return {'FINISHED'}


class RMCONTAINER_OT_unregister(Operator):
    """Drop the active container and every has_representation_model
    edge it implied. The DocumentNode itself stays (can be reused).
    """
    bl_idname = "rmcontainer.unregister"
    bl_label = "Unregister container"
    bl_description = (
        "Drop this RM container and every has_representation_model edge "
        "from its Document to the contained meshes. The DocumentNode "
        "stays in the graph."
    )
    bl_options = {'REGISTER', 'UNDO'}

    container_index: IntProperty(default=-1)  # type: ignore

    @classmethod
    def poll(cls, context):
        return active_container(context.scene) is not None

    def execute(self, context):
        scene = context.scene
        idx = (self.container_index
               if self.container_index >= 0 else scene.rm_containers_index)
        if idx < 0 or idx >= len(scene.rm_containers):
            self.report({'ERROR'}, "No container at that index")
            return {'CANCELLED'}
        label = scene.rm_containers[idx].label
        if not unregister_container(context, idx):
            self.report({'ERROR'}, "Failed to unregister container")
            return {'CANCELLED'}
        self.report({'INFO'}, f"Unregistered container {label!r}")
        return {'FINISHED'}


class RMCONTAINER_OT_sync(Operator):
    """Run the RM container sanitisation pass manually."""
    bl_idname = "rmcontainer.sync"
    bl_label = "Sync RM containers"
    bl_description = (
        "Validate that every mesh referenced by an RM container still "
        "exists in the scene. Missing meshes are removed from their "
        "container and reported in the warnings list."
    )
    bl_options = {'REGISTER'}

    def execute(self, context):
        before = len(context.scene.rm_container_warnings)
        sync_rm_containers(context)
        after = len(context.scene.rm_container_warnings)
        new_warn = after - before
        if new_warn > 0:
            self.report({'WARNING'},
                        f"Sync complete — {new_warn} new warning(s); "
                        f"see panel header.")
        else:
            self.report({'INFO'}, "Sync complete — no new warnings.")
        return {'FINISHED'}


class RMCONTAINER_OT_bootstrap_legacy(Operator):
    """Bootstrap the automatic "Legacy RMs" container by bundling every
    existing :class:`RMItem` whose object still exists in the scene.

    Runs only when ``rm_containers`` is empty and ``rm_list`` is not —
    this keeps the two-level UI populated for projects that predate
    the container feature. User-triggered so Blender's ID-write
    restriction during ``draw()`` is respected.
    """
    bl_idname = "rmcontainer.bootstrap_legacy"
    bl_label = "Bootstrap Legacy RMs"
    bl_description = (
        "Bundle every existing Representation Model into an automatic "
        "'Legacy RMs' container. Runs once — after that, the container "
        "becomes part of the RM Manager list and can be renamed or "
        "unregistered as any other."
    )
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        scene = context.scene
        return (len(scene.rm_containers) == 0
                and len(scene.rm_list) > 0)

    def execute(self, context):
        before = len(context.scene.rm_containers)
        bootstrap_legacy_container_if_needed(context)
        after = len(context.scene.rm_containers)
        if after > before:
            count = len(context.scene.rm_containers[0].mesh_names)
            self.report({'INFO'},
                        f"Legacy RMs container created with "
                        f"{count} mesh(es)")
        else:
            self.report({'INFO'}, "Nothing to bootstrap")
        return {'FINISHED'}


class RMCONTAINER_OT_acknowledge_warnings(Operator):
    """Clear the RM container warnings list after the user has read
    them.
    """
    bl_idname = "rmcontainer.acknowledge_warnings"
    bl_label = "Acknowledge warnings"
    bl_description = "Clear the RM container sanitisation warnings list."
    bl_options = {'REGISTER'}

    def execute(self, context):
        n = len(context.scene.rm_container_warnings)
        context.scene.rm_container_warnings.clear()
        self.report({'INFO'}, f"Cleared {n} warning(s)")
        return {'FINISHED'}


_CONTAINER_OPS = (
    RMCONTAINER_OT_link_existing_document,
    RMCONTAINER_OT_create_empty,
    RMCONTAINER_OT_link_this_to_doc,
    RMCONTAINER_OT_create_and_link_new_document,
    RMCONTAINER_OT_add_selected_meshes,
    RMCONTAINER_OT_move_selected_to_container,
    RMCONTAINER_OT_remove_mesh_from_container,
    RMCONTAINER_OT_unregister,
    RMCONTAINER_OT_sync,
    RMCONTAINER_OT_bootstrap_legacy,
    RMCONTAINER_OT_acknowledge_warnings,
)


def register_container_operators():
    for cls in _CONTAINER_OPS:
        try:
            bpy.utils.register_class(cls)
        except ValueError:
            # Already registered — unregister and retry.
            try:
                bpy.utils.unregister_class(cls)
            except Exception:
                pass
            bpy.utils.register_class(cls)


def unregister_container_operators():
    for cls in reversed(_CONTAINER_OPS):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
