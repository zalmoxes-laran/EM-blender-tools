"""The container's alternative in the RM Containers panel (E.D., 17 Oct 2026).

«Alternative: —» and «Choose…» on the active container: three ways to the same
dialog (:class:`RMCONTAINER_OT_alt_confirm`) —

1. a tileset already in the graph (:class:`RMCONTAINER_OT_alt_from_graph`);
2. a .3tz, a .zip or a folder with ``tileset.json`` from the disk, with
   Blender's file browser (:class:`RMCONTAINER_OT_alt_from_disk`);
3. a .3tz or .zip dropped on the 3D Viewport's sidebar
   (:class:`RMCONTAINER_FH_tileset`, Blender's FileHandler: it takes files by
   extension, not folders).

The dialog proposes the name, shows the coverage check (an aid: it never
blocks) and offers «Add to the container» for the models the tileset holds and
the container lacks, «Confirm anyway», or Cancel. The bytes enter the project's
storage (``container_alternative.storage_plan``), the graph is written by
s3Dgraphy (the container is the hat). The logic is in
:mod:`.container_alternative`, measured outside Blender.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import bpy  # type: ignore
from bpy.types import Operator, Menu  # type: ignore
from bpy.props import (StringProperty, IntProperty, EnumProperty,  # type: ignore
                       CollectionProperty, BoolProperty)

from . import container_alternative as ca
from .containers import (active_container, add_mesh_to_container,
                         find_container_for_mesh, reconcile_container_groups,
                         resolve_rm_node_id)

#: what the dialog measured in invoke(), read by draw() (a dialog cannot
#: compute in draw: it would read the disk at every redraw)
_PENDING: Dict[str, Any] = {}

_USE_ITEMS = [(u, u, f"The tileset serves «{u}»") for u in
              ("web", "realtime", "mobile_ar", "heriverse", "aton", "analysis",
               "preview", "render", "print")]


def _ordered(uses) -> List[str]:
    """The uses in the order of the list (web, realtime, …), not a set's."""
    return [u for u, _n, _d in _USE_ITEMS if u in uses]


def _graph(context):
    em_tools = context.scene.em_tools
    if not (0 <= em_tools.active_file_index < len(em_tools.graphml_files)):
        return None
    try:
        from s3dgraphy import get_graph
        return get_graph(em_tools.graphml_files[em_tools.active_file_index].name)
    except Exception:  # noqa: BLE001
        return None


def _container(context, index: int):
    scene = context.scene
    idx = index if index >= 0 else scene.rm_containers_index
    if 0 <= idx < len(scene.rm_containers):
        return idx, scene.rm_containers[idx]
    return -1, None


def _emjson_dir(context) -> str:
    from ..sync_manager.bring import _active_entry
    entry = _active_entry(context)
    raw = getattr(entry, "graphml_path", "") if entry is not None else ""
    if not raw:
        return ""
    path = bpy.path.abspath(raw)
    return path if os.path.isdir(path) else os.path.dirname(path)


def _project_root(context) -> Optional[str]:
    try:
        from ..sync_manager.file_states import project_root
        return project_root(context)
    except Exception:  # noqa: BLE001
        return None


def _resolver(context):
    """A locator of the graph → a path on this disk (the em.json's folder, the
    other bases of the project, then the standard tree), or None."""
    from ..sync_manager.bring import base_dirs
    bases = list(base_dirs(context))
    root = _project_root(context)
    if root:
        from s3dgraphy.project_tree import search_bases
        bases += search_bases(root)

    def resolve(url: str) -> Optional[str]:
        if not url:
            return None
        if os.path.isabs(url):
            return url if os.path.exists(url) else None
        for b in bases:
            p = os.path.normpath(os.path.join(b, *url.split("/")))
            if os.path.exists(p):
                return p
        return None
    return resolve


def _world_box(obj):
    from mathutils import Vector  # type: ignore
    if obj is None or obj.type not in {"MESH", "CURVE"}:
        return None
    pts = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    return ([min(p[i] for p in pts) for i in range(3)], [max(p[i] for p in pts) for i in range(3)])


