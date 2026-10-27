"""Headless smoke · «Prepare for a use…» refuses a mesh without faces (27 Oct 2026).

With its linked library lost, an object shows an empty placeholder mesh, and the
operator wrote a 184-byte glb and registered it as a version. Now: CANCELLED, the
reason in the operator's report, no file written, nothing added to the graph —
for a mesh linked from a library deleted before the file is reopened (the real
case), an empty mesh, and a mesh of points only.
Self-contained (factory scene, an in-memory graph), any profile with EM Tools:

    BLENDER_USER_RESOURCES=/tmp/ottim3/profile52 \\
    "/Applications/Blender 520.app/Contents/MacOS/Blender" -b --factory-startup \\
        --python ~/Documents/GitHub/EM-blender-tools/tests/blender_smoke_prepare_faceless.py -- /tmp/faceless

(`--factory-startup` keeps the add-ons off; the script enables the extension it
finds installed in the profile.)
"""
import addon_utils
import importlib
import os
import shutil
import sys

import bpy

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
WORK = ARGS[0] if ARGS else "/tmp/faceless"
FAILURES = []


def check(label, condition, detail=""):
    print(f"[SMOKE] {'PASS' if condition else 'FAIL'}: {label} {detail}")
    if not condition:
        FAILURES.append(label)


def files_under(folder):
    return {os.path.join(d, f) for d, _, fs in os.walk(folder) for f in fs}


shutil.rmtree(WORK, ignore_errors=True)
os.makedirs(WORK)

names = [n for n in sys.modules if n.endswith(".graph_origins") and n.startswith("bl_ext.")]
if not names:   # --factory-startup: enable the EM Tools the profile has
    mod = next((m.__name__ for m in addon_utils.modules()
                if m.__name__.startswith("bl_ext.") and m.__name__.split(".")[-1]
                in ("em_tools", "EM-blender-tools")), None)
    check("EM Tools is installed in this profile", mod is not None)
    if mod:
        addon_utils.enable(mod, default_set=True)
    names = [n for n in sys.modules if n.endswith(".graph_origins") and n.startswith("bl_ext.")]
PKG = names[0].rsplit(".graph_origins", 1)[0]
print("[SMOKE] package:", PKG, sys.modules[PKG].__file__)
av = importlib.import_module(PKG + ".sync_manager.asset_versions")
check("the operator exists", hasattr(bpy.ops.em, "asset_prepare_for_use"))

# the real case: a mesh linked from a library that is then lost. A library
# with a cube, linked into the working file (in WORK: the cache, em_cache, goes
# beside it), the library deleted, the working file reopened
lib_path = os.path.join(WORK, "lib", "podio_lib.blend")
os.makedirs(os.path.dirname(lib_path))
cube = bpy.data.meshes.new("PODIO_lib_mesh")
cube.from_pydata([(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)], [], [(0, 1, 2, 3)])
bpy.data.libraries.write(lib_path, {cube}, path_remap="RELATIVE")
bpy.data.meshes.remove(cube)
with bpy.data.libraries.load(lib_path, link=True, relative=True) as (src, dst):
    dst.meshes = ["PODIO_lib_mesh"]
linked = bpy.data.objects.new("ME_LINKED", dst.meshes[0])
bpy.context.scene.collection.objects.link(linked)
check("the linked mesh has its face", len(linked.data.polygons) == 1)
main_path = os.path.join(WORK, "faceless.blend")
bpy.ops.wm.save_as_mainfile(filepath=main_path)
os.remove(lib_path)
bpy.ops.wm.open_mainfile(filepath=main_path)
linked = bpy.data.objects["ME_LINKED"]
print("[SMOKE] ME_LINKED after the library is lost:", linked.data.name,
      "missing" if getattr(linked.data, "is_missing", False) else "present",
      len(linked.data.vertices), "vertices", len(linked.data.polygons), "faces")
check("the library is lost: a placeholder mesh", len(linked.data.polygons) == 0)
scene = bpy.context.scene

# an in-memory graph, the active one
from s3dgraphy import Graph  # noqa: E402
from s3dgraphy.multigraph.multigraph import multi_graph_manager  # noqa: E402
from s3dgraphy.nodes.base_node import Node  # noqa: E402
graph = Graph(graph_id="faceless_smoke")
graph.add_node(Node(node_id="anchor", name="anchor"))
multi_graph_manager.graphs["faceless_smoke"] = graph
row = scene.em_tools.graphml_files.add()
row.name = "faceless_smoke"
scene.em_tools.active_file_index = len(scene.em_tools.graphml_files) - 1

# the object of a lost library: an empty mesh; and one with points only
lost = bpy.data.objects.new("ME_LOST", bpy.data.meshes.new("ME_LOST_mesh"))
pts_mesh = bpy.data.meshes.new("ME_POINTS_mesh")
pts_mesh.from_pydata([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [], [])
points = bpy.data.objects.new("ME_POINTS", pts_mesh)
for o in (lost, points):
    scene.collection.objects.link(o)

for obj in (linked, lost, points):
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    before_files = files_under(WORK)
    before_nodes = {n.node_id for n in graph.nodes}
    av.PREPARED.clear()
    result, message = None, ""
    try:
        result = bpy.ops.em.asset_prepare_for_use(use={"web"}, ratio=1.0)
    except RuntimeError as exc:          # -b: an ERROR report raises
        result, message = {"CANCELLED"}, str(exc)
    print(f"[SMOKE] {obj.name}: {result} · {message.strip()}")
    check(f"{obj.name}: refused", result == {"CANCELLED"}, str(result))
    check(f"{obj.name}: the report says why", "no faces" in message
          and obj.name in message, message.strip()[:200])
    new_files = files_under(WORK) - before_files
    check(f"{obj.name}: nothing written", not new_files, str(sorted(new_files)[:5]))
    check(f"{obj.name}: nothing registered",
          {n.node_id for n in graph.nodes} == before_nodes and not av.PREPARED,
          str(sorted({n.node_id for n in graph.nodes} - before_nodes)))

print("[SMOKE] RESULT:", "ALL PASS" if not FAILURES else f"FAILED {FAILURES}")
sys.stdout.flush()
sys.exit(0 if not FAILURES else 1)
