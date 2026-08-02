"""Load an .em.json file (EM 1.6 native format) as an EM graph.

Mirrors the tail of ``importer_graphml.EM_import_GraphML`` (register in the
multigraph → connect paradata → populate the Blender lists → statistics), but
uses the em.json importer. NOTE: ``s3dgraphy.parse_emjson`` builds a ``Graph``
object but does NOT register it in the multigraph manager, so we register it
here explicitly (``multi_graph_manager.graphs[gid] = graph``).

em.json is the canonical live-sync format (ADR-002); GraphML stays a legacy
import path.
"""

from __future__ import annotations

import os

import bpy  # type: ignore
from bpy.props import StringProperty, IntProperty  # type: ignore
from bpy_extras.io_utils import ImportHelper  # type: ignore

from s3dgraphy import get_graph  # noqa: F401 (kept for symmetry / debugging)
from s3dgraphy.multigraph.multigraph import multi_graph_manager

from ..populate_lists import (
    clear_lists,
    populate_blender_lists_from_graph,
    update_graph_statistics,
)
from ..functions import ensure_valid_index, show_popup_message
from ..emjson_support import import_graph_from_emjson


class EM_import_emjson(bpy.types.Operator, ImportHelper):
    bl_idname = "import.em_emjson"
    bl_label = "Load em.json"
    bl_description = "Load an .em.json file as an EM graph and set it active"
    bl_options = {"REGISTER", "UNDO"}

    filename_ext = ".em.json"
    filter_glob: StringProperty(default="*.em.json;*.json", options={"HIDDEN"})  # type: ignore
    # >=0 → reload the existing entry's stored path without a file dialog
    # (per-row 🔄). <0 → open the dialog (Load graph).
    file_index: IntProperty(default=-1, options={"HIDDEN"})  # type: ignore

    def invoke(self, context, event):
        if self.file_index >= 0:
            # reloading replaces the in-memory graph with the file on disk →
            # confirm first so live-sync / unsaved edits are not lost silently.
            return context.window_manager.invoke_confirm(
                self, event,
                title="Reload graph from disk?",
                message=("Reloading replaces the in-memory graph with the file "
                         "on disk. Unsaved changes (including live-sync edits) "
                         "will be lost. Save first if you want to keep them."),
                confirm_text="Reload")
        return ImportHelper.invoke(self, context, event)

    def execute(self, context):
        scene = context.scene
        em_tools = scene.em_tools

        if self.file_index >= 0:
            if self.file_index >= len(em_tools.graphml_files):
                self.report({"ERROR"}, "Invalid graph index")
                return {"CANCELLED"}
            path = em_tools.graphml_files[self.file_index].graphml_path
        else:
            path = self.filepath

        if not path or not os.path.exists(path):
            self.report({"ERROR"}, f"em.json file not found: {path}")
            return {"CANCELLED"}

        # --- import + register in the multigraph -----------------------------
        try:
            graph, warnings = import_graph_from_emjson(path)
        except Exception as exc:  # noqa: BLE001
            self.report({"ERROR"}, f"em.json import failed: {exc}")
            show_popup_message(context, "Import Error", str(exc), "ERROR")
            return {"CANCELLED"}

        gid = getattr(graph, "graph_id", None)
        if not gid:
            self.report({"ERROR"}, "Imported graph has no graph_id")
            return {"CANCELLED"}
        # parse_emjson does NOT register the graph — do it here (overwrite).
        multi_graph_manager.graphs[gid] = graph

        # --- find/create the file entry for this graph -----------------------
        entry = None
        for i, f in enumerate(em_tools.graphml_files):
            if f.name == gid:
                entry = f
                em_tools.active_file_index = i
                break
        if entry is None:
            entry = em_tools.graphml_files.add()
            em_tools.active_file_index = len(em_tools.graphml_files) - 1
        entry.name = gid
        entry.graphml_path = path  # the generic "Path" field holds the em.json path
        if hasattr(entry, "file_format"):
            entry.file_format = "EMJSON"
        attrs = getattr(graph, "attributes", {}) or {}
        if "graph_code" in attrs:
            entry.graph_code = attrs["graph_code"]
        if hasattr(entry, "import_warnings"):
            entry.import_warnings = "\n".join(warnings) if warnings else ""
        # Structured counterpart: the panel groups by `kind` instead of matching
        # message text, and each record names the element it points at. Only the
        # state families have records; the free-form warnings stay strings and
        # the panel falls back to matching for those.
        if hasattr(entry, "import_warning_records"):
            try:
                import json as _json
                from s3dgraphy.api import graph_warnings
                entry.import_warning_records = _json.dumps(graph_warnings(graph))
            except Exception as exc:  # noqa: BLE001
                entry.import_warning_records = ""
                print(f"[em.json import] WARN warning records: {exc}")

        # S6 — version banner: what the document declares (em.json
        # schema_version, S2a) next to what is reading it (EM datamodel).
        try:
            from ..em_setup.version_banner import read_graph_versions
            _v = read_graph_versions(graph)
            entry.emjson_schema_version = _v["emjson_schema"]
            entry.em_datamodel_version = _v["em_datamodel"]
            entry.stratigraph_version = _v["stratigraph"]
        except Exception as exc:  # noqa: BLE001
            print(f"[em.json import] WARN version banner: {exc}")

        # --- common populate tail (mirrors importer_graphml) -----------------
        clear_lists(context)
        try:
            graph.connect_paradatagroup_propertynode_to_stratigraphic(verbose=False)
        except Exception as exc:  # noqa: BLE001
            print(f"[em.json import] WARN connect paradata: {exc}")

        strat = em_tools.stratigraphy
        strat.units_index = 0
        em_tools.epochs.list_index = 0

        populate_blender_lists_from_graph(context, graph)
        try:
            update_graph_statistics(context, graph, entry)
        except Exception as exc:  # noqa: BLE001
            print(f"[em.json import] WARN statistics: {exc}")

        ensure_valid_index(strat.units, "units_index", context, data_object=strat)
        ensure_valid_index(em_tools.epochs.list, "list_index", context,
                           show_popup=False, data_object=em_tools.epochs)

        n_warn = len(warnings) if warnings else 0
        self.report({"INFO"},
                    f"Loaded em.json '{gid}' — {len(graph.nodes)} nodes, "
                    f"{len(graph.edges)} edges, {n_warn} warning(s)")
        return {"FINISHED"}


def register():
    bpy.utils.register_class(EM_import_emjson)


def unregister():
    bpy.utils.unregister_class(EM_import_emjson)
