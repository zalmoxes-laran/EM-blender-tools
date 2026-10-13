"""Headless smoke · MICRO il proxy arriva come proprietà (13 Oct 2026) — LIVE
against the dev stack's room `tavolo-2026-10-12`. The .blend is NOT saved.

    TOKEN=$(~/Documents/GitHub/stratigraph-server/dev-stack/token.sh --user=editor2 | tail -1)
    EM_ROOM_URL=http://localhost:8000 EM_ROOM_ID=tavolo-2026-10-12 EM_ROOM_TOKEN=$TOKEN \\
    PYTHONPATH=~/Documents/GitHub/s3Dgraphy/src \\
    "/Applications/Blender 520.app/Contents/MacOS/Blender" -b --factory-startup \\
        --python-use-system-env \\
        --python ~/Documents/GitHub/EM-blender-tools/tests/blender_smoke_proxy_property.py

(1) enter the room adopting its document (measured: US1-3 carry the
`<US>.model` of an older EMtools, no proxy chain); (2) Graph info counts the
room's epoch, and an op-driven rebuild refreshes the counter (it used to be
written at import only); (3) the proxy of US3 — its own glb, fetched from the
room's store — is promoted as «Sync the scene…» promotes a new model: the room
gets `US3 ─has_property→ geometry ─has_semantic_shape→ SemanticShape
─has_linked_resource→ proxy_model`, never a new `<US>.model`; (4) «Sync the
scene…» migrates the other `<US>.model` once, and a second Sync finds nothing.
"""
import importlib
import os
import sys
import tempfile
import time

import bpy

ROOM_URL = os.environ["EM_ROOM_URL"]
ROOM = os.environ["EM_ROOM_ID"]
TOKEN = os.environ["EM_ROOM_TOKEN"]
FAILURES = []


def check(label, condition, detail=""):
    print(f"[SMOKE] {'PASS' if condition else 'FAIL'}: {label} {detail}", flush=True)
    if not condition:
        FAILURES.append(label)
    return condition


def finish():
    print("[SMOKE] RESULT:", "ALL PASS" if not FAILURES else f"FAILED {FAILURES}")
    sys.stdout.flush()
    sys.exit(0 if not FAILURES else 1)


try:
    bpy.ops.preferences.addon_enable(module="bl_ext.user_default.EM-blender-tools")
except Exception as exc:  # noqa: BLE001 — already enabled in a non-factory start
    print(f"[SMOKE] addon_enable: {exc}")
names = [n for n in sys.modules if n.endswith(".sync_manager.operators")]
PKG = names[0].rsplit(".sync_manager.operators", 1)[0]
ops = importlib.import_module(PKG + ".sync_manager.operators")
rs = importlib.import_module(PKG + ".sync_manager.room_session")
room_cfg = importlib.import_module(PKG + ".sync_manager.room")
ss = importlib.import_module(PKG + ".sync_manager.scene_sync")
cmds = importlib.import_module(PKG + ".sync_manager.commands")
pc = importlib.import_module(PKG + ".proxy_chain")
helpers = importlib.import_module(PKG + ".operators.addon_prefix_helpers")
fn = importlib.import_module(PKG + ".functions")
import s3dgraphy  # noqa: E402
print("[SMOKE] s3dgraphy from", s3dgraphy.__file__)

# ── (1) into the room ──────────────────────────────────────────────────────
arrival = ops.join_room(bpy.context, ROOM_URL, ROOM, TOKEN, adopt=True)
check("joined the room", arrival.get("ok"), str(arrival.get("message"))[:200])
ok, graph = fn.is_graph_available(bpy.context)
check("the room's graph is here", ok and graph is not None,
      f"{len(graph.nodes) if graph else 0} nodes")
legacy = [u for u, _n, _r in pc.legacy_unit_models(graph)]
print(f"[SMOKE] units with a <US>.model before: {legacy}")

# ── (2) Graph info: the epochs ─────────────────────────────────────────────
em_tools = bpy.context.scene.em_tools
row = em_tools.graphml_files[em_tools.active_file_index]
epochs = len(graph.indices.nodes_by_type.get("EpochNode", []))
check("Graph info counts the room's epoch at the entry",
      row.epoch_count == epochs and epochs >= 1, f"{row.epoch_count} of {epochs}")
