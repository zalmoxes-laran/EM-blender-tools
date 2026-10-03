"""Headless smoke · M2, two rooms in one scene — LIVE against a StratiGraph node.

NOT a pytest test (needs bpy and a running node). After the T-M1 smoke has
written the two containers in EM_M1_WORK:

    EM_ROOM_URL=http://localhost:8000 EM_ROOM_TOKEN=$(stratigraph-server/dev-stack/token.sh) \\
    EM_M1_WORK=/tmp/micro-asset-versioni/m1g1 \\
    "/Applications/Blender 520.app/Contents/MacOS/Blender" -b \\
        --python tests/blender_smoke_two_rooms.py

1. the two graphs (Tempio Grande, Tempio accanto) are seated in two NEW rooms
   and Blender joins both: two sessions, one per graph, both joined;
2. with Tempio Grande active, an edit goes to ITS room only (an observer in
   each room says who received it);
3. an op sent in the second room lands in the second graph although the first
   is the active one;
4. leaving the active graph's room leaves the other joined.

The rooms are archived at the end. Exits non-zero on failure.
"""
import importlib
import json
import os
import queue
import sys
import time
import uuid

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
ops = importlib.import_module(PKG + ".sync_manager.operators")
rs = importlib.import_module(PKG + ".sync_manager.room_session")
room_cfg = importlib.import_module(PKG + ".sync_manager.room")
rooms_list = importlib.import_module(PKG + ".sync_manager.rooms_list")
inventory = importlib.import_module(PKG + ".sync_manager.inventory")
ws_client = importlib.import_module(PKG + ".sync_bridge.ws_client")
wire = importlib.import_module(PKG + ".sync_bridge.wire")
IMPORT = getattr(bpy.ops, "import")

BASE = os.environ.get("EM_ROOM_URL", "")
TOKEN = os.environ.get("EM_ROOM_TOKEN", "")
WORK = os.environ.get("EM_M1_WORK", "/tmp/micro-asset-versioni/m1g1")
if not (BASE and TOKEN):
    print("[SMOKE] aborting: set EM_ROOM_URL and EM_ROOM_TOKEN")
    sys.exit(1)

from s3dgraphy import get_graph                                    # noqa: E402
from s3dgraphy.exporter.emjson_exporter import build_emjson        # noqa: E402

ctx = bpy.context
em = ctx.scene.em_tools
while len(em.graphml_files):
    em.graphml_files.remove(0)
for f in ("TempioGrande.em.json", "TempioAccanto.em.json"):
    IMPORT.em_emjson(filepath=os.path.join(WORK, f))
gid_a, gid_b = em.graphml_files[0].name, em.graphml_files[1].name
ga, gb = get_graph(gid_a), get_graph(gid_b)
probe_id = next(n.node_id for n in ga.nodes
                if getattr(n, "node_type", "") == "US" and gb.find_node_by_id(n.node_id))
print(f"[SMOKE] graphs {gid_a[:8]} / {gid_b[:8]}, probe node {probe_id}")

# ── 1 · two rooms, seated, both joined ───────────────────────────────────────
tag = uuid.uuid4().hex[:6]
rid = []
for title, graph in ((f"m2 tempio grande {tag}", ga), (f"m2 tempio accanto {tag}", gb)):
    made = rooms_list.create_room(BASE, TOKEN, title)
    room_id = made.get("room_id") or made.get("id")
    seeded = rooms_list.send_ops(BASE, TOKEN, room_id,
                                 inventory.seed_ops(graph, build_emjson(graph)["graph"]))
    print(f"[SMOKE] room {room_id}: seeded {seeded['applied']} ops")
    rid.append(room_id)

j1 = ops.join_room(ctx, BASE, rid[0], TOKEN, adopt=True)
j2 = ops.join_room(ctx, BASE, rid[1], TOKEN, adopt=True)
check("both joins succeed", j1["ok"] and j2["ok"], f"{j1.get('message')} | {j2.get('message')}")
# A room's graph is the room's (D-A): adopting it brings a graph whose id is the
# room's, beside the file's graph it was seeded from. Those are the bound ones.
room_graph = {rs.where_of(g)["room_id"]: g for g in list(rs._by_graph)}
print(f"[SMOKE] bound: {room_graph}")
gid_a, gid_b = room_graph.get(rid[0]), room_graph.get(rid[1])
ga, gb = get_graph(gid_a), get_graph(gid_b)
sa, sb = rs.session_of(gid_a), rs.session_of(gid_b)
check("one session per graph", sa is not None and sb is not None and sa is not sb)
check("both rooms joined at once", bool(sa and sa.joined and sb and sb.joined))
check("each room's graph is bound to its room", bool(gid_a and gid_b))
rows = {r.name: r for r in em.graphml_files}
check("the rows record the room as their origin",
      (rows[gid_a].origin_kind, rows[gid_a].origin_room) == ("ROOM", rid[0])
      and (rows[gid_b].origin_kind, rows[gid_b].origin_room) == ("ROOM", rid[1]))
