"""Headless smoke · NIGHT-TAGLI-E-NEUTRE (em_visual_rules 1.6.44 `threed`): the
proxies drawn as their TYPE asks, in a new empty scene — a US (a layer), a
USN (a pit cut: the volume of the matter removed) with its fill (a US) inside,
a USNt (a room) — the same scene as EMStudio's check-threed-browser.mjs:

* the materials: US and the fill at the slider's alpha (as before), the USN
  at 0.3 × the slider, the USNt at 0 (no face);
* the slider MULTIPLIES: 0.5 → 0.8, each type keeps its ratio;
* the type's edges: a curve child of the USN (solid, 12 segments of a
  frustum) and of the USNt (dashed), none for the US;
* the edges follow the proxy (hidden → hidden) and leave in another display mode;
* a render (EEVEE) of the scene, when an output folder is given.

    PYTHONPATH=~/Documents/GitHub/s3Dgraphy/src \\
    "/Applications/Blender 520.app/Contents/MacOS/Blender" -b --factory-startup=0 --python-use-system-env \\
        --python tests/blender_smoke_threed_style.py -- <out.json> [<render dir>]
"""
import json
import math
import os
import sys

import bpy

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = ARGS[0] if ARGS else "/tmp/threed_style.json"
SHOTS = ARGS[1] if len(ARGS) > 1 else None
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append({"check": name, "ok": bool(ok), "detail": str(detail)})
    print(f"[SMOKE] {'PASS' if ok else 'FAIL'} {name} {detail}")


def mod(suffix):
    names = [n for n in sys.modules if n.endswith("." + suffix) and n.startswith("bl_ext.")
             and "EM-blender-tools" in n]
    return sys.modules[names[0]]


fn = mod("EM-blender-tools.functions")
import importlib  # noqa: E402
ts = importlib.import_module(fn.__name__.rsplit(".", 1)[0] + ".threed_style")
import s3dgraphy  # noqa: E402
check("s3dgraphy with the rule (1.6.44)", hasattr(__import__("s3dgraphy.utils.utils", fromlist=["x"]),
                                                  "get_threed_style"), s3dgraphy.__file__)

sc = bpy.context.scene
et = sc.em_tools
for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
proxy_coll = bpy.data.collections.get("Proxy") or bpy.data.collections.new("Proxy")
if proxy_coll.name not in sc.collection.children:
    sc.collection.children.link(proxy_coll)


def box(x0, y0, z0, x1, y1, z1):
    return [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]


def frustum(a, b, z0, z1):  # mouth half side a at z1, bottom b at z0 (z up)
    return [(-b, -b, z0), (b, -b, z0), (b, b, z0), (-b, b, z0), (-a, -a, z1), (a, -a, z1), (a, a, z1), (-a, a, z1)]


FACES = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]


def proxy(name, verts):
    # the origin at the centre of the geometry, as a real proxy: EEVEE sorts
    # the transparent objects by their origin
    c = [sum(v[i] for v in verts) / len(verts) for i in range(3)]
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v[i] - c[i] for i in range(3)) for v in verts], [], FACES)
    me.update()
    ob = bpy.data.objects.new(name, me)
    ob.location = c
    proxy_coll.objects.link(ob)
    return ob


units = [(proxy("US1", box(-3.6, -1.2, -1.4, -1.3, 1.2, 0)), "US"),
         (proxy("USN2", frustum(1.1, 0.55, -1.4, 0)), "USN"),
         (proxy("US3", frustum(0.82, 0.5, -1.35, -0.55)), "US"),
         (proxy("USNt4", box(1.8, -1, -1.4, 3.8, 1, 0.6)), "USNt")]

et.proxy_display_alpha = 0.5
fn.consolidate_EM_material_presence(True)
pairs = []
for ob, t in units:
    ob.data.materials.clear()
    ob.data.materials.append(bpy.data.materials[t])
    pairs.append((ob, t))
et.proxy_display_mode = "EM"
done = ts.apply_threed(bpy.context, pairs)
check("edges for the two voids only", done["edges"] == 2, done)


def alpha(name):
    m = bpy.data.materials[name]
    p = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    return round(p.inputs['Alpha'].default_value, 3), round(m.diffuse_color[3], 3), m.blend_method