def _boxes(context, graph, cont):
    """The container's models, the models of no container (in the scene, and
    in the graph only), and those of the other containers — with their boxes."""
    scene = context.scene
    members = {e.name: _world_box(bpy.data.objects.get(e.name)) for e in cont.mesh_names
               if bpy.data.objects.get(e.name) is not None
               and bpy.data.objects[e.name].type in {"MESH", "CURVE"}}
    elsewhere, candidates, scene_rms = {}, {}, set()
    for o in scene.objects:
        if o.type not in {"MESH", "CURVE"}:
            continue
        rid = resolve_rm_node_id(graph, o, scene=scene, migra=False) if graph is not None else None
        if rid:
            scene_rms.add(rid)
        if o.name in members:
            continue
        idx = find_container_for_mesh(scene, o.name)
        if idx is not None:
            elsewhere[o.name] = _world_box(o)
        elif any(item.name == o.name for item in scene.rm_list):
            candidates[o.name] = _world_box(o)
    if graph is not None:
        from s3dgraphy.resources.alternatives import container_of
        tileset_hats = {h for a in ca.tileset_assets(graph) for h in a["hats"]}
        loose = [n.node_id for n in graph.nodes
                 if getattr(n, "node_type", "") == "representation_model"
                 and n.node_id not in scene_rms and n.node_id not in tileset_hats
                 and container_of(graph, n.node_id) is None]
        for rid, (name, box) in ca.graph_model_boxes(graph, loose, _resolver(context)).items():
            candidates[name] = box
    return members, candidates, elsewhere


def place_twins(context, graph, cont) -> Dict[str, str]:
    """``{mesh: rm_id}`` for the container's meshes that carry no RM of the
    graph, matched BY PLACE to an RM of the graph that no scene object stands
    for (the same box, IoU ≥ 0.9). Measured on GreatTemple_2026_v2.blend: the
    10 ME_ meshes of the survey resolve to no RM, while SM_OB_*_LOD1 of v3.2
    have their boxes to the millimetre."""
    if graph is None:
        return {}
    scene = context.scene
    loose_boxes = {}
    members = {}
    for e in cont.mesh_names:
        obj = bpy.data.objects.get(e.name)
        if obj is None or obj.type not in {"MESH", "CURVE"}:
            continue
        if not resolve_rm_node_id(graph, obj, scene=scene, migra=False):
            members[e.name] = _world_box(obj)
    if not members:
        return {}
    scene_rms = {resolve_rm_node_id(graph, o, scene=scene, migra=False) for o in scene.objects}
    loose = [n.node_id for n in graph.nodes
             if getattr(n, "node_type", "") == "representation_model" and n.node_id not in scene_rms]
    for rid, (_name, box) in ca.graph_model_boxes(graph, loose, _resolver(context)).items():
        loose_boxes[rid] = box
    return {m: rid for rid, m in ca.twins(members, loose_boxes).items()}


def refresh_from_graph(container, graph) -> None:
    """The panel's copy of the container's alternative, from the graph (the
    truth): written by the operators and on opening an em.json."""
    alt = ca.alternative_of(graph, container.group_node_id) if graph is not None else None
    container.alt_asset_id = alt["asset_id"] if alt else ""
    container.alt_name = alt["name"] if alt else ""
    container.alt_uses = ", ".join(alt["uses"]) if alt else ""
    if not alt:
        container.alt_note = ""


