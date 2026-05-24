# export_manager/providers/rdf/ui.py
"""Draw function for the 'RDF Export' section of the Export Manager panel."""


def poll(context):
    # Available in both basic and advanced modes — RDF is core deliverable
    return True


def draw(box, context):
    scene = context.scene

    # ── Format + path ─────────────────────────────────────────────────────
    row = box.row()
    row.prop(scene, "rdf_format", text="Format")

    row = box.row()
    row.prop(scene, "rdf_export_path", text="Output Path")

    # ── Base URI ──────────────────────────────────────────────────────────
    row = box.row()
    row.prop(scene, "rdf_base_uri", text="Base URI")

    info = box.box()
    info.scale_y = 0.7
    info.label(text="Base URI is the prefix for minted IRIs:", icon='INFO')
    info.label(text="  <base>/graph/<id>/node/<node_id>")
    info.label(text="  Local test: any value works (e.g. urn:em:)")
    info.label(text="  LOD publishing: use your resolvable domain")

    # ── Graph scope ───────────────────────────────────────────────────────
    row = box.row()
    row.prop(scene, "rdf_export_all_graphs", text="Export all publishable graphs")
    if not scene.rdf_export_all_graphs:
        box.label(text="Only the currently active GraphML will be exported", icon='INFO')

    # ── Advanced (parent HDT) ─────────────────────────────────────────────
    row = box.row()
    row.prop(
        scene, "rdf_export_advanced",
        text="Advanced RDF options",
        icon='TRIA_DOWN' if scene.rdf_export_advanced else 'TRIA_RIGHT',
        emboss=False,
    )

    if scene.rdf_export_advanced:
        adv = box.box()
        adv.label(text="HDT-O integration:", icon='LINKED')
        adv.prop(scene, "rdf_parent_hdt_iri", text="Parent HDT IRI")
        adv.scale_y = 0.9
        note = adv.box()
        note.scale_y = 0.7
        note.label(text="If set, every exported EMGraph (HC16) is bound to this HC2")
        note.label(text="via hdto:HP33i_is_proposition_set_of. Use when the graphs")
        note.label(text="are proposition sets of the same parent HDT (e.g. the site")
        note.label(text="HDT). Leave empty to skip — HDTNodes inside the graph still work.")

    # ── Export button ─────────────────────────────────────────────────────
    row = box.row(align=True)
    row.scale_y = 1.3
    row.operator("export.rdf", text="Export to RDF", icon='EXPORT')

    # ── Quick post-export workflow tip ────────────────────────────────────
    tip = box.box()
    tip.scale_y = 0.7
    tip.label(text="Workflow after export:", icon='QUESTION')
    tip.label(text="  1. Load .ttl into Oxigraph / GraphDB / Virtuoso")
    tip.label(text="  2. Open YasGUI or workbench → run SPARQL queries")
    tip.label(text="  3. See panel help (?) for setup instructions")
