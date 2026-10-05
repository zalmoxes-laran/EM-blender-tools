"""Headless smoke · T-R1, the residence follows the origin — LIVE against the
dev node (user `dev` of the realm `em-dev`).

    cd ~/Documents/GitHub/stratigraph-server/dev-stack
    EM_DEV_TOKEN=$(./token.sh) EM_NODE=http://localhost:8000 \\
    PYTHONPATH=~/Documents/GitHub/s3Dgraphy/src \\
    "/Applications/Blender 520.app/Contents/MacOS/Blender" -b --python-use-system-env \\
        --python ~/Documents/GitHub/EM-blender-tools/tests/blender_smoke_residence.py -- /tmp/tr1

(1) a graph from the example xlsx in a new room; two models published into
the room's store and documented — a survey (Document, geometry reality_based)
and a reconstruction (geometry asserted); (2) both objects removed, «Sync the
scene…» brings them back: the reality-based one LINKED from its library
(`em_cache/<room>/<asset>.blend`), the source-based one RESIDENT; (3) the
source-based mesh edited: Sync offers it as changed (a revision), and never
the linked one; sent, it is a revision of its resource; (4) Q4, the
source-based one given a version: gone and synced again, it comes back LINKED
from its library, like any asset with versions.
"""
import os
import shutil
import sys
import time

import bpy

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
WORK = ARGS[0] if ARGS else "/tmp/tr1"
NODE = os.environ.get("EM_NODE", "http://localhost:8000")
TOKEN = os.environ.get("EM_DEV_TOKEN", "")
FAILURES = []


def check(label, condition, detail=""):
    print(f"[SMOKE] {'PASS' if condition else 'FAIL'}: {label} {detail}")
    if not condition:
        FAILURES.append(label)


def mod(suffix):
    names = [n for n in sys.modules if n.endswith(".graph_origins") and n.startswith("bl_ext.")]
    import importlib
    return importlib.import_module(names[0].rsplit(".", 1)[0] + suffix)


if not TOKEN:
    print("[SMOKE] aborting: set EM_DEV_TOKEN")
    sys.exit(1)
shutil.rmtree(WORK, ignore_errors=True)
os.makedirs(WORK)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(WORK, "tr1.blend"))  # a folder for em_cache
scene = bpy.context.scene
em = scene.em_tools
ops = mod(".sync_manager.operators")
rs = mod(".sync_manager.room_session")
room_cfg = mod(".sync_manager.room")
commands = mod(".sync_manager.commands")
ss = mod(".sync_manager.scene_sync")
sc = mod(".sync_manager.scene_check")

xlsx = os.path.join(WORK, "example_stratigraphy.xlsx")
shutil.copyfile(os.path.expanduser("~/Documents/GitHub/s3Dgraphy/example_stratigraphy.xlsx"), xlsx)
em.table_import_type = "emdb_xlsx"
em.emdb_xlsx_file = xlsx
em.emdb_mapping = "excel_to_graphml_mapping"
check("the graph", bpy.ops.em.import_from_table() == {"FINISHED"})
from s3dgraphy import api, get_graph  # noqa: E402
from s3dgraphy.nodes.stratigraphic_node import StratigraphicNode  # noqa: E402
graph = get_graph(em.graphml_files[em.active_file_index].name)
units = [n for n in graph.nodes if isinstance(n, StratigraphicNode)]
scene.em_room_url = NODE
room_cfg.set_room(NODE, None, TOKEN)
check("into a new room", bpy.ops.em.room_bring(name=f"T-R1 {int(time.time())}", confirm=True)
      == {"FINISHED"})
ROOM = room_cfg.room().get("room_id")

# ── (1) two models published and documented ────────────────────────────────
bpy.ops.mesh.primitive_cube_add(location=(0, 0, 0))
survey = bpy.context.active_object
survey.name = "R1_survey"
bpy.ops.mesh.primitive_cone_add(location=(3, 0, 0))
recon = bpy.context.active_object
recon.name = "R1_reconstruction"
before = ss._section(graph)
for obj, unit, rid, axis in ((survey, units[0], "R1-survey.model", "reality_based"),
                             (recon, units[1], "R1-recon.model", "asserted")):
    r = commands.promote_model(unit.node_id, {"object": obj.name, "residency": "resident",
                                              "resource_id": rid}, bpy.context, graph)
    check(f"{obj.name} published", r.get("ok"), str(r.get("error")))
    api.hat_as_document(graph, rid, name=f"D.{obj.name}", geometry=axis)
