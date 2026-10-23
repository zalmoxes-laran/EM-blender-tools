"""Headless smoke · proxies and models as files of the EM project (E.D.,
23 Oct 2026), on the COPY of Templu Mare (never saved).

    PYTHONPATH=~/Documents/GitHub/s3Dgraphy/src \\
    "/Applications/Blender 520.app/Contents/MacOS/Blender" -b --python-use-system-env \\
        ~/Documents/GitHub/_datasets/templu-mare-prove/GreatTemple_2026_v3_multigraph_test_CLAUDE.blend \\
        --python ~/Documents/GitHub/EM-blender-tools/tests/blender_smoke_project_files.py

Everything is written under a temporary project (``<tmp>/Tempio/EM`` holds a
copy of the GraphML, read into its em.json there); the cache of the versions
is pointed at the same temporary folder. Nothing lands beside the .blend nor
in the GraphML's own folder.

(1) one proxy selected, «Write proxy files…»: its glb in EM/proxies, the
graph's proxy resource names ``proxies/<unit>.glb`` with the checksum of those
bytes, a dtcstamp beside it; (2) «Export a version for a use…» with the
project as destination: the glb in RM/<container>/, the version's url there;
(3) the dialog and the container row draw.
"""
import hashlib
import importlib
import os
import shutil
import sys
import tempfile
import types

import bpy

FAILURES = []


def check(label, condition, detail=""):
    print(f"[SMOKE] {'PASS' if condition else 'FAIL'}: {label} {detail}")
    if not condition:
        FAILURES.append(label)


names = [n for n in sys.modules if n.endswith(".graph_origins") and n.startswith("bl_ext.")]
PKG = names[0].rsplit(".graph_origins", 1)[0]
av = importlib.import_module(PKG + ".sync_manager.asset_versions")
pf = importlib.import_module(PKG + ".sync_manager.project_files")
seal = importlib.import_module(PKG + ".resource_seal")

TMP = tempfile.mkdtemp(prefix="em-projfiles-")
ROOT = os.path.join(TMP, "Tempio")
EM_DIR = os.path.join(ROOT, "EM")
os.makedirs(EM_DIR)
#: the versions' cache and the assets' libraries in the temporary folder too
av.cache_folder = lambda: TMP

scene = bpy.context.scene
em = scene.em_tools
row0 = em.graphml_files[0]
src0 = bpy.path.abspath(row0.graphml_path)
check("the first row is a GraphML", src0.lower().endswith(".graphml"), src0)
dst0 = os.path.join(EM_DIR, os.path.basename(src0))
shutil.copy2(src0, dst0)
row0.graphml_path = dst0
em.active_file_index = 0
getattr(bpy.ops, "import").em_graphml(graphml_index=0)
from s3dgraphy import get_graph  # noqa: E402
graph = get_graph(em.graphml_files[0].name)
print("[SMOKE] em.json:", pf.active_emjson(bpy.context))
where = pf.folders_here(bpy.context)
print("[SMOKE] folders:", where)
check("the project is the temporary one", where is not None
      and os.path.normpath(where["base"]) == os.path.normpath(ROOT), str(where))

# ── (1) a proxy written ───────────────────────────────────────────────────
targets = pf.proxy_targets(bpy.context, graph, selected_only=False)
check("proxies of the graph in the scene", len(targets) > 0, str(len(targets)))
obj, unit, unit_id = targets[0]
for o in bpy.context.view_layer.objects:
    o.select_set(False)
obj.select_set(True)
bpy.context.view_layer.objects.active = obj
r = bpy.ops.em.proxies_write_files(which="SELECTED")
check("Write proxy files… (selected)", r == {"FINISHED"}, str(r))
path = os.path.join(where["proxies"], f"{unit}.glb")
check("the glb in EM/proxies", os.path.isfile(path), path)
proxy_chain = importlib.import_module(PKG + ".proxy_chain")
_shape, res = proxy_chain.glb_proxy(graph, unit_id)
from s3dgraphy import api  # noqa: E402
if res is not None:
    res = graph.find_node_by_id(api.current_revision(graph, res.node_id))
