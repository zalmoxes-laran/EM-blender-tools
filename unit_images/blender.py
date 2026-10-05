"""U5 · the images of the units in Blender: propose by name, confirm, keep as
resources, see them with their thumbnail and their file's state.

The decisions are in ``core.py``; this file reads the scene and the graph,
writes what the person confirmed (a resource with its sha256 and position, an
edge ``has_linked_resource`` from the unit), and keeps the thumbnails in the
derived cache (``~/.em_cache/thumbs``, keyed by sha256: never in the project,
never in the room — any computer rebuilds them).
"""

import os
from typing import Any, Dict, List, Optional

import bpy
import bpy.utils.previews
from bpy.props import BoolProperty, CollectionProperty, PointerProperty, StringProperty
from bpy.types import Operator, PropertyGroup

from . import core

_PREVIEWS = None
#: {resource_id: (state, path)} as the resolver last said it, for drawing
_STATES: Dict[str, Any] = {}
_STRATIGRAPHIC = ("US", "USV", "USVs", "USVn", "USVS", "USVA", "USM", "USR", "USD", "SF", "VSF",
                  "TSU", "SE", "BR", "serSU", "serUSVn", "serUSVs", "serUSD", "UL")


def cache_root() -> str:
    return os.path.expanduser(os.environ.get("EM_THUMBS_DIR") or os.path.join("~", ".em_cache", "thumbs"))


def _graph(context):
    from ..functions import is_graph_available
    ok, graph = is_graph_available(context)
    return graph if ok else None


def _project_root(context) -> Optional[str]:
    try:
        from ..sync_manager.file_states import project_root
        return project_root(context)
    except Exception:  # noqa: BLE001
        return None


def units_of(graph) -> List[tuple]:
    """(node_id, name) of the stratigraphic units and the finds of the graph."""
    out = []
    for n in getattr(graph, "nodes", []) or []:
        nt = str(getattr(n, "node_type", "") or "")
        if nt in _STRATIGRAPHIC or nt.startswith("US"):
            out.append((n.node_id, str(getattr(n, "name", "") or "")))
    return out


def _data(node) -> Dict[str, Any]:
    d = getattr(node, "data", None)
    return d if isinstance(d, dict) else {}


def _locator(node) -> str:
    return str(_data(node).get("url") or getattr(node, "url", "") or "")


def _checksum(node) -> str:
    return str(_data(node).get("checksum") or getattr(node, "checksum", "") or "")


def linked_images(graph, unit_id: str) -> List[Any]:
    """The image resources a unit links (``has_linked_resource``)."""
    out = []
    for e in getattr(graph, "edges", []) or []:
        if e.edge_type != "has_linked_resource" or e.edge_source != unit_id:
            continue
        node = graph.find_node_by_id(e.edge_target)
        if node is None or getattr(node, "node_type", "") != "resource":
            continue
        if core.is_image(_locator(node)) or str(_data(node).get("media_type", "")).startswith("image/") \
                or getattr(node, "url_type", "") == "image":
            out.append(node)
    return out


def resource_by_sha(graph, hexd: str):
    want = core.thumb_path("", hexd).rsplit(os.sep, 1)[-1].split("_")[0]
    for n in getattr(graph, "nodes", []) or []:
        if getattr(n, "node_type", "") == "resource" and _checksum(n).split(":", 1)[-1].lower() == want:
            return n
    return None


def make_thumb(src: str, dst: str) -> bool:
    """The thumbnail of ``src`` written at ``dst`` (PNG, fitted in 256 px)."""
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    try:
        from PIL import Image, ImageOps
        with Image.open(src) as img:
            img = img.convert("RGB")
            ImageOps.fit(img, (core.THUMB_SIZE, core.THUMB_SIZE)).save(dst, "PNG")
        return True
    except Exception:  # noqa: BLE001 — without Pillow, Blender scales it
        try:
            im = bpy.data.images.load(src, check_existing=False)
            w, h = im.size
            k = core.THUMB_SIZE / max(w, h, 1)
            im.scale(max(1, int(w * k)), max(1, int(h * k)))
            im.filepath_raw = dst
            im.file_format = 'PNG'
            im.save()
            bpy.data.images.remove(im)
            return True
        except Exception as exc:  # noqa: BLE001
            print(f"[unit images] no thumbnail for {src}: {exc}")
            return False


