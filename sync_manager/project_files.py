"""The proxies and the representation models as FILES of the EM project
(E.D., 23 Oct 2026: «li voglio poter referenziare anche all'esterno di
Blender»; his answer: the EM standard tree).

Until today a proxy existed in the graph as ``proxies/<US>.glb`` and on disk
only if the old Heriverse exporter (now dead code) had written it; a model
existed as a datablock of the .blend, or as a version in ``em_cache`` beside
it. Nothing put them where a reader outside Blender looks: the project tree
of :mod:`s3dgraphy.project_tree`.

* a proxy → ``<project>/EM/proxies/<unit>.glb`` — the url the graph already
  writes (``proxy_chain.proxy_url``) lands there when the em.json sits in
  ``EM/``, and the resolver looks in ``EM/proxies`` first anyway;
* a model → ``<project>/RM/<container>/<object>…glb``, written by «Export a
  version for a use…» with its destination set to the project (its recipe,
  its stamp, its version in the graph — the same gesture, another folder).

With no standard tree the same folders sit beside the active em.json
(``proxies/``, ``RM/<container>/``); a graph never saved as em.json has no
place to write to, and that is said.

The decisions are pure (:func:`project_folders`, :func:`model_folder`,
:func:`proxy_file`, :func:`unit_for_object`), measured by
``tests/test_project_files.py``; the Blender side sits below them.
"""

# NOT `from __future__ import annotations`: the operators are built inside a
# function with `bpy` imported lazily, and Blender evaluates their property
# annotations (the same note as asset_versions).
import os
import re
from typing import Any, Dict, Iterable, List, Optional

#: the folders of the standard tree this module writes into
PROXIES_IN_TREE = ("EM", "proxies")
MODELS_IN_TREE = ("RM",)
#: beside the em.json, when there is no standard tree
PROXIES_BESIDE = "proxies"
MODELS_BESIDE = "RM"
#: the folder of a model that sits in no container
NO_CONTAINER = "models"

NEED_A_PLACE = ("save the graph as em.json first (EM ▸ Save As…): proxies "
                "and models are written in its project, beside it")


def project_folders(project_root: Optional[str], emjson_path: Optional[str]
                    ) -> Optional[Dict[str, str]]:
    """``{proxies, models, base, standard}``: where proxies and models go.

    ``project_root`` (the folder with ``EM/``) wins; else the folder of the
    em.json; None when there is neither."""
    if project_root:
        root = os.path.abspath(project_root)
        return {"proxies": os.path.join(root, *PROXIES_IN_TREE),
                "models": os.path.join(root, *MODELS_IN_TREE),
                "base": root, "standard": True}
    if emjson_path:
        here = os.path.dirname(os.path.abspath(emjson_path))
        return {"proxies": os.path.join(here, PROXIES_BESIDE),
                "models": os.path.join(here, MODELS_BESIDE),
                "base": here, "standard": False}
    return None


def safe_folder(label: str) -> str:
    """A container's label as a folder name: what a file system refuses
    becomes ``_``, the spaces and the accents stay (it is read by people)."""
    text = re.sub(r'[\\/:*?"<>|\x00-\x1f]+', "_", str(label or "")).strip(" ._")
    return text or NO_CONTAINER


def model_folder(models_root: str, container_label: Optional[str]) -> str:
    """``RM/<container>`` (``RM/models`` for a model in no container)."""
    return os.path.join(models_root, safe_folder(container_label or ""))


def proxy_file(proxies_root: str, unit_name: str) -> Optional[str]:
    """``<proxies>/<unit>.glb``, the file the graph's ``proxies/<unit>.glb``
    names. None for a unit name that cannot be a file name (a separator in
    it): the url and the file would not meet."""
    name = str(unit_name or "")
    if not name or "/" in name or "\\" in name or name in (".", ".."):
        return None
    return os.path.join(proxies_root, f"{name}.glb")


def unit_for_object(object_name: str, unit_names: Iterable[str]) -> Optional[str]:
    """The unit an object is the proxy of, matched as the old exporter did:
    the exact name, else ``<prefix>.<unit>`` (a graph's prefix). The longest
    unit wins a tie (``A.US1`` against ``US1`` and ``1``)."""
    names = [n for n in unit_names if n]
    if object_name in names:
        return object_name
    hits = [n for n in names if object_name.endswith("." + n)]
    return max(hits, key=len) if hits else None


def relative_url(base: str, path: str) -> str:
    """``path`` relative to ``base`` with ``/`` (what a graph writes)."""
    return os.path.relpath(path, base).replace(os.sep, "/")


# ── Blender ───────────────────────────────────────────────────────────────────

def _bpy():  # pragma: no cover — bpy
    import bpy  # type: ignore
    return bpy


