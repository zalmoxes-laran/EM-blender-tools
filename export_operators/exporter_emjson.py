"""Save the active EM graph to a file — "Save As…" with a format choice.

  * em.json (default) — the canonical, FULL, lossless graph serialization
    (EM 1.6 native; the live-sync format, ADR-002).
  * GraphML — legacy interchange, NOT lossless (from-scratch export via
    s3dgraphy's GraphMLExporter; layout is regenerated, some EM 1.6 data has
    no yEd representation).

Layout note: EMStudio owns the 2D swimlane layout; Blender has none, so it
exports with ``layout=None``. Re-opening in EMStudio re-lays-out.
"""

from __future__ import annotations

import bpy  # type: ignore
from bpy.props import StringProperty, EnumProperty  # type: ignore
from bpy_extras.io_utils import ExportHelper  # type: ignore

from ..functions import is_graph_available, show_popup_message
from ..emjson_support import export_graph_to_emjson


class EM_export_saveas(bpy.types.Operator, ExportHelper):
    bl_idname = "export.em_saveas"
    bl_label = "Save As…"
    bl_description = "Save the active EM graph — em.json (full, lossless) or GraphML (legacy, not lossless)"

    # Single-dot filename_ext: Blender's ensure_ext splits on the last dot, so
    # ".em.json" would double to ".em.em.json". We normalise in execute.
    filename_ext = ".json"
    filter_glob: StringProperty(default="*.em.json;*.json;*.graphml", options={"HIDDEN"})  # type: ignore

    fmt: EnumProperty(
        name="Format",
        description="Output format",
        items=[
            ("EMJSON", "em.json (full graph)", "Canonical EM 1.6 JSON — full, lossless"),
            ("GRAPHML", "GraphML (not lossless)", "Legacy yEd GraphML — layout regenerated, some data lost"),
        ],
        default="EMJSON",
    )  # type: ignore

    @classmethod
    def poll(cls, context):
        ok, _ = is_graph_available(context)
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
        return root + (".em.json" if fmt == "EMJSON" else ".graphml")

    def draw(self, context):
        self.layout.prop(self, "fmt")

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
            if self.fmt == "EMJSON":
                out = export_graph_to_emjson(graph, out_path, layout=None)
            else:
                from s3dgraphy.exporter.graphml.graphml_exporter import GraphMLExporter
                GraphMLExporter(graph).export(out_path)
                out = out_path
        except Exception as exc:  # noqa: BLE001 — surface any exporter error to the UI
            self.report({"ERROR"}, f"Save failed: {exc}")
            show_popup_message(context, "Export Error", str(exc), "ERROR")
            return {"CANCELLED"}

        self.report({"INFO"}, f"Saved {self.fmt} → {out}")
        return {"FINISHED"}


def register():
    bpy.utils.register_class(EM_export_saveas)


def unregister():
    bpy.utils.unregister_class(EM_export_saveas)
