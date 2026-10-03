"""Headless smoke: il proxy di `create_proxy_for_unit` nel sistema della scena.

NOT a pytest test (needs bpy) — run it inside Blender with the EM-tools
extension enabled:

    /Applications/Blender\\ 520.app/Contents/MacOS/Blender --background \\
        --python tests/blender_smoke_proxy_scene.py

Un "modello" (un parallelepipedo 1×2×3 fuori dall'origine, così ogni asse si
vede) esportato come fa l'export Heriverse, cioè dall'exporter glTF di Blender
(Y-up). Un proxy che lo racchiude esattamente, legato a una US con il verbo
`_bbox_hull` + `create_geometry_proxy`, le due chiamate del verbo
`create_proxy_for_unit` (che su un proxy GIÀ in scena non scrive niente: Y5).
Il convesso che finisce nel grafo, riletto da
s3Dgraphy e scritto con `geometry_to_gltf`, deve avere lo STESSO bounding box
del glb del modello; e reimportato in Blender deve ricadere sul proxy.
Prima della conversione il convesso era Z-up: sdraiato di 90° accanto al
modello.

Exits non-zero on failure.
"""
import importlib
import json
import os
import struct
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
if not check("addon loaded", pkg is not None):
    sys.exit(1)
commands = importlib.import_module(pkg + ".sync_manager.commands")
proxy_chain = importlib.import_module(pkg + ".proxy_chain")

from s3dgraphy.api import geometry_to_gltf, gltf_to_geometry  # noqa: E402
from s3dgraphy.graph import Graph  # noqa: E402
from s3dgraphy.nodes.stratigraphic_node import StratigraphicUnit  # noqa: E402


def glb_bbox(data):
    """min/max di tutte le POSITION di un glb, nel frame glTF (le trasformazioni
    dei nodi sono applicate prima dell'export: qui non ce ne sono)."""
    length = struct.unpack_from("<I", data, 12)[0]
    doc = json.loads(data[20:20 + length])
    for node in doc.get("nodes", []):
        assert not any(k in node for k in ("matrix", "rotation", "scale")) and \
            not any(node.get("translation", [0, 0, 0])), node
    mins, maxs = [1e30] * 3, [-1e30] * 3
    for mesh in doc["meshes"]:
        for prim in mesh["primitives"]:
            acc = doc["accessors"][prim["attributes"]["POSITION"]]
            mins = [min(a, b) for a, b in zip(mins, acc["min"])]
            maxs = [max(a, b) for a, b in zip(maxs, acc["max"])]
    return mins, maxs


def world_bbox(obj):
    from mathutils import Vector
    pts = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    return ([min(p[i] for p in pts) for i in range(3)],
            [max(p[i] for p in pts) for i in range(3)])


def close(a, b, eps=1e-4):
    return all(abs(u - v) < eps for u, v in zip(a, b))


def select_only(obj):
    for o in bpy.data.objects:
        o.select_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob)
work = tempfile.mkdtemp(prefix="em_proxy_scene_")

# ── il modello, esportato come l'export Heriverse (exporter glTF, Y-up) ─────
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(2.0, 5.0, 1.5))
model = bpy.context.active_object
model.name = "Model"
model.scale = (1.0, 2.0, 3.0)
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
select_only(model)
model_glb = os.path.join(work, "model.glb")
bpy.ops.export_scene.gltf(filepath=model_glb, use_selection=True, export_format='GLB')
m_min, m_max = glb_bbox(open(model_glb, "rb").read())
print(f"[SMOKE] INFO: model glb bbox {m_min} {m_max}")
check("model glb is Y-up (the 3 m height is on glTF y)",
      abs((m_max[1] - m_min[1]) - 3.0) < 1e-4 and abs((m_max[2] - m_min[2]) - 2.0) < 1e-4)

# ── il proxy che lo racchiude, legato a una US col verbo ────────────────────
proxy = model.copy()
proxy.data = model.data.copy()
proxy.name = "US01"
bpy.context.scene.collection.objects.link(proxy)

graph = Graph(graph_id="smoke_proxy_scene")
graph.add_node(StratigraphicUnit(node_id="us-1", name="US01"))
# Y5 · the verb on a unit whose proxy object EXISTS writes nothing: it says so
# and selects the object (measured on Templu Mare: a third geometry property)
n0, e0 = len(graph.nodes), len(graph.edges)
out = commands.create_proxy_for_unit("us-1", {}, bpy.context, graph)
check("create_proxy_for_unit on an existing proxy: already, nothing written",
      out.get("ok") and out["info"].get("already") and out["info"]["reused_object"]
      and out["delta"] == {"nodes": [], "edges": []}
      and (len(graph.nodes), len(graph.edges)) == (n0, e0), str(out.get("info") or out))
check("…and the existing proxy is the active, selected object",
      bpy.context.view_layer.objects.active == proxy and proxy.select_get())
# the hull the verb writes when it DOES model one: the same two calls
from s3dgraphy.api import create_geometry_proxy  # noqa: E402
made = create_geometry_proxy(graph, "us-1", {"convexshapes": [commands._bbox_hull(proxy)]})
shape = graph.find_node_by_id(made.shape_id)
hull = (shape.data.get("convexshapes") or [[]])[0] if shape is not None else []
check("one convex of 8 corners in the graph", len(hull) == 24, str(len(hull)))
check("the shape is the unit's proxy along the chain",
      shape is not None and shape in proxy_chain.geometry_shapes(graph, "us-1"))

# ── riletto da s3Dgraphy e scritto in glTF: cade sul modello ────────────────
shape_glb = geometry_to_gltf(shape)
s_min, s_max = glb_bbox(shape_glb)
print(f"[SMOKE] INFO: proxy glb bbox {s_min} {s_max}")
check("proxy glTF bbox == model glTF bbox (scene frame, Y-up)",
      close(s_min, m_min) and close(s_max, m_max))
back = gltf_to_geometry(shape_glb, "convex")
check("convex round-trips through glTF", sorted(back["convexshapes"][0]) == sorted(float(v) for v in hull))

# ── e in Blender ricade sul proxy (l'importer fa Y-up → Z-up) ───────────────
path = os.path.join(work, "shape.glb")
open(path, "wb").write(shape_glb)
before = set(bpy.data.objects)
bpy.ops.import_scene.gltf(filepath=path)
imported = [o for o in bpy.data.objects if o not in before and o.type == 'MESH']
check("the shape glb imports as one mesh", len(imported) == 1)
if imported:
    i_min, i_max = world_bbox(imported[0])
    p_min, p_max = world_bbox(proxy)
    print(f"[SMOKE] INFO: imported {i_min} {i_max} / proxy {p_min} {p_max}")
    check("imported shape lands on the Blender proxy", close(i_min, p_min) and close(i_max, p_max))

# ── la funzione inversa, sul convesso del grafo ─────────────────────────────
scene_space = importlib.import_module(pkg + ".scene_space")
pts = scene_space.flat_to_blender(hull)
p_min, p_max = world_bbox(proxy)
check("scene_space.flat_to_blender(hull) == the proxy's world corners",
      close([min(p[i] for p in pts) for i in range(3)], p_min)
      and close([max(p[i] for p in pts) for i in range(3)], p_max))

print(f"[SMOKE] {'OK' if not FAILURES else 'FAILED: ' + ', '.join(FAILURES)}")
sys.exit(1 if FAILURES else 0)