def resolve(context, node) -> tuple:
    """(state, path) of an image resource, with the one resolver (R1)."""
    from s3dgraphy import api
    try:
        from ..sync_manager.bring import base_dirs
        bases = base_dirs(context)
    except Exception:  # noqa: BLE001
        bases = []
    r = api.resolve_file({"id": node.node_id, "locator": _locator(node), "checksum": _checksum(node)},
                         project_root=_project_root(context), base_dirs=bases)
    _STATES[node.node_id] = (r.get("state") or "missing", r.get("path") or "")
    return _STATES[node.node_id]


def thumb_icon(node, path: str = "") -> int:
    """The icon id of a resource's thumbnail from the cache, made from ``path``
    when the cache does not have it yet; 0 when there is none."""
    global _PREVIEWS
    hexd = _checksum(node).split(":", 1)[-1]
    if not hexd:
        return 0
    dst = core.thumb_path(cache_root(), hexd)
    if not os.path.isfile(dst):
        if not (path and os.path.isfile(path) and make_thumb(path, dst)):
            return 0
    if _PREVIEWS is None:
        _PREVIEWS = bpy.utils.previews.new()
    if hexd not in _PREVIEWS:
        _PREVIEWS.load(hexd, dst, 'IMAGE')
    return _PREVIEWS[hexd].icon_id


# ── what the panel keeps ─────────────────────────────────────────────────────

class EM_UnitImageProposal(PropertyGroup):
    path: StringProperty()  # type: ignore
    unit_id: StringProperty()  # type: ignore
    unit_name: StringProperty()  # type: ignore
    take: BoolProperty(name="Link", default=True,
                       description="Link this image to the unit (confirmed when you press Link)")  # type: ignore


class EM_UnitImagesSettings(PropertyGroup):
    pattern: StringProperty(
        name="Name pattern", default=core.DEFAULT_PATTERN,
        description="How an image's name says its unit: {unit} is the unit's code (US012 = US12), "
                    "* any text. Example: {unit}_* matches US012_north.jpg")  # type: ignore
    folder: StringProperty(
        name="Folder", subtype='DIR_PATH', default="",
        description="Where to look; empty: the EM standard tree of the project (EM/DosCo, EM, RB, SB)")  # type: ignore
    proposals: CollectionProperty(type=EM_UnitImageProposal)  # type: ignore
    show_tools: BoolProperty(name="Find images", default=False)  # type: ignore


# ── the gestures ─────────────────────────────────────────────────────────────

class EM_OT_unit_images_propose(Operator):
    """Look for images whose name says a unit of the graph (the pattern) in
    the EM standard tree of the project, or in the folder given, and propose
    them: nothing is linked until you confirm"""
    bl_idname = "em.unit_images_propose"
    bl_label = "Propose images"
    bl_options = {'REGISTER'}

    def execute(self, context):
        graph = _graph(context)
        if graph is None:
            self.report({'ERROR'}, "no graph loaded: load one first")
            return {'CANCELLED'}
        st = context.scene.em_unit_images
        root = _project_root(context)
        folders = [bpy.path.abspath(st.folder)] if st.folder else core.start_folders(root)
        if not folders:
            self.report({'ERROR'}, "where to look? The graph is in no EM project tree (EM/DosCo …): "
                                   "give a folder")
            return {'CANCELLED'}
        props = core.propose(core.images_under(folders), units_of(graph), st.pattern)
        already = {(e.edge_source, _locator(graph.find_node_by_id(e.edge_target)))
                   for e in graph.edges if e.edge_type == "has_linked_resource"
                   and graph.find_node_by_id(e.edge_target) is not None}
        st.proposals.clear()
        n = 0
        for p in props:
            if (p["unit_id"], core.locator_for(p["path"], root)) in already:
                continue
            item = st.proposals.add()
            item.path, item.unit_id, item.unit_name = p["path"], p["unit_id"], p["unit_name"]
            n += 1
        units = len({p.unit_id for p in st.proposals})
        where = ", ".join(os.path.relpath(f, root) if root and f.startswith(root) else f for f in folders)
        self.report({'INFO'}, f"{n} image(s) proposed for {units} unit(s) — searched {where}; "
                              f"check them and press Link" if n else
                              f"no new image whose name says a unit ({st.pattern}) — searched {where}")
        return {'FINISHED'}


