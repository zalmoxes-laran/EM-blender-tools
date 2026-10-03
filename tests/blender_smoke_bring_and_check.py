"""Headless smoke · P3 «Bring into a room…» and S1 «Check the scene against the
room» (MICRO-LA-BARRA-E-LE-STANZE), against a LIVE node.

NOT a pytest test (needs bpy and a node) — run it inside Blender with the
EM-tools extension enabled:

    cd ~/Documents/GitHub/stratigraph-server/dev-stack
    EM_DEV_TOKEN=$(./token.sh) EM_NODE=http://localhost:8000 \\
    /Applications/Blender\\ 520.app/Contents/MacOS/Blender --background \\
        --python ~/Documents/GitHub/EM-blender-tools/tests/blender_smoke_bring_and_check.py

What it builds, all in a temporary folder (no user data): a COPY of the fixture
em.json loaded as the active graph, a few of the files its resources name
(`DosCo/D.01.jpg`, `out.glb`, the `photos/` folder), two raw photographs in a
`dtc_acquisition` batch, and a scene with the RM of `M_model` (a cube in the RM
list) and a «Decoration» cube linked to nothing.

P3 · a NEW room (`t-p3-<time>`): the inventory has its four groups; the found
files go up and their resources become store-backed with the disk path kept as
a second address; the batch is one line; the RM is published, the decoration is
NOT; the graph is seated; Blender is IN the room. A second «Bring» into the same
room sends nothing (HEAD).

S1 · the decoration is listed «only here» and marked; the RM object is deleted
and the check downloads it again from the store.

Exits non-zero on failure.
"""
import json
import os
import shutil
import sys
import tempfile
import time

import bpy

FAILURES = []