def active_emjson(context) -> str:  # pragma: no cover — bpy
    """The em.json the active graph is saved in, or ""."""
    bpy = _bpy()
    try:
        from .. import graph_origins
        em = context.scene.em_tools
        rows = list(em.graphml_files)
        if not (0 <= em.active_file_index < len(rows)):
            return ""
        origin = graph_origins.origin_of(rows[em.active_file_index],
                                         abspath=bpy.path.abspath)
        return origin.path if origin.is_emjson else ""
    except Exception:  # noqa: BLE001
        return ""


def folders_here(context) -> Optional[Dict[str, str]]:  # pragma: no cover — bpy
    """:func:`project_folders` for this scene: the project of the active
    graph (``file_states.project_root``), else its em.json."""
    emjson = active_emjson(context)
    root = None
    try:
        from s3dgraphy.project_tree import find_project_root
        if emjson:
            root = find_project_root(emjson)
        if not root:
            from .file_states import project_root
            root = project_root(context)
    except Exception:  # noqa: BLE001
        root = None
    return project_folders(root, emjson)


def container_label_of(scene, obj_name: str) -> str:  # pragma: no cover — bpy
    """The label of the first container that holds the object, or ""."""
    for c in getattr(scene, "rm_containers", ()):
        if any(e.name == obj_name for e in c.mesh_names):
            return c.label or c.doc_name or ""
    return ""


def models_folder_for(context, obj) -> Optional[str]:  # pragma: no cover — bpy
    """``RM/<container>`` for ``obj``, or None (no place to write)."""
    where = folders_here(context)
    if where is None:
        return None
    return model_folder(where["models"], container_label_of(context.scene, obj.name))


def _units(context, graph) -> Dict[str, str]:  # pragma: no cover — bpy
    """``{unit name: node id}`` of the active graph's stratigraphic list."""
    out = {}
    try:
        for item in context.scene.em_tools.stratigraphy.units:
            if item.name and item.id_node:
                out[item.name] = item.id_node
    except AttributeError:
        pass
    if not out and graph is not None:
        #: the list not filled yet: the graph's stratigraphic nodes
        try:
            from s3dgraphy.nodes.stratigraphic_node import StratigraphicNode
        except ImportError:
            return out
        for n in graph.nodes:
            if isinstance(n, StratigraphicNode) and getattr(n, "name", ""):
                out[n.name] = n.node_id
    return out


def proxy_targets(context, graph, *, selected_only: bool):  # pragma: no cover — bpy
    """``[(object, unit name, unit id)]``: the selected proxies, or every
    proxy of the active graph present in the scene."""
    bpy = _bpy()
    units = _units(context, graph)
    names = list(units)
    out, seen = [], set()
    pool = (list(context.selected_objects) if selected_only
            else [o for o in bpy.data.objects if o.type == "MESH"])
    if selected_only:
        for obj in pool:
            if obj.type != "MESH":
                continue
            unit = unit_for_object(obj.name, names)
            if unit and unit not in seen:
                seen.add(unit)
                out.append((obj, unit, units[unit]))
        return out
    by_name = {o.name: o for o in pool}
    for unit in names:
        obj = by_name.get(unit)
        if obj is None:
            obj = next((o for o in pool if o.name.endswith("." + unit)), None)
        if obj is not None and unit not in seen:
            seen.add(unit)
            out.append((obj, unit, units[unit]))
    return out


def export_proxy_glb(context, obj, path: str) -> None:  # pragma: no cover — bpy
    """The proxy as the old exporter wrote it: this object alone, in world
    coordinates, its modifiers applied, no materials' images, a glb. The
    object is made visible and selectable for the export and put back."""
    bpy = _bpy()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    was = {"hide_viewport": obj.hide_viewport, "hide_select": obj.hide_select,
           "hidden": obj.hide_get()}
    selected = list(context.selected_objects)
    active = context.view_layer.objects.active
    try:
        obj.hide_viewport = False
        obj.hide_select = False
        obj.hide_set(False)
        for o in selected:
            o.select_set(False)
        obj.select_set(True)
        context.view_layer.objects.active = obj
        bpy.ops.export_scene.gltf(
            filepath=path, export_format="GLB", use_selection=True,
            export_apply=True, export_texcoords=True, export_normals=True,
            export_materials="NONE", export_yup=True, export_extras=False,
            export_animations=False)
    finally:
        obj.select_set(False)
        obj.hide_viewport = was["hide_viewport"]
        obj.hide_select = was["hide_select"]
        obj.hide_set(was["hidden"])
        for o in selected:
            try:
                o.select_set(True)
            except Exception:  # noqa: BLE001
                pass
        try:
            context.view_layer.objects.active = active
        except Exception:  # noqa: BLE001
            pass


