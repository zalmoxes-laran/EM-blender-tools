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
from ..emjson_support import import_container_from_emjson


def _record_file_origin(row, path: str) -> None:
    """M1 · this row's graph comes from this file, and «Save» goes back there."""
    if hasattr(row, "origin_kind"):
        row.origin_kind = "FILE"
        row.origin_path = path
        row.origin_room = ""
        row.origin_node = ""


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
            # Q4 · and the versions added here, counted and named
            lost = ""
            if self.file_index < len(context.scene.em_tools.graphml_files):
                from ..sync_manager.asset_versions import reload_warning
                lost = reload_warning(
                    context.scene.em_tools.graphml_files[self.file_index].name)
            return context.window_manager.invoke_confirm(
                self, event,
                title="Reload graph from disk?",
                message=(lost or
                         "Reloading replaces the in-memory graph with the file "
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

        # a slot may hold a path relative to the .blend (`//../EM/x.em.json`, the
        # way a dataset folder carries its graph beside its models): the
        # existence is asked of the absolute path, as everything below reads it
        if not path or not os.path.exists(bpy.path.abspath(path)):
            self.report({"ERROR"}, f"em.json file not found: {path}")
            return {"CANCELLED"}

        # --- import + register in the multigraph -----------------------------
        #
        # CONTAINER (2026-08-13): an em.json holds 1..N graphs plus the project
        # shelf, and a legacy single-graph file is a container-of-one. Every
        # member is registered, so opening a project puts ALL of its graphs in
        # this one Blender scene — which is what a .blend has always been able to
        # hold, arriving now from one file instead of several.
        #
        # The ACTIVE member is the one the panels populate from, because the
        # lists (units, epochs) show one graph at a time; the others are loaded
        # and reachable, exactly as they were when they came from separate files.
        #
        # M1 · the same graph cannot come from two files: the scene keeps one
        # graph per id, and the second file would replace the first one's
        # graph in memory — then «Save» writes it into the wrong file. Refused
        # before anything is loaded, naming the file it is already open from.
        from .. import graph_origins
        target_origin = graph_origins.file_origin(path, abspath=bpy.path.abspath)
        try:
            # the slot being reloaded is not «another file»: its recorded origin
            # may be where the project was before it was moved or copied (a
            # dataset folder handed on), and its own path is the one it names now
            others = [e for i, e in enumerate(em_tools.graphml_files)
                      if i != self.file_index]
            clash = graph_origins.conflicts(
                graph_origins.peek_graph_ids(bpy.path.abspath(path)),
                others, target_origin, abspath=bpy.path.abspath)
        except Exception:  # noqa: BLE001 — unreadable here, the importer says why
            clash = []
        if clash:
            gid0, where = clash[0]
            msg = (f"graph {gid0} is already open from {where.label}: the same "
                   f"graph cannot come from two files (give the copy its own "
                   f"graph id, or close the other one first)")
            self.report({"ERROR"}, msg)
            if not bpy.app.background:      # a popup has no window to open in -b
                show_popup_message(context, "Graph already open", msg, "ERROR")
            return {"CANCELLED"}

        try:
            container, warnings = import_container_from_emjson(bpy.path.abspath(path))
        except Exception as exc:  # noqa: BLE001
            self.report({"ERROR"}, f"em.json import failed: {exc}")
            show_popup_message(context, "Import Error", str(exc), "ERROR")
            return {"CANCELLED"}
        graph_origins.remember(target_origin.path, container)

        graph = container.active()
        # the row 🔄 reloads THAT row's graph, not the file's active one
        if self.file_index >= 0:
            row_gid = em_tools.graphml_files[self.file_index].name
            if row_gid in container.graphs:
                graph = container.graphs[row_gid]
        if graph is None and container.shelf is not None:
            # a shelf-only project: readable, and there is nothing to populate
            self.report({"INFO"}, "em.json holds only a shelf — loaded, nothing to draw")
            return {"FINISHED"}
        gid = getattr(graph, "graph_id", None)
        if not gid:
            self.report({"ERROR"}, "Imported graph has no graph_id")
            return {"CANCELLED"}

        # One file entry per member, so the panel lists the project's graphs the
        # way it used to list the files. (The active one is selected below.)
        for member_id in container.graph_ids():
            if member_id == gid:
                continue
            existing = next((f for f in em_tools.graphml_files if f.name == member_id), None)
            if existing is None:
                extra = em_tools.graphml_files.add()
                extra.name = member_id
                extra.graphml_path = path
                if hasattr(extra, "file_format"):
                    extra.file_format = "EMJSON"
                existing = extra
            _record_file_origin(existing, target_origin.path)

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
        _record_file_origin(entry, target_origin.path)
        # M2 · a graph from a file: its edits go to no room
        try:
            from ..sync_manager import room_session as _rs
            _rs.activate(gid)
        except Exception as exc:  # noqa: BLE001
            print(f"[em.json import] room activation skipped: {exc}")
        # G1 · the scene's reference system is the FIRST graph loaded's
        georef = getattr(scene, "em_georef", None)
        if georef is not None and hasattr(georef, "reference_graph") \
                and not georef.reference_graph:
            georef.reference_graph = gid
        if hasattr(entry, "file_format"):
            entry.file_format = "EMJSON"
        attrs = getattr(graph, "attributes", {}) or {}
        if "graph_code" in attrs:
            entry.graph_code = attrs["graph_code"]
        elif (getattr(graph, "data", None) or {}).get("graph_code"):
            # U4 · a graph made from a table carries its code in graph.data
            entry.graph_code = str(graph.data["graph_code"])
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

        # The Document Manager reads `scene.doc_list`, synced from
        # em_sources_list — the GraphML import ends the same way. Without it a
        # project opened from an em.json showed an empty Document Manager
        # (measured, MICRO-EMTOOLS-DEV26).
        try:
            from ..document_manager.data import sync_doc_list
            sync_doc_list(context.scene)
        except Exception as exc:  # noqa: BLE001
            print(f"[em.json import] WARN doc_list sync: {exc}")

        # B1 · chi aspettava un grafo dal ponte (EMStudio in Sidecar) lo riceve
        # adesso, senza doversi riconnettere.
        try:
            from ..sync_manager.operators import grafo_caricato
            grafo_caricato(context)
        except Exception as exc:  # noqa: BLE001 — il caricamento è riuscito comunque
            print(f"[em.json import] snapshot push skipped: {exc}")

        n_warn = len(warnings) if warnings else 0
        n_graphs = len(container.graph_ids())
        project = f"{n_graphs} graphs" if n_graphs > 1 else "1 graph"
        shelf_note = " + shelf" if container.shelf is not None else ""
        self.report({"INFO"},
                    f"Loaded em.json project ({project}{shelf_note}); active "
                    f"'{gid}' — {len(graph.nodes)} nodes, "
                    f"{len(graph.edges)} edges, {n_warn} warning(s)")
        return {"FINISHED"}


def register():
    bpy.utils.register_class(EM_import_emjson)


def unregister():
    bpy.utils.unregister_class(EM_import_emjson)
