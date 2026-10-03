"""Headless smoke · T-M1 + T-G1 (MICRO-ASSET-VERSIONI-E-SCENE-MULTIGRAFO).

NOT a pytest test (needs bpy). Run inside Blender with the EM-tools extension
enabled (no --factory-startup: the extension must load):

    EM_M1_WORK=/tmp/micro-asset-versioni/m1g1 \\
    EM_M1_SOURCE=/tmp/micro-asset-versioni/Temple_20260930.em.json \\
    "/Applications/Blender 520.app/Contents/MacOS/Blender" -b \\
        --python tests/blender_smoke_multigraph_tree.py

Optional, for the different-EPSG case through the server:
    EM_ROOM_URL=http://localhost:8000 EM_ROOM_TOKEN=<dev token>
    EM_G1_EXPECT_CONV=<pyproj convergence 33N→32N at the anchor, degrees>

T-M1 · two containers in one scene → two branches; «Save» of the graph of the
second file rewrites ONLY that file (sha256 of both before/after); a third file
holding a graph already open is refused; the origins survive a .blend save.
T-G1 · same EPSG, different shifts → relative position to 1 mm, and a second
«Align» does not move twice; different EPSG → the Z rotation is computed through
/v1/reproject and declared; with no server and no pyproj the refusal says so.

Writes only under EM_M1_WORK (copies). Exits non-zero on failure.
"""
import copy
import hashlib
import json
import math
import os
import shutil
import sys
import uuid

import bpy

FAILURES = []


def check(label, condition, detail=""):
    print(f"[SMOKE] {'PASS' if condition else 'FAIL'}: {label} {detail}")
    if not condition:
        FAILURES.append(label)
    return condition