def measure_choice(context, cont, source: str, asset_id: str = "", path: str = "") -> Dict[str, Any]:
    """What the dialog shows, measured once when it opens (and by the headless
    smoke the same way): the tileset read, the storage plan for a file of the
    disk, the coverage against the container. Fills :data:`_PENDING` and
    returns ``{name, uses, action}`` for the dialog's fields. Raises
    ValueError when the choice is not a tileset."""
    _PENDING.clear()
    graph = _graph(context)
    known = {i[0] for i in _USE_ITEMS}
    name, uses = "", set(ca.DEFAULT_USES)
    target = ""
    if source == 'GRAPH':
        a = next((x for x in ca.tileset_assets(graph) if x["asset_id"] == asset_id), None)
        if a is None:
            raise ValueError(f"{asset_id!r} is not a tileset of the graph")
        name = a["name"]
        uses = {u for u in a["uses"] if u in known} or uses
        target = _resolver(context)(a["url"]) or ""
        if not target:
            _PENDING["error"] = f"{a['url']}: not on this disk — the coverage cannot be measured"
    else:
        target = bpy.path.abspath(path)
    inspection = None
    if target:
        try:
            inspection = ca.inspect_tileset(target)
        except (ValueError, OSError) as exc:
            if source == 'DISK':
                raise ValueError(str(exc))
            _PENDING["error"] = str(exc)
    if source == 'DISK':
        name = inspection["name"]
        _PENDING["plan"] = ca.storage_plan(target, _project_root(context), _emjson_dir(context))
    action = 'CONFIRM'
    if inspection is not None:
        members, candidates, elsewhere = _boxes(context, graph, cont)
        cov = ca.coverage(inspection, members, candidates, elsewhere)
        _PENDING.update(inspection=inspection, coverage=cov)
        action = 'CONFIRM' if cov["same"] else 'ANYWAY'
    _PENDING["container"] = cont.label
    return {"name": name, "uses": uses, "action": action}


# ── «Choose…» ────────────────────────────────────────────────────────────────

class RMCONTAINER_MT_alt_choose(Menu):
    bl_idname = "RMCONTAINER_MT_alt_choose"
    bl_label = "Choose the container's alternative"

    def draw(self, context):
        layout = self.layout
        layout.operator_context = 'INVOKE_DEFAULT'
        layout.operator("rmcontainer.alt_from_graph", text="A tileset of the graph…",
                        icon='NODETREE')
        layout.operator("rmcontainer.alt_from_disk", text="A file or folder from the disk…",
                        icon='FILE_FOLDER')
        layout.separator()
        layout.label(text="or drop a .3tz / .zip on this sidebar", icon='IMPORT')


def _graph_tileset_items(self, context):
    graph = _graph(context)
    items = []
    for a in ca.tileset_assets(graph):
        uses = ", ".join(a["uses"]) or "no use"
        held = f" · held by {', '.join(a['hat_names'])}" if a["hat_names"] else ""
        items.append((a["asset_id"], f"{a['name']}  ·  {uses}  ·  {ca.human_size(a['size_bytes'])}",
                      f"{a['url']}{held}"))
    _graph_tileset_items.cache = items or [("", "No tileset in the graph", "")]
    return _graph_tileset_items.cache


class RMCONTAINER_OT_alt_from_graph(Operator):
    """A tileset already in the graph as the alternative of the active container."""
    bl_idname = "rmcontainer.alt_from_graph"
    bl_label = "A tileset of the graph"
    bl_property = "asset_id"

    container_index: IntProperty(default=-1)  # type: ignore
    asset_id: EnumProperty(name="Tileset", items=_graph_tileset_items)  # type: ignore

    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        if not self.asset_id:
            self.report({'WARNING'}, "No tileset in the active graph: choose one from the disk")
            return {'CANCELLED'}
        return bpy.ops.rmcontainer.alt_confirm('INVOKE_DEFAULT', container_index=self.container_index,
                                               source='GRAPH', asset_id=self.asset_id)


class RMCONTAINER_OT_alt_from_disk(Operator):
    """A .3tz, a .zip, or a folder with tileset.json (open the folder and press
    the button with no file selected)."""
    bl_idname = "rmcontainer.alt_from_disk"
    bl_label = "Use as alternative"
    bl_description = ("Choose a .3tz, a .zip or a folder with tileset.json: it enters "
                      "the project's storage and becomes the container's alternative")

    container_index: IntProperty(default=-1)  # type: ignore
    filepath: StringProperty(subtype='FILE_PATH')  # type: ignore
    directory: StringProperty(subtype='DIR_PATH')  # type: ignore
    filter_glob: StringProperty(default="*.3tz;*.zip;tileset.json", options={'HIDDEN'})  # type: ignore
    filter_folder: BoolProperty(default=True, options={'HIDDEN'})  # type: ignore

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        path = self.filepath
        if not path or os.path.isdir(path) or not os.path.basename(path):
            path = self.directory
        path = bpy.path.abspath(path)
        return bpy.ops.rmcontainer.alt_confirm('INVOKE_DEFAULT', container_index=self.container_index,
                                               source='DISK', path=path)


