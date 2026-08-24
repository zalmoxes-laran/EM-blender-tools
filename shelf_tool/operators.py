"""Operators for the EM Shelf tool.

A folder picker, a 3D-first scan that drives the acquisition pipeline in-process,
standalone save/load + remove, and the **Hat** dialog: the user picks the FACET
explicitly (RM / RMSF / RMDoc / Document) and then a compatible target, which
s3dgraphy derives from the datamodel. All graph work is in shelf_backend.py (which
calls s3dgraphy); what lives here is Blender-side: the mesh import, the object
binds, and the shared Document helper.
"""

from __future__ import annotations

import os

import bpy
from bpy.types import Operator

from . import properties, shelf_backend

_STALE = ("Shelf unavailable: the active s3dgraphy is stale — activate the "
          "dev/updated s3dgraphy (./em.sh s3d), then reopen.")


class EM_OT_shelf_set_folder(Operator):
    bl_idname = "em.shelf_set_folder"
    bl_label = "Set project folder"
    bl_description = "Choose the project folder to scan (opens a folder browser)"
    bl_options = {'REGISTER'}

    directory: bpy.props.StringProperty(subtype='DIR_PATH')  # type: ignore

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        context.scene.em_shelf.folder = self.directory
        for area in context.screen.areas:
            area.tag_redraw()
        return {'FINISHED'}


class EM_OT_shelf_scan(Operator):
    bl_idname = "em.shelf_scan"
    bl_label = "Scan for 3D"
    bl_description = ("Scan the project folder for 3D files and acquire each onto "
                      "the Shelf (import + origin)")
    bl_options = {'REGISTER'}

    def execute(self, context):
        if not shelf_backend.shelf_supported():
            self.report({'ERROR'}, _STALE)
            return {'CANCELLED'}
        p = context.scene.em_shelf
        folder = bpy.path.abspath(p.folder) if p.folder else ""
        if not folder or not os.path.isdir(folder):
            self.report({'WARNING'}, "Set a valid project folder first.")
            return {'CANCELLED'}
        try:
            res = shelf_backend.scan_folder(folder, recursive=p.recursive)
        except Exception as exc:
            self.report({'ERROR'}, f"Scan failed: {exc}")
            return {'CANCELLED'}
        p.status = (f"Scanned {res['scanned']} 3D file(s) — Shelf has "
                    f"{res['shelf_count']} resource(s)")
        properties.sync_items(context.scene)
        for area in context.screen.areas:
            area.tag_redraw()
        return {'FINISHED'}


class EM_OT_shelf_new(Operator):
    bl_idname = "em.shelf_new"
    bl_label = "New Shelf"
    bl_description = "Start a new empty Shelf (unsaved)"
    bl_options = {'REGISTER'}

    def execute(self, context):
        if not shelf_backend.shelf_supported():
            self.report({'ERROR'}, _STALE)
            return {'CANCELLED'}
        shelf_backend.new_shelf()
        context.scene.em_shelf.status = "New shelf"
        properties.sync_items(context.scene)
        for area in context.screen.areas:
            area.tag_redraw()
        return {'FINISHED'}


class EM_OT_shelf_save(Operator):
    bl_idname = "em.shelf_save"
    bl_label = "Save Shelf"
    bl_description = "Save the Shelf as a standalone .em.json (reusable in any study)"
    bl_options = {'REGISTER'}

    filepath: bpy.props.StringProperty(subtype='FILE_PATH')  # type: ignore
    filter_glob: bpy.props.StringProperty(default="*.em.json;*.json", options={'HIDDEN'})  # type: ignore

    def invoke(self, context, event):
        if shelf_backend.active_shelf() is None:
            self.report({'WARNING'}, "No shelf yet — scan or New Shelf first.")
            return {'CANCELLED'}
        self.filepath = shelf_backend.active_path() or "shelf.em.json"
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        path = self.filepath
        if path and not path.endswith(".json"):
            path += ".em.json"
        try:
            saved = shelf_backend.save_shelf(path)
        except Exception as exc:
            self.report({'ERROR'}, f"Save failed: {exc}")
            return {'CANCELLED'}
        context.scene.em_shelf.status = f"Saved → {os.path.basename(saved)}"
        return {'FINISHED'}