def sha(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def module(suffix):
    names = [n for n in sys.modules if n.endswith(suffix) and n.startswith("bl_ext.")]
    if not names:
        print(f"[SMOKE] aborting: {suffix} not loaded — enable the extension")
        sys.exit(1)
    return sys.modules[names[0]]


origins = module(".graph_origins")
IMPORT = getattr(bpy.ops, "import")      # `import` is a keyword
import importlib                                                     # noqa: E402
_pkg = origins.__name__.rsplit(".graph_origins", 1)[0]
room_session = importlib.import_module(_pkg + ".sync_manager.room_session")
room_cfg = importlib.import_module(_pkg + ".sync_manager.room")

WORK = os.environ.get("EM_M1_WORK", "/tmp/micro-asset-versioni/m1g1")
SOURCE = os.environ.get("EM_M1_SOURCE",
                        "/tmp/micro-asset-versioni/Temple_20260930.em.json")
os.makedirs(WORK, exist_ok=True)
A = os.path.join(WORK, "TempioGrande.em.json")
B = os.path.join(WORK, "TempioAccanto.em.json")
C = os.path.join(WORK, "CopiaDiA.em.json")

REF_SHIFT = (291960.5, 4640631.8, 12.0)
B_SHIFT = (292010.25, 4640600.3, 14.5)

# ── the two containers: A = a copy of Temple, B = Temple with its own graph id
doc = json.load(open(SOURCE, encoding="utf-8"))
gid_a = doc["active_graph_id"]


def set_geo(section, epsg, shift):
    for n in section["nodes"]:
        if n.get("node_type") == "geo_position":
            n["data"] = {"epsg": epsg, "shift_x": shift[0], "shift_y": shift[1],
                         "shift_z": shift[2], "rotation": 0.0}


doc_a = copy.deepcopy(doc)
set_geo(doc_a["graphs"][gid_a], 32633, REF_SHIFT)
json.dump(doc_a, open(A, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

gid_b = str(uuid.uuid5(uuid.NAMESPACE_URL, "em:micro-m1:tempio-accanto"))
doc_b = copy.deepcopy(doc)
sec = doc_b["graphs"].pop(gid_a)
sec["graph_id"] = gid_b
sec["name"] = "Tempio accanto"
set_geo(sec, 32633, B_SHIFT)
doc_b["graphs"] = {gid_b: sec, "shelf": doc_b["graphs"]["shelf"]}
doc_b["active_graph_id"] = gid_b
doc_b.pop("layout", None)
json.dump(doc_b, open(B, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
shutil.copyfile(A, C)

# ── T-M1 · two branches ──────────────────────────────────────────────────────
scene = bpy.context.scene
em = scene.em_tools
while len(em.graphml_files):
    em.graphml_files.remove(0)
scene.em_georef.reference_graph = ""
r1 = IMPORT.em_emjson(filepath=A)
r2 = IMPORT.em_emjson(filepath=B)
check("both containers load", r1 == {"FINISHED"} and r2 == {"FINISHED"}, f"{r1} {r2}")
for row in em.graphml_files:
    row.graph_code = "GT16" if row.name == gid_a else "GT17"
tree = origins.tree(em.graphml_files, abspath=bpy.path.abspath)
labels = [o.label for o, _ in tree]
check("the tree has two branches, one per file",
      labels == ["TempioGrande.em.json", "TempioAccanto.em.json"], str(labels))
check("each branch holds its own graph",
      [[em.graphml_files[i].name for i in ix] for _o, ix in tree] == [[gid_a], [gid_b]])
check("the first graph loaded is the scene's reference",
      scene.em_georef.reference_graph == gid_a, scene.em_georef.reference_graph)

# a third file carrying a graph already open from A is refused
before_rows = len(em.graphml_files)
try:
    r3 = IMPORT.em_emjson(filepath=C)
except RuntimeError as exc:          # the operator reports ERROR → RuntimeError
    r3 = {"CANCELLED"}
    print(f"[SMOKE] refused as expected: {str(exc).strip()[:160]}")
check("the same graph from a second file is refused",
      r3 == {"CANCELLED"} and len(em.graphml_files) == before_rows)

# ── save B only: A stays byte-identical ──────────────────────────────────────
sha_before = {"A": sha(A), "B": sha(B)}
from s3dgraphy import get_graph                                      # noqa: E402
from s3dgraphy.nodes.stratigraphic_node import StratigraphicUnit     # noqa: E402

idx_b = next(i for i, r in enumerate(em.graphml_files) if r.name == gid_b)
bpy.ops.em.graph_activate(index=idx_b)
check("activating B makes it the active graph", em.active_file_index == idx_b)
get_graph(gid_b).add_node(StratigraphicUnit(node_id="m1-new-us", name="US 999"))
r_save = bpy.ops.export.em_save()
sha_after = {"A": sha(A), "B": sha(B)}
print(f"[SMOKE] sha256 A before {sha_before['A'][:16]} after {sha_after['A'][:16]}")
print(f"[SMOKE] sha256 B before {sha_before['B'][:16]} after {sha_after['B'][:16]}")
check("Save finished", r_save == {"FINISHED"}, str(r_save))
check("A untouched (sha256 identical)", sha_before["A"] == sha_after["A"])
check("B rewritten (sha256 changed)", sha_before["B"] != sha_after["B"])
saved_b = json.load(open(B, encoding="utf-8"))
check("B holds its own graph and its shelf only",
      sorted(saved_b["graphs"]) == sorted([gid_b, "shelf"]), str(sorted(saved_b["graphs"])))
check("B carries the edit",
      any(n.get("id") == "m1-new-us" for n in saved_b["graphs"][gid_b]["nodes"]))
check("A's graph did not enter B", gid_a not in saved_b["graphs"])

# ── T-G1 · same EPSG, different shifts ───────────────────────────────────────
for ob in list(bpy.data.objects):
    if ob.name.startswith(("GT16.probe", "GT17.probe")):
        bpy.data.objects.remove(ob)
probe_a = bpy.data.objects.new("GT16.probe", None)
probe_b = bpy.data.objects.new("GT17.probe", None)
for ob in (probe_a, probe_b):
    scene.collection.objects.link(ob)
LOCAL_B = (3.0, -7.5, 1.25)
probe_b.location = LOCAL_B
r_al = bpy.ops.em.georef_align_graphs()
row_b = em.graphml_files[idx_b]
want = tuple(B_SHIFT[k] + LOCAL_B[k] - REF_SHIFT[k] for k in range(3))
got = tuple(probe_b.matrix_world.translation)
err = max(abs(a - b) for a, b in zip(got, want))
check("same EPSG: relative position within 1 mm", err < 1e-3,
      f"got {tuple(round(v, 4) for v in got)} want {tuple(round(v, 4) for v in want)} err {err:.2e} m")
check("the reference graph's objects did not move",
      tuple(probe_a.matrix_world.translation) == (0.0, 0.0, 0.0))
check("what was applied is declared on the graph",
      "difference of the shifts" in row_b.geo_note, row_b.geo_note)
bpy.ops.em.georef_align_graphs()
got2 = tuple(probe_b.matrix_world.translation)
check("a second Align does not move twice",
      max(abs(a - b) for a, b in zip(got2, want)) < 1e-3)

# ── T-G1 · different EPSG ────────────────────────────────────────────────────
geo_b = None
for n in get_graph(gid_b).nodes:
    if getattr(n, "node_type", "") == "geo_position":
        geo_b = n
# B declared in UTM 32N: the same place, the other zone. The 32N coordinates of
# B_SHIFT come from pyproj, outside Blender (EM_G1_B32N="x,y"); without them the
# anchor is 100 m off and only the rotation is checked.
b32 = os.environ.get("EM_G1_B32N", "789796.43,4643459.56").split(",")
geo_b.data.update({"epsg": 32632, "shift_x": float(b32[0]),
                   "shift_y": float(b32[1])})

# 1 · no server → local pyproj, when Blender's Python has it (measured: it does
# when BlenderGIS/3DSC bring it); 2 · neither → the refusal says what is needed
graph_align = importlib.import_module(_pkg + ".georef_manager.graph_align")
room_cfg.set_room(None, None, None)
scene.em_room_url = ""
if graph_align.pyproj_reprojector() is not None:
    import pyproj                                                    # noqa: E402
    print(f"[SMOKE] pyproj {pyproj.__version__} in Blender: {pyproj.__file__}")
    bpy.ops.em.georef_align_graphs()
    check("different EPSG, no server: reprojected via local pyproj",
          "via pyproj" in row_b.geo_note, row_b.geo_note)
_real = graph_align.pyproj_reprojector
graph_align.pyproj_reprojector = lambda: None
try:
    bpy.ops.em.georef_align_graphs()
finally:
    graph_align.pyproj_reprojector = _real
check("different EPSG, no server and no pyproj: refused and said",
      "reprojection is needed" in row_b.geo_note and "pyproj" in row_b.geo_note,
      row_b.geo_note)

# 2 · the server's /v1/reproject
url = os.environ.get("EM_ROOM_URL", "")
token = os.environ.get("EM_ROOM_TOKEN", "")
expect = os.environ.get("EM_G1_EXPECT_CONV", "")
if url and token:
    room_cfg.set_room(url, "m1g1-probe", token)
    bpy.ops.em.georef_align_graphs()
    print(f"[SMOKE] declared: {row_b.geo_note}")
    check("different EPSG: reprojected via the server",
          "via server" in row_b.geo_note, row_b.geo_note)
    rot = math.degrees(probe_b.matrix_world.to_euler().z)
    check("the Z rotation applied is the declared one",
          abs(rot - row_b.geo_rot_z) < 1e-4, f"{rot:.6f} vs {row_b.geo_rot_z:.6f}")
    if expect:
        check("…and equals pyproj's convergence (computed independently)",
              abs(row_b.geo_rot_z - float(expect)) < 1e-3,
              f"{row_b.geo_rot_z:.6f}° vs pyproj {float(expect):.6f}°")
    if os.environ.get("EM_G1_B32N"):
        got3 = tuple(probe_b.matrix_world.translation)
        # the local point, rotated by the convergence, around B's anchor which
        # reprojects back onto B_SHIFT in 33N
        a = math.radians(row_b.geo_rot_z)
        lx = math.cos(a) * LOCAL_B[0] - math.sin(a) * LOCAL_B[1]
        ly = math.sin(a) * LOCAL_B[0] + math.cos(a) * LOCAL_B[1]
        want3 = (B_SHIFT[0] - REF_SHIFT[0] + lx, B_SHIFT[1] - REF_SHIFT[1] + ly)
        err3 = max(abs(got3[0] - want3[0]), abs(got3[1] - want3[1]))
        check("…and B's origin lands where 33N puts it (round trip, 1 cm)",
              err3 < 1e-2, f"err {err3:.2e} m")
else:
    print("[SMOKE] SKIP server case: set EM_ROOM_URL and EM_ROOM_TOKEN")

# ── the origins survive the .blend ───────────────────────────────────────────
blend = os.path.join(WORK, "m1g1_scene.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend, copy=True)
print(f"[SMOKE] saved {blend} for the reopen check")

print(f"[SMOKE] {'OK' if not FAILURES else 'FAILED: ' + ', '.join(FAILURES)}")
sys.exit(1 if FAILURES else 0)
