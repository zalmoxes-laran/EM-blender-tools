"""HDT-O UI (fetta 3) — an INLINE collapsible section drawn inside the EM Data
Tree panel (em_setup/ui.py), styled like its sibling sections (Auxiliary
Resources, Utils) rather than a native child panel.

HDT-O info is PER-GRAPH: it attaches to the graph currently selected in the EM
Data Tree's multigraph list. This graph (a proposition set / Study) becomes the
pertinence of a Heritage Digital Twin (HC2), which is about a Heritage Entity
(HC1), optionally under a Project (HC13). Linking is OPTIONAL and non-blocking,
but enabling a graph for its HDT is what makes it shareable in the collaborative
cloud. All HDT-O info is graph-level metadata — never a Blender scene object.

Note: a multigraph-level HDT and HDT nesting (monument ⊂ city) are deliberately
out of scope here (future); different graphs may reference the same upstream HDT,
which the Copy-from control supports by cloning settings between graphs.

This module registers no Panel — `draw_graph_info_section` is called by the EM
Data Tree panel so HDT-O sits among the other sub-sections (before Utils).
"""

from __future__ import annotations

from . import hdto_graph


def draw_graph_info_section(layout, context) -> None:
    """Draw the collapsible 'HDT-O' section (box + TRIA header), matching the
    Utils/Auxiliary sibling style. Call from EM_SetupPanel.draw, before Utils."""
    p = getattr(context.scene, "em_graph_info", None)
    if p is None:
        return
    box = layout.box()
    header = box.row(align=True)
    header.prop(
        p, "show", text="HDT-O · Heritage Digital Twin",
        icon="TRIA_DOWN" if p.show else "TRIA_RIGHT", emboss=False)
    if not p.show:
        return
    _draw_body(box, context, p)


def _draw_body(layout, context, p) -> None:
    from ..functions import check_active_graph
    ok, graph = check_active_graph(context, show_message=False)
    if not (ok and graph is not None):
        layout.label(text="No graph selected in the list above.", icon='INFO')
        return

    gid = getattr(graph, "graph_id", "")
    gname = graph.name
    if isinstance(gname, dict):
        gname = gname.get("default") or gid
    layout.label(text=f"For graph: {gname or gid}", icon='OUTLINER_OB_GROUP_INSTANCE')
    layout.label(text="Optional — enables this graph for HDT / cloud.", icon='INFO')

    # Blocker surface: the bundled s3dgraphy may be too old for HDT-O.
    if not hdto_graph.hdto_supported():
        b = layout.box()
        b.alert = True
        b.label(text="HDT-O layer unavailable", icon='ERROR')
        b.label(text="The bundled s3dgraphy is out of date.")
        b.label(text="Activate the dev/updated s3dgraphy (./em.sh s3d),")
        b.label(text="then reopen this panel.")
        return

    # per-graph context: warn if the buffer reflects a different graph
    if p.loaded_graph_id and p.loaded_graph_id != gid:
        layout.box().label(text="Buffer is from another graph — press Load.", icon='ERROR')

    bar = layout.row(align=True)
    bar.operator("em.graph_info_refresh", text="Load", icon='FILE_REFRESH')
    bar.operator("em.graph_info_apply", text="Apply", icon='CHECKMARK')
    if p.status:
        layout.label(text=p.status, icon='INFO')

    # Copy-from another graph (multigraph reuse of the same upstream HDT)
    crow = layout.row(align=True)
    crow.prop(p, "copy_from_graph", text="")
    crow.operator("em.graph_info_copy_from", text="Copy", icon='PASTEDOWN')

    # Study (HC9)
    sbox = layout.box()
    sbox.label(text="Study (HC9)", icon='CURVE_PATH')
    sbox.prop(p, "study_title")
    sbox.prop(p, "study_authors")
    sbox.prop(p, "study_date")

    # Heritage entity (HC1) + authority
    hbox = layout.box()
    hbox.label(text="Heritage entity (HC1)", icon='WORLD')
    hbox.prop(p, "heritage_name")

    auth = hbox.box()
    auth.label(text="Authority reference")
    arow = auth.row(align=True)
    arow.prop(p, "authority_facet", text="")
    arow.prop(p, "heritage_uri", text="")
    arow.operator("em.graph_info_resolve_authority", text="", icon='VIEWZOOM')
    if p.heritage_authority_ref_json:
        auth.label(text="✓ resolved authority linked", icon='LINKED')
    for i, c in enumerate(p.candidates):
        row = auth.row(align=True)
        op = row.operator("em.graph_info_pick_authority", text="", icon='IMPORT')
        op.index = i
        row.label(text=f"{c.label}  ·  {c.authority} ({c.match}, #{c.rank})")

    hbox.prop(p, "parent_name")

    # Project (HC13)
    pbox = layout.box()
    pbox.label(text="Project (HC13)", icon='OUTLINER')
    pbox.prop(p, "project_name")

    # Reference HDT (HC2) — auto-derived, read-only
    tbox = layout.box()
    tbox.label(text="Reference HDT (HC2)", icon='LINK_BLEND')
    tbox.label(text=(p.twin_name or "— (created on Apply when a Heritage Entity is set)"))

    # ── EXTENSION POINT ────────────────────────────────────────────────
    # Future: a 2D geographic map for geonode positioning (E.D. supplies it
    # separately). DO NOT build the map here — this labelled placeholder is
    # the mounting point.
    geo = layout.box()
    geo.enabled = False
    geo.label(text="Geographic map — coming soon", icon='MOD_OCEAN')
    geo.label(text="(geonode positioning — extension point)")


# No Panel classes: HDT-O is drawn inline by the EM Data Tree panel.
def _purge_stale_panel() -> None:
    """Earlier fetta-3 iterations registered a standalone/child Panel
    'VIEW3D_PT_EM_GraphInfo'. After switching to an inline section a hot-reload
    can leave that old class registered → a DUPLICATE panel. Drop it if present.
    (A full Blender restart also clears it; this makes dev reloads clean.)"""
    import bpy
    cls = getattr(bpy.types, "VIEW3D_PT_EM_GraphInfo", None)
    if cls is not None:
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass


def register():
    _purge_stale_panel()


def unregister():
    _purge_stale_panel()