class EM_OT_shelf_load(Operator):
    bl_idname = "em.shelf_load"
    bl_label = "Load Shelf"
    bl_description = "Load a standalone Shelf .em.json"
    bl_options = {'REGISTER'}

    filepath: bpy.props.StringProperty(subtype='FILE_PATH')  # type: ignore
    filter_glob: bpy.props.StringProperty(default="*.em.json;*.json", options={'HIDDEN'})  # type: ignore

    def invoke(self, context, event):
        if not shelf_backend.shelf_supported():
            self.report({'ERROR'}, _STALE)
            return {'CANCELLED'}
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        if not os.path.isfile(self.filepath):
            self.report({'WARNING'}, "Pick an existing .em.json shelf.")
            return {'CANCELLED'}
        try:
            _g, warnings = shelf_backend.load_shelf(self.filepath)
        except Exception as exc:
            self.report({'ERROR'}, f"Load failed: {exc}")
            return {'CANCELLED'}
        for w in warnings:
            print(f"[EM Shelf] warning: {w}")
        context.scene.em_shelf.status = (f"Loaded {len(shelf_backend.cards())} "
                                         f"resource(s)")
        properties.sync_items(context.scene)
        for area in context.screen.areas:
            area.tag_redraw()
        return {'FINISHED'}


class EM_OT_shelf_remove(Operator):
    bl_idname = "em.shelf_remove"
    bl_label = "Remove"
    bl_description = ("Remove this resource from the Shelf (keeps it if it is "
                      "referenced/hatted; cleans up its acquisition event otherwise)")
    bl_options = {'REGISTER', 'UNDO'}

    resource_id: bpy.props.StringProperty()  # type: ignore

    def execute(self, context):
        if not self.resource_id:
            return {'CANCELLED'}
        rep = shelf_backend.remove(self.resource_id)
        if rep.get("referenced"):
            context.scene.em_shelf.status = "Kept — resource is referenced (hatted)"
        elif rep.get("removed"):
            context.scene.em_shelf.status = (
                f"Removed (event cleaned: {rep.get('events_removed', 0)})")
        properties.sync_items(context.scene)
        for area in context.screen.areas:
            area.tag_redraw()
        return {'FINISHED'}


class EM_OT_shelf_adopt_project(Operator):
    bl_idname = "em.shelf_adopt_project"
    bl_label = "Read the project's shelf"
    bl_description = ("List the ShelfGraph this project already carries — no "
                      "file, no import. Blender does not export the shelf: it "
                      "browses it and brings one entry at a time into the scene")
    bl_options = {'REGISTER'}

    def execute(self, context):
        if not shelf_backend.shelf_supported():
            self.report({'ERROR'}, _STALE)
            return {'CANCELLED'}
        report = shelf_backend.adopt_project_shelf()
        p = context.scene.em_shelf
        if not report.get("adopted"):
            p.status = "This project carries no shelf (no ShelfGraph member)"
            self.report({'WARNING'}, p.status)
            return {'CANCELLED'}
        # …and re-read the cards against the ACTIVE STUDY GRAPH, or every entry
        # would read "only_shelf": the mode is the hatting reference-check, and
        # the hats live in the study graph, not on the shelf.
        shelf_backend.refresh(_active_graph(context))
        properties.sync_items(context.scene)
        p.status = (f"Reading the project's shelf «{report['graph_id']}» — "
                    f"{report['count']} resource(s)")
        for area in context.screen.areas:
            area.tag_redraw()
        return {'FINISHED'}


def _active_graph(context):
    """The active study graph (the selected GraphML), or None."""
    try:
        from ..functions import check_active_graph
        ok, graph = check_active_graph(context, show_message=False)
        return graph if ok else None
    except Exception:
        return None


