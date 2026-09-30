"""Headless smoke: il proxy come proprietà, dalla scena al glb e alla risorsa.

NOT a pytest test (needs bpy) — run it inside Blender with the EM-tools
extension enabled:

    /Applications/Blender\\ 520.app/Contents/MacOS/Blender --background \\
        --python tests/blender_smoke_proxy_chain.py

`tests/test_proxy_chain.py` misura il grafo con s3Dgraphy vero; qui si misura
quello che quei test non possono vedere:

* l'abbinamento PER NOME di `update_semantic_shapes` — nome esatto, e suffisso
  ``.<US>`` per il prefisso di grafo — su due oggetti veri;
* il vero `export_proxies` dell'export Heriverse: il glb scritto su disco e la
  risorsa `proxy_model` che ne riceve percorso e checksum;
* che un secondo aggiornamento, e un secondo export, lasciano il grafo uguale.

Il .blend e i glb vanno in una cartella temporanea che viene cancellata.
Exits non-zero on failure.
"""
import hashlib
import importlib
import os
import shutil
import sys
import tempfile

import bpy

FAILURES = []


def check(label, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print(f"[SMOKE] {status}: {label} {detail}")
    if not condition:
        FAILURES.append(label)
    return condition


def addon_module():
    for name in list(sys.modules):
        if name.endswith(".graph_updaters") and name.startswith("bl_ext."):
            return name.rsplit(".", 1)[0]
    return None


pkg = addon_module()
if not check("addon loaded", pkg is not None and hasattr(bpy.context.scene, "em_tools")):
    sys.exit(1)

gu = importlib.import_module(pkg + ".graph_updaters")
pc = importlib.import_module(pkg + ".proxy_chain")
heriverse = importlib.import_module(pkg + ".export_operators.heriverse.operator")

from s3dgraphy.graph import Graph  # noqa: E402
from s3dgraphy.multigraph.multigraph import multi_graph_manager  # noqa: E402
from s3dgraphy.nodes.stratigraphic_node import StratigraphicUnit  # noqa: E402

work = tempfile.mkdtemp(prefix="em_proxy_chain_")
try:
    scene = bpy.context.scene
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob)

    # ── due proxy: uno col nome esatto, uno col prefisso di grafo ──────────
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, 0))
    bpy.context.active_object.name = "US01"
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(3, 0, 0))
    bpy.context.active_object.name = "DEMO.US02"
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(work, "proxy_chain.blend"))

    graph = Graph(graph_id="smoke_proxy")
    graph.add_node(StratigraphicUnit("us-1", "US01"))
    graph.add_node(StratigraphicUnit("us-2", "US02"))
    graph.add_node(StratigraphicUnit("us-3", "US03"))   # nessun oggetto in scena
    multi_graph_manager.graphs["smoke_proxy"] = graph
    em_tools = scene.em_tools
    em_tools.graphml_files.clear()
    gfile = em_tools.graphml_files.add()
    gfile.name = "smoke_proxy"
    em_tools.active_file_index = 0

    ok = gu.update_graph_with_scene_data("smoke_proxy")
    check("update_graph_with_scene_data returns True", ok)

    def chain(unit_id):
        shape, res = pc.glb_proxy(graph, unit_id)
        direct = [e for e in graph.edges
                  if e.edge_source == unit_id and e.edge_type == "has_semantic_shape"]
        return shape, res, direct

    for uid, name in (("us-1", "US01"), ("us-2", "US02")):
        shape, res, direct = chain(uid)
        check(f"{name}: proxy as property → shape → proxy_model resource",
              shape is not None and res is not None
              and res.data.get("url_type") == "proxy_model",
              f"shape={getattr(shape, 'node_id', None)}")
        check(f"{name}: resource url proxies/{name}.glb",
              res is not None and res.data.get("url") == f"proxies/{name}.glb")
        check(f"{name}: no direct US → has_semantic_shape", not direct)
        check(f"{name}: shape carries no url",
              shape is not None and not (shape.data or {}).get("url"))
    check("US03 (no object) has no proxy", pc.glb_proxy(graph, "us-3") == (None, None))

    def snap():
        return ({n.node_id: repr(sorted((getattr(n, "data", {}) or {}).items()))
                 for n in graph.nodes},
                {(e.edge_source, e.edge_type, e.edge_target) for e in graph.edges})

    prima = snap()
    gu.update_graph_with_scene_data("smoke_proxy")
    check("second update leaves the graph identical", snap() == prima)

    # ── il vero export_proxies dell'export Heriverse ───────────────────────
    Op = heriverse.EXPORT_OT_heriverse

    class Esportatore:
        """Lo stato che `execute` prepara, attorno ai metodi veri."""

        def report(self, level, msg):
            print(f"[export] {level}: {msg}")

    for attr, val in vars(Op).items():
        if callable(val) or isinstance(val, (staticmethod, tuple)):
            if not attr.startswith("__") and attr not in ("report",):
                setattr(Esportatore, attr, val)

    folder = os.path.join(work, "proxies")
    os.makedirs(folder, exist_ok=True)
    esp = Esportatore()
    esp._esiti_falliti, esp._esiti_saltati = [], []
    exported = Op.export_proxies(esp, bpy.context, folder)
    check("export_proxies returns True", exported is True, f"got {exported!r}")
    check("no export failures", not esp._esiti_falliti, str(esp._esiti_falliti))

    for uid, name in (("us-1", "US01"), ("us-2", "US02")):
        glb = os.path.join(folder, f"{name}.glb")
        check(f"{name}.glb written", os.path.isfile(glb))
        shape, res, _ = chain(uid)
        if os.path.isfile(glb) and res is not None:
            digest = "sha256:" + hashlib.sha256(open(glb, "rb").read()).hexdigest()
            check(f"{name}: resource has the glb checksum", res.data.get("checksum") == digest)
            check(f"{name}: resource is the distribution",
                  res.data.get("tier") == "distribution"
                  and res.data.get("url_type") == "proxy_model")
            check(f"{name}: no second `<shape>_link` node",
                  graph.find_node_by_id(f"{shape.node_id}_link") is None)
            masters = [r for r in pc._targets(graph, shape.node_id, "has_linked_resource")
                       if (r.data or {}).get("tier") == "master"]
            check(f"{name}: master datablock declared on the shape", len(masters) == 1,
                  str([m.node_id for m in masters]))

    prima = snap()
    Op.export_proxies(esp, bpy.context, folder)
    gu.update_graph_with_scene_data("smoke_proxy")
    check("second export + update leave the graph identical", snap() == prima)

    # ── e il JSON di Heriverse proietta il percorso sulla forma ────────────
    from s3dgraphy.exporter.json_exporter import JSONExporter
    nodes = JSONExporter.__new__(JSONExporter)._process_nodes(graph)
    shape, _res, _ = chain("us-2")
    check("Heriverse JSON: semantic_shapes[..].data.url projected",
          nodes["semantic_shapes"][shape.node_id]["data"].get("url") == "proxies/US02.glb")
finally:
    shutil.rmtree(work, ignore_errors=True)

print(f"[SMOKE] {'OK' if not FAILURES else 'FAILED: ' + ', '.join(FAILURES)}")
sys.exit(1 if FAILURES else 0)
