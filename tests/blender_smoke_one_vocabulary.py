"""Headless smoke · V1, one vocabulary of operations — LIVE against a StratiGraph node.

NOT a pytest test (needs bpy and a running node). With s3Dgraphy from source
(the translator is newer than the bundled wheel until the next release):

    PYTHONPATH=~/Documents/GitHub/s3Dgraphy/src \\
    EM_V1_EMJSON=/tmp/micro-asset-versioni/m1g1/TempioGrande.em.json \\
    EM_ROOM_URL=http://localhost:8000 EM_ROOM_TOKEN=$(stratigraph-server/dev-stack/token.sh) \\
    "/Applications/Blender 520.app/Contents/MacOS/Blender" -b --python-use-system-env \\
        --python tests/blender_smoke_one_vocabulary.py

The measured defect (4 Oct 2026): a description written in Blender reached the
room as `update_node`, which the library refuses — «unknown operation
'update_node'» — so it never arrived. Here:

1. a description typed in the EM list (the panel's own update callback) leaves
   as `update_field` and the room applies it; an observer in the room (what
   EMStudio is on the wire) receives it;
2. the other way: an `update_field` from the observer lands in Blender's node
   AND in its list row;
3. an EMStudio before V1 (`update_node{patch}`) still lands: translated by the
   library at the door;
4. a verb nobody speaks, and an operation the ROOM refuses (a node that is not
   there), each become a sentence in `RIFIUTI` — what the panel and the status
   bar show — never a silent drop.

The room is archived at the end. Exits non-zero on failure.
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
rooms_list = importlib.import_module(PKG + ".sync_manager.rooms_list")
inventory = importlib.import_module(PKG + ".sync_manager.inventory")
ws_client = importlib.import_module(PKG + ".sync_bridge.ws_client")
wire = importlib.import_module(PKG + ".sync_bridge.wire")
IMPORT = getattr(bpy.ops, "import")

import s3dgraphy                                                   # noqa: E402
from s3dgraphy import crdt, get_graph                              # noqa: E402
from s3dgraphy.exporter.emjson_exporter import build_emjson        # noqa: E402
print("[SMOKE] s3dgraphy from", s3dgraphy.__file__)
if not hasattr(crdt, "ops_for_local_change"):
    print("[SMOKE] aborting: this s3dgraphy has no ops_for_local_change (PYTHONPATH?)")
    sys.exit(1)

BASE = os.environ.get("EM_ROOM_URL", "")
TOKEN = os.environ.get("EM_ROOM_TOKEN", "")
HERE = os.path.dirname(os.path.abspath(__file__))
if not (BASE and TOKEN):
    print("[SMOKE] aborting: set EM_ROOM_URL and EM_ROOM_TOKEN")
    sys.exit(1)

ctx = bpy.context
em = ctx.scene.em_tools
while len(em.graphml_files):
    em.graphml_files.remove(0)
IMPORT.em_emjson(filepath=os.environ.get(
    "EM_V1_EMJSON", "/tmp/micro-asset-versioni/m1g1/TempioGrande.em.json"))
g0 = get_graph(em.graphml_files[0].name)

tag = uuid.uuid4().hex[:6]
made = rooms_list.create_room(BASE, TOKEN, f"v1 one vocabulary {tag}")
room_id = made.get("room_id") or made.get("id")
seeded = rooms_list.send_ops(BASE, TOKEN, room_id,
                             inventory.seed_ops(g0, build_emjson(g0)["graph"]))
print(f"[SMOKE] room {room_id}: seeded {seeded['applied']} ops")
j = ops.join_room(ctx, BASE, room_id, TOKEN, adopt=True)
check("joined", j["ok"], j.get("message", ""))
gid = next(g for g in list(rs._by_graph) if rs.where_of(g)["room_id"] == room_id)
g = get_graph(gid)
sess = rs.session_of(gid)


def observer():
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


def seen(client, kind="op", wait=2.5):
    out, end = [], time.time() + wait
    while time.time() < end:
        try:
            msg = json.loads(client.inbox.get(timeout=0.2))
        except queue.Empty:
            continue
        if msg.get("type") == kind:
            out.append(msg.get("payload") or {})
    return out


def drain_blender(wait=1.5):
    time.sleep(wait)
    ops._drain_inbox()            # in -b the timers do not run: same function


obs = observer()
units = ctx.scene.em_tools.stratigraphy.units
row = next((u for u in units if g.find_node_by_id(u.node_id) is not None
            or any(n.name == u.name for n in g.nodes)), None)
check("a unit row of the room's graph", row is not None)
node = g.find_node_by_id(row.node_id) if row.node_id else next(n for n in g.nodes if n.name == row.name)
print(f"[SMOKE] probe: {node.name} ({node.node_id})")

# ── 1 · Blender → room → the observer ───────────────────────────────────────
text1 = f"written in Blender {tag}"
row.description = text1                       # the panel's own update callback
got = seen(obs)
fields = [(p.get("op"), p.get("node_id"), p.get("field"), p.get("value")) for p in got]
check("the room broadcast an update_field of the description",
      ("update_field", node.node_id, "description", text1) in fields, str(fields)[:300])
check("…and no update_node left Blender", not any(p.get("op") == "update_node" for p in got))
results = [m.get("payload") for m in sess.drain() if m.get("type") == "op_result"]
check("the room answered Blender: applied", any(r.get("applied") for r in results),
      str(results)[:300])

# ── 2 · the observer (EMStudio on the wire) → Blender ───────────────────────
text2 = f"written in EMStudio {tag}"
obs.send(json.dumps(wire.envelope("op", {
    "op": "update_field", "node_id": node.node_id, "field": "description",
    "value": text2, "ts": "2099-01-01T00:00:00Z"}, source="v1-observer")))
drain_blender()
check("the description arrived in Blender's node", node.description == text2,
      repr(node.description))
check("…and in its EM list row", row.description == text2, repr(row.description))

# ── 3 · an EMStudio before V1: update_node{patch}, translated at the door ───
text3 = f"legacy patch {tag}"
ops._apply_op({"op": "update_node", "node_id": node.node_id,
               "patch": {"description": text3}, "ts": "2099-01-02T00:00:00Z"}, ctx, g)
check("a legacy update_node still lands (translated)", node.description == text3)

# ── 4 · refusals are sentences ──────────────────────────────────────────────
ops.RIFIUTI.clear()
ops.emit_op({"op": "rename_node", "node_id": node.node_id})
check("a verb nobody speaks is a sentence, not a drop",
      bool(ops.RIFIUTI) and "unknown operation 'rename_node'" in ops.RIFIUTI[0]["frase"],
      str(ops.RIFIUTI[:1]))
ops.RIFIUTI.clear()
ops.emit_op({"op": "update_node", "node_id": f"nobody-{tag}", "patch": {"description": "x"}})
drain_blender(2.0)
check("an operation the room refuses is a sentence in Blender",
      any("is not here" in r["frase"] for r in ops.RIFIUTI), str(ops.RIFIUTI[:2]))
for r in ops.RIFIUTI[:3]:
    print(f"[SMOKE] refusal shown: {r['ora']} · {r['frase']}")

obs.close()
ops._lascia_tutte_le_stanze()
import urllib.request                                              # noqa: E402
try:
    req = urllib.request.Request(f"{BASE.rstrip('/')}/v1/rooms/{room_id}/archive",
                                 data=b"{}", method="POST",
                                 headers={"Authorization": f"Bearer {TOKEN}",
                                          "Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=10)
    print(f"[SMOKE] room {room_id} archived")
except Exception as exc:  # noqa: BLE001
    print(f"[SMOKE] could not archive {room_id}: {exc}")

print(f"[SMOKE] {'ALL PASS' if not FAILURES else 'FAILURES: ' + ', '.join(FAILURES)}")
sys.exit(1 if FAILURES else 0)