def register_proxy_file(graph, unit_id: str, unit_name: str, path: str
                        ) -> Dict[str, Any]:  # pragma: no cover — s3dgraphy
    """The unit's proxy resource names these bytes: url ``proxies/<unit>.glb``
    and their checksum. A resource with no bytes yet takes them; the same
    bytes change nothing; other bytes make a REVISION (``replace_file``), the
    way a resource changes in this ecosystem. → ``{resource_id, state}``."""
    from s3dgraphy import api
    from s3dgraphy.room_import.node import sha256_of_file
    from ..proxy_chain import ensure_unit_proxy, migrate_old_proxies, proxy_url
    migrate_old_proxies(graph)
    got = ensure_unit_proxy(graph, unit_id, unit_name)
    rid = got["resource_id"]
    try:
        rid = api.current_revision(graph, rid)
    except Exception:  # noqa: BLE001
        pass
    node = graph.find_node_by_id(rid)
    data = node.data if node is not None and isinstance(node.data, dict) else {}
    digest = sha256_of_file(path)
    digest = digest if str(digest).startswith("sha256:") else f"sha256:{digest}"
    size = os.path.getsize(path)
    url = proxy_url(unit_name)
    old = str(data.get("checksum") or "")
    if old == digest:
        return {"resource_id": rid, "state": "unchanged"}
    if not old:
        data.update(url=url, checksum=digest, media_type="model/gltf-binary")
        if hasattr(node, "url"):
            node.url = url
        try:
            node.set_measures(size_bytes=size)
        except Exception:  # noqa: BLE001
            data["size_bytes"] = size
        return {"resource_id": rid, "state": "registered"}
    out = api.replace_file(graph, rid, None, checksum=digest, url=url,
                           size_bytes=size, media_type="model/gltf-binary")
    return {"resource_id": out.get("new_resource_id") or rid, "state": "revised"}


def stamp_proxy(context, obj, path: str, resource_id: str, unit_name: str
                ) -> Dict[str, Any]:  # pragma: no cover — bpy
    """The proxy's dtcstamp beside its glb (``birth_stamp``): exported from its
    object in this .blend, the resource id the graph gave it."""
    from .. import birth_stamp as BS
    return BS.stamp_blender_export(path, objects=[obj], technique="glTF export of the proxy",
                                   parameters={"unit": unit_name},
                                   resource_id=resource_id,
                                   label=f"Proxy of {unit_name}",
                                   register_in_graph=False, context=context)


def write_proxies(context, graph, targets) -> Dict[str, Any]:  # pragma: no cover — bpy
    """Each ``(object, unit, unit id)`` written, registered and stamped.
    → ``{written, revised, unchanged, stamped, failed, folder}``."""
    where = folders_here(context)
    if where is None:
        raise RuntimeError(NEED_A_PLACE)
    out = {"written": [], "revised": [], "unchanged": [], "stamped": 0,
           "failed": [], "folder": where["proxies"], "stamp_note": ""}
    for obj, unit, unit_id in targets:
        path = proxy_file(where["proxies"], unit)
        if path is None:
            out["failed"].append(f"{unit}: not a file name")
            continue
        try:
            export_proxy_glb(context, obj, path)
            reg = register_proxy_file(graph, unit_id, unit, path)
        except Exception as exc:  # noqa: BLE001 — said per proxy
            out["failed"].append(f"{unit}: {exc}")
            continue
        out["written"].append(unit)
        if reg["state"] == "revised":
            out["revised"].append(unit)
        elif reg["state"] == "unchanged":
            out["unchanged"].append(unit)
        st = stamp_proxy(context, obj, path, reg["resource_id"], unit)
        if st.get("state") in ("stamped", "revised", "unchanged"):
            out["stamped"] += 1
        elif not out["stamp_note"]:
            out["stamp_note"] = st.get("line") or ""
    return out


