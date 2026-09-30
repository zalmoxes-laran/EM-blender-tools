"""Headless smoke: le letture 3D del grafo in Blender, attraverso il glTF.

NOT a pytest test (needs bpy) — run it inside Blender with the EM-tools
extension enabled:

    /Applications/Blender\\ 520.app/Contents/MacOS/Blender --background \\
        --python tests/blender_smoke_readings.py

Un grafo con una lettura punto e una polilinea → `em.show_readings` → due
oggetti in `EM_readings`, con il nome della regione, nelle coordinate del
modello (glTF Y-up → Blender Z-up: ``(x, y, z) → (x, -z, y)``, la stessa
conversione che subisce il glb del modello). Poi: si sposta un oggetto → la
lettura è marcata spostata e il grafo non cambia; un secondo «mostra» la
rimette dov'era. E il ritorno misurato: l'exporter di Blender con
``use_mesh_vertices`` / ``use_mesh_edges`` / ``export_extras`` e
`gltf_to_geometry` senza kind — dalla dev23 la polilinea torna ricucita, 4
vertici su 4.

Exits non-zero on failure.
"""
import importlib
import os
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


pkg = next((n.rsplit(".", 1)[0] for n in list(sys.modules)
            if n.startswith("bl_ext.") and n.endswith(".graph_updaters")), None)
if not check("addon loaded", pkg is not None and hasattr(bpy.ops.em, "show_readings")):
    sys.exit(1)
rv_core = importlib.import_module(pkg + ".readings_view.core")
rv_ops = importlib.import_module(pkg + ".readings_view.operators")

from s3dgraphy.api import gltf_to_geometry  # noqa: E402
from s3dgraphy.graph import Graph  # noqa: E402
from s3dgraphy.multigraph.multigraph import multi_graph_manager  # noqa: E402
from s3dgraphy.nodes.annotation_region_node import AnnotationRegionNode  # noqa: E402

PT = [[1.0, 2.0, 3.0]]
PL = [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [1.0, 1.0, 0.0], [1.0, 1.0, 2.0]]


def to_blender(p):
    x, y, z = p
    return (x, -z, y)


def close(a, b, eps=1e-5):
    return len(a) == len(b) and all(abs(u - v) < eps for pa, pb in zip(a, b)
                                    for u, v in zip(pa, pb))


scene = bpy.context.scene
for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob)

graph = Graph(graph_id="smoke_readings")
graph.add_node(AnnotationRegionNode("reg-pt", "punto A", geometry_kind="point", coords=PT))
graph.add_node(AnnotationRegionNode("reg-pl", "polilinea B", geometry_kind="polyline", coords=PL))
multi_graph_manager.graphs["smoke_readings"] = graph
em_tools = scene.em_tools
em_tools.graphml_files.clear()
em_tools.graphml_files.add().name = "smoke_readings"
em_tools.active_file_index = 0

res = bpy.ops.em.show_readings()
check("show_readings FINISHED", res == {"FINISHED"}, str(res))
coll = bpy.data.collections.get("EM_readings")
check("collection EM_readings exists and is in the scene",
      coll is not None and coll.name in scene.collection.children)
objs = {o.get(rv_core.PROP_ID): o for o in coll.objects} if coll else {}
check("two objects in EM_readings", len(coll.objects) == 2 if coll else False,
      str([o.name for o in coll.objects]) if coll else "")

pt, pl = objs.get("reg-pt"), objs.get("reg-pl")
check("point named after the region", pt is not None and pt.name == "punto A")
check("polyline named after the region", pl is not None and pl.name == "polilinea B")
if pt is not None:
    check("point = mesh with one vertex, no edges",
          pt.type == 'MESH' and len(pt.data.vertices) == 1 and len(pt.data.edges) == 0)
    check("point in model coordinates (Y-up → Z-up)",
          close(rv_ops.world_points(pt), [to_blender(p) for p in PT]),
          str(rv_ops.world_points(pt)))
    check("point drawn in front of the model", pt.show_in_front)
if pl is not None:
    check("polyline = mesh of edges only (4 verts, 3 edges, 0 faces)",
          pl.type == 'MESH' and len(pl.data.vertices) == 4
          and len(pl.data.edges) == 3 and len(pl.data.polygons) == 0)
    check("polyline in model coordinates",
          close(rv_ops.world_points(pl), [to_blender(p) for p in PL]),
          str(rv_ops.world_points(pl)))

# ── spostarla: avviso, e il grafo non cambia ────────────────────────────────
before = repr(graph.find_node_by_id("reg-pt").data)
if pt is not None:
    check("not flagged before moving", not pt.get(rv_core.PROP_MOVED))
    pt.location.x += 0.5
    bpy.context.view_layer.update()      # fa girare depsgraph_update_post
    check("moved reading is flagged (handler)", bool(pt.get(rv_core.PROP_MOVED)))
    check("the graph is untouched", repr(graph.find_node_by_id("reg-pt").data) == before)

res = bpy.ops.em.show_readings()
objs = {o.get(rv_core.PROP_ID): o for o in coll.objects}
check("show again: still two objects (no duplicates)", len(coll.objects) == 2)
pt = objs.get("reg-pt")
check("show again: point back where the graph says, flag cleared",
      pt is not None and close(rv_ops.world_points(pt), [to_blender(p) for p in PT])
      and not pt.get(rv_core.PROP_MOVED))

# ── il ritorno, misurato: dalla dev23 la polilinea torna ricucita ──────────
# export con le custom property del nodo (`em_reading_kind`), e
# `gltf_to_geometry` senza kind: lo legge dagli extras del nodo
work = tempfile.mkdtemp(prefix="em_readings_")
for rid, kind, coords in (("reg-pt", "point", PT), ("reg-pl", "polyline", PL)):
    obj = objs[rid]
    for o in bpy.data.objects:
        o.select_set(False)
    obj.select_set(True)
    path = os.path.join(work, rid + ".glb")
    bpy.ops.export_scene.gltf(filepath=path, use_selection=True, export_format='GLB',
                              use_mesh_vertices=True, use_mesh_edges=True,
                              export_extras=True)
    back = gltf_to_geometry(open(path, "rb").read())
    print(f"[SMOKE] INFO: {kind} back from Blender: {back}")
    check(f"{kind}: kind read from the node extras",
          back.get("geometry_kind") == kind and not back.get("warnings"), str(back.get("warnings")))
    check(f"{kind} comes back exact ({len(coords)} vertices, in order)",
          close(back.get("coords") or [], coords))

print(f"[SMOKE] {'OK' if not FAILURES else 'FAILED: ' + ', '.join(FAILURES)}")
sys.exit(1 if FAILURES else 0)