class RMCONTAINER_OT_alt_drop(Operator):
    """What a .3tz / .zip dropped on the sidebar opens: the same dialog."""
    bl_idname = "rmcontainer.alt_drop"
    bl_label = "Tileset as the container's alternative"
    bl_options = {'INTERNAL'}

    directory: StringProperty(subtype='DIR_PATH', options={'SKIP_SAVE', 'HIDDEN'})  # type: ignore
    files: CollectionProperty(type=bpy.types.OperatorFileListElement,  # type: ignore
                              options={'SKIP_SAVE', 'HIDDEN'})
    filepath: StringProperty(subtype='FILE_PATH', options={'SKIP_SAVE', 'HIDDEN'})  # type: ignore

    def invoke(self, context, event):
        return self.execute(context)

    def execute(self, context):
        path = self.filepath
        if not path and self.files:
            path = os.path.join(self.directory, self.files[0].name)
        if not path:
            return {'CANCELLED'}
        return bpy.ops.rmcontainer.alt_confirm('INVOKE_DEFAULT', source='DISK', path=path)


if hasattr(bpy.types, "FileHandler"):
    class RMCONTAINER_FH_tileset(bpy.types.FileHandler):
        """A .3tz or .zip dropped on the 3D Viewport's SIDEBAR (where the RM
        Containers panel is), with a container active."""
        bl_idname = "RMCONTAINER_FH_tileset"
        bl_label = "Container alternative (tileset)"
        bl_import_operator = "rmcontainer.alt_drop"
        bl_file_extensions = ".3tz;.zip"

        @classmethod
        def poll_drop(cls, context):
            area, region = context.area, context.region
            return (area is not None and area.type == 'VIEW_3D'
                    and region is not None and region.type == 'UI'
                    and active_container(context.scene) is not None)
else:                                                        # pragma: no cover
    RMCONTAINER_FH_tileset = None


# ── the dialog: name, uses, coverage, the three answers ─────────────────────

