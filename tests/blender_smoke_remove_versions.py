"""Headless smoke · «Export a version for a use…» on a SELECTION and «Remove
versions…» (E.D., 22 Oct 2026), on the COPY of Templu Mare (never saved).

    PYTHONPATH=~/Documents/GitHub/s3Dgraphy/src \\
    "/Applications/Blender 520.app/Contents/MacOS/Blender" -b --python-use-system-env \\
        ~/Documents/GitHub/_datasets/templu-mare-prove/GreatTemple_2026_v3_multigraph_test_CLAUDE.blend \\
        --python ~/Documents/GitHub/EM-blender-tools/tests/blender_smoke_remove_versions.py

(1) two objects selected, «Export a version for a use…» (web): one version
EACH, the active's in PREPARED; (2) «Remove versions…» on one of them (mode
ONE): the version, its step and its node out of the graph, its glb and stamp
off the disk, its mesh out of the asset's library, the object still showing
its master; (3) DERIVED names the other's, removed by its row; (4) the master refused.
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


names = [n for n in sys.modules if n.endswith(".graph_origins") and n.startswith("bl_ext.")]
PKG = names[0].rsplit(".graph_origins", 1)[0]
print("[SMOKE] package:", PKG, sys.modules[PKG].__file__)
av = importlib.import_module(PKG + ".sync_manager.asset_versions")
scene = bpy.context.scene
row0 = scene.em_tools.graphml_files[0]
src0 = bpy.path.abspath(row0.graphml_path)
if src0.lower().endswith(".graphml"):
    dst0 = os.path.join(tempfile.mkdtemp(prefix="em-rm-"), os.path.basename(src0))
    shutil.copy2(src0, dst0)
    row0.graphml_path = dst0
scene.em_tools.active_file_index = 0
getattr(bpy.ops, "import").em_graphml(graphml_index=0)
from s3dgraphy import get_graph  # noqa: E402
graph = get_graph(scene.em_tools.graphml_files[0].name)

a = bpy.data.objects["ME_PODIO"]
b = next(o for o in scene.objects if o.type == "MESH" and o != a
         and len(o.data.polygons) > 50 and o.name.startswith("ME_"))
print("[SMOKE] objects:", a.name, b.name)
for o in bpy.context.view_layer.objects:
    o.select_set(False)
a.select_set(True)
b.select_set(True)
bpy.context.view_layer.objects.active = a
mesh_a, mesh_b = a.data.name, b.data.name

# ── (1) one export, two versions ──────────────────────────────────────────
r = bpy.ops.em.asset_prepare_for_use(use={"web"}, ratio=0.5, max_texture=512, draco=True)
check("Export a version for a use… on two objects", r == {"FINISHED"}, str(r))
va = av.PREPARED.get("version_id")
from s3dgraphy import api  # noqa: E402
asset_a = av.master_of(graph, a, scene)
asset_b = av.master_of(graph, b, scene)
check("…PREPARED is the active's", bool(va) and api.asset_of(graph, va) == asset_a, str(va))
web_b = [e for e in api.versions_of(graph, asset_b) if "web" in (e.get("use") or [])]
check("…and one for the other object", bool(web_b), str([e["id"] for e in web_b]))
check("both still show what they showed", a.data.name == mesh_a and b.data.name == mesh_b,
      f"{a.data.name} {b.data.name}")
glb_a = av.PREPARED.get("entry")
check("the glb of A on disk", os.path.isfile(glb_a or ""), str(glb_a))
lib_a = av.library_abspath(asset_a, av._room_id())
level_a = av.PREPARED.get("level")
check("A's level in its library", level_a in av.linked_meshes(lib_a), str(level_a))

# ── (2) remove one version, by its row ───────────────────────────────────
plan = av.removal_plan_here(graph, [va])
print("[SMOKE] plan:", {k: plan[k] for k in ("resources", "processes", "files_cache",
                                              "stamps_cache", "files_outside")})
check("the plan names the glb", glb_a in plan["files_cache"])
r = bpy.ops.em.asset_remove_versions(mode="ONE", version_id=va, object_name=a.name)
check("Remove versions… (one)", r == {"FINISHED"}, str(r))
check("…the node is gone", graph.find_node_by_id(va) is None)
check("…its step is gone", all(graph.find_node_by_id(p) is None for p in plan["processes"]))
check("…the glb is gone", not os.path.exists(glb_a or ""))
check("…its stamps are gone", all(not os.path.exists(p) for p in plan["stamps_cache"]))
check("…its mesh left the library", level_a not in av.linked_meshes(lib_a),
      str(list(av.linked_meshes(lib_a)) if os.path.isfile(lib_a) else "library gone"))
check("…A still shows its master", a.data is not None and av.current_level(a) != level_a,
      f"{a.data.name if a.data else None} {av.current_level(a)}")

# ── (3) the derived versions of the selection ────────────────────────────
for o in bpy.context.view_layer.objects:
    o.select_set(False)
b.select_set(True)
bpy.context.view_layer.objects.active = b
#: DERIVED would also take the derived versions the copy already had (and
#: their files in its cache): measured on the plan, removed one by one
from importlib import import_module  # noqa: E402
derived_ids = [e["id"] for e in import_module(PKG + ".version_families").families(
    graph, asset_b)["derived"]]
check("DERIVED of B names its new web version", web_b[0]["id"] in derived_ids,
      f"{len(derived_ids)} derived")
r = bpy.ops.em.asset_remove_versions(mode="ONE", version_id=web_b[0]["id"],
                                     object_name=b.name)
check("Remove versions… (B's web)", r == {"FINISHED"}, str(r))
left = [e for e in api.versions_of(graph, asset_b) if e["id"] == web_b[0]["id"]]
check("…B's web version is gone", not left)

# ── (4) the master is never removed ──────────────────────────────────────
plan = av.removal_plan_here(graph, [asset_a])
check("the master is refused", not plan["resources"] and plan["refused"], str(plan["refused"]))

print("[SMOKE] RESULT:", "ALL PASS" if not FAILURES else f"FAILED {FAILURES}")
sys.stdout.flush()
sys.exit(0 if not FAILURES else 1)
