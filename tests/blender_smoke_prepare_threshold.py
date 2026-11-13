"""Headless smoke · MICRO-ASSETS-LIVELLI p.5, «Prepare for a use…» with a
threshold of triangles (``min_triangles``) on a COPY of Templu Mare (never
saved): a mesh under the threshold is not reduced — its use points to the
lightest version it has (``data.use``), no file is written; with no version,
it is written without decimation. 0 keeps the behaviour of before.

    PYTHONPATH=~/Documents/GitHub/s3Dgraphy/src \\
    "/Applications/Blender 520.app/Contents/MacOS/Blender" -b --python-use-system-env \\
        /tmp/al-livelli/blend/GreatTemple_2026_v3_multigraph_test_CLAUDE.blend \\
        --python ~/Documents/GitHub/EM-blender-tools/tests/blender_smoke_prepare_threshold.py \\
        --python-exit-code 1
"""
import importlib
import os
import shutil
import sys
import tempfile

import bpy

FAILURES = []


def check(label, condition, detail=""):
    print(f"[SMOKE] {'PASS' if condition else 'FAIL'}: {label} {detail}")
    if not condition:
        FAILURES.append(label)


# in -b a popup (the import's warnings) crashes Blender 5.2: no popup here
bpy.types.WindowManager.popup_menu = lambda *a, **k: None
names = [n for n in sys.modules if n.endswith(".graph_origins") and n.startswith("bl_ext.")]
PKG = names[0].rsplit(".graph_origins", 1)[0]
av = importlib.import_module(PKG + ".sync_manager.asset_versions")
scene = bpy.context.scene
row0 = scene.em_tools.graphml_files[0]
src0 = bpy.path.abspath(row0.graphml_path)
if src0.lower().endswith(".graphml"):
    dst0 = os.path.join(tempfile.mkdtemp(prefix="em-thr-"), os.path.basename(src0))
    shutil.copy2(src0, dst0)
    row0.graphml_path = dst0
scene.em_tools.active_file_index = 0
getattr(bpy.ops, "import").em_graphml(graphml_index=0)
from s3dgraphy import api, get_graph  # noqa: E402
graph = get_graph(scene.em_tools.graphml_files[0].name)

C = next(c for c in av._CLASSES if getattr(c, "bl_idname", "") == "em.asset_prepare_for_use")
check("the operator takes min_triangles", "min_triangles" in C.__annotations__)

obj = bpy.data.objects["ME_PODIO"]
for o in bpy.context.view_layer.objects:
    o.select_set(False)
obj.select_set(True)
bpy.context.view_layer.objects.active = obj
tris = av._object_triangles(bpy.context, obj)
check("the object's triangles are read", isinstance(tris, int) and tris > 0, str(tris))

# (1) a first version, reduced as before (threshold 0)
r = bpy.ops.em.asset_prepare_for_use(use={"web"}, ratio=0.5, max_texture=512, draco=True)
check("prepare (web, no threshold) reduces as before", r == {"FINISHED"}, str(r))
v1 = dict(av.PREPARED)
check("a version is born", bool(v1.get("version_id")) and not v1.get("pointed"), str(v1.get("version_id")))
master = av.master_of(graph, obj, scene)
before = [e["id"] for e in api.versions_of(graph, api.asset_of(graph, master)) if not e.get("master")]

# (2) under the threshold: no new file, the use written on the lightest version
r = bpy.ops.em.asset_prepare_for_use(use={"mobile_ar"}, ratio=0.25, max_texture=512, draco=True,
                                      min_triangles=tris + 1)
check("prepare (mobile_ar, under the threshold) finishes", r == {"FINISHED"}, str(r))
out = dict(av.PREPARED)
pt = out.get("pointed") or {}
after = [e["id"] for e in api.versions_of(graph, api.asset_of(graph, master)) if not e.get("master")]
check("no version is born", sorted(after) == sorted(before), f"{len(before)} → {len(after)}")
node = graph.find_node_by_id(pt.get("id") or "")
check("the use points to the lightest version", node is not None and "mobile_ar" in (node.data or {}).get("use", []),
      f"{pt}")

# (3) above the threshold: reduced
r = bpy.ops.em.asset_prepare_for_use(use={"mobile_ar"}, ratio=0.25, max_texture=512, draco=True,
                                      min_triangles=max(1, tris // 2))
out3 = dict(av.PREPARED)
check("above the threshold it is reduced", r == {"FINISHED"} and bool(out3.get("version_id")) and not out3.get("pointed"),
      str(out3.get("level")))

print(f"[SMOKE] {'OK' if not FAILURES else 'FAILED: ' + ', '.join(FAILURES)}")
if FAILURES:
    raise SystemExit(1)