row.epoch_count = 0            # as a .blend saved before the epoch was born
ops._repopulate(bpy.context, graph)   # what an incoming structural op triggers
check("an op-driven rebuild refreshes «Epochs»", row.epoch_count == epochs,
      f"{row.epoch_count}")

# ── (3) the proxy of US3, promoted ─────────────────────────────────────────
unit = graph.find_node_by_id("US3")
old = graph.find_node_by_id("US3.model")
digest = str((getattr(old, "data", None) or {}).get("checksum") or "")
if not check("US3's glb is in the room's store", bool(digest), digest[:20]):
    finish()
data, _media = room_cfg.get_asset(digest)
path = os.path.join(tempfile.mkdtemp(prefix="em-proxy-"), "US3.glb")
with open(path, "wb") as handle:
    handle.write(data)
before_objs = set(bpy.data.objects)
bpy.ops.import_scene.gltf(filepath=path)
imported = [o for o in bpy.data.objects if o not in before_objs and o.type == "MESH"]
check("the glb imported", len(imported) >= 1, str([o.name for o in imported]))
proxy = imported[0]
proxy.name = helpers.node_name_to_proxy_name(unit.name, context=bpy.context, graph=graph)
check("the object is US3's proxy by name",
      cmds._proxy_object_for(unit.name, bpy.context, graph) == proxy, proxy.name)

done = ss.send(bpy.context, graph, [{"object": proxy.name, "target": "US3",
                                     "kind": "proxy", "state": ss.STATE_NEW}])
check("sent", len(done["sent"]) == 1 and not done["failed"], str(done)[:300])
props, shapes, res = [], [], []
props = [e.edge_target for e in graph.edges
         if e.edge_source == "US3" and e.edge_type == "has_property"
         and getattr(graph.find_node_by_id(e.edge_target), "property_type", "") == "geometry"]
shapes = [e.edge_target for e in graph.edges
          if e.edge_source in props and e.edge_type == "has_semantic_shape"]
res = [e.edge_target for e in graph.edges
       if e.edge_source in shapes and e.edge_type == "has_linked_resource"]
check("US3 → has_property → geometry → SemanticShape → resource",
      len(props) == len(shapes) == len(res) == 1, f"{props} {shapes} {res}")
resource = graph.find_node_by_id(res[0]) if res else None
rdata = getattr(resource, "data", {}) or {}
check("the resource is a resident proxy_model with the bytes",
      rdata.get("url_type") == "proxy_model" and rdata.get("residency") == "resident"
      and bool(rdata.get("checksum")), str({k: rdata.get(k) for k in
                                            ("url_type", "residency", "checksum")}))
check("no unit cites a <US>.model for US3",
      not any(e.edge_source == "US3" and e.edge_type == "has_linked_resource"
              for e in graph.edges))
check("the object is bound to the chain's resource",
      proxy.get("em_resource_id") == (res[0] if res else None))

# ── (4) «Sync the scene…»: the rest migrated, once ─────────────────────────
r = bpy.ops.em.scene_check(download=False, send="NONE")
check("Sync the scene… ran", r == {"FINISHED"}, str(r))
left = [u for u, _n, _r in pc.legacy_unit_models(graph)]
check("no <US>.model left on a unit", left == [], str(left))
again = ss.migrate_proxy_models(bpy.context, graph)
check("a second sync migrates nothing", again["migrated"] == [] and again["ops"] == 0,
      str(again))

# the room answers what was sent — in background the timers do not run, so
# the drain the timer would call is called here
sess = rs.session_of_room(ROOM_URL, ROOM)
for _ in range(20):
    time.sleep(0.5)
    ops._drain_inbox()
    if sess is None or sess.waiting() == 0:
        break
check("the room confirmed every op", sess is not None and sess.waiting() == 0,
      f"sent {getattr(sess, 'sent_ops', '?')} answered {getattr(sess, 'answered_ops', '?')}"
      f" refused {getattr(sess, 'refused_ops', '?')}")
ops.leave_room(sess)
finish()