check("the room just entered is the graph in front, and its room the edit target",
      em.graphml_files[em.active_file_index].name == gid_b and rs.SESSION is sb)
tree = importlib.import_module(PKG + ".graph_origins").tree(
    em.graphml_files, abspath=bpy.path.abspath)
for origin, ix in tree:
    print(f"[SMOKE] branch {origin.kind} {origin.label!r} → "
          f"{[em.graphml_files[i].name[:12] for i in ix]}")
check("the tree has four branches: two files, two rooms",
      [o.kind for o, _ in tree] == ["FILE", "FILE", "ROOM", "ROOM"])
check("the scene says Room mode", ops.session_mode(ctx) == ops.MODE_HUB)


def observer(room_id):
    url = BASE.replace("http", "ws", 1).rstrip("/") + f"/v1/rooms/{room_id}/ws"
    client = ws_client.WsClient(url, headers={"Authorization": f"Bearer {TOKEN}"})
    client.connect(timeout=10)
    time.sleep(0.5)
    while True:
        try:
            client.inbox.get_nowait()
        except queue.Empty:
            break
    return client


def ops_seen(client, wait=2.5):
    seen, end = [], time.time() + wait
    while time.time() < end:
        try:
            msg = json.loads(client.inbox.get(timeout=0.2))
        except queue.Empty:
            continue
        if msg.get("type") == "op":
            seen.append(msg.get("payload") or {})
    return seen


obs = [observer(r) for r in rid]

# ── 2 · the active graph's room receives the edit, the other does not ────────
idx_a = next(i for i, r in enumerate(em.graphml_files) if r.name == gid_a)
bpy.ops.em.graph_activate(index=idx_a)
check("activating Tempio Grande points the edits at its room",
      rs.SESSION is sa and room_cfg.room()["room_id"] == rid[0])
# `add_node`: one of the five verbs a room accepts and EMtools applies (a
# room refuses `update_node` — measured: «unknown operation 'update_node'»)
new_a = f"m2-from-blender-{tag}"
ops.emit_op({"type": "op", "op": "add_node",
             "node": {"id": new_a, "node_type": "US", "name": f"US M2 {tag}",
                      "description": "", "data": {"lang": "it"}}})
seen1, seen2 = ops_seen(obs[0]), ops_seen(obs[1], wait=1.0)
for m in sa.drain():
    print(f"[SMOKE] room 1 answered Blender: {m.get('type')} "
          f"{json.dumps(m.get('payload'))[:200]}")
def _ids(seen):
    return [(p.get("node") or {}).get("id") for p in seen]


check("the edit reached Tempio Grande's room", new_a in _ids(seen1), str(_ids(seen1)))
check("…and not the other room", new_a not in _ids(seen2), str(_ids(seen2)))

# ── 3 · an op in the second room lands in the second graph ───────────────────
new_b = f"m2-from-room-2-{tag}"
obs[1].send(json.dumps(wire.envelope(
    "op", {"op": "add_node", "node": {"id": new_b, "node_type": "US",
                                      "name": f"US M2 room 2 {tag}",
                                      "description": "", "data": {"lang": "it"}}},
    source="m2-observer")))
time.sleep(1.5)
for _ in range(10):
    try:
        m = json.loads(obs[1].inbox.get_nowait())
        print(f"[SMOKE] room 2 answered the observer: {m.get('type')} "
              f"{json.dumps(m.get('payload'))[:200]}")
    except queue.Empty:
        break
ops._drain_inbox()                      # in -b the timers do not run: same function
check("the op of room 2 landed in room 2's graph", gb.find_node_by_id(new_b) is not None)
check("…and not in the active graph (room 1's)", ga.find_node_by_id(new_b) is None)

# ── 4 · leaving A's room leaves B's joined ───────────────────────────────────
ops.leave_room()
check("A's room left", bool(sa) and not sa.joined and rs.session_of(gid_a) is None)
check("B's room still joined", bool(sb) and sb.joined and rs.session_of(gid_b) is sb)

for c in obs:
    c.close()
ops._lascia_tutte_le_stanze()
check("standalone leaves every room", not rs.any_joined())
import urllib.request                                              # noqa: E402
for r in rid:
    try:
        req = urllib.request.Request(f"{BASE.rstrip('/')}/v1/rooms/{r}/archive",
                                     data=b"{}", method="POST",
                                     headers={"Authorization": f"Bearer {TOKEN}",
                                              "Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10).read()
        print(f"[SMOKE] archived {r}")
    except Exception as exc:  # noqa: BLE001
        print(f"[SMOKE] could not archive {r}: {exc}")

print(f"[SMOKE] {'OK' if not FAILURES else 'FAILED: ' + ', '.join(FAILURES)}")
sys.exit(1 if FAILURES else 0)
