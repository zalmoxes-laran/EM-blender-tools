"""Headless smoke · MICRO-BLEND-OFFICINA-2 (E.D.'s answers of 31 Oct 2026) on a
COPY of Templu Mare, Blender 5.2, EM Tools and 3D Survey Collection as the
working copies, s3dgraphy ≥ 1.6.0.dev79 (PYTHONPATH)::

    BO_PROJECT=/tmp/officina2/A3 PYTHONPATH=~/Documents/GitHub/s3Dgraphy/src \\
    BLENDER_USER_RESOURCES=<profile with 3DSC> \\
    "/Applications/Blender 520.app/Contents/MacOS/Blender" -b --python-use-system-env \\
        --python-exit-code 1 /tmp/officina2/A3/SB/GreatTemple_2026_v2.blend \\
        --python tests/blender_smoke_blend_officina_2.py

Detail on request on the RB tileset (light set, more detail here, less,
the recipe, the cache refused as a master and as a document), the crop of an
RB master at 5 cm through 3DSC, the selection's ids, the lease (read-only →
the save goes to a new version with the person's name). The .blend held and
the em.json are never written."""
import json
import os
import sys
import time

import bpy

PROJECT = os.environ.get("BO_PROJECT", "/tmp/officina2/A3")
FAILURES = []


def check(label, condition, detail=""):
    print(f"[SMOKE] {'PASS' if condition else 'FAIL'}: {label} {detail}")
    if not condition:
        FAILURES.append(label)
    return condition


def mod(suffix):
    for name, m in sys.modules.items():
        if name.endswith(suffix):
            return m
    raise RuntimeError(suffix + " not loaded")


BO = mod(".sync_manager.blend_officina")
BD = mod(".sync_manager.blend_detail")
BL = mod(".sync_manager.blend_lease")
OPS = mod(".sync_manager.operators")
from s3dgraphy.resources import detail as D  # noqa: E402

held = bpy.data.filepath
held_mtime = os.path.getmtime(held)
emjson = os.path.join(PROJECT, "EM", "TempluMare_v6_optimized.em.json")
em_bytes = open(emjson, "rb").read()
emt = bpy.context.scene.em_tools
emt.graphml_files.clear()
row = emt.graphml_files.add()
row.name = "TempluMare_v6"
row.graphml_path = emjson
emt.active_file_index = 0
getattr(bpy.ops, "import").em_emjson(file_index=0)
graph, _doc, em_folder = BO.active_graph_doc(bpy.context)
check("graph loaded", graph is not None)
ctx = bpy.context

# ── point 1 · the light set of the RB tileset (.3tz)
tz = os.path.join(PROJECT, "RB", "cesium", "TempluMare.3tz")
plan = BD.plan_light(ctx, tz, None)
check("light set planned with its estimate", plan["cut"] == ["Data/a.b3dm"] and plan["estimate"]["ram_mb"] < 5,
      plan["estimate"]["say"])
got = BD.do_load_set(ctx, tz, None)
objs = [o for o in bpy.data.objects if o.get(BD.P_TILE)]
check("light set loaded into «Detail (cache)»", len(objs) >= 1 and all(
    BD.COLLECTION in [c.name for c in o.users_collection] for o in objs), [o.name for o in objs])
files = os.listdir(got["folder"])
check("in em_cache/local/detail/<key>/ with the texture outside", "/em_cache/local/detail/" in got["folder"]
      and any(f.endswith(".gltf") for f in files) and any(f.endswith(".jpg") for f in files), files)
tile = objs[0]
from mathutils import Vector  # noqa: E402
tb = [tile.matrix_world @ Vector(c) for c in tile.bound_box]
rb_obj = bpy.data.objects.get("ME_PODIO_LOD1")
if rb_obj is not None:
    rbb = [rb_obj.matrix_world @ Vector(c) for c in rb_obj.bound_box]
    lo = [min(p[i] for p in tb) for i in range(3)]
    hi = [max(p[i] for p in tb) for i in range(3)]
    rlo = [min(p[i] for p in rbb) for i in range(3)]
    rhi = [max(p[i] for p in rbb) for i in range(3)]
    overlap = all(lo[i] <= rhi[i] and rlo[i] <= hi[i] for i in range(3))
    print(f"[SMOKE] frame: tile {[round(v, 1) for v in lo + hi]} · RB podium {[round(v, 1) for v in rlo + rhi]}")
    check("the tiles sit where the RB models sit (same frame)", overlap)