data = (res.data or {}) if res is not None else {}
digest = "sha256:" + hashlib.sha256(open(path, "rb").read()).hexdigest() \
    if os.path.isfile(path) else ""
check("the resource names proxies/<unit>.glb", data.get("url") == f"proxies/{unit}.glb",
      str(data.get("url")))
check("…with the checksum of those bytes", data.get("checksum") == digest,
      f"{data.get('checksum')} vs {digest}")
stamp = seal.find_stamp(path) if os.path.isfile(path) else None
print("[SMOKE] stamp:", stamp)
check("a dtcstamp beside it", bool(stamp))
r = bpy.ops.em.proxies_write_files(which="SELECTED")
res2 = graph.find_node_by_id(api.current_revision(graph, res.node_id)) if res is not None else None
check("written again: the same bytes, the same resource",
      res2 is not None and res2.node_id == res.node_id, str(res2 and res2.node_id))

# ── (2) a model into RM/<container>/ ──────────────────────────────────────
cont = next((c for c in scene.rm_containers
             if any(bpy.data.objects.get(e.name) is not None
                    and bpy.data.objects[e.name].type == "MESH" for e in c.mesh_names)), None)
check("a container with a mesh", cont is not None)
model = next(bpy.data.objects[e.name] for e in cont.mesh_names
             if bpy.data.objects.get(e.name) is not None
             and bpy.data.objects[e.name].type == "MESH")
for o in bpy.context.view_layer.objects:
    o.select_set(False)
model.select_set(True)
bpy.context.view_layer.objects.active = model
print("[SMOKE] model:", model.name, "container:", cont.label)
r = bpy.ops.em.asset_prepare_for_use(use={"web"}, ratio=0.5, max_texture=512, draco=True,
                                     destination="PROJECT")
check("Export a version for a use… to the project", r == {"FINISHED"}, str(r))
entry = av.PREPARED.get("entry") or ""
want = pf.model_folder(where["models"], pf.container_label_of(scene, model.name))
print("[SMOKE] entry:", entry)
check("the glb in RM/<container>/", os.path.isfile(entry)
      and os.path.normpath(os.path.dirname(entry)) == os.path.normpath(want),
      f"{entry} vs {want}")
vnode = graph.find_node_by_id(av.PREPARED.get("version_id") or "")
vurl = str(((vnode.data or {}) if vnode is not None else {}).get("url") or "")
check("the version's url points there", os.path.normpath(vurl) == os.path.normpath(entry),
      vurl)

# ── (3) the dialog and the container row draw ────────────────────────────
class L:
    def __init__(s, d=0):
        s.d = d
        s.enabled = True
        s.scale_y = 1.0

    def __getattr__(s, n):
        def f(*a, **k):
            txt = k.get("text") or ""
            print("  " * s.d + f"[DRAW] {n}: {txt}")
            if n == "operator":
                return types.SimpleNamespace()
            return L(s.d + 1)
        return f


try:
    C = next(c for c in av._CLASSES if getattr(c, "bl_idname", "") == "em.asset_prepare_for_use")
    m = types.SimpleNamespace(layout=L(), use={"web"}, destination="PROJECT",
                              computed="lod0", category="rm", format="glb",
                              transform="local", ratio=1.0, max_texture=2048,
                              jpeg_quality=0, animations="none", frame_range=True,
                              draco=True, level="")
    C.draw(m, bpy.context)
    pf.draw_container_files(L(), bpy.context, cont)
    P = next(c for c in pf._CLASSES if c.bl_idname == "em.proxies_write_files")
    mp = types.SimpleNamespace(layout=L(), which="ALL")
    P.draw(mp, bpy.context)
    drew = True
except Exception as exc:  # noqa: BLE001
    import traceback
    traceback.print_exc()
    drew = False
check("the dialogs and the row draw", drew)

print("[SMOKE] temporary project:", TMP)
print("[SMOKE] RESULT:", "ALL PASS" if not FAILURES else f"FAILED {FAILURES}")
shutil.rmtree(TMP, ignore_errors=True)
sys.stdout.flush()
sys.exit(0 if not FAILURES else 1)