# Blender needs the enum item lists to stay alive (macOS GC's temporary strings),
# so every dynamic callback keeps its result in this module-level cache.
_ENUM_CACHE = {"facet": [], "epochs": [], "targets": [], "role": [], "nature": [],
               "geometry": []}


def _facet_items(self, context):
    _ENUM_CACHE["facet"] = list(shelf_backend.FACET_ITEMS)
    return _ENUM_CACHE["facet"]


def _candidates(context, facet):
    """The attach candidates for ``facet`` in the active graph — s3dgraphy derives
    them from the datamodel, so this UI never hardcodes a node-type list."""
    graph = _active_graph(context)
    if graph is None or not shelf_backend.shelf_supported():
        return []
    try:
        return shelf_backend.attach_candidates(facet, graph)
    except Exception as exc:
        print(f"[EM Shelf] attach candidates failed for {facet}: {exc}")
        return []


def _epoch_items(self, context):
    """The epochs an RM can bind to, chronological (first = has_first_epoch)."""
    items = []
    for i, c in enumerate(_candidates(context, 'RM')[:32]):  # ENUM_FLAG = 32 bits
        items.append((c["id"], c["name"], f"Epoch {c['name']}", 1 << i))
    _ENUM_CACHE["epochs"] = items
    return items


def _target_items(self, context):
    """The compatible attach target for the picked facet (RMSF → SF, RMDoc →
    Document, Document → Extractor / stratigraphic / paradata)."""
    items = [('NONE', "(no attach)", "Create the facet now, attach it later")]
    facet = getattr(self, "facet", 'RM')
    if facet != 'RM':
        for c in _candidates(context, facet):
            items.append((c["id"], f"{c['name']}  [{c['node_type']}]",
                          f"{c['edge']} → {c['name']}"))
    _ENUM_CACHE["targets"] = items
    return items


def _vocab_items(key, vocabulary, none_label=None):
    """Enum items derived from a s3dgraphy document vocabulary (em_visual_rules is
    the single source of truth — never a hardcoded list here)."""
    items = []
    if none_label:
        items.append(('none', none_label, "Leave this axis unset"))
    for v in vocabulary:
        # 'master_unknown' is a STYLE fallback key, not a geometry class
        if v == "master_unknown":
            continue
        items.append((v, v.replace("_", " ").capitalize(), v))
    _ENUM_CACHE[key] = items
    return items


def _role_items(self, context):
    from s3dgraphy.nodes.document_node import DOCUMENT_ROLES
    return _vocab_items("role", DOCUMENT_ROLES)


def _nature_items(self, context):
    from s3dgraphy.nodes.document_node import DOCUMENT_CONTENT_NATURES
    return _vocab_items("nature", DOCUMENT_CONTENT_NATURES)


def _geometry_items(self, context):
    from s3dgraphy.nodes.document_node import DOCUMENT_GEOMETRIES
    return _vocab_items("geometry", DOCUMENT_GEOMETRIES,
                        none_label="No 3D spatialization")


def _bind_epochs(obj, epoch_names):
    """Mirror the RM's epochs on the Blender object (``EM_ep_belong_ob``) — the
    RM Manager / epoch manager object-side convention."""
    try:
        obj.EM_ep_belong_ob.clear()
        for name in epoch_names:
            obj.EM_ep_belong_ob.add().epoch = name
    except Exception as exc:
        print(f"[EM Shelf] could not bind epochs on {obj.name}: {exc}")