# more detail on a 4 m column inside the tile's box
cx, cy = (tb[0][0] + tb[6][0]) / 2, (tb[0][1] + tb[6][1]) / 2
tree, _rb = BD.open_tileset(tz)
leaf = [n for n in tree["nodes"].values() if n["depth"] == 7][2000]
b = leaf["aabb"]
cx, cy = (b[0] + b[3]) / 2, (b[1] + b[4]) / 2
area = [cx - 2, cy - 2, b[2] - 5, cx + 2, cy + 2, b[5] + 5]
p1 = BD.plan_more(ctx, area, "next")
check("one level more: planned with the estimate", p1["load"] and p1["estimate"]["pieces"] == len(p1["load"]),
      p1["estimate"]["say"])
m1 = BD.do_more(ctx, area, "next")
check("one level more: loaded, the root dropped", m1["dropped"] == 1 and m1["loaded"] == len(p1["load"]), m1["said"])
pd = BD.plan_more(ctx, area, "densest")
md = BD.do_more(ctx, area, "densest")
st = BD.get_state(ctx)
deep = max(tree["nodes"][n]["depth"] for n in st["cut"])
check("densest where asked", deep >= 6, f"{len(st['cut'])} tiles, deepest {deep}; {pd['estimate']['say']}")
n_tiles = len([o for o in bpy.data.objects if o.get(BD.P_TILE)])
check("the objects are the cut", n_tiles >= len(st["cut"]), f"{n_tiles} objects for {len(st['cut'])} tiles")
check("the recipe is kept", len(st["recipes"]) == 3, [r["key"] for r in st["recipes"]])
less = BD.do_less(ctx, area, "light")
st = BD.get_state(ctx)
check("less detail: back to the light set", st["cut"] == ["Data/a.b3dm"], less)
check("less detail: the objects freed", len([o for o in bpy.data.objects if o.get(BD.P_TILE)]) <= 2)

# the cache is never a master, never a version, never a document
tile = [o for o in bpy.data.objects if o.get(BD.P_TILE)][0]
try:
    BO.export_master(ctx, graph, tile, emjson)
    check("a detail refused as a master", False)
except RuntimeError as exc:
    check("a detail refused as a master", "cache" in str(exc), str(exc))
try:
    BO.register_version(ctx, graph, tile, emjson)
    check("a detail refused as a version", False)
except RuntimeError as exc:
    check("a detail refused as a version", "cache" in str(exc))
import importlib  # noqa: E402
R = importlib.import_module(BO.__name__.rsplit(".sync_manager", 1)[0] + ".em_setup.resource_utils")
unit = next(n for n in graph.nodes if getattr(n, "node_type", "") == "US")
cache_file = os.path.join(got["folder"], files[0])
doc_node = next(n for n in graph.nodes if getattr(n, "node_type", "") == "document")
D.add_recipe(doc_node.data, D.recipe(document=doc_node.node_id, source="x", area=[0, 0, 0, 1, 1, 1]))
key = doc_node.data["detail_recipes"][-1]["key"]
fake = os.path.join(em_folder, "em_cache", "local", "detail", key, "Data_a.gltf")
cited = R.create_document_for_resource(graph, unit, fake, "Data_a.gltf", "main", em_folder)
check("a cache file cites its recipe's DOCUMENT", cited is doc_node, getattr(cited, "name", cited))
try:
    R.create_document_for_resource(graph, unit, cache_file, files[0], "main", em_folder)
    check("a cache file with no recipe in the graph is refused", False)
except ValueError as exc:
    check("a cache file with no recipe in the graph is refused", "cite the document" in str(exc))

