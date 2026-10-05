"""Headless smoke · T-P1, offline is kept and sent again — LIVE against the dev
node (user `dev` of the realm `em-dev`), the room's document read from Postgres.

    cd ~/Documents/GitHub/stratigraph-server/dev-stack
    EM_DEV_TOKEN=$(./token.sh) EM_NODE=http://localhost:8000 \\
    PYTHONPATH=~/Documents/GitHub/s3Dgraphy/src \\
    "/Applications/Blender 520.app/Contents/MacOS/Blender" -b --python-use-system-env \\
        --python ~/Documents/GitHub/EM-blender-tools/tests/blender_smoke_offline_queue.py -- /tmp/tp1

(1) a graph from s3Dgraphy's example xlsx, brought into a NEW room of the node;
(2) the WebSocket is closed under the session; three edits through `emit_op`
wait («3 edits waiting to be sent») and the seat is kept; (3) `join_room` again
→ `resume`, the three go as they were, every one answered; (4) the room's
document, read from Postgres after a save, has the three; (5) the same with the
room compacted past the base meanwhile (an observer writes, acks, saves) →
`resync`, re-stamped, the emptying kept, the three in Postgres; (6) a left room
parks its waiting edit, a save keeps it in the .blend, a load puts it back.
"""
import json
import os
import shutil
import subprocess
import sys
import time

import bpy

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
WORK = ARGS[0] if ARGS else "/tmp/tp1"
NODE = os.environ.get("EM_NODE", "http://localhost:8000")
TOKEN = os.environ.get("EM_DEV_TOKEN", "")
FAILURES = []


def check(label, condition, detail=""):
    print(f"[SMOKE] {'PASS' if condition else 'FAIL'}: {label} {detail}")
    if not condition:
        FAILURES.append(label)
    return condition


def mod(suffix):
    names = [n for n in sys.modules if n.endswith(".graph_origins") and n.startswith("bl_ext.")]
    import importlib
    return importlib.import_module(names[0].rsplit(".", 1)[0] + suffix)


def finish():
    print("[SMOKE] RESULT:", "ALL PASS" if not FAILURES else f"FAILED {FAILURES}")
    sys.stdout.flush()
    sys.exit(0 if not FAILURES else 1)


def pump(seconds=4.0, until=None):
    """The drain Blender's timers would run, by hand (headless)."""
    deadline = time.time() + seconds
    while time.time() < deadline:
        ops._drain_inbox()
        if until is not None and until():
            return True
        time.sleep(0.1)
    return until() if until is not None else True


def postgres_doc(room_id):
    """The room's latest document as Postgres holds it (the node's store)."""
    sql = ("select doc::text from documents where project_id = "
           f"'{room_id}' order by revision desc limit 1")
    out = subprocess.run(["docker", "exec", "em-dev-postgres", "psql", "-U", "em",
                          "-d", "em_documents", "-At", "-c", sql],
                         capture_output=True, text=True, timeout=30)
    try:
        return json.loads(out.stdout.strip() or "{}")
    except ValueError:
        return {}


def nodes_of(doc):
    return {n.get("id"): n for sec in (doc.get("graphs") or {}).values()
            if isinstance(sec, dict) for n in (sec.get("nodes") or [])}


if not TOKEN:
    print("[SMOKE] aborting: set EM_DEV_TOKEN (dev-stack/token.sh)")
    sys.exit(1)

os.makedirs(WORK, exist_ok=True)
scene = bpy.context.scene
em = scene.em_tools
ops = mod(".sync_manager.operators")
rs = mod(".sync_manager.room_session")
room_cfg = mod(".sync_manager.room")

# ── (1) the graph, into a new room ─────────────────────────────────────────
xlsx = os.path.join(WORK, "example_stratigraphy.xlsx")
shutil.copyfile(os.path.expanduser("~/Documents/GitHub/s3Dgraphy/example_stratigraphy.xlsx"), xlsx)
em.table_import_type = "emdb_xlsx"
em.emdb_xlsx_file = xlsx
em.emdb_mapping = "excel_to_graphml_mapping"
check("the graph from the table", bpy.ops.em.import_from_table() == {"FINISHED"})
from s3dgraphy import get_graph  # noqa: E402
graph = get_graph(em.graphml_files[em.active_file_index].name)
from s3dgraphy.nodes.stratigraphic_node import StratigraphicNode  # noqa: E402
units = [n for n in graph.nodes if isinstance(n, StratigraphicNode)][:5]
check("five units to edit", len(units) == 5, str(len(units)))
scene.em_room_url = NODE
room_cfg.set_room(NODE, None, TOKEN)
r = bpy.ops.em.room_bring(name=f"T-P1 {int(time.time())}", confirm=True)
check("Bring into a room", r == {"FINISHED"}, str(r))
ROOM = room_cfg.room().get("room_id")
check("Blender is in the room", bool(ROOM) and rs.SESSION.joined, str(ROOM))
pump(2.0)


def edit(node, text):
    node.description = text
    ops.emit_op({"op": "update_node", "node_id": node.node_id,
                 "patch": {"description": text}})


# one edit online first: answered, it is the base the re-entry compares
edit(units[4], f"T-P1 online {ROOM}")
check("the online edit is answered (a base)",
      pump(6.0, until=lambda: rs.SESSION.waiting() == 0) and bool(rs.SESSION.last_applied),
      str(rs.SESSION.last_applied))

