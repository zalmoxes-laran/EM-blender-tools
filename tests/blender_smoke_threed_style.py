"""Headless smoke · NIGHT-TAGLI-E-NEUTRE (em_visual_rules 1.6.44 `threed`): the
proxies drawn as their TYPE asks, in a new empty scene — a US (a layer), a
USN (a pit cut: the volume of the matter removed) with its fill (a US) inside,
a USNt (a room) — the same scene as EMStudio's check-threed-browser.mjs:

* the materials: US and the fill at the slider's alpha (as before), the USN
  at 0.3 × the slider, the USNt at 0 (no face);
* the slider MULTIPLIES: 0.5 → 0.8, each type keeps its ratio;
* the type's edges (1.6.45): a curve child of EVERY proxy — the US thin and
  continuous in its frame colour, the USN solid in dark grey (#8C8C8C), the
  USNt dashed;
* the edges follow the proxy (hidden → hidden);
* Epochs mode (decision 3): the USNt stays without faces (a variant of the
  epoch material at alpha 0), the USN at 0.3, the edges in the epoch colour;
* decision 4: the proxies' materials render «Dithered» with backface culling;
* renders (EEVEE) with the proxies' origins at their centres AND at 0,0,0,
  when an output folder is given.

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


CENTRE = [True]


def proxy(name, verts):
    # the origin at the centre of the geometry, or at 0,0,0 (a proxy modelled
    # in place): «Blended» sorted by origin and lost the fill in the second case
    c = [sum(v[i] for v in verts) / len(verts) for i in range(3)] if CENTRE[0] else [0.0, 0.0, 0.0]
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
check("edges for every proxy (1.6.45)", done["edges"] == 4, done)


def alpha(name):
    m = bpy.data.materials[name]
    p = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    return round(p.inputs['Alpha'].default_value, 3), round(m.diffuse_color[3], 3), m.blend_method


a = {t: alpha(t) for t in ("US", "USN", "USNt")}
check("US: the slider's alpha, as before", a["US"][0] == 0.5, a["US"])
check("USN: 0.3 × the slider", a["USN"][0] == 0.15, a["USN"])
rm = {t: (bpy.data.materials[t].surface_render_method, bpy.data.materials[t].use_backface_culling)
      for t in ("US", "USN", "USNt")}
check("decision 4: Dithered + backface culling (order independent)",
      all(v == ("DITHERED", True) for v in rm.values()), rm)
check("USNt: no face (alpha 0)", a["USNt"][0] == 0.0 and a["USNt"][1] == 0.0, a["USNt"])

et.proxy_display_alpha = 0.8
fn.apply_proxy_alpha(bpy.context)
b = {t: alpha(t) for t in ("US", "USN", "USNt")}
check("the slider at 0.8 multiplies", (b["US"][0], b["USN"][0], b["USNt"][0]) == (0.8, 0.24, 0.0), b)

edges = {o.parent.name: o for o in bpy.data.collections[ts.EDGES_COLLECTION].objects}
check("a curve of edges under every proxy",
      sorted(edges) == ["US1", "US3", "USN2", "USNt4"], sorted(edges))
col_us = tuple(round(x, 3) for x in edges["US1"].data.materials[0].diffuse_color[:3])
check("US edges: thin, continuous, its frame colour (linear #9B3333)", col_us == (0.328, 0.033, 0.033)
      and edges["US1"]["em_threed_style"] == "solid", col_us)
col_usn = tuple(round(x, 3) for x in edges["USN2"].data.materials[0].diffuse_color[:3])
check("decision 2: USN edges dark grey 0.262", col_usn == (0.262, 0.262, 0.262), col_usn)
nseg_usn = sum(len(sp.points) - 1 for sp in edges["USN2"].data.splines)
n_usn = nseg_usn
n_usnt = len(edges["USNt4"].data.splines)
diag = math.sqrt(2 ** 2 + 2 ** 2 + 2 ** 2)
expect_usnt = 4 * math.ceil(2 / (0.065 * diag)) * 2 + 4 * math.ceil(2 / (0.065 * diag))
check("USN: 12 solid edges", n_usn == 12 and edges["USN2"]["em_threed_style"] == "solid", n_usn)
check("USNt: dashed", edges["USNt4"]["em_threed_style"] == "dashed" and n_usnt == expect_usnt, (n_usnt, expect_usnt))
col = tuple(round(x, 3) for x in edges["USNt4"].data.materials[0].diffuse_color[:3])
check("USNt edges in its grey (linear 0.262)", col == (0.262, 0.262, 0.262), col)
check("the edges are not selectable", all(o.hide_select for o in edges.values()))

# decision 3: Epochs mode — the epoch's material on every proxy, then the types
fn.consolidate_epoch_material_presence("ep_Roman")
fn.em_setup_mat_cycles("ep_Roman", 0.05, 0.2, 0.6)
for ob, t in units:
    ob.data.materials.clear()
    ob.data.materials.append(bpy.data.materials["ep_Roman"])
done = ts.apply_threed_mode(bpy.context, pairs, "Epochs")
mats = {ob.name: ob.data.materials[0].name for ob, _ in units}
check("Epochs: US keeps the epoch material, USN/USNt a variant",
      mats == {"US1": "ep_Roman", "US3": "ep_Roman", "USN2": "ep_Roman.EM_faces_USN",
               "USNt4": "ep_Roman.EM_faces_USNt"}, mats)
check("Epochs: USNt without faces", alpha("ep_Roman.EM_faces_USNt")[0] == 0.0, alpha("ep_Roman.EM_faces_USNt"))
check("Epochs: USN at 0.3 × the slider", alpha("ep_Roman.EM_faces_USN")[0] == 0.24, alpha("ep_Roman.EM_faces_USN"))
edges = {o.parent.name: o for o in bpy.data.collections[ts.EDGES_COLLECTION].objects}
ecol = {k: tuple(round(x, 3) for x in o.data.materials[0].diffuse_color[:3]) for k, o in edges.items()}
check("Epochs: every edge in the epoch colour", set(ecol.values()) == {(0.05, 0.2, 0.6)}, ecol)
check("Epochs: the USNt still dashed", edges["USNt4"]["em_threed_style"] == "dashed")
et.proxy_display_alpha = 0.5
fn.apply_proxy_alpha(bpy.context)
check("the slider keeps the variant's factor", (alpha("ep_Roman")[0], alpha("ep_Roman.EM_faces_USN")[0],
      alpha("ep_Roman.EM_faces_USNt")[0]) == (0.5, 0.15, 0.0))
check("infer_display_mode reads Epochs", fn.infer_display_mode(bpy.context) == "Epochs")
# back to EM
for ob, t in units:
    ob.data.materials.clear()
    ob.data.materials.append(bpy.data.materials[t])
ts.apply_threed_mode(bpy.context, pairs, "EM")
edges = {o.parent.name: o for o in bpy.data.collections[ts.EDGES_COLLECTION].objects}
col_usn = tuple(round(x, 3) for x in edges["USN2"].data.materials[0].diffuse_color[:3])
check("EM again: the type colours the edges", col_usn == (0.262, 0.262, 0.262), col_usn)


def render(path):
    sc.render.filepath = path
    try:
        bpy.ops.render.render(write_still=True)
        check(f"render {os.path.basename(path)}", os.path.exists(path), f"{sc.render.engine} {path}")
    except Exception as exc:  # noqa: BLE001
        check(f"render {os.path.basename(path)}", False, exc)


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
    render(os.path.join(SHOTS, "blender-origine-centro.png"))
    # the Epochs look
    for ob, t in units:
        ob.data.materials.clear()
        ob.data.materials.append(bpy.data.materials["ep_Roman"])
    ts.apply_threed_mode(bpy.context, pairs, "Epochs")
    render(os.path.join(SHOTS, "blender-epoche.png"))
    for ob, t in units:
        ob.data.materials.clear()
        ob.data.materials.append(bpy.data.materials[t])
    ts.apply_threed_mode(bpy.context, pairs, "EM")

# the edges follow their proxy
edges = {o.parent.name: o for o in bpy.data.collections[ts.EDGES_COLLECTION].objects}
units[3][0].hide_set(True)
ts.sync_edges_visibility(sc)
check("USNt hidden → its edges hidden", edges["USNt4"].hide_get() is True)
units[3][0].hide_set(False)
ts.sync_edges_visibility(sc)
check("…shown again", edges["USNt4"].hide_get() is False)

fn._drop_type_edges()
left = len(bpy.data.collections[ts.EDGES_COLLECTION].objects)
check("the clean-up takes the edges away", left == 0, left)
ts.apply_threed(bpy.context, pairs)
check("EM draws them again", len(bpy.data.collections[ts.EDGES_COLLECTION].objects) == 4)

# decision 4: the same scene with every origin at 0,0,0 (no change to the data
# of a real file: here the test builds its own proxies)
if SHOTS:
    for ob, _ in units:
        bpy.data.objects.remove(ob, do_unlink=True)
    ts.remove_all_edges()
    CENTRE[0] = False
    units = [(proxy("US1", box(-3.6, -1.2, -1.4, -1.3, 1.2, 0)), "US"),
             (proxy("USN2", frustum(1.1, 0.55, -1.4, 0)), "USN"),
             (proxy("US3", frustum(0.82, 0.5, -1.35, -0.55)), "US"),
             (proxy("USNt4", box(1.8, -1, -1.4, 3.8, 1, 0.6)), "USNt")]
    pairs = []
    for ob, t in units:
        ob.data.materials.append(bpy.data.materials[t])
        pairs.append((ob, t))
    check("origins at 0,0,0", all(tuple(ob.location) == (0, 0, 0) for ob, _ in units))
    ts.apply_threed(bpy.context, pairs)
    render(os.path.join(SHOTS, "blender-origine-zero.png"))
    # the same with the old method, for the comparison (Blended sorts by origin)
    for t in ("US", "USN", "USNt"):
        bpy.data.materials[t].surface_render_method = "BLENDED"
        bpy.data.materials[t].use_backface_culling = False
    render(os.path.join(SHOTS, "blender-origine-zero-PRIMA-blended.png"))

with open(OUT, "w") as fh:
    json.dump(RESULTS, fh, indent=1)
fails = [r for r in RESULTS if not r["ok"]]
print(f"[SMOKE] {len(RESULTS) - len(fails)}/{len(RESULTS)} passed")
sys.exit(1 if fails else 0)
