"""Headless smoke · T-P2, «Sync the scene…» on the COPY of Templu Mare — LIVE
against the dev node (user `dev` of the realm `em-dev`). The .blend is NOT saved.

    cd ~/Documents/GitHub/stratigraph-server/dev-stack
    EM_DEV_TOKEN=$(./token.sh) EM_NODE=http://localhost:8000 \\
    PYTHONPATH=~/Documents/GitHub/s3Dgraphy/src \\
    "/Applications/Blender 520.app/Contents/MacOS/Blender" -b --python-use-system-env \\
        ~/Documents/GitHub/_datasets/templu-mare-prove/GreatTemple_2026_v3_multigraph_test_CLAUDE.blend \\
        --python ~/Documents/GitHub/EM-blender-tools/tests/blender_smoke_sync_scene.py

(1) the graph of slot 0 (its GraphML copied to a temporary folder first), brought
into a NEW room — the proxies published; (2) one proxy is removed from the
scene and another one is edited (a vertex moved); (3) Sync without the dialog
and sending nothing: the removed one is downloaded, the edited one is offered,
ticked; (4) Sync sending the changed ones: it goes as a revision of its
resource, the citations moved, the change reaches the room; (5) the next check
says 0 changed and owes the scene nothing.
"""
import importlib
import os
import shutil
import sys
import tempfile
import time

import bpy

NODE = os.environ.get("EM_NODE", "http://localhost:8000")
TOKEN = os.environ.get("EM_DEV_TOKEN", "")
FAILURES = []


def check(label, condition, detail=""):
    print(f"[SMOKE] {'PASS' if condition else 'FAIL'}: {label} {detail}")
    if not condition:
        FAILURES.append(label)
    return condition


def finish():
    print("[SMOKE] RESULT:", "ALL PASS" if not FAILURES else f"FAILED {FAILURES}")
    sys.stdout.flush()
    sys.exit(0 if not FAILURES else 1)


names = [n for n in sys.modules if n.endswith(".graph_origins") and n.startswith("bl_ext.")]
PKG = names[0].rsplit(".graph_origins", 1)[0]
ops = importlib.import_module(PKG + ".sync_manager.operators")
rs = importlib.import_module(PKG + ".sync_manager.room_session")
room_cfg = importlib.import_module(PKG + ".sync_manager.room")
sc = importlib.import_module(PKG + ".sync_manager.scene_check")
ss = importlib.import_module(PKG + ".sync_manager.scene_sync")
bring = importlib.import_module(PKG + ".sync_manager.bring")
if not TOKEN:
    print("[SMOKE] aborting: set EM_DEV_TOKEN")
    sys.exit(1)

scene = bpy.context.scene
row0 = scene.em_tools.graphml_files[0]
src0 = bpy.path.abspath(row0.graphml_path)
if src0.lower().endswith(".graphml"):
    dst0 = os.path.join(tempfile.mkdtemp(prefix="em-smoke-"), os.path.basename(src0))
    shutil.copy2(src0, dst0)
    row0.graphml_path = dst0
scene.em_tools.active_file_index = 0
getattr(bpy.ops, "import").em_graphml(graphml_index=0)
from s3dgraphy import get_graph  # noqa: E402
graph = get_graph(scene.em_tools.graphml_files[0].name)
check("the graph of slot 0", graph is not None and len(graph.nodes) > 0,
      f"{len(graph.nodes)} nodes")

# ── (1) into a new room ────────────────────────────────────────────────────
scene.em_room_url = NODE
room_cfg.set_room(NODE, None, TOKEN)
t0 = time.time()
r = bpy.ops.em.room_bring(name=f"T-P2 {int(time.time())}", confirm=True)
check("Bring into a room", r == {"FINISHED"}, f"{r} in {time.time() - t0:.0f} s")
ROOM = room_cfg.room().get("room_id")
check("Blender is in the room", rs.SESSION.joined, str(ROOM))
proxies = [m for m in bring.scene_models(bpy.context, graph) if m["kind"] == "proxy"
           and bpy.data.objects[m["object"]].get("em_asset_sha256")]