# ── (2) the WebSocket closes; three edits wait ─────────────────────────────
rs.SESSION.client.close()
check("the connection dropped, the seat is kept",
      rs.SESSION.offline and rs.SESSION.seated and not rs.SESSION.joined)
for i, unit in enumerate(units[:3]):
    edit(unit, f"T-P1 offline edit {i} {ROOM}")
status = ops.room_status(bpy.context)
check("three edits waiting to be sent", status["waiting"] == 3 and status["offline"],
      f"waiting={status['waiting']}")

# ── (3) the re-entry: resume ───────────────────────────────────────────────
res = ops.join_room(bpy.context, NODE, ROOM, TOKEN, adopt=True)
check("back in the room", res["ok"] and rs.SESSION.joined, res.get("message", ""))
check("…as a resume", res.get("plan") == "resume", str(res.get("plan")))
check("…the three sent again as they were",
      "3 waiting edit(s) sent again (as they were)" in res["message"], res["message"])
check("every one answered: aligned",
      pump(8.0, until=lambda: rs.SESSION.waiting() == 0), f"waiting={rs.SESSION.waiting()}")
rs.SESSION.send("request_save")
pump(2.0)
doc = postgres_doc(ROOM)
got = nodes_of(doc)
check("Postgres holds the room's document", bool(got), f"{len(got)} nodes")
for i, unit in enumerate(units[:3]):
    check(f"…with offline edit {i}",
          (got.get(unit.node_id) or {}).get("description") == f"T-P1 offline edit {i} {ROOM}",
          str((got.get(unit.node_id) or {}).get("description")))

# ── (5) the room compacts past the base meanwhile: resync ──────────────────
base = rs.SESSION.last_applied
rs.SESSION.client.close()
for i, unit in enumerate(units[2:4]):
    edit(unit, f"T-P1 after compaction {i} {ROOM}")
# an emptying, made offline: it must come back as an act
target = units[0]
target.description = ""
ops.emit_op({"op": "update_field", "node_id": target.node_id, "field": "description",
             "remove": True})
check("three more waiting", rs.SESSION.waiting() == 3, str(rs.SESSION.waiting()))
observer = rs.RoomSession()
room_cfg.set_room(NODE, ROOM, TOKEN)
observer.join()
time.sleep(0.5)
observer.send_op({"op": "update_field", "node_id": units[4].node_id,
                  "field": "description", "value": f"observer {ROOM}",
                  "ts": time.strftime("%Y-%m-%dT%H:%M:%S.000000Z", time.gmtime())})
answer = None
deadline = time.time() + 6
while time.time() < deadline and answer is None:
    for m in observer.drain():
        if m.get("type") == "op_result":
            answer = m
    time.sleep(0.1)
later = ((answer or {}).get("payload") or {}).get("op", {}).get("ts")
observer.send("ack", {"ts": later})
time.sleep(0.3)
observer.send("request_save")
time.sleep(1.0)
res = ops.join_room(bpy.context, NODE, ROOM, TOKEN, adopt=True)
check("back in the compacted room", res["ok"], res.get("message", ""))
check("…as a resync (the base was older than the compaction point)",
      res.get("plan") == "resync", f"plan={res.get('plan')} base={base} gc={rs.SESSION.gc_watermark}")
check("…the three re-stamped", "re-stamped" in res["message"], res["message"])
check("every one answered", pump(8.0, until=lambda: rs.SESSION.waiting() == 0),
      f"waiting={rs.SESSION.waiting()}")
rs.SESSION.send("request_save")
pump(2.0)
got = nodes_of(postgres_doc(ROOM))
for i, unit in enumerate(units[2:4]):
    check(f"Postgres: re-stamped edit {i}",
          (got.get(unit.node_id) or {}).get("description") == f"T-P1 after compaction {i} {ROOM}",
          str((got.get(unit.node_id) or {}).get("description")))
check("Postgres: the emptying made offline holds",
      not (got.get(target.node_id) or {}).get("description"),
      str((got.get(target.node_id) or {}).get("description")))
check("Postgres: the observer's edit is there too",
      (got.get(units[4].node_id) or {}).get("description") == f"observer {ROOM}")
observer.leave()

# ── (6) leave with a waiting edit: parked, kept in the .blend ──────────────
rs.SESSION.client.close()
edit(units[1], f"T-P1 parked {ROOM}")
ops.leave_room()
check("left: the edit is parked for its room", rs.parked_for(NODE, ROOM) == 1)
blend = os.path.join(WORK, "tp1.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend, copy=True)
kept = json.loads(bpy.context.scene.em_room_unconfirmed or "{}")
check("the .blend keeps it", sum(len(v["ops"]) for v in kept.values()) == 1, str(list(kept)))
rs.take_parked(NODE, ROOM)
bpy.ops.wm.open_mainfile(filepath=blend)
check("…and a load puts it back", rs.parked_for(NODE, ROOM) == 1)
res = ops.join_room(bpy.context, NODE, ROOM, TOKEN, adopt=True)
check("the next entry sends it", res["ok"] and "1 waiting edit(s) sent again" in res["message"],
      res.get("message", ""))
check("answered", pump(8.0, until=lambda: rs.SESSION.waiting() == 0))
ops.leave_room()
with open(os.path.join(WORK, "room.txt"), "w") as fh:
    fh.write(str(ROOM))
finish()