class RMCONTAINER_OT_alt_confirm(Operator):
    """The container's alternative: the coverage check, then the declaration."""
    bl_idname = "rmcontainer.alt_confirm"
    bl_label = "Container alternative"
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    container_index: IntProperty(default=-1)  # type: ignore
    source: EnumProperty(items=[('GRAPH', "Graph", ""), ('DISK', "Disk", "")])  # type: ignore
    asset_id: StringProperty()  # type: ignore
    path: StringProperty(subtype='FILE_PATH')  # type: ignore
    name: StringProperty(name="Name", description="The tileset's name in the graph")  # type: ignore
    uses: EnumProperty(name="Uses", items=_USE_ITEMS, options={'ENUM_FLAG'},  # type: ignore
                       default={"web", "realtime"})
    action: EnumProperty(  # type: ignore
        name="Answer",
        items=[('CONFIRM', "Confirm", "Declare the alternative"),
               ('ADD', "Add to the container", "Put in the container the models the "
                "tileset holds and the container lacks, then declare"),
               ('ANYWAY', "Confirm anyway", "Declare it as it is: the row keeps a warning")],
        default='CONFIRM')

    def invoke(self, context, event):
        idx, cont = _container(context, self.container_index)
        if cont is None:
            self.report({'WARNING'}, "No active container")
            return {'CANCELLED'}
        self.container_index = idx
        try:
            got = measure_choice(context, cont, self.source, self.asset_id, self.path)
        except ValueError as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        self.name = got["name"]
        self.uses = got["uses"]
        self.action = got["action"]
        return context.window_manager.invoke_props_dialog(self, width=520)

    def draw(self, context):
        layout = self.layout
        layout.label(text=f"Alternative of «{_PENDING.get('container', '')}»", icon='MOD_ARRAY')
        layout.prop(self, "name")
        row = layout.row(align=True)
        row.label(text="Uses:")
        row.prop(self, "uses")
        plan = _PENDING.get("plan")
        if plan:
            box = layout.box()
            box.scale_y = 0.8
            box.label(text=("Copied into the project: " if plan["copy"] else "Stays where it is: ")
                      + plan["locator"], icon='FILE_FOLDER')
            if plan.get("unpack"):
                box.label(text="The .zip is unpacked beside it: the folder is the version served")
            if plan.get("note"):
                box.label(text=plan["note"], icon='INFO')
        cov = _PENDING.get("coverage")
        box = layout.box()
        if cov is None:
            box.label(text=_PENDING.get("error") or "Coverage not measured", icon='QUESTION')
        else:
            for i, line in enumerate(ca.coverage_lines(cov)):
                box.label(text=line, icon=('CHECKMARK' if cov["same"] else 'INFO') if i == 0 else 'DOT')
            sub = box.column()
            sub.scale_y = 0.7
            sub.label(text=f"Measured on {cov['leaves']} leaf tiles (no tile loaded); "
                           f"never a lock: the declaration is yours")
        if cov is not None and not cov["same"]:
            layout.prop(self, "action", expand=True)

    def execute(self, context):
        idx, cont = _container(context, self.container_index)
        graph = _graph(context)
        if cont is None or graph is None:
            self.report({'WARNING'}, "No active container or graph")
            return {'CANCELLED'}
        cov = _PENDING.get("coverage") or {}
        if self.action == 'ADD' and cov.get("extra"):
            added, refused = [], []
            for name in cov["extra"]:
                obj = bpy.data.objects.get(name)
                if obj is None:
                    refused.append(name)
                    continue
                ok, _why = add_mesh_to_container(context, cont, obj)
                (added if ok else refused).append(name)
            if refused:
                self.report({'WARNING'}, f"Not added (no object in the scene, or in another "
                                         f"container): {', '.join(refused)}")
        if not cont.group_node_id:
            reconcile_container_groups(context, create_missing=True)
        if not cont.group_node_id or graph.find_node_by_id(cont.group_node_id) is None:
            reconcile_container_groups(context, create_missing=True)
        if not cont.group_node_id or graph.find_node_by_id(cont.group_node_id) is None:
            self.report({'WARNING'}, f"«{cont.label}» has no group in the graph: press Project first")
            return {'CANCELLED'}
        asset = self.asset_id
        if self.source == 'DISK':
            try:
                plan = ca.apply_storage(_PENDING.get("plan") or ca.storage_plan(
                    bpy.path.abspath(self.path), _project_root(context), _emjson_dir(context)))
                master = ca.measure(plan["dest"], plan["locator"])
                served = ca.measure(plan["unpack"], plan["unpack_locator"]) if plan.get("unpack") else None
            except Exception as exc:  # noqa: BLE001 — the reason is the user's
                self.report({'ERROR'}, f"The tileset could not enter the storage: {exc}")
                return {'CANCELLED'}
            asset = ca.find_by_checksum(graph, master["file"]["checksum"])
            if asset:
                # the same bytes are already a resource of the graph: the same
                # resource, with the name it has there (the file's name the
                # dialog proposed would overwrite somebody's)
                known = graph.find_node_by_id(asset)
                self.report({'INFO'}, f"These bytes are already in the graph as "
                                      f"«{getattr(known, 'name', asset)}»: that resource is used")
                self.name = ""
            else:
                asset = ca.new_tileset_asset(graph, self.name.strip() or "Tileset", master,
                                             served, _ordered(self.uses))["asset_id"]
        scene_rms = {str(o.get("em_rm_node_id")) for o in bpy.data.objects if o.get("em_rm_node_id")}
        try:
            res = ca.write_alternative(graph, cont.group_node_id, asset, uses=_ordered(self.uses),
                                       name=self.name.strip(), scene_rm_ids=scene_rms)
        except ValueError as exc:
            self.report({'WARNING'}, str(exc))
            return {'CANCELLED'}
        refresh_from_graph(cont, graph)
        cont.alt_note = ca.note_of(cov) if self.action == 'ANYWAY' else ""
        insp = _PENDING.get("inspection")
        if insp and insp.get("envelope"):
            lo, hi = insp["envelope"]
            cont.alt_box_min, cont.alt_box_max = lo, hi
        apply_view(cont, context)
        for w in res.get("warnings") or []:
            self.report({'WARNING'}, w)
        said = f"«{cont.alt_name}» is the alternative of «{cont.label}»"
        if res.get("dropped_rm"):
            said += " (its RM, which only held it, is gone)"
        self.report({'INFO'}, said)
        _PENDING.clear()
        return {'FINISHED'}