def _import_mesh(path):
    """Import a 3D file into the scene, returning the newly-created objects.
    Per-extension dispatch over Blender's importers (glTF/OBJ/FBX/PLY/STL/DAE/USD).
    Blender-only → covered by E.D.'s manual verify."""
    ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
    before = set(bpy.data.objects)
    try:
        if ext in ("glb", "gltf"):
            bpy.ops.import_scene.gltf(filepath=path)
        elif ext == "obj":
            (bpy.ops.wm.obj_import if hasattr(bpy.ops.wm, "obj_import")
             else bpy.ops.import_scene.obj)(filepath=path)
        elif ext == "fbx":
            bpy.ops.import_scene.fbx(filepath=path)
        elif ext == "ply":
            (bpy.ops.wm.ply_import if hasattr(bpy.ops.wm, "ply_import")
             else bpy.ops.import_mesh.ply)(filepath=path)
        elif ext == "stl":
            (bpy.ops.wm.stl_import if hasattr(bpy.ops.wm, "stl_import")
             else bpy.ops.import_mesh.stl)(filepath=path)
        elif ext == "dae":
            bpy.ops.wm.collada_import(filepath=path)
        elif ext in ("usd", "usda", "usdc", "usdz"):
            bpy.ops.wm.usd_import(filepath=path)
        else:
            return []
    except Exception as exc:  # importer missing / bad file
        print(f"[EM Shelf] mesh import failed for {path}: {exc}")
        return []
    return [o for o in bpy.data.objects if o not in before]