# ── point 1 · the crop of a master (3DSC) at 5 cm, and 1 cm refused on a big area
src = os.path.join(PROJECT, "RB", "LOD0", "OB_INT_L_LOD0.obj")
big = [0, 0, 0, 20, 20, 5]
check("1 cm refused on 20 m", not D.crop_plan(big, 0.01)["ok"])
# the area: the middle of the object's box, 4 m
bpy.ops.wm.obj_import(filepath=src)
o = [x for x in bpy.data.objects if x.name.startswith("OB_INT_L")][0]
pts = [o.matrix_world @ Vector(c) for c in o.bound_box]
lo = [min(p[i] for p in pts) for i in range(3)]
hi = [max(p[i] for p in pts) for i in range(3)]
c = [(lo[i] + hi[i]) / 2 for i in range(3)]
carea = [c[0] - 2, c[1] - 2, lo[2], c[0] + 2, c[1] + 2, hi[2]]
mesh = o.data
bpy.data.objects.remove(o, do_unlink=True)
bpy.data.meshes.remove(mesh)
t0 = time.time()
crop = BD.crop_into_cache(ctx, src, carea, 0.05, document=doc_node.node_id, resource="")
print("[SMOKE] crop:", {k: crop["result"][k] for k in ("triangles", "source_triangles", "faces_in_box", "files")},
      round(time.time() - t0, 1), "s")
check("crop at 5 cm into the cache, textures outside", crop["result"]["ok"] and any(
    f.endswith(".jpg") for f in crop["result"]["files"]) and "/em_cache/local/detail/" in crop["result"]["path"])
check("the crop is imported as detail", all(bpy.data.objects[n].get(BD.P_RECIPE) for n in crop["objects"]))
check("the crop's recipe is in the document", any(r.get("kind") == "crop" for r in doc_node.data["detail_recipes"]),
      crop["said"])

# ── point 3 · the selection's ids for any object
arch = bpy.data.objects["Architrave_1_BAKE_SM_Architrave_1_BAKE"]
nid = OPS._node_id_for_object(arch, graph)
check("an architecture → its RM id", nid == arch.get("em_rm_node_id"), nid)
check("…and back", [x.name for x in OPS._objects_for_ids([nid])] == [arch.name])
OPS._apply_incoming_select(nid, ctx, graph)
check("an incoming RM id selects the object", arch.select_get())

# ── point 6 · the lease (a fake joined room that keeps leases)
from s3dgraphy.resources import blend_room as BR  # noqa: E402
sent = []


class FakeSession:
    joined = True
    holds_supported = True
    author = "elisa"
    role = "editor"
    leases = []

    def send_hold(self, action, key, host="", force=False):
        sent.append((action, key))
        return True


fake_s = FakeSession()
BL._session = lambda: fake_s
st = BL.tick(ctx, headless=True)
check("free → take", sent and sent[-1][0] == "take" and sent[-1][1] == "SB/GreatTemple_2026_v2.blend", sent)
fake_s.leases = [BR.lease_record("SB/GreatTemple_2026_v2.blend", person="ed", display="Emanuel", host="mac-ed")]
st = BL.tick(ctx, headless=True)
check("held by another → read only, said", st["mode"] == "readonly" and st["say"].startswith("aperto da Emanuel"),
      st["say"])
bpy.context.scene["em_smoke_change"] = 1
bpy.ops.ed.undo_push(message="change")
check("a change made read-only", bpy.data.is_dirty)
BL.tick(ctx, headless=True)
check("…goes to a new version with the person's name",
      bpy.data.filepath.endswith(f"versions/GreatTemple_2026_v2@manual-{time.strftime('%Y-%m-%d')}-elisa.blend"),
      bpy.data.filepath)
check("the held .blend was not written", os.path.getmtime(held) == held_mtime)
check("the em.json was not written", open(emjson, "rb").read() == em_bytes)

print("[SMOKE] " + ("ALL PASS" if not FAILURES else f"FAILED: {FAILURES}"))
if FAILURES:
    sys.exit(1)
