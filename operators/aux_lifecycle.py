"""Hybrid-C auxiliary-lifecycle operators (Phases 2 and 4).

Phase 2 — Orphan list UI
    An auxiliary row (DosCo folder, em_paradata.xlsx, pyArchInit DB…)
    may contain entries whose key id does not match any host node in
    the active graph. The s3dgraphy importers record them as
    ``importer.orphans`` and the EMtools adapter promotes them into
    ``graph.attributes['aux_orphans']``. These operators surface that
    data in the EM tree and offer a "Create host node" action per
    orphan.

Phase 4 — Bake button
    When the user is happy with the enrichment, a one-time bake
    promotes every ``injected_by``-tagged node / edge / attribute
    override to graph-native status (by clearing the bookkeeping
    tags) and writes the result to disk via
    ``GraphMLExporter.export(persist_auxiliary=True)``.

Helper: ``AUX_OT_revert_injector`` wraps
``s3dgraphy.transforms.revert_injector`` so the user can unregister a
single auxiliary without affecting other injectors.
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional

import bpy  # type: ignore
from bpy.props import (  # type: ignore
    StringProperty, BoolProperty, IntProperty, EnumProperty,
)


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

def _get_graph(context, graphml_name: str):
    from s3dgraphy import get_graph
    return get_graph(graphml_name)


def _active_graphml_and_graph(context):
    em_tools = context.scene.em_tools
    if em_tools.active_file_index < 0 or not em_tools.graphml_files:
        return None, None
    graphml = em_tools.graphml_files[em_tools.active_file_index]
    graph = _get_graph(context, graphml.name)
    return graphml, graph


def _injector_summary(graph) -> Dict[str, Dict[str, int]]:
    """Return ``{injector_id: {"nodes", "edges", "orphans", "overrides"}}``
    for every injector_id observed in the graph — used by the bake
    modal to tell the user what's about to be promoted.
    """
    if graph is None:
        return {}
    out: Dict[str, Dict[str, int]] = {}

    def _bump(key, field):
        out.setdefault(key, {"nodes": 0, "edges": 0, "orphans": 0,
                             "overrides": 0})
        out[key][field] += 1

    for n in graph.nodes:
        attrs = getattr(n, "attributes", None) or {}
        inj = attrs.get("injected_by")
        if inj:
            _bump(inj, "nodes")
        for _attr_name, rec in (attrs.get("_aux_overrides") or {}).items():
            rec_inj = rec.get("injector") if isinstance(rec, dict) else None
            if rec_inj:
                _bump(rec_inj, "overrides")

    for e in graph.edges:
        attrs = getattr(e, "attributes", None) or {}
        inj = attrs.get("injected_by")
        if inj:
            _bump(inj, "edges")

    attrs = getattr(graph, "attributes", None) or {}
    for entry in attrs.get("aux_orphans", []) or []:
        inj = entry.get("injector")
        if inj:
            _bump(inj, "orphans")

    return out


# Shorthand prefix → human label.
_INJECTOR_PREFIX_LABEL = {
    "DosCo:":       "DosCo",
    "emdb:":        "EM Paradata (xlsx)",
    "pyarchinit:":  "pyArchInit (db)",
    "sources_list:": "Sources List",
    "resource_folder:": "Resource Folder",
}


def _injector_label(injector_id: str) -> str:
    for pfx, lbl in _INJECTOR_PREFIX_LABEL.items():
        if injector_id.startswith(pfx):
            return f"{lbl}: {injector_id[len(pfx):]}"
    return injector_id


# ----------------------------------------------------------------------
# Public helper for ui.py
# ----------------------------------------------------------------------

def has_injected_content(graph) -> bool:
    """``True`` if the graph currently carries any Hybrid-C-tagged
    content (nodes, edges, attribute overrides, or orphan entries).
    Used by ui.py to decide whether to show the bake button.
    """
    if graph is None:
        return False
    for n in graph.nodes:
        attrs = getattr(n, "attributes", None) or {}
        if attrs.get("injected_by"):
            return True
        if attrs.get("_aux_overrides"):
            return True
    for e in graph.edges:
        attrs = getattr(e, "attributes", None) or {}
        if attrs.get("injected_by"):
            return True
    attrs = getattr(graph, "attributes", None) or {}
    if attrs.get("aux_orphans"):
        return True
    return False


def _normalize(raw_path: str) -> str:
    """Return the same absolute path that the DosCo harvester / aux
    importers pass to the s3dgraphy side. Must match the normalisation
    done in ``em_setup.resource_utils.resolve_resource_path`` so the
    injector id computed here matches the one tagged on nodes/edges
    during import.
    """
    if not raw_path:
        return ""
    absolute = bpy.path.abspath(raw_path)
    try:
        return os.path.normpath(absolute)
    except Exception:
        return absolute


def compute_injector_id_for_aux(aux_file) -> Optional[str]:
    """Return the canonical ``injector_id`` string for an auxiliary
    file property group, or ``None`` if we cannot map it yet.
    Mirrors the computation in the import adapters so the UI can match
    ``aux_file`` rows to the corresponding ``injected_by`` tags.
    """
    ft = getattr(aux_file, "file_type", "") or ""
    if ft == "dosco":
        path = _normalize(aux_file.dosco_folder or "")
        if path:
            return f"DosCo:{path}"
    elif ft == "emdb_xlsx":
        path = _normalize(aux_file.filepath or "")
        if path:
            return f"emdb:{path}"
    elif ft == "pyarchinit":
        path = _normalize(aux_file.filepath or "")
        if path:
            return f"pyarchinit:{path}"
    elif ft == "source_list":
        path = _normalize(aux_file.filepath or "")
        if path:
            return f"sources_list:{path}"
    elif ft == "resource_collection":
        path = _normalize(aux_file.resource_folder or "")
        if path:
            return f"resource_folder:{path}"
    return None


def count_attached(graph, injector_id: str) -> int:
    if graph is None or not injector_id:
        return 0
    n = 0
    for node in graph.nodes:
        attrs = getattr(node, "attributes", None) or {}
        if attrs.get("injected_by") == injector_id:
            n += 1
    return n


def iter_orphans_for(graph, injector_id: str):
    if graph is None:
        return
    attrs = getattr(graph, "attributes", None) or {}
    for entry in attrs.get("aux_orphans", []) or []:
        if entry.get("injector") == injector_id:
            yield entry


# ----------------------------------------------------------------------
# Operators
# ----------------------------------------------------------------------

# Module-level cache — Blender's EnumProperty items callback requires
# Python to retain references to returned strings or the C side reads
# freed memory and renders garbled labels (observed as "Pïß5" on macOS).
_EPOCH_ITEMS_CACHE: list = []


def _epoch_items_for_active_graph(self, context):
    """EnumProperty items callback: epochs present in the active
    graph, with a default "derive from year" sentinel. When the user
    leaves the dropdown on ``__derive__`` they MUST provide a year;
    the operator resolves the anchor epoch by looking up which epoch
    range contains that year.
    """
    global _EPOCH_ITEMS_CACHE
    items = [("__derive__", "-- derive from year --",
              "Derive the has_first_epoch anchor by looking up which "
              "EpochNode range contains the year below")]
    _graphml, graph = _active_graphml_and_graph(context)
    if graph is not None:
        for n in graph.nodes:
            if type(n).__name__ == "EpochNode":
                start = getattr(n, "start_time", None)
                end = getattr(n, "end_time", None)
                range_hint = ""
                if start is not None and end is not None:
                    range_hint = f" [{int(start)}..{int(end)}]"
                items.append((n.node_id, (n.name or n.node_id) + range_hint,
                              f"Anchor has_first_epoch to {n.name}"))
    _EPOCH_ITEMS_CACHE = items
    return items


def _resolve_epoch_from_year(graph, year: int):
    """Return the EpochNode whose ``[start_time, end_time]`` range
    contains ``year``, preferring the narrowest matching range when
    multiple epochs overlap. Returns ``None`` when no epoch covers
    the year.
    """
    if graph is None:
        return None
    best = None
    best_width = None
    for n in graph.nodes:
        if type(n).__name__ != "EpochNode":
            continue
        start = getattr(n, "start_time", None)
        end = getattr(n, "end_time", None)
        if start is None or end is None:
            continue
        if start <= year <= end:
            width = (end - start)
            if best is None or width < best_width:
                best = n
                best_width = width
    return best


class AUX_OT_create_host_for_orphan(bpy.types.Operator):
    """Create a graph-native host node (Master Document / host US) for
    an orphan auxiliary row and optionally anchor it to an epoch plus
    an absolute-time range. After creation, the orphan entry is
    dropped; the next auxiliary refresh can then attach the payload
    (e.g. DosCo URL) to the new host.

    By default the change is in-memory only. Tick "Save GraphML now"
    to persist to disk via the volatile Save (keeps the host + drops
    the DosCo enrichment layer), or run the Bake operator later to
    persist enrichment too.
    """
    bl_idname = "em.aux_create_host_for_orphan"
    bl_label = "Create host node"
    bl_description = (
        "Create a graph-native host (Master Document or US) for this "
        "orphan. Dialog asks for an epoch anchor and optional "
        "absolute-time range."
    )
    bl_options = {'REGISTER', 'UNDO'}

    # Context — passed by the caller button.
    injector_id: StringProperty()  # type: ignore
    key_id: StringProperty()  # type: ignore

    # Dialog inputs.
    new_name: StringProperty(
        name="Name",
        description="Name for the new graph-native node",
    )  # type: ignore

    new_description: StringProperty(
        name="Description",
        description=(
            "Free-text description for the new graph-native node. "
            "Leave empty to use an auto-generated default mentioning "
            "the auxiliary source."
        ),
        default="",
    )  # type: ignore

    epoch_id: EnumProperty(
        name="Anchor epoch",
        description=(
            "Epoch this host first appears in. Creates a "
            "has_first_epoch edge. Leave on 'derive from year' to "
            "let the operator pick the epoch whose range contains "
            "the provided year."
        ),
        items=_epoch_items_for_active_graph,
    )  # type: ignore

    creation_year: IntProperty(
        name="Creation year",
        description=(
            "Dating of this document (year; negative = BCE). Used to "
            "derive the anchor epoch when 'Anchor epoch' is left on "
            "'derive from year'. Stored as an absolute_time_start "
            "PropertyNode."
        ),
        default=0,
    )  # type: ignore

    has_creation_year: BoolProperty(
        name="Provide creation year",
        description=(
            "Tick to record a creation year for this Master Document. "
            "Required if 'Anchor epoch' is left on 'derive from year'."
        ),
        default=False,
    )  # type: ignore

    persist_after_create: BoolProperty(
        name="Persist to GraphML after creation",
        description=(
            "Preference: after the host is created, also run a "
            "volatile Save GraphML so the new node survives Blender "
            "close / graph reload. Leave unticked to review the "
            "change in memory and save later."
        ),
        default=False,
    )  # type: ignore

    doc_role: EnumProperty(
        name="Document role",
        description=(
            "Axis 1 of the three-axis Master-Document classification "
            "(EM 1.6): how this document participates in the "
            "reconstructive reasoning. 'analytical' = primary source "
            "about this context; 'comparative' = external reference / "
            "analogy from other sites, epochs, typologies."
        ),
        items=[
            ("analytical", "Analytical",
             "Primary source for direct reasoning about this context"),
            ("comparative", "Comparative",
             "External reference / analogy from other contexts"),
        ],
        default="analytical",
    )  # type: ignore

    doc_content_nature: EnumProperty(
        name="Content nature",
        description=(
            "Axis 2 of the three-axis Master-Document classification "
            "(EM 1.6): the intrinsic nature of the document's content."
        ),
        items=[
            ("2d_object", "2D Object",
             "Image, drawing, photograph, text"),
            ("3d_object", "3D Object",
             "Three-dimensional model (mesh, laser scan, "
             "photogrammetric model)"),
        ],
        default="2d_object",
    )  # type: ignore

    doc_geometry: EnumProperty(
        name="Geometry (RM spatialization)",
        description=(
            "Axis 3 of the three-axis Master-Document classification "
            "(EM 1.6): how the document's Representation Model is "
            "spatialized in the 3D scene. Choose 'No 3D spatialization' "
            "for documents without an RM (PDF articles, bibliographies) "
            "— no geometry node is created."
        ),
        items=[
            ("none", "No 3D spatialization",
             "The document has no RM — no geometry node is created "
             "in the graph (e.g. PDF article, bibliography)"),
            ("reality_based", "Reality-based (red)",
             "Robust sensor / algorithmic positioning: photogrammetric "
             "model, calibrated photo, instrumentally-surveyed find"),
            ("observable", "Observable (orange)",
             "Reconstructed with approximation from rigorous "
             "archaeological documentation (plans, sections)"),
            ("asserted", "Asserted (yellow)",
             "Compositional positioning asserted by the operator, "
             "without claim of restitution"),
            ("em_based", "EM-based reconstruction (blue)",
             "3D reconstruction produced via the Extended Matrix "
             "methodology — typically a hypothesis model from "
             "another EM graph"),
        ],
        default="none",
    )  # type: ignore

    def invoke(self, context, event):
        # Always reset the name and description to defaults for the
        # current orphan. Blender persists operator property values
        # across invocations in the same session — without this reset,
        # opening the dialog for the next orphan would pre-fill it with
        # the previous entry.
        if self.key_id:
            self.new_name = self.key_id
        self.new_description = ""
        return context.window_manager.invoke_props_dialog(self, width=440)

    def draw(self, context):
        layout = self.layout
        kind = (self.injector_id or "").split(":", 1)[0]
        is_document_kind = kind in ("DosCo", "sources_list")
        host_kind_label = "DocumentNode (Master)" if is_document_kind \
            else "StratigraphicUnit"

        layout.label(
            text=f"Orphan: {self.key_id}   ->   {host_kind_label}",
            icon='INFO')
        layout.separator()
        layout.prop(self, "new_name")
        layout.prop(self, "new_description")

        # Epoch + year — the two anchor paths. User must provide one.
        anchor_box = layout.box()
        anchor_box.label(text="Temporal anchor (required):",
                         icon='TIME')
        anchor_box.prop(self, "epoch_id", text="Epoch")
        row = anchor_box.row(align=True)
        row.prop(self, "has_creation_year", text="Year")
        sub = row.row(align=True)
        sub.enabled = self.has_creation_year
        sub.prop(self, "creation_year", text="")

        if self.epoch_id == "__derive__" and not self.has_creation_year:
            warn = anchor_box.row()
            warn.alert = True
            warn.label(
                text="Choose an epoch OR tick Year with a date",
                icon='ERROR')
        elif self.epoch_id == "__derive__" and self.has_creation_year:
            resolved = _resolve_epoch_from_year(
                _active_graphml_and_graph(context)[1],
                self.creation_year)
            hint = anchor_box.row()
            if resolved is None:
                hint.alert = True
                hint.label(
                    text=f"No epoch covers year {self.creation_year}",
                    icon='ERROR')
            else:
                hint.label(
                    text=f"Will anchor to {resolved.name}",
                    icon='CHECKMARK')

        # Master Document classification — three orthogonal axes (EM 1.6).
        if is_document_kind:
            cls_box = layout.box()
            cls_box.label(text="Master Document classification:",
                          icon='OUTLINER_DATA_LATTICE')
            cls_box.prop(self, "doc_role", text="Role")
            cls_box.prop(self, "doc_content_nature", text="Content")
            cls_box.prop(self, "doc_geometry", text="Geometry")
            hint = cls_box.row()
            color_hint = {
                "none":          "no RM -> no geometry node",
                "reality_based": "border red",
                "observable":    "border orange",
                "asserted":      "border yellow",
                "em_based":      "border blue",
            }.get(self.doc_geometry, "--")
            hint.label(text=color_hint, icon='CHECKMARK')

        # Persistence preference — boxed to distinguish from actions.
        persist_box = layout.box()
        persist_box.label(text="Persistence preference:",
                          icon='PREFERENCES')
        persist_box.prop(self, "persist_after_create")
        note = persist_box.row()
        if self.persist_after_create:
            note.label(
                text="Host will be written to the .graphml file "
                     "after creation (volatile save).",
                icon='FILE_TICK')
        else:
            note.label(
                text="In-memory only — lost on reload or Blender close.",
                icon='MEMORY')

    def execute(self, context):
        graphml, graph = _active_graphml_and_graph(context)
        if graph is None:
            self.report({'ERROR'}, "No active graph")
            return {'CANCELLED'}
        if not self.injector_id or not self.key_id:
            self.report({'ERROR'}, "Missing injector_id/key_id")
            return {'CANCELLED'}
        name = (self.new_name or self.key_id or "").strip()
        if not name:
            self.report({'ERROR'}, "Name is required")
            return {'CANCELLED'}

        # Resolve the anchor epoch: explicit pick wins; otherwise
        # derive from the creation year.
        resolved_epoch = None
        if self.epoch_id and self.epoch_id != "__derive__":
            resolved_epoch = next(
                (n for n in graph.nodes if n.node_id == self.epoch_id),
                None)
        elif self.has_creation_year:
            resolved_epoch = _resolve_epoch_from_year(
                graph, self.creation_year)
            if resolved_epoch is None:
                self.report({'ERROR'},
                            f"No epoch range contains year "
                            f"{self.creation_year}. Pick an epoch "
                            f"explicitly or adjust the year.")
                return {'CANCELLED'}

        if resolved_epoch is None:
            self.report({'ERROR'},
                        "Temporal anchor required: pick an epoch "
                        "or tick Year with a valid date.")
            return {'CANCELLED'}

        kind = self.injector_id.split(":", 1)[0]
        is_document_kind = kind in ("DosCo", "sources_list")
        desc = (self.new_description or "").strip()

        if is_document_kind:
            # Delegate to the shared helper — keeps the DocumentNode
            # shape (attributes + has_first_epoch + absolute_time_start
            # chain) consistent with the Document Manager's standalone
            # Create-Master-Document flow and the RM Manager container
            # creation flow.
            from ..master_document_helpers import create_master_document_node
            _role = self.doc_role
            _nature = self.doc_content_nature
            _geom = (self.doc_geometry
                     if self.doc_geometry != "none" else None)
            node = create_master_document_node(
                graph,
                name=name,
                description=desc or (f"Master Document created from "
                                     f"{kind} orphan ({self.key_id})"),
                resolved_epoch=resolved_epoch,
                creation_year=(self.creation_year
                               if self.has_creation_year else None),
                role=_role,
                content_nature=_nature,
                geometry=_geom,
                mark_as_master=True,
            )
        elif kind in ("emdb", "pyarchinit"):
            from s3dgraphy.exporter.graphml.utils import generate_uuid
            from s3dgraphy.nodes.stratigraphic_node import StratigraphicUnit
            node = StratigraphicUnit(
                node_id=generate_uuid(),
                name=name,
                description=desc or (f"Host created from {kind} orphan "
                                     f"({self.key_id})"),
            )
            graph.add_node(node)
            graph.add_edge(
                edge_id=(f"{node.node_id}_has_first_epoch_"
                         f"{resolved_epoch.node_id}"),
                edge_source=node.node_id,
                edge_target=resolved_epoch.node_id,
                edge_type="has_first_epoch",
            )
        else:
            self.report({'ERROR'},
                        f"Don't know how to create a host for {kind!r}")
            return {'CANCELLED'}

        # Drop the matching orphan entry.
        attrs = getattr(graph, "attributes", None) or {}
        all_orphans = attrs.get("aux_orphans", []) or []
        cleaned = [
            e for e in all_orphans
            if not (e.get("injector") == self.injector_id
                    and e.get("key_id") == self.key_id)
        ]
        graph.attributes["aux_orphans"] = cleaned

        # Refresh EMTools UI lists so the new host shows up in the
        # Document Manager / EM tree immediately, without requiring a
        # graphml reload.
        if is_document_kind:
            from ..master_document_helpers import refresh_document_lists
            refresh_document_lists(context, node, graph)

        # Optional: persist to disk via volatile Save.
        persisted = False
        if self.persist_after_create:
            try:
                result = bpy.ops.export.graphml_update()
                persisted = 'FINISHED' in result
            except Exception as e:
                self.report({'WARNING'},
                            f"Host created but persist failed: {e}")

        msg_tail = f" @ {resolved_epoch.name}"
        if self.has_creation_year:
            msg_tail += f" ({self.creation_year})"
        if persisted:
            msg_tail += " [persisted]"
        self.report({'INFO'},
                    f"Created {type(node).__name__} {name!r}{msg_tail}")
        for area in context.screen.areas:
            area.tag_redraw()
        return {'FINISHED'}


class AUX_OT_revert_injector(bpy.types.Operator):
    """Unregister a single auxiliary: remove its injected nodes/edges,
    revert its attribute overrides per the volatile policy, clear its
    orphan entries. Other auxiliaries are untouched.
    """
    bl_idname = "em.aux_revert_injector"
    bl_label = "Revert this auxiliary"
    bl_description = (
        "Remove everything this auxiliary injected (nodes, edges, "
        "attribute overrides, orphan entries). Other auxiliaries are "
        "untouched. The auxiliary file on disk is NOT modified."
    )
    bl_options = {'REGISTER', 'UNDO'}

    injector_id: StringProperty()  # type: ignore

    def execute(self, context):
        graphml, graph = _active_graphml_and_graph(context)
        if graph is None:
            self.report({'ERROR'}, "No active graph")
            return {'CANCELLED'}
        if not self.injector_id:
            self.report({'ERROR'}, "Missing injector_id")
            return {'CANCELLED'}
        try:
            from s3dgraphy.transforms import revert_injector
        except ImportError:
            self.report({'ERROR'}, "aux_tracking not available")
            return {'CANCELLED'}

        report = revert_injector(graph, self.injector_id)
        self.report({'INFO'},
                    f"Reverted {self.injector_id}: "
                    f"-{report['nodes']} nodes, -{report['edges']} edges, "
                    f"{report['reverted']} reverted attrs, "
                    f"{report['kept']} kept, "
                    f"{report['orphans_cleared']} orphans cleared")
        for area in context.screen.areas:
            area.tag_redraw()
        return {'FINISHED'}


class AUX_OT_bake_to_graphml(bpy.types.Operator):
    """Write the auxiliary enrichment layer to disk as graph-native.

    Opens a confirmation dialog summarising, per injector, how many
    nodes / edges / attribute overrides / orphans will be promoted or
    dropped. On confirm, calls
    :meth:`s3dgraphy.GraphMLExporter.export(persist_auxiliary=True)`
    which clears the ``injected_by`` / ``_aux_overrides`` bookkeeping
    and writes a fully graph-native GraphML file.

    After bake, the auxiliaries can be unregistered without losing
    their enrichment. This is a **one-way** operation: future edits
    to the auxiliary file on disk will no longer affect the baked
    content.
    """
    bl_idname = "em.aux_bake_to_graphml"
    bl_label = "Bake auxiliary → GraphML"
    bl_description = (
        "Promote the auxiliary enrichment to graph-native and save "
        "the GraphML. One-way operation."
    )
    bl_options = {'REGISTER'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=520)

    def draw(self, context):
        layout = self.layout
        _graphml, graph = _active_graphml_and_graph(context)
        summary = _injector_summary(graph)
        if not summary:
            layout.label(
                text="No auxiliary-injected content found. Bake is a no-op.",
                icon='INFO')
            return
        layout.label(
            text="The following enrichment will be promoted to "
                 "graph-native:", icon='INFO')
        for injector_id, stats in sorted(summary.items()):
            box = layout.box()
            box.label(text=_injector_label(injector_id), icon='FILE_TICK')
            box.label(
                text=f"  +{stats['nodes']} nodes, +{stats['edges']} edges, "
                     f"{stats['overrides']} attribute overrides frozen, "
                     f"{stats['orphans']} orphans dropped"
            )
        layout.separator()
        layout.label(
            text="After bake, these items become part of the GraphML "
                 "file and survive unregistering the auxiliary.",
            icon='CHECKMARK')
        layout.label(
            text="This is a one-way operation — re-editing the "
                 "auxiliary on disk will NOT refresh the baked copy.",
            icon='ERROR')

    def execute(self, context):
        graphml, graph = _active_graphml_and_graph(context)
        if graph is None or graphml is None:
            self.report({'ERROR'}, "No active graph / GraphML")
            return {'CANCELLED'}
        graphml_path = bpy.path.abspath(graphml.graphml_path or "")
        if not graphml_path:
            self.report({'ERROR'}, "Active GraphML has no path")
            return {'CANCELLED'}
        # Write-lock pre-flight — Bake overwrites the .graphml on disk.
        from ..graphml_lock import abort_if_graphml_locked
        if not abort_if_graphml_locked(self, graphml_path):
            return {'CANCELLED'}
        try:
            from s3dgraphy.exporter.graphml import GraphMLExporter
        except ImportError as e:
            self.report({'ERROR'}, f"s3dgraphy unavailable: {e}")
            return {'CANCELLED'}

        try:
            exporter = GraphMLExporter(graph)
            exporter.export(graphml_path, persist_auxiliary=True)
        except Exception as e:
            self.report({'ERROR'}, f"Bake failed: {e}")
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}

        self.report({'INFO'},
                    f"Baked auxiliaries into {os.path.basename(graphml_path)}")
        for area in context.screen.areas:
            area.tag_redraw()
        return {'FINISHED'}


# ----------------------------------------------------------------------
# Registration
# ----------------------------------------------------------------------

classes = (
    AUX_OT_create_host_for_orphan,
    AUX_OT_revert_injector,
    AUX_OT_bake_to_graphml,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