def check(label, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print(f"[SMOKE] {status}: {label} {detail}")
    if not condition:
        FAILURES.append(label)
    return condition


def mod(suffix):
    names = [n for n in sys.modules if n.endswith(suffix) and n.startswith("bl_ext.")]
    if not names:
        print(f"[SMOKE] aborting: {suffix} not loaded — enable the extension")
        sys.exit(1)
    return sys.modules[names[0]]


NODE = os.environ.get("EM_NODE", "http://localhost:8000")
TOKEN = os.environ.get("EM_DEV_TOKEN", "")
if not TOKEN:
    print("[SMOKE] aborting: set EM_DEV_TOKEN (dev-stack/token.sh)")
    sys.exit(1)

bring = mod(".sync_manager.bring")
inventory = mod(".sync_manager.inventory")
room_cfg = mod(".sync_manager.room")
scene_check = mod(".sync_manager.scene_check")
ops = mod(".sync_manager.operators")
from s3dgraphy.nodes.dtc_acquisition_node import DTCAcquisitionNode  # noqa: E402
from s3dgraphy.nodes.resource_node import ResourceNode  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
work = tempfile.mkdtemp(prefix="em-p3-")
copy = os.path.join(work, "p3.em.json")
shutil.copyfile(os.path.join(HERE, "fixtures", "emtools_cb25e71_dev23.em.json"), copy)
os.makedirs(os.path.join(work, "DosCo"))
os.makedirs(os.path.join(work, "photos"))
open(os.path.join(work, "DosCo", "D.01.jpg"), "wb").write(os.urandom(4000))
open(os.path.join(work, "out.glb"), "wb").write(os.urandom(9000))
raw = []
for i in range(2):
    p = os.path.join(work, "photos", f"IMG_{i:04d}.JPG")
    open(p, "wb").write(os.urandom(6000 + i))
    raw.append(p)

# ── the project: the graph loaded, the scene with one RM and one decoration ──
scene = bpy.context.scene
em_tools = scene.em_tools
while len(em_tools.graphml_files):
    em_tools.graphml_files.remove(0)
esito = getattr(bpy.ops, "import").em_emjson(filepath=copy)
check("the fixture graph loads", esito == {"FINISHED"}, repr(esito))
ok, graph = ops.is_graph_available(bpy.context)
graph.add_node(DTCAcquisitionNode("acq-raw", name="Raw photos 2026-10",
                                  dtc_kind="local_import"))
for i, p in enumerate(raw):
    graph.add_node(ResourceNode(f"raw-{i}", name=os.path.basename(p), url=p))
    graph.add_edge(f"e-raw-{i}", "acq-raw", f"raw-{i}", "dtc_had_output")
LINKED_DOC = graph.find_node_by_id("link-1")

for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
bpy.ops.mesh.primitive_cube_add(size=1)
rm_obj = bpy.context.active_object
rm_obj.name = "M_rm_object"
scene.rm_list.clear()
item = scene.rm_list.add()
item.name = rm_obj.name
item.node_id = "M_model"
bpy.ops.mesh.primitive_cube_add(size=0.3, location=(3, 0, 0))
decoration = bpy.context.active_object
decoration.name = "Decoration"

scene.em_room_url = NODE
room_cfg.set_room(NODE, None, TOKEN)        # the session's access, in memory
ROOM_NAME = f"T-P3 {int(time.time())}"
ROOM_ID = mod(".sync_manager.rooms_list").room_id_from_name(ROOM_NAME)

# ── P3 · the first «Bring into a room…» ─────────────────────────────────────
esito = bpy.ops.em.room_bring(name=ROOM_NAME, confirm=True)
check("bring: FINISHED", esito == {"FINISHED"}, repr(esito))
rows = bring.STATE.get("rows") or []
groups = {g: [r["id"] for r in rows if r["group"] == g] for g in inventory.GROUPS}
print("[SMOKE] inventory:", json.dumps({g: len(v) for g, v in groups.items()}))
for line in inventory.sentences(inventory.summarise(rows)):
    print("[SMOKE]   ", line)
check("found: the DosCo jpg, out.glb, the two raw photos",
      {"link-1", "raw-0", "raw-1"} <= set(groups["found"]), repr(groups["found"]))
check("missing: the files not on this disk (models/M.gltf …)",
      "M_model_link" in groups["missing"], repr(groups["missing"]))
check("the batch is ONE line", len(inventory.summarise(rows)["batches"]) == 1)
rep = bring.ULTIMO_REFERTO
print("[SMOKE] report:", rep.get("sentence"))
check("uploaded something", rep.get("uploaded", 0) >= 4, repr(rep.get("uploaded")))
check("no failures", not rep.get("failed"), repr(rep.get("failed")))
node = graph.find_node_by_id("link-1")
addresses = (node.data or {}).get("addresses") or []
check("the uploaded resource is store-backed",
      node.data.get("residency") == "resident"
      and "/asset/sha256:" in str(node.data.get("url")), repr(node.data.get("url")))
check("…and keeps its original path as a second address",
      [a.get("locator") for a in addresses][1:] == ["DosCo/D.01.jpg"], repr(addresses))
check("the RM model was published", rep.get("models") == ["M_rm_object"],
      repr(rep.get("models")))
check("the RM object carries its digest", bool(rm_obj.get("em_asset_sha256")))
published = rm_obj.get("em_asset_sha256")
check("the decoration was NOT uploaded",
      "Decoration" not in (rep.get("models") or [])
      and not decoration.get("em_asset_sha256"))
check("the graph was seated", rep.get("ops_applied", 0) > 10,
      repr(rep.get("ops_applied")))
check("Blender is in the room (D-B)", rep.get("joined") is True
      and ops.session_mode(bpy.context) == ops.MODE_HUB, repr(rep.get("join_message")))
check("the report carries the room link", ROOM_ID in str(rep.get("link")),
      repr(rep.get("link")))

# S1 at the door: joining ran the check, and the decoration is «only here»
check("S1 at join: the decoration is marked only here",
      bool(decoration.get(scene_check.PROP_ONLY_HERE)),
      repr(scene_check.ULTIMA_VERIFICA.get("only_here")))
check("S1 at join: the RM object is not", not rm_obj.get(scene_check.PROP_ONLY_HERE))

# ── P3 · the second «Bring» into the same room sends nothing ────────────────
esito = bpy.ops.em.room_bring(name=ROOM_NAME, confirm=True)
check("second bring: FINISHED", esito == {"FINISHED"}, repr(esito))
rep2 = bring.ULTIMO_REFERTO
print("[SMOKE] second report:", rep2.get("sentence"), "| already:", rep2.get("already"))
check("second bring: nothing uploaded", rep2.get("uploaded") == 0, repr(rep2.get("uploaded")))
check("second bring: the stored group holds what went up the first time",
      {"link-1", "raw-0", "raw-1"} <= {r["id"] for r in bring.STATE["rows"]
                                       if r["group"] == "stored"})

# ── S1 · a graph-linked model deleted from the scene comes back ─────────────
bpy.data.objects.remove(rm_obj, do_unlink=True)
esito = bpy.ops.em.scene_check(download=True)
check("scene check: FINISHED", esito == {"FINISHED"}, repr(esito))
for line in scene_check.ULTIMA_VERIFICA.get("sentences") or []:
    print("[SMOKE]   ", line)
back = [o for o in bpy.data.objects if o.get("em_asset_sha256") == published]
check("the deleted RM model was downloaded again", len(back) >= 1,
      repr([o.name for o in bpy.data.objects]))
check("the decoration is still only here, and still not uploaded",
      "Decoration" in (scene_check.ULTIMA_VERIFICA.get("only_here") or [])
      and not decoration.get("em_asset_sha256"))

ops.leave_room()
shutil.rmtree(work, ignore_errors=True)
if FAILURES:
    print(f"[SMOKE] {len(FAILURES)} failure(s): {FAILURES}")
    sys.exit(1)
print("[SMOKE] all checks passed")