class EM_OT_unit_images_confirm(Operator):
    """Link the proposed images that are ticked: each becomes a resource of the
    graph (its sha256 and where it is) linked to its unit, and gets its
    thumbnail in the cache"""
    bl_idname = "em.unit_images_confirm"
    bl_label = "Link"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        from s3dgraphy import api
        from ..sync_manager.asset_upload import sha256_of_file
        graph = _graph(context)
        st = context.scene.em_unit_images
        if graph is None:
            self.report({'ERROR'}, "no graph loaded")
            return {'CANCELLED'}
        root = _project_root(context)
        linked, made, keep = 0, 0, []
        for p in st.proposals:
            if not p.take:
                keep.append((p.path, p.unit_id, p.unit_name, False))
                continue
            hexd = sha256_of_file(p.path).split(":", 1)[-1]
            res = resource_by_sha(graph, hexd)
            new_nodes = []
            if res is None:
                ext = os.path.splitext(p.path)[1].lower().lstrip(".")
                res = api.add_resource(graph, name=os.path.basename(p.path), kind="image", files=[{
                    "path": core.locator_for(p.path, root), "checksum": f"sha256:{hexd}",
                    "size_bytes": os.path.getsize(p.path),
                    "media_type": "image/" + ("jpeg" if ext in ("jpg", "jpeg") else ext)}])
                made += 1
                new_nodes.append(res)
            exists = any(e.edge_type == "has_linked_resource" and e.edge_source == p.unit_id
                         and e.edge_target == res.node_id for e in graph.edges)
            new_edge = None
            if not exists:
                new_edge = graph.add_edge(f"{p.unit_id}_has_linked_resource_{res.node_id}",
                                          p.unit_id, res.node_id, "has_linked_resource")
                linked += 1
            _emit(new_nodes, [new_edge] if new_edge is not None else [])
            make_thumb(p.path, core.thumb_path(cache_root(), hexd))
        st.proposals.clear()
        for path, uid, uname, take in keep:
            it = st.proposals.add()
            it.path, it.unit_id, it.unit_name, it.take = path, uid, uname, take
        _STATES.clear()
        self.report({'INFO'}, f"{linked} image(s) linked to their unit ({made} new resource(s)); "
                              f"{len(keep)} left unticked")
        return {'FINISHED'}


def _emit(nodes, edges) -> None:
    """The same edits to the room (or the Sidecar), when there is one."""
    try:
        from ..sync_manager import operators as sync
        for n in nodes:
            sync.emit_op({"type": "op", "op": "add_node", "node": {
                "id": n.node_id, "name": str(getattr(n, "name", "")), "node_type": "resource",
                "data": dict(_data(n))}})
        for e in edges:
            sync.emit_op({"type": "op", "op": "add_edge", "edge": {
                "id": e.edge_id, "source": e.edge_source, "target": e.edge_target,
                "edge_type": e.edge_type}})
    except Exception as exc:  # noqa: BLE001 — linked here all the same
        print(f"[unit images] not sent: {exc}")


class EM_OT_unit_images_unlink(Operator):
    """Remove the link between this unit and this image, linked by mistake: the
    image stays a resource of the graph (another unit may use it, and its file
    is untouched); only the edge from the unit goes, here and in the room"""
    bl_idname = "em.unit_images_unlink"
    bl_label = "Remove link"
    bl_options = {'REGISTER', 'UNDO'}

    unit_id: StringProperty()  # type: ignore
    resource_id: StringProperty()  # type: ignore

    def execute(self, context):
        graph = _graph(context)
        if graph is None:
            self.report({'ERROR'}, "no graph loaded")
            return {'CANCELLED'}
        gone = [e for e in list(graph.edges)
                if e.edge_type == "has_linked_resource" and e.edge_source == self.unit_id
                and e.edge_target == self.resource_id]
        if not gone:
            self.report({'WARNING'}, "this image is not linked to this unit")
            return {'CANCELLED'}
        for e in gone:
            graph.remove_edge(e.edge_id)
        _emit_removed(gone)
        _STATES.pop(self.resource_id, None)
        still = sum(1 for e in graph.edges if e.edge_target == self.resource_id)
        res = graph.find_node_by_id(self.resource_id)
        name = str(getattr(res, "name", "") or self.resource_id)
        self.report({'INFO'}, f"{name} is no longer linked to this unit"
                              + (f" (still linked {still} time(s) elsewhere)" if still
                                 else " (the resource stays in the graph, linked to nothing)"))
        return {'FINISHED'}