check("published proxies to work on", len(proxies) >= 2, str(len(proxies)))

# ── (2) one removed, one edited ────────────────────────────────────────────
gone, edited = proxies[0], proxies[1]
gone_digest = bpy.data.objects[gone["object"]]["em_asset_sha256"]
bpy.data.objects.remove(bpy.data.objects[gone["object"]])
obj = bpy.data.objects[edited["object"]]
old_rid = obj["em_resource_id"]
obj.data.vertices[0].co.x += 0.05
obj.data.update()

# ── (3) Sync, sending nothing ──────────────────────────────────────────────
r = bpy.ops.em.scene_check(send="NONE")
check("Sync (check only)", r == {"FINISHED"}, str(r))
lines = sc.ULTIMA_VERIFICA.get("sentences") or []
print("[SMOKE] sentences:", lines[:6])
print("[SMOKE] counts:", sc.ULTIMA_VERIFICA.get("counts"))
# a proxy's bytes are cited twice (its model and its chain's glb): one
# download, the second record reuses it
check("it downloaded the removed one", any("missing:" in l and " downloaded" in l for l in lines)
      and any(o.get("em_asset_sha256") == gone_digest for o in bpy.data.objects),
      next((l for l in lines if "missing" in l), ""))
rows = list(bpy.context.window_manager.em_sync_rows)
offered = [x for x in rows if x.object == edited["object"]]
check("the edited one is offered as changed", bool(offered) and offered[0].state == "changed",
      str([(x.object, x.state) for x in rows][:5]))
check("…ticked by default", bool(offered) and offered[0].send)
check("…and nothing else is changed", sum(1 for x in rows if x.state == "changed") == 1,
      str(sum(1 for x in rows if x.state == "changed")))
check("the counts say ≠ 1 changed", "≠ 1 changed" in (sc.ULTIMA_VERIFICA.get("counts") or ""))

# ── (4) Sync, sending the changed ones ─────────────────────────────────────
sent_before = rs.SESSION.sent_ops
r = bpy.ops.em.scene_check(send="CHANGED", download=False)
check("Sync (send the changed)", r == {"FINISHED"}, str(r))
done = sc.ULTIMA_VERIFICA.get("sent") or {}
check("one model sent", len(done.get("sent") or []) == 1, str(done))
new_rid = obj.get("em_resource_id")
check("as a new revision of its resource", new_rid and new_rid != old_rid
      and any(e.edge_type == "was_revision_of" and e.edge_source == new_rid
              and e.edge_target == old_rid for e in graph.edges), f"{old_rid} → {new_rid}")
check("the old one stays in the graph", graph.find_node_by_id(old_rid) is not None)
check("its changes went to the room as operations", rs.SESSION.sent_ops > sent_before,
      f"{rs.SESSION.sent_ops - sent_before} op(s), {done.get('ops')} in the delta")
deadline = time.time() + 10
while time.time() < deadline and rs.SESSION.waiting():
    ops._drain_inbox()
    time.sleep(0.1)
check("…every one answered", rs.SESSION.waiting() == 0 and rs.SESSION.refused_ops == 0,
      f"waiting {rs.SESSION.waiting()}, refused {rs.SESSION.refused_ops}")

# ── (5) the next check ─────────────────────────────────────────────────────
r = bpy.ops.em.scene_check(send="NONE", download=False)
counts = sc.ULTIMA_VERIFICA.get("counts") or ""
print("[SMOKE] counts after:", counts)
check("the next check says 0 changed", "≠ 0 changed" in counts, counts)
check("…and owes the scene nothing", "✕ 0 missing" in counts, counts)
reader = rs.RoomSession()
room_cfg.set_room(NODE, ROOM, TOKEN)
doc = reader.join()["snapshot"]["payload"]["doc"]
reader.leave()
ids = {n.get("id") for sec in doc.get("graphs", {}).values() if isinstance(sec, dict)
       for n in sec.get("nodes") or []}
check("the room holds the revision", new_rid in ids, str(new_rid))
ops.leave_room()
finish()
