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
rimette dov'era. Il ritorno: l'export di «Bring back to graph» e
`gltf_to_geometry` senza kind — dalla dev23 la polilinea torna ricucita, 4
vertici su 4. Poi `em.readings_to_graph`: un vertice spostato cambia coords e
lunghezza di quel tanto; un punto spostato come oggetto torna spostato; una
polilinea spezzata in due non scrive e lo dice.

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
    check("point = its vertex + a cross of 3 edges that do not touch it (7 verts)",
          pt.type == 'MESH' and len(pt.data.vertices) == 7 and len(pt.data.edges) == 3
          and not any(0 in e.vertices for e in pt.data.edges))
    check("point in model coordinates (Y-up → Z-up)",
          close(rv_ops.world_points(pt)[:1], [to_blender(p) for p in PT]),
          str(rv_ops.world_points(pt)[:1]))
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
      pt is not None and close(rv_ops.world_points(pt)[:1], [to_blender(p) for p in PT])
      and not pt.get(rv_core.PROP_MOVED))

# ── il ritorno, misurato: dalla dev23 la polilinea torna ricucita ──────────
# l'export che usa «Bring back to graph» (matrix_world cotta, extras) e
# `gltf_to_geometry` senza kind: lo legge dagli extras del nodo
for rid, kind, coords in (("reg-pt", "point", PT), ("reg-pl", "polyline", PL)):
    back = gltf_to_geometry(rv_ops.export_reading_glb(bpy.context, objs[rid]))
    print(f"[SMOKE] INFO: {kind} back from Blender: {back}")
    check(f"{kind}: kind read from the node extras",
          back.get("geometry_kind") == kind and not back.get("warnings"), str(back.get("warnings")))
    check(f"{kind} comes back exact ({len(coords)} vertices, in order)",
          close(back.get("coords") or [], coords))


def select_only(*objects):
    for o in bpy.data.objects:
        o.select_set(o in objects)
    bpy.context.view_layer.objects.active = objects[0]


def reading(rid):
    return graph.find_node_by_id(rid).data


# ── «Bring back to graph»: un vertice della polilinea spostato ──────────────
pl = objs["reg-pl"]
pl.data.vertices[3].co.z += 0.5            # Blender z = scena y: +0,5
bpy.context.view_layer.update()
check("moved polyline vertex is flagged", bool(pl.get(rv_core.PROP_MOVED)))
select_only(pl)
res = bpy.ops.em.readings_to_graph()
check("readings_to_graph FINISHED", res == {"FINISHED"}, str(res))
want = [list(p) for p in PL]
want[3] = [1.0, 1.5, 2.0]
data = reading("reg-pl")
check("polyline coords changed by exactly that vertex", close(data["coords"], want),
      str(data["coords"]))
new_len = 1.0 + 1.0 + (0.5 ** 2 + 2.0 ** 2) ** 0.5
check("length recomputed (4.0 → 4.0616)", abs(data["length"] - new_len) < 1e-5,
      str(data["length"]))
check("the written fields carry their clocks",
      {"data.coords", "data.length"} <= set(data.get("field_clocks") or {}))
check("written reading no longer flagged moved", not pl.get(rv_core.PROP_MOVED))

# ── un punto spostato come OGGETTO (G): la trasformazione è cotta ──────────
pt = objs["reg-pt"]
pt.location.x += 0.5
bpy.context.view_layer.update()
select_only(pt)
bpy.ops.em.readings_to_graph()
check("point moved by its object transform comes back moved (matrix_world baked)",
      close(reading("reg-pt")["coords"], [[1.5, 2.0, 3.0]]), str(reading("reg-pt")["coords"]))
check("selection restored after the export", pt.select_get()
      and bpy.context.view_layer.objects.active == pt
      and not any(o.name.startswith(pt.name + ".") for o in bpy.data.objects))

# ── niente cambiato → niente scritto ────────────────────────────────────────
clocks = repr(reading("reg-pl").get("field_clocks"))
select_only(pl)
bpy.ops.em.readings_to_graph()
check("unchanged reading: nothing rewritten", repr(reading("reg-pl").get("field_clocks")) == clocks)

# ── due pezzi: il grafo non cambia, e l'avviso arriva ───────────────────────
import bmesh  # noqa: E402
before = repr(reading("reg-pl"))
bm = bmesh.new()
bm.from_mesh(pl.data)
bm.edges.ensure_lookup_table()
bm.edges.remove(bm.edges[1])               # il segmento di mezzo: due catene
bm.to_mesh(pl.data)
bm.free()
select_only(pl)
results = rv_ops.readings_to_graph(bpy.context, graph, [pl])
print(f"[SMOKE] INFO: two pieces → {results}")
check("two pieces: not written, s3Dgraphy's warning handed on",
      not results[0]["written"] and "pieces" in results[0]["reason"]
      and results[0]["warnings"], str(results[0]))
check("two pieces: the graph is unchanged", repr(reading("reg-pl")) == before)
res = bpy.ops.em.readings_to_graph()
check("two pieces via the operator: FINISHED with a warning, graph unchanged",
      res == {"FINISHED"} and repr(reading("reg-pl")) == before)
# (l'impronta guarda le posizioni dei vertici, non gli spigoli: togliere uno
# spigolo non segna la lettura come spostata — detto nel referto)

print(f"[SMOKE] {'OK' if not FAILURES else 'FAILED: ' + ', '.join(FAILURES)}")
sys.exit(1 if FAILURES else 0)
