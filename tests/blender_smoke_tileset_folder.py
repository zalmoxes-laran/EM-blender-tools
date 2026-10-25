"""Headless smoke · MICRO tileset-cartella (25 Oct 2026): a tileset as it
arrives — a folder, the RealityScan pair, a zip without its root — through
«Shall I prepare it?» into «Add Cesium Tileset» and the container's
alternative. On a COPY of the GT16 (never the originals)::

    rm -rf /tmp/emt-tsc && mkdir -p /tmp/emt-tsc && cp -R /tmp/emt-georef-save/EM \\
        /tmp/emt-georef-save/SB /tmp/emt-tsc/
    EM_TSC_DIR=/tmp/emt-tsc \\
    "/Applications/Blender 520.app/Contents/MacOS/Blender" -b --python-use-system-env \\
        /tmp/emt-tsc/SB/GreatTemple_2026_v2.blend \\
        --python ~/Documents/GitHub/EM-blender-tools/tests/blender_smoke_tileset_folder.py

A dialog cannot open in -b: «Prepare» runs with EXEC (its invoke measures the
same way, ``_measure``), the alternative's dialog is measured then run.
The tilesets are small RealityScan-shaped fixtures written here, with the
Basilica Iulia's root transform (the geocentric warning).
"""
import importlib
import json
import os
import shutil
import sys
import zipfile

import bpy

FAILURES = []
DIR = os.environ.get("EM_TSC_DIR", "/tmp/emt-tsc")
EMJSON = os.path.join(DIR, "EM", "TempluMare_v4.em.json")
#: outside the project, as the Desktop is: the package is copied into RM/tilesets
FIX = DIR.rstrip("/") + "-incoming"
BASILICA_T = [-0.18243234, 0.98321841, 0.0, 0.0, -0.00000197, -0.00000036, 1.0, 0.0,
              0.98321841, 0.18243234, 0.000002, 0.0,
              6271103.68898329, 1163587.9280063, 12.30476309, 1.0]


def check(label, condition, detail=""):
    print(f"[SMOKE] {'PASS' if condition else 'FAIL'}: {label} {detail}")
    if not condition:
        FAILURES.append(label)


names = [n for n in sys.modules if n.endswith(".rm_manager.alternative_operators")
         and n.startswith("bl_ext.")]
PKG = names[0].rsplit(".rm_manager.alternative_operators", 1)[0]
print("[SMOKE] package:", PKG)
ao = importlib.import_module(PKG + ".rm_manager.alternative_operators")
tsh = importlib.import_module(PKG + ".rm_manager.tileset_shape")


def rs_export(where, name):
    """RealityScan's shape: name.json (the root) beside name/."""
    d = os.path.join(where, name, "Geometry")
    os.makedirs(d, exist_ok=True)
    for i in range(3):
        with open(os.path.join(d, f"lod1_{i}.b3dm"), "wb") as f:
            f.write(b"b3dm" + bytes([i]) * 200)
    with open(os.path.join(where, name, "tileset_lod1_0.json"), "w") as f:
        json.dump({"asset": {"version": "1.0"}, "geometricError": 0.1,
                   "root": {"boundingVolume": {"box": [0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1]},
                            "geometricError": 0, "content": {"url": "Geometry/lod1_1.b3dm"}}}, f)
    with open(os.path.join(where, f"{name}.json"), "w") as f:
        json.dump({"asset": {"version": "1.0", "extras": {"createdWith": "RealityScan 2.2.0.119430"}},
                   "geometricError": 54.8,
                   "root": {"boundingVolume": {"box": [0, 0, 5, 40, 0, 0, 0, 20, 0, 0, 0, 6]},
                            "geometricError": 0.9, "refine": "REPLACE", "transform": BASILICA_T,
                            "content": {"url": f"{name}/Geometry/lod1_0.b3dm"},
                            "children": [{"boundingVolume": {"box": [0, 0, 5, 20, 0, 0, 0, 10, 0, 0, 0, 3]},
                                          "geometricError": 0.1,
                                          "content": {"url": f"{name}/tileset_lod1_0.json"}}]}}, f)
    return os.path.join(where, name)


def listing(top):
    return sorted((os.path.relpath(os.path.join(d, f), top), os.path.getsize(os.path.join(d, f)))
                  for d, _s, fs in os.walk(top) for f in fs)


shutil.rmtree(FIX, ignore_errors=True)
os.makedirs(FIX)
pair_dir = os.path.join(FIX, "pair")
os.makedirs(pair_dir)
rs_export(pair_dir, "tileset_Basilica_TLS_ED")
alone_dir = os.path.join(FIX, "alone")
os.makedirs(alone_dir)
rs_export(alone_dir, "tileset_B")
with zipfile.ZipFile(os.path.join(alone_dir, "Archivio.zip"), "w") as z:
    for d, _s, fs in os.walk(os.path.join(alone_dir, "tileset_B")):
        for f in fs:
            p = os.path.join(d, f)
            z.write(p, os.path.relpath(p, alone_dir).replace(os.sep, "/"))
shutil.rmtree(os.path.join(alone_dir, "tileset_B"))    # the zip and its root beside it
nothing = os.path.join(FIX, "nothing.zip")
with zipfile.ZipFile(nothing, "w") as z:
    z.writestr("some/notes.txt", "x")
before_pair = listing(pair_dir)

# ── the graph ────────────────────────────────────────────────────────────────
scene = bpy.context.scene
em = scene.em_tools
em.graphml_files.clear()
em.active_file_index = -1
r = getattr(bpy.ops, "import").em_emjson(filepath=EMJSON)
graph = ao._graph(bpy.context)
check("the GT16 copy is loaded", r == {"FINISHED"} and graph is not None and len(em.epochs.list) > 0,
      f"{r} epochs={len(em.epochs.list)}")