for op in ss.section_delta_ops(before, ss._section(graph)):
    ops.emit_op(op)
deadline = time.time() + 10
while time.time() < deadline and rs.SESSION.waiting():
    ops._drain_inbox()
    time.sleep(0.1)
check("…and the room has them", rs.SESSION.waiting() == 0 and rs.SESSION.refused_ops == 0,
      f"waiting {rs.SESSION.waiting()} refused {rs.SESSION.refused_ops}")

# ── (2) gone from the scene; Sync brings each back where its origin says ───
for obj in (survey, recon):
    bpy.data.objects.remove(obj)
r = bpy.ops.em.scene_check(send="NONE")
lines = sc.ULTIMA_VERIFICA.get("sentences") or []
print("[SMOKE] sentences:", lines)
check("Sync says the origins", any(l.startswith("Origin:") and "1 reality-based" in l
                                   and "1 source-based" in l for l in lines),
      next((l for l in lines if l.startswith("Origin")), ""))
linked = [o for o in bpy.data.objects if o.get("em_asset_id") == "R1-survey.model"]
check("the reality-based one is LINKED from its library",
      bool(linked) and linked[0].data.library is not None
      and "em_cache" in (linked[0].data.library.filepath if linked[0].data.library else ""),
      str(linked and linked[0].data.library and linked[0].data.library.filepath))
resident = [o for o in bpy.data.objects if o.get("em_resource_id") == "R1-recon.model"]
check("the source-based one is RESIDENT", bool(resident) and resident[0].data.library is None
      and resident[0].library is None, str([o.name for o in resident]))

# ── (3) the source-based one edited: offered as a revision ─────────────────
obj = resident[0]
obj.data.vertices[0].co.z += 0.1
obj.data.update()
bpy.ops.em.scene_check(send="NONE", download=False)
rows = list(bpy.context.window_manager.em_sync_rows)
print("[SMOKE] offered:", [(x.object, x.state) for x in rows])
check("Sync offers the source-based one as changed",
      any(x.object == obj.name and x.state == "changed" and x.send for x in rows))
check("…and never the linked reality-based one",
      not any(x.object == (linked[0].name if linked else "") for x in rows))
bpy.ops.em.scene_check(send="CHANGED", download=False)
new_rid = obj.get("em_resource_id")
check("sent as a revision of its resource",
      any(e.edge_type == "was_revision_of" and e.edge_source == new_rid
          and e.edge_target == "R1-recon.model" for e in graph.edges), str(new_rid))
# ── (4) Q4 · the source-based one WITH VERSIONS goes into a library ──────
for o in bpy.context.view_layer.objects:
    o.select_set(False)
obj.select_set(True)
bpy.context.view_layer.objects.active = obj
before = ss._section(graph)
r = bpy.ops.em.asset_add_version(source="DECIMATE", ratio=0.5, use={"web"})
check("Q4: the reconstruction gets a version", r == {"FINISHED"}, str(r))
for op in ss.section_delta_ops(before, ss._section(graph)):
    ops.emit_op(op)
deadline = time.time() + 10
while time.time() < deadline and rs.SESSION.waiting():
    ops._drain_inbox()
    time.sleep(0.1)
asset = obj.get("em_asset_id")
check("…an asset with versions", bool(asset), str(asset))
for o in [o for o in bpy.data.objects if o.get("em_asset_id") == asset]:
    bpy.data.objects.remove(o)
bpy.ops.em.scene_check(send="NONE")
lines = sc.ULTIMA_VERIFICA.get("sentences") or []
print("[SMOKE] sentences:", [l for l in lines if l.startswith("Origin") or "missing" in l])
back = [o for o in bpy.data.objects if o.get("em_asset_id") == asset]
lib = back[0].data.library.filepath if back and back[0].data and back[0].data.library else ""
check("Q4: the source-based one with versions comes back LINKED from its library",
      bool(back) and "em_cache" in lib, f"{[o.name for o in back]} {lib}")
ops.leave_room()
print("[SMOKE] RESULT:", "ALL PASS" if not FAILURES else f"FAILED {FAILURES}")
sys.stdout.flush()
sys.exit(0 if not FAILURES else 1)