class RMCONTAINER_OT_alt_remove(Operator):
    """Remove the alternative: the container stops being its hat; the resource
    and its file stay."""
    bl_idname = "rmcontainer.alt_remove"
    bl_label = "Remove the alternative"
    bl_options = {'REGISTER', 'UNDO'}

    container_index: IntProperty(default=-1)  # type: ignore

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        _idx, cont = _container(context, self.container_index)
        graph = _graph(context)
        if cont is None:
            return {'CANCELLED'}
        if graph is not None and cont.group_node_id:
            ca.remove_alternative(graph, cont.group_node_id)
        name = cont.alt_name
        cont.alt_mode = 'MODELS'
        refresh_from_graph(cont, graph)
        box = bpy.data.objects.get(box_name(cont))
        if box is not None:
            bpy.data.objects.remove(box, do_unlink=True)
        self.report({'INFO'}, f"«{name}» is no longer the alternative of «{cont.label}» "
                              f"(the resource and its file stay)")
        return {'FINISHED'}


# ── the eye and the mode, on the scene ──────────────────────────────────────

def box_name(cont) -> str:
    return f"{cont.alt_name or 'Tileset'} · alternative of {cont.label}"


def apply_view(cont, context=None) -> None:
    """Models / Tileset / Automatic on the scene: Blender does not draw a
    tileset, so the tileset stands as a box (an empty) over what it holds, and
    «Automatic» is «Models» here (no distance to switch on). The eye shows or
    hides the box."""
    if not cont.alt_asset_id:
        return
    tileset = cont.alt_mode == 'TILESET'
    for e in cont.mesh_names:
        obj = bpy.data.objects.get(e.name)
        if obj is not None:
            try:
                obj.hide_set(tileset)
            except RuntimeError:            # not in the view layer
                pass
    name = box_name(cont)
    box = bpy.data.objects.get(name)
    if box is None and any(cont.alt_box_max[i] > cont.alt_box_min[i] for i in range(3)):
        box = bpy.data.objects.new(name, None)
        box.empty_display_type = 'CUBE'
        box["em_alternative_of"] = cont.label
        box["em_alternative_asset"] = cont.alt_asset_id
        (context.scene if context else bpy.context.scene).collection.objects.link(box)
    if box is not None:
        lo, hi = cont.alt_box_min, cont.alt_box_max
        box.location = [(lo[i] + hi[i]) / 2 for i in range(3)]
        box.scale = [max(1e-3, (hi[i] - lo[i]) / 2) for i in range(3)]
        try:
            box.hide_set(not cont.alt_shown)
        except RuntimeError:
            pass


_CLASSES = [RMCONTAINER_MT_alt_choose, RMCONTAINER_OT_alt_from_graph, RMCONTAINER_OT_alt_from_disk,
            RMCONTAINER_OT_alt_drop, RMCONTAINER_OT_alt_confirm, RMCONTAINER_OT_alt_remove]
if RMCONTAINER_FH_tileset is not None:
    _CLASSES.append(RMCONTAINER_FH_tileset)


def register_alternative_operators():
    for cls in _CLASSES:
        try:
            bpy.utils.register_class(cls)
        except ValueError:
            bpy.utils.unregister_class(cls)
            bpy.utils.register_class(cls)


def unregister_alternative_operators():
    for cls in reversed(_CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:  # noqa: BLE001
            pass
