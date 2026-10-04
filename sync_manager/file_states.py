"""R1/R2 · where the files of the active graph are, said with ONE resolver.

EMtools does not resolve a file by itself any more: it asks s3dgraphy
(``api.resolve_files``) with what it knows — the project's standard tree (C1,
found from the em.json or the .blend), the DosCo folder, the folders of the
graph and of the .blend, the cache beside the .blend, and the room's HEAD when
this graph is in a room — and shows the STATE with the sign of the common list
(``state_symbols``). EMStudio (through its bridge) and StratiField ask the same
function, so the same files give the same state in the three.

The gestures on a file are here too: «Find here…» relinks a missing one,
«Upload to the room» sends one that is on the disk, «Open where it is» shows
it in the file manager. The resolution is run by a gesture («Check files»),
not at every redraw: it touches the disk and, in a room, the node.
"""

import os
from typing import Any, Callable, Dict, List, Optional

#: the last resolution of the active graph, for the panel (session state)
ULTIMI: Dict[str, Any] = {"graph_id": "", "results": [], "filter": ""}


def project_root(context) -> Optional[str]:  # pragma: no cover — bpy
    """The EM project of the active graph: from its em.json/GraphML, else from
    the .blend."""
    import bpy  # type: ignore
    from s3dgraphy.project_tree import find_project_root
    from .bring import _active_entry
    entry = _active_entry(context)
    for raw in (getattr(entry, "graphml_path", "") if entry is not None else "",
                bpy.data.filepath):
        if raw:
            root = find_project_root(bpy.path.abspath(raw))
            if root:
                return root
    return None


def node_probe() -> Optional[Callable[[str], bool]]:  # pragma: no cover — network
    """``on_node(hex)`` for the room this Blender is in, or None outside a room."""
    from . import room as room_cfg
    from .asset_upload import has_asset
    where = room_cfg.room()
    if not (where.get("base_url") and where.get("room_id") and where.get("has_token")):
        return None
    token = room_cfg._session.get("token")

    def on_node(hexd: str) -> bool:
        return has_asset(where["base_url"], where["room_id"], hexd, token, timeout=10)
    return on_node


def resolve_active(context, graph) -> List[Dict[str, Any]]:  # pragma: no cover — bpy
    """The state of every resource of ``graph``, remembered for the panel."""
    from s3dgraphy import api
    from .asset_upload import sha256_of_file
    from .asset_versions import CACHE_DIR, cache_folder
    from .bring import base_dirs
    cache = os.path.join(cache_folder(), CACHE_DIR)
    results = api.resolve_files(graph, project_root=project_root(context),
                                base_dirs=base_dirs(context),
                                cache_dirs=[cache] if os.path.isdir(cache) else [],
                                on_node=node_probe(), hasher=sha256_of_file)
    ULTIMI.update({"graph_id": str(getattr(graph, "graph_id", "")),
                   "results": results})
    return results


def counts(results: List[Dict[str, Any]]) -> Dict[str, int]:
    from s3dgraphy.resources.locate import summary
    return summary(results)


def sentence(results: List[Dict[str, Any]]) -> str:
    """One line for the scene check: how many files in each state."""
    from ..state_symbols import sign
    c = counts(results)
    parts = [f"{sign('file.' + k)[1].split(' ', 1)[0]} {n} {k.replace('_', ' ')}"
             for k, n in c.items() if n]
    return "Files: " + (", ".join(parts) if parts else "none in the graph")


def relink(graph, resource_id: str, path: str) -> None:  # pragma: no cover — bpy
    """«Find here…»: the resource now points at ``path`` (a new locator, the
    digest written if the graph had none). The node keeps its id."""
    from s3dgraphy import api
    from .asset_upload import sha256_of_file
    node = graph.find_node_by_id(resource_id)
    if node is None:
        raise ValueError(f"no resource {resource_id}")
    api.set_field(node, "data.url", path)
    if not (node.data or {}).get("checksum") and os.path.isfile(path):
        api.set_field(node, "data.checksum", "sha256:" + sha256_of_file(path))


