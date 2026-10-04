"""Headless smoke · T-D1, the level, uses and measures of a version — in Blender.

NOT a pytest test (needs bpy). With s3Dgraphy from source:

    PYTHONPATH=~/Documents/GitHub/s3Dgraphy/src \\
    "/Applications/Blender 520.app/Contents/MacOS/Blender" -b --python-use-system-env \\
        --python tests/blender_smoke_lod_levels.py

A master mesh (a subdivided, textured grid of 10 × 10 m) bound to a master
resource; «Add version…» three times, each from the version the object shows:
master → lod0 → lod1 → lod2. Then: levels computed, measures present (tris/m²,
texel side in the form of the formula, atlases, UV), the em.json written with
``lod_level``, reloaded with no warning; the same file with one ``lod_level``
falsified is reloaded and its entry's warnings say so (what the panel lists).
"""
import importlib
import json
import os
import sys
import tempfile

import bpy

FAILURES = []


def check(label, condition, detail=""):
    print(f"[SMOKE] {'PASS' if condition else 'FAIL'}: {label} {detail}")
    if not condition:
        FAILURES.append(label)
    return condition


names = [n for n in sys.modules if n.endswith(".graph_origins") and n.startswith("bl_ext.")]
if not names:
    print("[SMOKE] aborting: the extension is not loaded")
    sys.exit(1)
PKG = names[0].rsplit(".graph_origins", 1)[0]
av = importlib.import_module(PKG + ".sync_manager.asset_versions")
IMPORT = getattr(bpy.ops, "import")

import s3dgraphy                                                   # noqa: E402
from s3dgraphy import api                                          # noqa: E402
from s3dgraphy.graph import Graph                                  # noqa: E402
from s3dgraphy.multigraph.multigraph import multi_graph_manager    # noqa: E402
from s3dgraphy.exporter.emjson_exporter import export_emjson       # noqa: E402
print("[SMOKE] s3dgraphy from", s3dgraphy.__file__)
import s3dgraphy.resources.versions as _versions  # noqa: E402
if not hasattr(_versions, "lod_level_of"):
    print("[SMOKE] aborting: this s3dgraphy has no lod_level_of (PYTHONPATH + --python-use-system-env)")
    sys.exit(1)

work = tempfile.mkdtemp(prefix="em-d1-")
for _o in list(bpy.data.objects):
    bpy.data.objects.remove(_o)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(work, "d1.blend"))

# the master: a 10 × 10 m grid, UV-unwrapped, one 2048 atlas
bpy.ops.mesh.primitive_grid_add(x_subdivisions=120, y_subdivisions=120, size=10.0)
obj = bpy.context.active_object
obj.name = "OB_PODIO"
img = bpy.data.images.new("T_PODIO", 2048, 2048)
mat = bpy.data.materials.new("M_PODIO")
mat.use_nodes = True
tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
tex.image = img
obj.data.materials.append(mat)

g = Graph("d1-smoke")
multi_graph_manager.graphs[g.graph_id] = g
api.add_resource(g, name="OB_PODIO master", kind="3d_model", tier="master",
                 files=[{"path": "podio_master.obj", "checksum": "sha256:" + "a" * 64}],
                 resource_id="podio")
obj["em_resource_id"] = "podio"

# point EMtools at this graph
em = bpy.context.scene.em_tools
while len(em.graphml_files):
    em.graphml_files.remove(0)
row = em.graphml_files.add()
row.name = g.graph_id
em.active_file_index = 0

levels = []
for i, ratio in enumerate((0.5, 0.5, 0.5)):
    mod = obj.modifiers.new("_dec", "DECIMATE")
    mod.ratio = ratio
    deps = bpy.context.evaluated_depsgraph_get()
    mesh = bpy.data.meshes.new_from_object(obj.evaluated_get(deps))
    obj.modifiers.remove(mod)
    path = os.path.join(work, f"v{i}.glb")
    with open(path, "wb") as fh:
        fh.write(b"glTF" + bytes([i]) * 64)
    files = [{"path": os.path.basename(path), "url": path,
              "checksum": "sha256:" + f"{i + 1}" * 64}]
    out = av.add_version_from_mesh(g, obj, mesh, files=files, room=None,
                                   use=["web"] if i else ["analysis", "realtime"],
                                   made_from=av._shown_version(obj),
                                   technique="decimation", parameters={"ratio": ratio})
    levels.append(out["lod_level"])
    av.set_level(obj, out["level"])
    print(f"[SMOKE] version {out['level']} = {out['lod_level']} · {av._measures_line(out['measures'])}")
    if i == 0:
        m0 = out["measures"]

check("the levels are computed from the chain", levels == ["lod0", "lod1", "lod2"], str(levels))
check("measures at birth: tris/m², texel side, atlases, UV",
      all(k in m0 for k in ("tris_per_m2", "texel_density_dd", "texture_count",
                            "texture_side_px", "uv_ratio")), str(m0))
entries = api.versions_of(g, "podio")
check("lod1 and lod2 say how much of LOD0 they keep",
      all(e["measures"].get("reduction_from_lod0") for e in entries[2:]),
      str([e["measures"] for e in entries]))
check("the uses are a list", entries[1]["use"] == ["analysis", "realtime"])

out_path = os.path.join(work, "d1.em.json")
export_emjson(g, out_path)
doc = json.load(open(out_path))
section = next(iter(doc["graphs"].values()))
written = {n["id"]: (n.get("data") or {}).get("lod_level") for n in section["nodes"]
           if n["node_type"] == "resource"}
check("the em.json carries lod_level on the versions, none on the master",
      sorted(v for v in written.values() if v) == ["lod0", "lod1", "lod2"]
      and written["podio"] is None, str(written))


def reload(path):
    while len(em.graphml_files):
        em.graphml_files.remove(0)
    IMPORT.em_emjson(filepath=path)
    return em.graphml_files[0].import_warnings


warn = reload(out_path)
check("reloaded: coherent, no lod_level line", "lod_level" not in warn, warn[:300])

lod2 = next(i for i, v in written.items() if v == "lod2")
for n in section["nodes"]:
    if n["id"] == lod2:
        n["data"]["lod_level"] = "lod0"
bad = os.path.join(work, "d1-falsified.em.json")
json.dump(doc, open(bad, "w"))
warn = reload(bad)
check("a falsified lod_level is a line in the import warnings (the Log)",
      "the file says lod0, the chain says lod2" in warn, warn[:400])
print(f"[SMOKE] the line: {[w for w in warn.splitlines() if 'lod_level' in w]}")

print(f"[SMOKE] {'ALL PASS' if not FAILURES else 'FAILURES: ' + ', '.join(FAILURES)}")
sys.exit(1 if FAILURES else 0)