em.epochs.list_index = 0
w = ao.writer_3tz()
print("[SMOKE] 3DSC .3tz writer:", w)

# ── the forms, as the dialog reads them ─────────────────────────────────────
rec = tsh.recognise(os.path.join(pair_dir, "tileset_Basilica_TLS_ED"))
pos = tsh.position(rec["root_doc"])
print("[SMOKE] dialog ·", rec["says"])
print("[SMOKE] dialog ·", pos["line"])
check("the pair is the RealityScan form, preparable", rec["form"] == "pair" and rec["preparable"])
check("the position line warns: geocentric", pos["warn"] and "geocentric" in pos["line"])

# ── «Add Cesium Tileset» on the folder X/ ───────────────────────────────────
before = set(bpy.data.objects.keys())
r = bpy.ops.rm.tileset_prepare('EXEC_DEFAULT', path=os.path.join(pair_dir, "tileset_Basilica_TLS_ED"),
                               then='ADD')
new = [bpy.data.objects[n] for n in set(bpy.data.objects.keys()) - before]
obj = next((o for o in new if "tileset_path" in o), None)
pk = os.path.join(pair_dir, "tileset_Basilica_TLS_ED" + (".3tz" if w else ".zip"))
check("prepared beside the original, then added to the epoch",
      r == {"FINISHED"} and os.path.isfile(pk) and obj is not None,
      f"{r} {pk} {obj and obj.name} {obj and obj['tileset_path']}")
with zipfile.ZipFile(pk) as z:
    nm = z.namelist()
check("the package: tileset.json at its root, the folder beside it",
      "tileset.json" in nm and "tileset_Basilica_TLS_ED/Geometry/lod1_0.b3dm" in nm, str(nm[:4]))
check("the original is untouched (only the package was added beside it)",
      [x for x in listing(pair_dir) if x[0] != os.path.basename(pk)] == before_pair)
if obj is not None:
    check("the package entered the project's storage (RM/tilesets)",
          "RM/tilesets/tileset_Basilica_TLS_ED" in obj["tileset_path"].replace(os.sep, "/"),
          obj["tileset_path"])
    check("its name is the RealityScan root's", obj.name.startswith("tileset_Basilica_TLS_ED"), obj.name)

# a second time: never over the first package
r = bpy.ops.rm.tileset_prepare('EXEC_DEFAULT', path=os.path.join(pair_dir, "tileset_Basilica_TLS_ED.json"),
                               then='ADD')
pk2 = os.path.join(pair_dir, "tileset_Basilica_TLS_ED-2" + (".3tz" if w else ".zip"))
check("chosen again (as X.json): a -2 beside, the first not written over",
      r == {"FINISHED"} and os.path.isfile(pk2))

# ── the zip without its root, the root beside it ────────────────────────────
r = bpy.ops.rm.tileset_prepare('EXEC_DEFAULT', path=os.path.join(alone_dir, "Archivio.zip"), then='ADD')
pk3 = os.path.join(alone_dir, "tileset_B" + (".3tz" if w else ".zip"))
check("Archivio.zip + tileset_B.json beside: prepared and added", r == {"FINISHED"} and os.path.isfile(pk3))

# ── what cannot become a package: the message says what is inside ──────────
try:
    r = bpy.ops.rm.add_tileset('EXEC_DEFAULT', filepath=nothing)
except RuntimeError as exc:                     # an ERROR report raises in -b
    print("[SMOKE] the report ·", exc)
    r = {"CANCELLED"}
says = tsh.recognise(nothing)["says"]
print("[SMOKE] error ·", says)
check("a zip with no tileset: cancelled, the message lists the contents",
      r == {"CANCELLED"} and "some/ (0 json, 0 tiles)" in says)

# ── the container's alternative ─────────────────────────────────────────────
ci = next((i for i, c in enumerate(scene.rm_containers) if len(c.mesh_names)), -1)
if ci < 0:
    c = scene.rm_containers.add()
    c.label = "SmokeTSC"
    for o in scene.objects:
        if o.type == "MESH":
            e = c.mesh_names.add()
            e.name = o.name
            break
    ci = len(scene.rm_containers) - 1
scene.rm_containers_index = ci
cont = scene.rm_containers[ci]
folder = os.path.join(FIX, "ready")
os.makedirs(folder)
rs_export(folder, "tileset_C")
shutil.move(os.path.join(folder, "tileset_C.json"), os.path.join(folder, "tileset.json"))
rec = tsh.recognise(folder)
check("a folder with tileset.json: ready and preparable", rec["form"] == "folder" and rec["ready"])
r = bpy.ops.rm.tileset_prepare('EXEC_DEFAULT', path=folder, then='ALTERNATIVE', container_index=ci,
                               choice='PACK')
print(f"[SMOKE] alternative from a folder (PACK): {r} → «{cont.alt_name}» {cont.alt_asset_id}")
check("the folder → package → the container's alternative",
      r == {"FINISHED"} and bool(cont.alt_asset_id)
      and os.path.isfile(folder + (".3tz" if w else ".zip")))
r = ao.route_tileset(type("Op", (), {"report": lambda *a: None})(), nothing, 'ALTERNATIVE')
check("the alternative refuses the zip with no tileset, with the message", r == {'CANCELLED'})

print("[SMOKE] RESULT:", "ALL PASS" if not FAILURES else f"FAILURES: {FAILURES}")
sys.stdout.flush()
os._exit(0 if not FAILURES else 1)
