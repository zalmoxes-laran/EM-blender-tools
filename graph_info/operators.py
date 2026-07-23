"""Operators for the Dataset / HDT-O info panel (fetta 3).

They bridge the Blender property buffer (properties.py) and the graph-level HDT-O
singletons on the active s3dgraphy graph (hdto_graph.py). The graph is the single
source of truth; changes persist through the existing emjson round-trip.
"""

from __future__ import annotations

import json

import bpy
from bpy.types import Operator

from . import hdto_graph


def _active_graph(context):
    """(ok, graph) for the active dataset, or (False, None) with a popup."""
    from ..functions import check_active_graph
    return check_active_graph(context)


def _fields_from_props(p) -> dict:
    ref = None
    if p.heritage_authority_ref_json:
        try:
            ref = json.loads(p.heritage_authority_ref_json)
        except Exception:
            ref = None
    return {
        "study_title": p.study_title,
        "study_authors": p.study_authors,
        "study_date": p.study_date,
        "heritage_name": p.heritage_name,
        "heritage_uri": p.heritage_uri,
        "heritage_authority_ref": ref,
        "parent_name": p.parent_name,
        "project_name": p.project_name,
    }


def _load_props_from_graph(p, graph) -> None:
    d = hdto_graph.read_hdto(graph)
    p.study_title = d["study_title"]
    p.study_authors = d["study_authors"]
    p.study_date = d["study_date"]
    p.heritage_name = d["heritage_name"]
    # set the hidden ref FIRST — assigning heritage_uri fires _on_uri_edit which
    # clears it, so we restore the pick right after.
    p.heritage_uri = d["heritage_uri"]
    p.heritage_authority_ref_json = (
        json.dumps(d["heritage_authority_ref"]) if d["heritage_authority_ref"] else ""
    )
    p.parent_name = d["parent_name"]
    p.project_name = d["project_name"]
    p.twin_name = d["twin_name"]
    p.twin_id = d["twin_id"]
    p.loaded_graph_id = getattr(graph, "graph_id", "") or ""


class EM_OT_graph_info_refresh(Operator):
    bl_idname = "em.graph_info_refresh"
    bl_label = "Load from graph"
    bl_description = "Load the HDT-O dataset info from the active graph"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        ok, graph = _active_graph(context)
        if not ok:
            return {'CANCELLED'}
        p = context.scene.em_graph_info
        _load_props_from_graph(p, graph)
        p.status = "Loaded from graph"
        return {'FINISHED'}


class EM_OT_graph_info_apply(Operator):
    bl_idname = "em.graph_info_apply"
    bl_label = "Apply to graph"
    bl_description = (
        "Write the HDT-O dataset info onto the active graph as gated metadata "
        "nodes/edges (idempotent — no duplicates, no scene objects)")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        ok, graph = _active_graph(context)
        if not ok:
            return {'CANCELLED'}
        if not hdto_graph.hdto_supported():
            self.report({'ERROR'},
                        "HDT-O unavailable: the active s3dgraphy is stale — re-vendor "
                        "the dev/updated s3dgraphy (see fetta3 report).")
            return {'CANCELLED'}
        p = context.scene.em_graph_info
        try:
            hdto_graph.apply_hdto(graph, _fields_from_props(p))
        except Exception as exc:  # surface to the UI, never crash the panel
            self.report({'ERROR'}, f"Apply failed: {exc}")
            return {'CANCELLED'}
        _load_props_from_graph(p, graph)  # reflect canonical state
        p.status = "Applied to graph"
        self.report({'INFO'}, "HDT-O dataset info applied")
        return {'FINISHED'}


class EM_OT_graph_info_resolve(Operator):
    bl_idname = "em.graph_info_resolve_authority"
    bl_label = "Search authority"
    bl_description = "Resolve the term against the offline authority registry (in-process)"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        p = context.scene.em_graph_info
        p.candidates.clear()
        p.candidates_index = -1
        term = (p.heritage_uri or "").strip()
        if not term or term.lower().startswith(("http://", "https://")):
            p.status = "Type a term (not a URI) to search"
            return {'CANCELLED'}
        cands = hdto_graph.resolve_authority(term, p.authority_facet)
        for c in cands:
            it = p.candidates.add()
            it.uri = str(c.get("uri", ""))
            it.authority = str(c.get("authority", ""))
            it.label = str(c.get("label", ""))
            it.rank = int(c.get("rank", 0) or 0)
            it.match = str(c.get("match", ""))
        p.status = (f"{len(cands)} candidate(s)" if cands
                    else "No matches (resolver offline or empty)")
        return {'FINISHED'}


class EM_OT_graph_info_pick(Operator):
    bl_idname = "em.graph_info_pick_authority"
    bl_label = "Use this authority"
    bl_description = "Adopt this candidate as the Heritage Entity's authority reference"
    bl_options = {'INTERNAL'}

    index: bpy.props.IntProperty()

    def execute(self, context):
        p = context.scene.em_graph_info
        if self.index < 0 or self.index >= len(p.candidates):
            return {'CANCELLED'}
        c = p.candidates[self.index]
        ref = {"uri": c.uri, "authority": c.authority, "label": c.label,
               "rank": c.rank, "match": c.match}
        # set the hidden pick, then the uri (its update clears the pick), then
        # restore — so the pick survives.
        p.heritage_uri = c.uri
        p.heritage_authority_ref_json = json.dumps(ref)
        p.candidates.clear()
        p.candidates_index = -1
        p.status = f"Picked {c.label} ({c.authority}) — press Apply to persist"
        return {'FINISHED'}


class EM_OT_graph_info_copy_from(Operator):
    bl_idname = "em.graph_info_copy_from"
    bl_label = "Copy HDT-O from graph"
    bl_description = (
        "Copy the HDT-O settings from another loaded graph into the active graph "
        "(useful when sibling graphs share the same upstream HDT). Review, then Apply.")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        ok, target = _active_graph(context)
        if not ok:
            return {'CANCELLED'}
        p = context.scene.em_graph_info
        src_id = (p.copy_from_graph or "").strip()
        if not src_id:
            self.report({'WARNING'}, "Pick a source graph to copy from")
            return {'CANCELLED'}
        if src_id == getattr(target, "graph_id", None):
            self.report({'WARNING'}, "Source and target are the same graph")
            return {'CANCELLED'}
        from s3dgraphy import get_graph
        source = get_graph(src_id)
        if source is None:
            self.report({'ERROR'}, f"Source graph '{src_id}' not loaded")
            return {'CANCELLED'}
        # clone the source's HDT-O fields into the target (new per-graph singletons
        # with the same values; shared-node identity across graphs is future work)
        src_fields = hdto_graph.read_hdto(source)
        try:
            hdto_graph.apply_hdto(target, src_fields)
        except Exception as exc:
            self.report({'ERROR'}, f"Copy failed: {exc}")
            return {'CANCELLED'}
        _load_props_from_graph(p, target)
        p.status = f"Copied HDT-O from '{src_id}'"
        self.report({'INFO'}, p.status)
        return {'FINISHED'}


classes = (
    EM_OT_graph_info_refresh,
    EM_OT_graph_info_apply,
    EM_OT_graph_info_resolve,
    EM_OT_graph_info_pick,
    EM_OT_graph_info_copy_from,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
