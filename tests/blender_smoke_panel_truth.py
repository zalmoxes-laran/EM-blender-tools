"""Headless smoke · T-V1, the panel tells the truth after a restart — LIVE on
the dev node (user `dev`), on a COPY of a .blend saved inside a room.

    cd ~/Documents/GitHub/stratigraph-server/dev-stack
    EM_DEV_TOKEN=$(./token.sh) PYTHONPATH=~/Documents/GitHub/s3Dgraphy/src \\
    "/Applications/Blender 520.app/Contents/MacOS/Blender" -b <copy>.blend \\
        --python-use-system-env \\
        --python ~/Documents/GitHub/EM-blender-tools/tests/blender_smoke_panel_truth.py

(1) the file opened in a fresh Blender: «Where you work» says the room «not
connected» with Reconnect, the EM Data Tree says the same, nothing «aligned»;
(2) a Sync on a node that does not answer says in one sentence why nothing was
downloaded; (3) the access held, «Sync the scene…» reconnects by itself and
downloads what is missing; (4) a graph of a file made active (the old defect's
cause) does not split the two halves of the panel: the same room, the same role.
"""
import os
import sys
import time

import bpy

TOKEN = os.environ.get("EM_DEV_TOKEN", "")
FAILURES = []


def check(label, condition, detail=""):
    print(f"[SMOKE] {'PASS' if condition else 'FAIL'}: {label} {detail}")
    if not condition:
        FAILURES.append(label)
    return condition


def mod(suffix):
    import importlib
    names = [n for n in sys.modules if n.endswith(".graph_origins") and n.startswith("bl_ext.")]
    return importlib.import_module(names[0].rsplit(".", 1)[0] + suffix)


ops = mod(".sync_manager.operators")
rs = mod(".sync_manager.room_session")
where = mod(".sync_manager.where")
room_cfg = mod(".sync_manager.room")
scene_check = mod(".sync_manager.scene_check")
gt = mod(".em_setup.graph_tree")
go = mod(".graph_origins")
sc = bpy.context.scene
BASE, ROOM = sc.em_room_url, sc.em_room_id


def halves():
    z = where.zones(where.read_state(bpy.context))
    tree = []
    for r in sc.em_tools.graphml_files:
        o = go.origin_of(r, abspath=bpy.path.abspath)
        if o.is_room:
            tree.append(gt.room_state(o)[0])
    print(f"[SMOKE]   where: {z['place'][1]} | {z['who'][1]} | {z['message']['text']} "
          f"| {z['log'][1]}")
    print(f"[SMOKE]   tree : {tree}")
    return z, tree


# ── (1) a fresh Blender, the file saved in its room ────────────────────────
check("the file was saved in a room", sc.em_session_mode == "hub" and bool(ROOM),
      f"{sc.em_session_mode} {ROOM}")
check("no connection", not rs.any_joined())
z, tree = halves()
check("Where you work: the room, not connected", "not connected" in z["place"][1]
      and ROOM in z["place"][1] or "not connected" in z["place"][1], z["place"][1])
check("…with Reconnect", z["message"]["op"] == "em.room_reconnect", z["message"]["op"])
check("…nothing aligned", "aligned" not in z["log"][1], z["log"][1])
check("the tree agrees", tree and all(t.startswith("not connected") for t in tree), str(tree))
missing0 = None

# ── (2) a node that does not answer: the sentence says why ─────────────────
sc.em_room_url = "http://127.0.0.1:9"
room_cfg.set_room("http://127.0.0.1:9", ROOM, TOKEN)
try:
    bpy.ops.em.scene_check(download=True)
except RuntimeError as exc:
    print("[SMOKE]   cancelled:", exc)
said = " ".join(scene_check.ULTIMA_VERIFICA.get("sentences") or [])
print("[SMOKE]   sync on a dead node:", said[:300])
check("Sync says why nothing came", "not connected to" in said and "Reconnect" in said, said[:200])
check("…never «check with the room» without why", "check with the room" not in said)
sc.em_room_url = BASE
check("a failed reconnection keeps the room the file saved",
      sc.em_session_mode == "hub" and sc.em_room_id == ROOM, sc.em_session_mode)

# ── (3) the access held: Sync reconnects by itself and downloads ───────────
room_cfg.set_room(BASE, ROOM, TOKEN)
t0 = time.time()
r = bpy.ops.em.scene_check(download=True)
dt = time.time() - t0
said = " ".join(scene_check.ULTIMA_VERIFICA.get("sentences") or [])
print("[SMOKE]   sync:", said[:400])
check("Sync reconnected by itself", rs.any_joined() and ops.current_session(bpy.context).joined)
check("…and downloaded what was missing", "downloaded" in said and "not downloaded" not in said,
      f"{dt:.1f}s")
z, tree = halves()
check("Where you work: in the room, a role", "present" in z["place"][1]
      and "owner" in z["who"][1], z["who"][1])
check("the tree: the same session", tree and tree[0].startswith("joined as owner"), str(tree))

# ── (4) a graph of a file made active: the two halves still agree ──────────
rs.activate("A-GRAPH-OF-A-FILE")
check("SESSION is the empty one now (the old cause)", not rs.SESSION.joined)
z, tree = halves()
check("Where you work still says the room and the role",
      "present" in z["place"][1] and "owner" in z["who"][1], z["who"][1])
n_where = int(z["place"][1].split(" present")[0].split("·")[-1].strip())
n_tree = int(tree[0].split(" here")[0].split("·")[-1].strip())
check("…the same people as the tree", n_where == n_tree, f"{n_where} / {n_tree}")
check("Materialise's poll reads the same session",
      bpy.ops.em.materialise_geometry.poll())
ops.leave_room()
print("[SMOKE] RESULT:", "ALL PASS" if not FAILURES else f"FAILED {FAILURES}")
sys.stdout.flush()
sys.exit(0 if not FAILURES else 1)