class EM_OT_shelf_hat(Operator):
    """Hat a shelf resource into the active study graph under an EXPLICIT facet.

    The role determines the facet, and the facets are NOT exclusive: the same
    resource can be hatted twice — e.g. a photogrammetric model as the RM of the
    epoch it depicts AND as a Document feeding an Extractor. Every facet keeps
    the P67 hinge to the Resource (stable ID); only Document imports no mesh.
    """
    bl_idname = "em.shelf_hat"
    bl_label = "Hat…"
    bl_description = ("Hat this resource into the active study graph under an "
                      "explicit facet (RM / RMSF / RMDoc / Document). Facets are "
                      "not exclusive — the same resource can carry several")
    bl_options = {'REGISTER', 'UNDO'}

    resource_id: bpy.props.StringProperty()  # type: ignore
    facet: bpy.props.EnumProperty(name="Facet", items=_facet_items)  # type: ignore
    epoch_targets: bpy.props.EnumProperty(  # type: ignore
        name="Epochs", items=_epoch_items, options={'ENUM_FLAG'},
        description="The epoch(s) this RM represents — the oldest picked gets "
                    "has_first_epoch, the others survive_in_epoch")
    target_node: bpy.props.EnumProperty(  # type: ignore
        name="Attach to", items=_target_items,
        description="The compatible node this facet attaches to")
    doc_name: bpy.props.StringProperty(name="Name", default="")  # type: ignore
    doc_description: bpy.props.StringProperty(name="Description", default="")  # type: ignore
    doc_role: bpy.props.EnumProperty(name="Role", items=_role_items)  # type: ignore
    doc_content_nature: bpy.props.EnumProperty(  # type: ignore
        name="Content", items=_nature_items)
    doc_geometry: bpy.props.EnumProperty(  # type: ignore
        name="Geometry", items=_geometry_items)
    rmdoc_geometry: bpy.props.EnumProperty(  # type: ignore
        name="Placement",
        items=_geometry_items,
        description="Metric authority of this RMDoc's placement (Q-C). An RMDoc "
                    "is never anchored to an epoch or a stratigraphic unit; what "
                    "grades it is HOW metric its positioning is — "
                    "reality_based > observable > asserted > symbolic")

    def _item(self, context):
        p = context.scene.em_shelf
        if 0 <= p.active_index < len(p.items):
            return p.items[p.active_index]
        return None

    def _target(self, context):
        """The picked attach target, or None. Re-validated against the current
        facet's candidates: switching facet in the dialog can leave a stale id
        behind, and attaching it would be wrong (the op would refuse it anyway)."""
        if self.target_node in ('', 'NONE'):
            return None
        valid = {c["id"] for c in _candidates(context, self.facet)}
        return self.target_node if self.target_node in valid else None

    def invoke(self, context, event):
        if not shelf_backend.shelf_supported():
            self.report({'ERROR'}, _STALE)
            return {'CANCELLED'}
        if _active_graph(context) is None:
            self.report({'WARNING'},
                        "No active study graph — select a GraphML in EM Setup.")
            return {'CANCELLED'}
        it = self._item(context)
        if not self.doc_name:
            try:
                from ..canonical_document_helpers import suggest_next_document_name
                self.doc_name = suggest_next_document_name(_active_graph(context))
            except Exception:
                self.doc_name = (it.name if it else "Document")
        # the Shelf search is 3D-first, so a hatted source is a 3D object
        try:
            self.doc_content_nature = "3d_object"
        except Exception:
            pass
        _epoch_items(self, context)   # prime the cache the dialog's draw reads
        return context.window_manager.invoke_props_dialog(self, width=460)

    def draw(self, context):
        col = self.layout.column()
        it = self._item(context)
        if it:
            col.label(text=it.name or it.resource_id[:8],
                      icon='MESH_DATA' if it.exists else 'ERROR')
        col.prop(self, "facet", text="")
        col.separator()
        if self.facet == 'RM':
            col.label(text="Epoch(s) this model represents:", icon='TIME')
            if _ENUM_CACHE["epochs"]:
                col.prop(self, "epoch_targets", expand=True)
            else:
                col.label(text="(no epochs in the active graph)", icon='INFO')
        elif self.facet == 'DOCUMENT':
            col.prop(self, "doc_name")
            col.prop(self, "doc_description")
            cls_box = col.box()
            cls_box.label(text="Classification (EM 1.6)", icon='PRESET')
            cls_box.prop(self, "doc_role")
            cls_box.prop(self, "doc_content_nature")
            cls_box.prop(self, "doc_geometry")
            col.prop(self, "target_node")
            col.label(text="No mesh: a Document is a source, not a placement.",
                      icon='INFO')
        else:
            if self.facet == 'RMDOC':
                col.prop(self, "rmdoc_geometry")
            col.prop(self, "target_node")

    # ── per-facet execution ────────────────────────────────────────────────
    def _mesh_or_none(self, context, it):
        loc = it.locator if it else ""
        if not loc or not os.path.isfile(bpy.path.abspath(loc)):
            self.report({'WARNING'}, f"Resource file not found on disk: {loc}")
            return None
        objs = _import_mesh(bpy.path.abspath(loc))
        if not objs:
            self.report({'ERROR'},
                        "Mesh import produced no object (unsupported format?).")
            return None
        return objs

    def _do_rm(self, context, graph, rid, objs):
        obj = objs[0]
        ordered = [c for c in _candidates(context, 'RM')
                   if c["id"] in set(self.epoch_targets)]
        out = shelf_backend.hat_as_rm(
            graph, rid, rm_id=f"{obj.name}_model",   # RM Manager convention
            name=f"Model for {obj.name}",            # …and its name convention
            epochs=[c["id"] for c in ordered])
        _bind_epochs(obj, [c["name"] for c in ordered])
        for o in objs:
            o["em_rm_node_id"] = out["rm_id"]
        eps = len(out.get("epochs") or [])
        return out["rm_id"], (f"RM {out['rm_id']} · {eps} epoch(s)" if eps
                              else f"RM {out['rm_id']} (no epoch yet)")

    def _do_rmsf(self, context, graph, rid, objs):
        obj = objs[0]
        target = self._target(context)
        out = shelf_backend.hat_as_rmsf(
            graph, rid, rmsf_id=f"{obj.name}_rmsf",  # anastylosis convention
            name=f"RMSF for {obj.name}", attach_to=target)
        for o in objs:
            o["em_rmsf_node_id"] = out["rmsf_id"]
        return out["rmsf_id"], (f"RMSF {out['rmsf_id']}"
                                + (" · attached to SF" if out.get("attached") else ""))

    def _do_rmdoc(self, context, graph, rid, objs):
        obj = objs[0]
        target = self._target(context)
        # graph_updaters.update_representation_model_docs derives the node id from
        # the document — use the SAME id so the updater keeps this node in sync
        # instead of creating a second one.
        rmdoc_id = f"{target}_rm_doc" if target else f"{obj.name}_rm_doc"
        out = shelf_backend.hat_as_rmdoc(
            graph, rid, rmdoc_id=rmdoc_id, name=f"RM Doc for {obj.name}",
            attach_to=target,
            geometry=None if self.rmdoc_geometry == 'none' else self.rmdoc_geometry)
        for o in objs:
            o["em_rmdoc_node_id"] = out["rmdoc_id"]
            if target:
                o["em_doc_node_id"] = target  # picked up by the RMDoc updater
        return out["rmdoc_id"], (f"RMDoc {out['rmdoc_id']}"
                                 + (f" · {out['geometry']}" if out.get("geometry")
                                    else "")
                                 + (" · attached" if out.get("attached") else ""))

    def _do_document(self, context, graph, rid):
        """No mesh: the resource becomes a SOURCE. The DocumentNode is built by
        the SHARED helper (create_canonical_document_node) so EMTools keeps one
        document shape; the op only wires the P67 hinge + the attach."""
        from ..canonical_document_helpers import (create_canonical_document_node,
                                               refresh_document_lists)
        node = create_canonical_document_node(
            graph, name=self.doc_name or "Document",
            description=self.doc_description.strip(),
            role=self.doc_role,
            content_nature=self.doc_content_nature,
            geometry=None if self.doc_geometry == 'none' else self.doc_geometry)
        target = self._target(context)
        out = shelf_backend.hat_as_document(graph, rid, doc_id=node.node_id,
                                            attach_to=target)
        refresh_document_lists(context, node, graph)
        return out["doc_id"], (f"Document {node.name}"
                               + (f" · {out['attach_edge']}" if out.get("attached")
                                  else ""))

    def execute(self, context):
        if not shelf_backend.shelf_supported():
            self.report({'ERROR'}, _STALE)
            return {'CANCELLED'}
        p = context.scene.em_shelf
        it = self._item(context)
        rid = self.resource_id or (it.resource_id if it else "")
        if not rid:
            return {'CANCELLED'}
        graph = _active_graph(context)
        if graph is None:
            self.report({'WARNING'},
                        "No active study graph — select a GraphML in EM Setup.")
            return {'CANCELLED'}

        objs = []
        if self.facet in shelf_backend.MESH_FACETS:
            objs = self._mesh_or_none(context, it)
            if objs is None:
                return {'CANCELLED'}
        try:
            if self.facet == 'RM':
                _nid, msg = self._do_rm(context, graph, rid, objs)
            elif self.facet == 'RMSF':
                _nid, msg = self._do_rmsf(context, graph, rid, objs)
            elif self.facet == 'RMDOC':
                _nid, msg = self._do_rmdoc(context, graph, rid, objs)
            else:
                _nid, msg = self._do_document(context, graph, rid)
        except Exception as exc:
            self.report({'ERROR'}, f"Hat failed: {exc}")
            return {'CANCELLED'}
        # every hatted object carries the Resource's stable ID (the R0 hinge)
        for o in objs:
            o["em_resource_id"] = rid
        p.status = f"Materialized → {msg}"
        # …and the LIST has to agree: this entry is now used in the graph, so the
        # cards are re-read against that graph. Without this the row still says
        # "only shelf" over an object that is standing in the viewport — the
        # exact confusion a derived badge exists to prevent.
        shelf_backend.refresh(graph)
        properties.sync_items(context.scene)
        for area in context.screen.areas:
            area.tag_redraw()
        return {'FINISHED'}


classes = (
    EM_OT_shelf_set_folder,
    EM_OT_shelf_scan,
    EM_OT_shelf_new,
    EM_OT_shelf_save,
    EM_OT_shelf_load,
    EM_OT_shelf_adopt_project,
    EM_OT_shelf_hat,
    EM_OT_shelf_remove,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
