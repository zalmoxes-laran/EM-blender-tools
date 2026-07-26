"""DTC authoring UI (EMTools) — an INLINE collapsible section drawn inside the EM
Data Tree panel (em_setup/ui.py), mirroring graph_info's HDT-O section.

The DTC = digital provenance that produces documents, modelled as RESOURCES
connected by PROCESS events. Authored here as graph metadata on the active
s3dgraphy graph (in-process s3dgraphy, em.json round-trip) — DTC nodes are NEVER
Blender 3D scene objects. Registers no Panel: `draw_dtc_section` is called by the
EM Data Tree panel.
"""

from __future__ import annotations

from . import dtc_graph


def draw_dtc_section(layout, context) -> None:
    p = getattr(context.scene, "em_dtc", None)
    if p is None:
        return
    box = layout.box()
    header = box.row(align=True)
    header.prop(
        p, "show", text="DTC · Digital Twin Chain",
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

    layout.label(text="Digital provenance: Resources produced by Process events.",
                 icon='NODETREE')
    layout.label(text="Graph metadata — never a 3D scene object.", icon='INFO')

    # Blocker surface: the bundled s3dgraphy may be too old for the DTC profile.
    if not dtc_graph.dtc_supported():
        b = layout.box()
        b.alert = True
        b.label(text="DTC profile unavailable", icon='ERROR')
        b.label(text="The bundled s3dgraphy is out of date.")
        b.label(text="Activate the dev/updated s3dgraphy (./em.sh s3d),")
        b.label(text="then reopen this panel.")
        return

    # add a process
    prow = layout.row(align=True)
    prow.prop(p, "process_kind", text="")
    prow.operator("em.dtc_add_process", text="Add process", icon='ADD')

    # active process selector
    layout.prop(p, "active_process", text="")

    if p.status:
        layout.label(text=p.status, icon='INFO')

    if not p.active_process:
        layout.label(text="Add or select a process to author its chain.", icon='INFO')
        return

    # read-back: the selected process's chain
    chain = next((c for c in dtc_graph.list_processes(graph) if c["id"] == p.active_process), None)
    if chain is None:
        layout.label(text="Selected process no longer in the graph.", icon='ERROR')
        return

    def _resource_rows(parent, resources, empty):
        if not resources:
            parent.label(text=empty)
            return
        for r in resources:
            row = parent.row(align=True)
            lbl = f"{r['name']}  ·  {r['kind']}"
            if r["url"]:
                lbl += "  (file)"
            row.label(text=lbl, icon='FILE')
            rm = row.operator("em.dtc_remove_node", text="", icon='X')
            rm.node_id = r["id"]

    # INPUTS
    ibox = layout.box()
    ibox.label(text="Inputs (acquisitions)", icon='IMPORT')
    _resource_rows(ibox, chain["inputs"], "— no input resources yet")
    irow = ibox.row(align=True)
    irow.prop(p, "input_kind", text="")
    irow.prop(p, "input_url", text="")
    irow.operator("em.dtc_add_input", text="", icon='ADD')

    # OUTPUTS
    obox = layout.box()
    obox.label(text="Outputs (produced objects)", icon='EXPORT')
    _resource_rows(obox, chain["outputs"], "— no output resources yet")
    orow = obox.row(align=True)
    orow.prop(p, "output_kind", text="")
    orow.prop(p, "output_url", text="")
    orow.operator("em.dtc_add_output", text="", icon='ADD')
    obox.prop(p, "derive_output")

    # remove the whole process
    drow = layout.row()
    rm = drow.operator("em.dtc_remove_node", text="Remove process", icon='TRASH')
    rm.node_id = p.active_process

    # glyphs note (nice-to-have, not built): per-kind 2017 DTC SVGs would show here
    layout.label(text="(per-kind DTC glyphs: a later nicety)", icon='BLANK1')


# No Panel classes: DTC is drawn inline by the EM Data Tree panel.
def register():
    pass


def unregister():
    pass
