"""GUI smoke + screenshot: translations, read-only, in a real Blender (MICRO-EMTOOLS-DEV26, parte 3).

Run in a CLEAN user folder with the extension installed (see
tests/blender_smoke_dev26.py); ``--background`` runs the checks and skips the
screenshot:

    BLENDER_USER_RESOURCES=<clean> /Applications/Blender\\ 520.app/Contents/MacOS/Blender \\
        --python tests/blender_shots_translations.py -- <out_dir>

* an em.json whose document D.1 (Latin) has three translations — Italian
  (manual), English (AI, not verified), French (review asked) — opens with
  EMtools' own `import.em_emjson`, the lists populate, nothing is lost;
* `export.em_saveas` writes it back with the three translations;
* `export.rdf`: Round trip carries the English, Publish leaves it out;
* the Document Manager shows ``la · en ✦ · fr ? · it ✓`` (screenshot).
"""
import os
import sys
import tempfile

import bpy

OUT = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else tempfile.mkdtemp()
os.makedirs(OUT, exist_ok=True)
FAILURES = []


def check(label, condition, detail=""):
    print(f"[SMOKE] {'PASS' if condition else 'FAIL'}: {label} {detail}")
    if not condition:
        FAILURES.append(label)
    return condition


def snapshot(graph):
    nodes = {n.node_id: (n.node_type, n.name, n.description or "",
                         dict(sorted((getattr(n, "data", None) or {}).items())))
             for n in graph.nodes}
    edges = sorted((e.edge_source, e.edge_target, e.edge_type) for e in graph.edges)
    return nodes, edges


def run_checks():
    from s3dgraphy import api
    from s3dgraphy.exporter.emjson_exporter import export_emjson
    from s3dgraphy.graph import Graph
    from s3dgraphy.importer.emjson_importer import import_emjson
    from s3dgraphy.multigraph.multigraph import multi_graph_manager
    from s3dgraphy.nodes.author_node import AuthorAINode, AuthorNode
    from s3dgraphy.nodes.document_node import DocumentNode

    work = tempfile.mkdtemp(prefix="em_transl_")
    g = Graph("vitruvio_smoke")
    g.add_node(AuthorNode("ed", name="Emanuel", orcid="0000-0002-1825-0097", surname="D"))
    g.add_node(AuthorAINode("claude", name="Claude"))
    doc = DocumentNode("d1", "D.1", "firmitatis, utilitatis, venustatis")
    doc.data = {"lang": "la"}
    g.add_node(doc)
    api.set_working_language(g, "it")
    api.add_translation(g, "d1", "description", "it", "solidità, utilità, bellezza", by="ed")
    api.add_translation(g, "d1", "description", "en", "strength, utility, beauty",
                        by="ed", method="ai", ai="claude", model="claude-opus-5-5")
    api.add_translation(g, "d1", "description", "fr", "solidité, utilité, beauté",
                        by="ed", review=True)
    src = os.path.join(work, "vitruvio.em.json")
    export_emjson(g, src)
    before = snapshot(import_emjson(src)[0])

    result = getattr(bpy.ops, "import").em_emjson(filepath=src)  # `import` is a keyword
    check("opened with import.em_emjson", result == {'FINISHED'}, str(result))
    graph = multi_graph_manager.graphs.get("vitruvio_smoke")
    check("graph registered", graph is not None)
    check("three translations in memory", len(api.translations(graph, "d1")) == 3)
    sources = [d.name for d in bpy.context.scene.em_tools.em_sources_list]
    check("em_sources_list populated", "D.1" in sources, str(sources))
    names = [d.name for d in bpy.context.scene.doc_list]
    check("doc_list populated", "D.1" in names, str(names))

    saved = os.path.join(work, "saved.em.json")
    bpy.ops.export.em_saveas(filepath=saved, fmt="EMJSON")
    check("saved with export.em_saveas", os.path.isfile(saved))
    back = import_emjson(saved)[0]
    check("the saved file keeps the three translations",
          len(api.translations(back, "d1")) == 3)
    check("the saved graph is the same graph", snapshot(back) == before)

    scene = bpy.context.scene
    scene.rdf_export_path = os.path.join(work, "vitruvio.ttl")
    scene.rdf_base_uri = "urn:em:"
    scene.rdf_mode = "round_trip"
    bpy.ops.export.rdf()
    body = open(os.path.join(work, "vitruvio.ttl"), encoding="utf-8").read()
    check("round trip carries the AI English", "strength, utility" in body)
    scene.rdf_mode = "publish"
    bpy.ops.export.rdf()
    body = open(os.path.join(work, "vitruvio.ttl"), encoding="utf-8").read()
    check("publish leaves it out", "strength, utility" not in body
          and "solidità, utilità, bellezza" in body)

    import importlib
    pkg = bpy.types.VIEW3D_PT_3DDocumentManager.__module__.rsplit(".", 2)[0]
    tags = importlib.import_module(pkg + ".translation_tags")
    line = tags.line(graph, graph.find_node_by_id("d1"))
    check("the language tags", line == "la · en ✦ · fr ? · it ✓", line)
    scene.doc_list_index = names.index("D.1")


def open_panel():
    parent = bpy.types.VIEW3D_PT_3DDocumentManager
    bpy.utils.unregister_class(parent)
    parent.bl_options = set()
    bpy.utils.register_class(parent)


STATE = {"step": 0}


def view3d():
    win = bpy.context.window_manager.windows[0]
    area = max((a for a in win.screen.areas if a.type == 'VIEW_3D'),
               key=lambda a: a.width * a.height)
    return win, area


def step():
    try:
        return _step()
    except Exception as exc:  # noqa: BLE001 — never leave Blender hanging
        import traceback
        traceback.print_exc()
        check("screenshot steps", False, repr(exc))
        finish()


def _step():
    win, area = view3d()
    s = STATE["step"]
    STATE["step"] += 1
    if s == 0:
        with bpy.context.temp_override(window=win, area=area):
            bpy.ops.screen.screen_full_area()
        return 0.5
    if s == 1:
        win, area = view3d()
        area.spaces.active.show_region_ui = True
        area.spaces.active.overlay.show_overlays = False
        return 0.5
    if s == 2:
        ui = next(r for r in area.regions if r.type == 'UI')
        ui.active_panel_category = "EM Scene"   # writable once the region is drawn
        area.tag_redraw()
        return 1.0
    path = os.path.join(OUT, "translations_document_manager.png")
    with bpy.context.temp_override(window=win, area=area):
        bpy.ops.screen.screenshot_area(filepath=path)
    check("screenshot", os.path.isfile(path), path)
    finish()


def finish():
    print(f"[SMOKE] {'OK' if not FAILURES else 'FAILED: ' + ', '.join(FAILURES)}")
    sys.stdout.flush()
    os._exit(1 if FAILURES else 0)


def start():
    try:
        bpy.context.scene.em_tools.mode_em_advanced = True
        run_checks()
        if not bpy.app.background:
            open_panel()
    except Exception as exc:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        check("checks ran", False, repr(exc))
        finish()
    if bpy.app.background:
        finish()
    bpy.app.timers.register(step, first_interval=0.5)
    return None


if bpy.app.background:
    start()
else:
    bpy.app.timers.register(start, first_interval=1.5)
