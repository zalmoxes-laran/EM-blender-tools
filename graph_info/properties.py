"""PropertyGroups backing the Dataset / HDT-O info panel (fetta 3).

These are the editable UI BUFFER only — the single source of truth is the
s3dgraphy graph (see hdto_graph.apply_hdto/read_hdto). Refresh loads the buffer
from the graph; Apply writes it back. Nothing here is persisted as a Blender
scene object.
"""

from __future__ import annotations

import bpy
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    EnumProperty,
    IntProperty,
    StringProperty,
)
from bpy.types import PropertyGroup


def _on_uri_edit(self, context):
    """Editing the URI/term by hand drops any resolved-pick metadata → the value
    becomes free-text (stored later as a bare {uri})."""
    self.heritage_authority_ref_json = ""


# Kept alive at module scope: Blender enum item callbacks must not let their
# returned strings be garbage-collected (a well-known crash gotcha).
_copy_from_items_cache = [("", "— none —", "")]


def _copy_from_items(self, context):
    """Other loaded graphs the current one can copy HDT-O settings FROM. Lets a
    graph reuse the same upstream HDT / Study / Project as a sibling graph in the
    multigraph (different graphs may share the same HDT)."""
    items = [("", "— select a graph —", "Choose a graph to copy HDT-O settings from")]
    em_tools = getattr(context.scene, "em_tools", None)
    if em_tools and hasattr(em_tools, "graphml_files"):
        active = em_tools.active_file_index
        for i, gf in enumerate(em_tools.graphml_files):
            if i == active:
                continue  # can't copy from self
            items.append((gf.name, gf.name, f"Copy HDT-O settings from '{gf.name}'"))
    _copy_from_items_cache.clear()
    _copy_from_items_cache.extend(items)
    return _copy_from_items_cache


# Authority facets = the P1-D resolver enum (not an EM node/edge type list).
# Default is inferred from the field's node type: this panel's authority field
# is the HC1 Heritage Entity → WHERE. User-overridable.
_FACETS = [
    ("WHERE", "WHERE (place)", "Getty TGN, GND, Wikidata — spatial"),
    ("WHAT", "WHAT (concept)", "Getty AAT, GND, Wikidata — typological"),
    ("WHEN", "WHEN (period)", "ChronOntology, PeriodO — temporal"),
    ("WHO", "WHO (agent)", "Getty ULAN, GND, VIAF, Wikidata — actors"),
]


class EM_GraphInfoCandidate(PropertyGroup):
    """One ranked authority candidate returned by the offline resolver."""
    uri: StringProperty(name="URI")
    authority: StringProperty(name="Authority")
    label: StringProperty(name="Label")
    rank: IntProperty(name="Rank")
    match: StringProperty(name="Match")


class EM_GraphInfoProps(PropertyGroup):
    # Study (HC9)
    study_title: StringProperty(name="Title", description="Study title (HC9)")
    study_authors: StringProperty(name="Author(s)", description="e.g. Rossi, Bianchi")
    study_date: StringProperty(name="Date", description="e.g. 2026")
    # Heritage entity (HC1)
    heritage_name: StringProperty(name="Name", description="e.g. Colosseo")
    heritage_uri: StringProperty(
        name="Authority URI / term",
        description="Type a term to search an authority, or paste a URI",
        update=_on_uri_edit,
    )
    # hidden: the resolved pick (JSON of {uri,authority,label,rank,match}); empty
    # ⇒ the URI field is treated as free-text
    heritage_authority_ref_json: StringProperty(name="", options={'HIDDEN'})
    parent_name: StringProperty(
        name="Part of", description="optional parent Heritage Entity (whole), e.g. Roma")
    # Project (HC13)
    project_name: StringProperty(name="Project", description="optional project (HC13)")

    # HDT (HC2) — auto-derived twin, read-only display
    twin_name: StringProperty(name="", default="")
    twin_id: StringProperty(name="", default="")

    authority_facet: EnumProperty(
        name="Facet", items=_FACETS, default="WHERE",
        description="Authority facet to search (default WHERE for a Heritage Entity)")

    candidates: CollectionProperty(type=EM_GraphInfoCandidate)
    candidates_index: IntProperty(default=-1)
    status: StringProperty(name="", default="")

    # expand/collapse state of the inline section under the EM Data Tree
    show: BoolProperty(name="HDT-O", default=False)
    # which graph the buffer currently reflects (to warn when the UIList
    # selection moved to another graph — the info is per-graph)
    loaded_graph_id: StringProperty(name="", default="")
    # copy-from source (multigraph): another loaded graph to clone settings from
    copy_from_graph: EnumProperty(
        name="Copy from", items=_copy_from_items,
        description="Copy HDT-O settings from another loaded graph")


classes = (
    EM_GraphInfoCandidate,
    EM_GraphInfoProps,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.em_graph_info = bpy.props.PointerProperty(type=EM_GraphInfoProps)


def unregister():
    del bpy.types.Scene.em_graph_info
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