def _operator_classes():  # pragma: no cover — bpy
    import bpy  # type: ignore

    def _graph(context):
        from ..functions import is_graph_available
        ok, graph = is_graph_available(context)
        return graph if ok else None

    class EM_OT_files_check(bpy.types.Operator):
        """Say where each file of the graph is: on the disk, on the node, both,
        only a reference, missing, an empty copy (one resolver for every tool)"""
        bl_idname = "em.files_check"
        bl_label = "Check files"

        def execute(self, context):
            graph = _graph(context)
            if graph is None:
                self.report({"ERROR"}, "no graph loaded")
                return {"CANCELLED"}
            results = resolve_active(context, graph)
            self.report({"INFO"}, sentence(results))
            return {"FINISHED"}

    class EM_OT_files_filter(bpy.types.Operator):
        """Show only the files in this state (again: all)"""
        bl_idname = "em.files_filter"
        bl_label = "Filter files"
        state: bpy.props.StringProperty()  # type: ignore

        def execute(self, context):
            ULTIMI["filter"] = "" if ULTIMI.get("filter") == self.state else self.state
            return {"FINISHED"}

    class EM_OT_files_find_here(bpy.types.Operator):
        """Find here…: point a missing file at where it is on this computer"""
        bl_idname = "em.files_find_here"
        bl_label = "Find here…"
        resource_id: bpy.props.StringProperty()  # type: ignore
        filepath: bpy.props.StringProperty(subtype="FILE_PATH")  # type: ignore

        def invoke(self, context, event):
            context.window_manager.fileselect_add(self)
            return {"RUNNING_MODAL"}

        def execute(self, context):
            graph = _graph(context)
            if graph is None or not self.filepath:
                return {"CANCELLED"}
            relink(graph, self.resource_id, bpy.path.abspath(self.filepath))
            resolve_active(context, graph)
            return {"FINISHED"}

    class EM_OT_files_upload(bpy.types.Operator):
        """Upload to the room: send this file's bytes to the room's store"""
        bl_idname = "em.files_upload"
        bl_label = "Upload to the room"
        resource_id: bpy.props.StringProperty()  # type: ignore

        def execute(self, context):
            from . import room as room_cfg
            from .asset_upload import upload_asset
            graph = _graph(context)
            row = next((r for r in ULTIMI["results"] if r["id"] == self.resource_id), None)
            where = room_cfg.room()
            if graph is None or row is None or not row.get("path"):
                self.report({"ERROR"}, "nothing on the disk to upload")
                return {"CANCELLED"}
            if not where.get("room_id"):
                self.report({"ERROR"}, "not in a room: «Bring into a room» first")
                return {"CANCELLED"}
            try:
                out = upload_asset(where["base_url"], where["room_id"], row["path"],
                                   row.get("sha256") or None, "",
                                   room_cfg._session.get("token"))
            except Exception as exc:  # noqa: BLE001 — the reason is the user's
                self.report({"ERROR"}, f"upload failed: {exc}")
                return {"CANCELLED"}
            self.report({"INFO"}, "already in the room" if out.get("already")
                        else f"uploaded {os.path.basename(row['path'])}")
            resolve_active(context, graph)
            return {"FINISHED"}

    class EM_OT_files_open_where(bpy.types.Operator):
        """Open where it is: the folder of this file"""
        bl_idname = "em.files_open_where"
        bl_label = "Open where it is"
        path: bpy.props.StringProperty()  # type: ignore

        def execute(self, context):
            folder = self.path if os.path.isdir(self.path) else os.path.dirname(self.path)
            bpy.ops.wm.path_open(filepath=folder)
            return {"FINISHED"}

    class EM_OT_new_em_project(bpy.types.Operator):
        """New EM project…: the standard tree (EM/ with DosCo/ and proxies/, RB/,
        SB/, RM/, README.md, LICENCE.md) in a new folder"""
        bl_idname = "em.new_em_project"
        bl_label = "New EM project…"
        directory: bpy.props.StringProperty(subtype="DIR_PATH")  # type: ignore
        name: bpy.props.StringProperty(name="Name", default="New EM project")  # type: ignore

        def invoke(self, context, event):
            context.window_manager.fileselect_add(self)
            return {"RUNNING_MODAL"}

        def execute(self, context):
            from s3dgraphy import api
            try:
                out = api.create_em_project(bpy.path.abspath(self.directory), self.name)
            except FileExistsError as exc:
                self.report({"ERROR"}, str(exc))
                return {"CANCELLED"}
            self.report({"INFO"}, f"{out['root']}: made {', '.join(out['made'])}")
            return {"FINISHED"}

    class EM_OT_reorder_em_project(bpy.types.Operator):
        """Reorder by the EM standard…: a PREVIEW of what would move into the
        standard tree; nothing moves without your yes, nothing is overwritten"""
        bl_idname = "em.reorder_em_project"
        bl_label = "Reorder by the EM standard…"
        directory: bpy.props.StringProperty(subtype="DIR_PATH")  # type: ignore

        def invoke(self, context, event):
            root = project_root(context) or (os.path.dirname(bpy.data.filepath)
                                             if bpy.data.filepath else "")
            self.directory = root
            PREVIEW["plan"] = []
            if root:
                from s3dgraphy import api
                PREVIEW["plan"] = api.em_project_reorder_plan(root)
            return context.window_manager.invoke_props_dialog(self, width=520)

        def draw(self, context):
            col = self.layout.column()
            col.label(text=f"Project: {self.directory or '—'}", icon="FILE_FOLDER")
            plan = PREVIEW.get("plan") or []
            if not plan:
                col.label(text="Already in the standard tree: nothing to do.", icon="CHECKMARK")
            for step in plan[:24]:
                col.label(text=(f"make {step['to']}/" if step["action"] == "mkdir"
                                else f"{step['from']} → {step['to']}"),
                          icon="NEWFOLDER" if step["action"] == "mkdir" else "FORWARD")
            col.label(text="OK moves these; nothing is overwritten.", icon="INFO")

        def execute(self, context):
            from s3dgraphy.project_tree import apply_plan
            plan = PREVIEW.get("plan") or []
            if not plan or not self.directory:
                return {"CANCELLED"}
            done = apply_plan(self.directory, plan, confirmed=True)
            self.report({"INFO"}, "; ".join(done[:6]))
            return {"FINISHED"}

    return (EM_OT_files_check, EM_OT_files_filter, EM_OT_files_find_here,
            EM_OT_files_upload, EM_OT_files_open_where, EM_OT_new_em_project,
            EM_OT_reorder_em_project)