a = {t: alpha(t) for t in ("US", "USN", "USNt")}
check("US: the slider's alpha, as before", a["US"][0] == 0.5, a["US"])
check("USN: 0.3 × the slider", a["USN"][0] == 0.15 and a["USN"][2] == 'BLEND', a["USN"])
check("USNt: no face (alpha 0)", a["USNt"][0] == 0.0 and a["USNt"][1] == 0.0, a["USNt"])

et.proxy_display_alpha = 0.8
fn.apply_proxy_alpha(bpy.context)
b = {t: alpha(t) for t in ("US", "USN", "USNt")}
check("the slider at 0.8 multiplies", (b["US"][0], b["USN"][0], b["USNt"][0]) == (0.8, 0.24, 0.0), b)

edges = {o.parent.name: o for o in bpy.data.collections[ts.EDGES_COLLECTION].objects}
check("a curve of edges under USN2 and USNt4, none under the US",
      sorted(edges) == ["USN2", "USNt4"], sorted(edges))
n_usn = len(edges["USN2"].data.splines)
n_usnt = len(edges["USNt4"].data.splines)
diag = math.sqrt(2 ** 2 + 2 ** 2 + 2 ** 2)
expect_usnt = 4 * math.ceil(2 / (0.065 * diag)) * 2 + 4 * math.ceil(2 / (0.065 * diag))
check("USN: 12 solid edges", n_usn == 12 and edges["USN2"]["em_threed_style"] == "solid", n_usn)
check("USNt: dashed", edges["USNt4"]["em_threed_style"] == "dashed" and n_usnt == expect_usnt, (n_usnt, expect_usnt))
col = tuple(round(x, 3) for x in edges["USNt4"].data.materials[0].diffuse_color[:3])
check("USNt edges in its grey (linear 0.262)", col == (0.262, 0.262, 0.262), col)
check("the edges are not selectable", all(o.hide_select for o in edges.values()))

if SHOTS:
    os.makedirs(SHOTS, exist_ok=True)
    cam_data = bpy.data.cameras.new("cam")
    cam = bpy.data.objects.new("cam", cam_data)
    sc.collection.objects.link(cam)
    cam.location = (7.5, -9.0, 6.0)
    cam.rotation_euler = (math.radians(62), 0, math.radians(40))
    sc.camera = cam
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
    sun.rotation_euler = (math.radians(40), math.radians(10), math.radians(30))
    sun.data.energy = 3.0
    sc.collection.objects.link(sun)
    world = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
    sc.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.8, 0.8, 0.8, 1)
        bg.inputs[1].default_value = 1.0
    for engine in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE", "BLENDER_WORKBENCH"):
        try:
            sc.render.engine = engine
            break
        except TypeError:
            continue
    sc.render.resolution_x, sc.render.resolution_y = 1200, 800
    sc.render.film_transparent = False
    sc.render.filepath = os.path.join(SHOTS, "blender-render.png")
    try:
        bpy.ops.render.render(write_still=True)
        check("render written", os.path.exists(sc.render.filepath), f"{sc.render.engine} {sc.render.filepath}")
    except Exception as exc:  # noqa: BLE001
        check("render written", False, exc)

# the edges follow their proxy
units[3][0].hide_set(True)
ts.sync_edges_visibility(sc)
check("USNt hidden → its edges hidden", edges["USNt4"].hide_get() is True)
units[3][0].hide_set(False)
ts.sync_edges_visibility(sc)
check("…shown again", edges["USNt4"].hide_get() is False)

fn._drop_type_edges()
left = len(bpy.data.collections[ts.EDGES_COLLECTION].objects)
check("another display mode takes the edges away", left == 0, left)
ts.apply_threed(bpy.context, pairs)
check("EM draws them again", len(bpy.data.collections[ts.EDGES_COLLECTION].objects) == 2)

with open(OUT, "w") as fh:
    json.dump(RESULTS, fh, indent=1)
fails = [r for r in RESULTS if not r["ok"]]
print(f"[SMOKE] {len(RESULTS) - len(fails)}/{len(RESULTS)} passed")
sys.exit(1 if fails else 0)
