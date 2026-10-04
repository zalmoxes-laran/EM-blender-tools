"""Save the active EM graph to a file — "Save As…", always em.json.

em.json is the canonical, FULL, lossless graph serialization (EM 1.6 native;
the live-sync format, ADR-002). G1 · the GraphML choice is gone: a GraphML is
read once (`import.em_graphml` turns it into an em.json) and nothing writes one
again (decision of E.D., 4 Oct 2026).

Layout note: EMStudio owns the 2D swimlane layout; Blender has none, so it
exports with ``layout=None``. Re-opening in EMStudio re-lays-out.
"""

from __future__ import annotations

import bpy  # type: ignore
from bpy.props import StringProperty, EnumProperty  # type: ignore
from bpy_extras.io_utils import ExportHelper  # type: ignore

from ..functions import is_graph_available, show_popup_message
from ..emjson_support import export_container_to_emjson, export_graph_to_emjson


def _save_as_origin(context, graph, out_path: str) -> str:
    """Write the active graph's origin group into `out_path` (a new file)."""
    from s3dgraphy import get_graph
    from .. import graph_origins

    em_tools = context.scene.em_tools
    rows = list(em_tools.graphml_files)
    index = em_tools.active_file_index
    gid = getattr(graph, "graph_id", None)
    if not (0 <= index < len(rows)):
        return export_container_to_emjson(out_path, active_graph_id=gid)
    origin = graph_origins.origin_of(rows[index], abspath=bpy.path.abspath)
    if origin.is_emjson:
        members = graph_origins.members_of(rows, origin, abspath=bpy.path.abspath)
        base = graph_origins.remembered(origin.path)
        return graph_origins.save_file(out_path, members, get_graph,
                                       active_graph_id=gid, base=base).path
    # a GraphML, a room's graph, a graph with no file: this graph alone
    return graph_origins.save_file(out_path, [gid], get_graph,
                                   active_graph_id=gid).path


def _rebind_origin(context, out: str) -> None:
    """After Save As, the saved graphs' origin is the new file — except a
    room's graph: the file is a copy, the room stays where it lives."""
    from .. import graph_origins

    em_tools = context.scene.em_tools
    rows = list(em_tools.graphml_files)
    index = em_tools.active_file_index
    if not (0 <= index < len(rows)):
        return
    origin = graph_origins.origin_of(rows[index], abspath=bpy.path.abspath)
    if origin.is_room:
        return
    targets = ([r for r in rows if graph_origins.origin_of(
        r, abspath=bpy.path.abspath).key == origin.key]
        if origin.is_emjson else [rows[index]])
    for entry in targets:
        entry.graphml_path = out
        if hasattr(entry, "file_format"):
            entry.file_format = "EMJSON"
        if hasattr(entry, "origin_kind"):
            entry.origin_kind = "FILE"
            entry.origin_path = out