#: the reorder's preview between invoke and the yes
PREVIEW: Dict[str, Any] = {"plan": []}


def draw(layout, context) -> None:  # pragma: no cover — bpy
    """The «Files» section: one sign per resource, a filter per state, the
    gestures on each file."""
    from ..state_symbols import sign
    proj = layout.row(align=True)
    proj.operator("em.new_em_project", icon="NEWFOLDER")
    proj.operator("em.reorder_em_project", icon="SORTALPHA")
    box = layout.box()
    head = box.row(align=True)
    head.label(text="Files", icon="FILE_FOLDER")
    head.operator("em.files_check", text="Check files", icon="FILE_REFRESH")
    results = ULTIMI.get("results") or []
    if not results:
        box.label(text="Not checked yet: «Check files» says where each one is.", icon="INFO")
        return
    c = counts(results)
    frow = box.row(align=True)
    for state, n in c.items():
        if not n:
            continue
        icon, text, _ = sign("file." + state)
        op = frow.operator("em.files_filter", text=f"{n}", icon=icon,
                           depress=ULTIMI.get("filter") == state)
        op.state = state
    chosen = ULTIMI.get("filter") or ""
    if chosen:
        box.label(text=sign("file." + chosen)[1] + " — " + sign("file." + chosen)[2],
                  icon="FILTER")
    from . import room as room_cfg
    in_room = bool(room_cfg.room().get("room_id"))
    for r in results:
        if chosen and r["state"] != chosen:
            continue
        icon, text, meaning = sign("file." + r["state"])
        row = box.row(align=True)
        row.alert = r["state"] in ("missing", "empty_copy")
        row.label(text=f"{r.get('name') or r['id'][:8]}", icon=icon)
        row.label(text=text)
        if r["state"] in ("missing", "empty_copy"):
            row.operator("em.files_find_here", text="", icon="VIEWZOOM").resource_id = r["id"]
        if r["state"] == "on_disk" and in_room:
            row.operator("em.files_upload", text="", icon="EXPORT").resource_id = r["id"]
        if r.get("path"):
            row.operator("em.files_open_where", text="", icon="FILEBROWSER").path = r["path"]


_CLASSES: tuple = ()


def register():  # pragma: no cover — bpy
    import bpy  # type: ignore
    global _CLASSES
    _CLASSES = _operator_classes()
    for cls in _CLASSES:
        bpy.utils.register_class(cls)


def unregister():  # pragma: no cover — bpy
    import bpy  # type: ignore
    for cls in reversed(_CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:  # noqa: BLE001
            pass