def _operator_classes():  # pragma: no cover — bpy
    bpy = _bpy()

    def _graph(context):
        from ..functions import is_graph_available
        ok, graph = is_graph_available(context)
        return graph if ok else None

    class EM_OT_proxies_write_files(bpy.types.Operator):
        """Write the proxies as glb files into the EM project
        (EM/proxies/<unit>.glb, or proxies/ beside the em.json), with their
        checksum in the graph and a dtcstamp beside each, so the graph can
        name them outside Blender"""

        bl_idname = "em.proxies_write_files"
        bl_label = "Write proxy files…"
        bl_options = {"REGISTER"}

        which: bpy.props.EnumProperty(  # type: ignore
            name="Which", default="ALL",
            items=[("SELECTED", "The selected proxies", ""),
                   ("ALL", "Every proxy of the graph", "")])

        @classmethod
        def poll(cls, context):
            return context.scene.em_tools.active_file_index >= 0

        def invoke(self, context, event):
            graph = _graph(context)
            if graph is None:
                self.report({"ERROR"}, "no graph loaded")
                return {"CANCELLED"}
            self.which = ("SELECTED" if proxy_targets(context, graph, selected_only=True)
                          else "ALL")
            return context.window_manager.invoke_props_dialog(
                self, width=460, title="Write proxy files", confirm_text="Write")

        def draw(self, context):
            col = self.layout.column()
            graph = _graph(context)
            col.row().prop(self, "which", expand=True)
            n = len(proxy_targets(context, graph, selected_only=self.which == "SELECTED")) \
                if graph is not None else 0
            col.label(text=f"{n} proxy file(s)", icon="MESH_CUBE")
            where = folders_here(context)
            if where is None:
                col.label(text=NEED_A_PLACE, icon="ERROR")
                return
            col.label(text=f"Into {where['proxies']}", icon="FILE_FOLDER")
            col.label(text="A file there already is replaced; its stamp keeps "
                           "the previous one", icon="INFO")

        def execute(self, context):
            graph = _graph(context)
            if graph is None:
                self.report({"ERROR"}, "no graph loaded")
                return {"CANCELLED"}
            targets = proxy_targets(context, graph,
                                    selected_only=self.which == "SELECTED")
            if not targets:
                self.report({"WARNING"}, "no proxy of this graph in the scene")
                return {"CANCELLED"}
            try:
                out = write_proxies(context, graph, targets)
            except RuntimeError as exc:
                self.report({"ERROR"}, str(exc))
                return {"CANCELLED"}
            for f in out["failed"][:4]:
                self.report({"WARNING"}, f"not written: {f}")
            if out["stamp_note"]:
                self.report({"WARNING"}, f"stamp: {out['stamp_note']}")
            self.report({"INFO"}, f"{len(out['written'])} proxy file(s) in "
                                  f"{out['folder']} · {len(out['revised'])} revised, "
                                  f"{len(out['unchanged'])} unchanged · "
                                  f"{out['stamped']} stamped · save the graph")
            return {"FINISHED"}

    class EM_OT_container_write_models(bpy.types.Operator):
        """Write the models of this container into the project
        (RM/<container>/): «Export a version for a use…» on its meshes, with
        the project's RM folder as destination"""

        bl_idname = "em.container_write_models"
        bl_label = "Write its models to the project…"
        bl_options = {"REGISTER"}

        container_index: bpy.props.IntProperty(default=-1)  # type: ignore

        def invoke(self, context, event):
            return self.execute(context)

        def execute(self, context):
            scene = context.scene
            conts = getattr(scene, "rm_containers", ())
            idx = self.container_index if self.container_index >= 0 \
                else getattr(scene, "rm_containers_index", -1)
            if not (0 <= idx < len(conts)):
                self.report({"ERROR"}, "no container chosen")
                return {"CANCELLED"}
            if folders_here(context) is None:
                self.report({"ERROR"}, NEED_A_PLACE)
                return {"CANCELLED"}
            objs = [o for o in (bpy.data.objects.get(e.name) for e in conts[idx].mesh_names)
                    if o is not None and o.type == "MESH"]
            if not objs:
                self.report({"WARNING"}, "no mesh in this container")
                return {"CANCELLED"}
            for o in context.view_layer.objects:
                o.select_set(False)
            for o in objs:
                try:
                    o.select_set(True)
                except RuntimeError:      # not in this view layer
                    pass
            context.view_layer.objects.active = objs[0]
            return bpy.ops.em.asset_prepare_for_use("INVOKE_DEFAULT", destination="PROJECT")

    return (EM_OT_proxies_write_files, EM_OT_container_write_models)


def draw_container_files(layout, context, container) -> None:  # pragma: no cover — bpy
    """The row in RM Manager's container box: write its models to the
    project, and where they go."""
    row = layout.row(align=True)
    op = row.operator("em.container_write_models", icon="EXPORT")
    op.container_index = getattr(context.scene, "rm_containers_index", -1)
    where = folders_here(context)
    sub = layout.row()
    sub.scale_y = 0.8
    if where is None:
        sub.label(text="Save the graph as em.json to give its models a folder",
                  icon="INFO")
    else:
        folder = model_folder(where["models"], container.label or container.doc_name)
        sub.label(text=f"→ {relative_url(where['base'], folder)}/", icon="FILE_FOLDER")


_CLASSES: tuple = ()


def register():  # pragma: no cover — bpy
    bpy = _bpy()
    global _CLASSES
    _CLASSES = _operator_classes()
    for cls in _CLASSES:
        bpy.utils.register_class(cls)


def unregister():  # pragma: no cover — bpy
    bpy = _bpy()
    for cls in reversed(_CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:  # noqa: BLE001
            pass