class EM_export_saveas(bpy.types.Operator, ExportHelper):
    bl_idname = "export.em_saveas"
    bl_label = "Save As…"
    bl_description = "Save the active EM graph as an em.json (full, lossless)"

    # Single-dot filename_ext: Blender's ensure_ext splits on the last dot, so
    # ".em.json" would double to ".em.em.json". We normalise in execute.
    filename_ext = ".json"
    filter_glob: StringProperty(default="*.em.json;*.json", options={"HIDDEN"})  # type: ignore

    #: kept so scripts that pass `fmt="EMJSON"` keep working; em.json is the
    #: only format (G1)
    fmt: EnumProperty(
        name="Format",
        description="Output format",
        items=[
            ("EMJSON", "em.json (full graph)", "Canonical EM 1.6 JSON — full, lossless"),
        ],
        default="EMJSON",
    )  # type: ignore

    @classmethod
    def poll(cls, context):
        ok, _ = is_graph_available(context)
        if not ok:
            # UX3/B · vedi `EM_export_save.poll`: spento con la ragione.
            cls.poll_message_set(
                "No graph loaded — add a graph, set its Path, then Load")
        return ok

    @staticmethod
    def _normalize_ext(path: str, fmt: str) -> str:
        """Force exactly one correct extension for the chosen format."""
        root = path
        while True:
            low = root.lower()
            if low.endswith(".em.json"):
                root = root[:-8]
            elif low.endswith(".graphml"):
                root = root[:-8]
            elif low.endswith(".json"):
                root = root[:-5]
            elif low.endswith(".em"):
                root = root[:-3]
            else:
                break
        return root + ".em.json"

    def draw(self, context):
        self.layout.label(text="em.json — the full graph", icon="FILE")

    def invoke(self, context, event):
        em_tools = context.scene.em_tools
        if not self.filepath and em_tools.graphml_files and em_tools.active_file_index >= 0:
            base = em_tools.graphml_files[em_tools.active_file_index].name or "graph"
            self.filepath = f"{base}.em.json"
        return ExportHelper.invoke(self, context, event)

    def execute(self, context):
        ok, graph = is_graph_available(context)
        if not ok or graph is None:
            self.report({"ERROR"}, "No active EM graph to export")
            return {"CANCELLED"}

        out_path = self._normalize_ext(self.filepath, self.fmt)
        try:
            # M1 · the file gets the graphs of the active graph's ORIGIN —
            # its file's graphs (with that file's shelf, corpus, header and
            # the graphs not open here), not every graph of the scene: a
            # scene holding two files must not fuse them into one. A graph
            # with no file, or from a room, is written alone.
            out = _save_as_origin(context, graph, out_path)
        except Exception as exc:  # noqa: BLE001 — surface any exporter error to the UI
            self.report({"ERROR"}, f"Save failed: {exc}")
            show_popup_message(context, "Export Error", str(exc), "ERROR")
            return {"CANCELLED"}

        # Remember the em.json path on the active entry so a later "Save" writes
        # in place (em.json is the canonical file).
        _rebind_origin(context, out)

        self.report({"INFO"}, f"Saved em.json → {out}")
        return {"FINISHED"}


class EM_export_save(bpy.types.Operator):
    bl_idname = "export.em_save"
    bl_label = "Save"
    bl_description = "Save the active graph to its .em.json file in place (falls back to Save As… when there is no em.json target)"

    @classmethod
    def poll(cls, context):
        ok, _ = is_graph_available(context)
        if not ok:
            # UX3/B · il bottone era già spento (il poll lo spegneva), ma non
            # diceva PERCHÉ. `poll_message_set` è il modo di Blender per farlo
            # comparire nel tooltip del bottone spento, e in casa è già usato
            # (`stratigraphy_manager/operators.py:1386`). Spento con la
            # ragione insegna; spento muto fa sembrare l'add-on rotto.
            cls.poll_message_set(
                "No graph loaded — add a graph, set its Path, then Load")
        return ok

    def execute(self, context):
        ok, graph = is_graph_available(context)
        if not ok or graph is None:
            self.report({"ERROR"}, "No active EM graph to save")
            return {"CANCELLED"}

        # M1 · «Save» writes the ACTIVE graph's origin and nothing else: its
        # em.json with that file's own graphs; a room receives edits live and
        # has no file; a GraphML or a graph with no file goes to Save As.
        from ..em_setup.graph_tree import save_origin
        em_tools = context.scene.em_tools
        try:
            ok, message, save_as = save_origin(context, em_tools.active_file_index)
        except Exception as exc:  # noqa: BLE001
            self.report({"ERROR"}, f"Save failed: {exc}")
            show_popup_message(context, "Save Error", str(exc), "ERROR")
            return {"CANCELLED"}
        if save_as:
            return bpy.ops.export.em_saveas("INVOKE_DEFAULT")
        self.report({"INFO"} if ok else {"WARNING"}, message)
        return {"FINISHED"} if ok else {"CANCELLED"}


def register():
    bpy.utils.register_class(EM_export_saveas)
    bpy.utils.register_class(EM_export_save)


def unregister():
    bpy.utils.unregister_class(EM_export_save)
    bpy.utils.unregister_class(EM_export_saveas)