def _emit_removed(edges) -> None:
    """The removal to the room (or the Sidecar), when there is one."""
    try:
        from ..sync_manager import operators as sync
        for e in edges:
            sync.emit_op({"type": "op", "op": "delete_edge", "edge": {
                "id": e.edge_id, "source": e.edge_source, "target": e.edge_target,
                "edge_type": e.edge_type}})
    except Exception as exc:  # noqa: BLE001 — removed here all the same
        print(f"[unit images] not sent: {exc}")


class EM_OT_unit_images_refresh(Operator):
    """Read again where the images of the unit are (the one resolver) and
    rebuild a thumbnail the cache lost"""
    bl_idname = "em.unit_images_refresh"
    bl_label = "Check the images"
    bl_options = {'REGISTER'}

    def execute(self, context):
        _STATES.clear()
        global _PREVIEWS
        if _PREVIEWS is not None:
            bpy.utils.previews.remove(_PREVIEWS)
            _PREVIEWS = None
        self.report({'INFO'}, "images read again")
        return {'FINISHED'}


def draw(layout, context, unit) -> None:
    """The section «Images of the unit» of the Stratigraphy Manager."""
    from ..state_symbols import sign
    graph = _graph(context)
    if graph is None or unit is None:
        layout.label(text="No graph loaded", icon='ERROR')
        return
    st = context.scene.em_unit_images
    imgs = linked_images(graph, unit.id_node)
    if not imgs:
        layout.label(text="No image linked to this unit", icon='INFO')
    for node in imgs:
        state, path = _STATES.get(node.node_id) or resolve(context, node)
        row = layout.row(align=True)
        icon = thumb_icon(node, path)
        if icon:
            row.template_icon(icon_value=icon, scale=3.0)
        col = row.column(align=True)
        col.label(text=str(getattr(node, "name", "")))
        _icon, said, _meaning = sign(f"file.{state}")
        col.label(text=said)
        row_ops = col.row(align=True)
        if path:
            op = row_ops.operator("wm.path_open", text="Open", icon='FILE_IMAGE')
            op.filepath = path
        op = row_ops.operator("em.unit_images_unlink", text="Remove link", icon='UNLINKED')
        op.unit_id, op.resource_id = unit.id_node, node.node_id
    mine = [p for p in st.proposals if p.unit_id == unit.id_node]
    if mine:
        box = layout.box()
        box.label(text=f"Proposed for {unit.name}: tick and press Link", icon='QUESTION')
        for p in mine:
            box.prop(p, "take", text=os.path.basename(p.path))
    tools = layout.box()
    tools.prop(st, "show_tools", icon='TRIA_DOWN' if st.show_tools else 'TRIA_RIGHT', emboss=False)
    if st.show_tools:
        tools.prop(st, "pattern")
        tools.prop(st, "folder")
        row = tools.row(align=True)
        row.operator("em.unit_images_propose", icon='VIEWZOOM')
        n = sum(1 for p in st.proposals if p.take)
        sub = row.row(align=True)
        sub.enabled = n > 0
        sub.operator("em.unit_images_confirm", text=f"Link {n}" if n else "Link", icon='LINKED')
        row.operator("em.unit_images_refresh", text="", icon='FILE_REFRESH')
        if st.proposals:
            tools.label(text=f"{len(st.proposals)} proposed for "
                             f"{len({p.unit_id for p in st.proposals})} unit(s)", icon='INFO')


classes = (EM_UnitImageProposal, EM_UnitImagesSettings, EM_OT_unit_images_propose,
           EM_OT_unit_images_confirm, EM_OT_unit_images_unlink, EM_OT_unit_images_refresh)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.em_unit_images = PointerProperty(type=EM_UnitImagesSettings)


def unregister():
    global _PREVIEWS
    if _PREVIEWS is not None:
        bpy.utils.previews.remove(_PREVIEWS)
        _PREVIEWS = None
    if hasattr(bpy.types.Scene, "em_unit_images"):
        del bpy.types.Scene.em_unit_images
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass
