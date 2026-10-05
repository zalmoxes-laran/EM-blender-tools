"""Headless smoke · T-J1, entering a room with the copy of Templu Mare open —
LIVE against the dev node (user `dev` of the realm `em-dev`).

    cd ~/Documents/GitHub/stratigraph-server/dev-stack
    EM_DEV_TOKEN=$(./token.sh) EM_NODE=http://localhost:8000 EM_ROOM=<a room of dev> \\
    PYTHONPATH=~/Documents/GitHub/s3Dgraphy/src \\
    "/Applications/Blender 520.app/Contents/MacOS/Blender" -b --python-use-system-env \\
        ~/Documents/GitHub/_datasets/templu-mare-prove/GreatTemple_2026_v3_multigraph_test_CLAUDE.blend \\
        --python ~/Documents/GitHub/EM-blender-tools/tests/blender_smoke_entry_choice.py

(1) the copy holds graphs: entering a room asks first (open the package / a new
file / merge) and joins nothing; (2) «start a new file»: a new file takes the
place of the copy in this Blender, the room's contents come into it, and the
copy on disk is intact (sha256 before and after). The copy is never saved.
"""
import hashlib
import importlib
import os
import sys

import bpy

NODE = os.environ.get("EM_NODE", "http://localhost:8000")
TOKEN = os.environ.get("EM_DEV_TOKEN", "")
ROOM = os.environ.get("EM_ROOM", "")
FAILURES = []


def check(label, condition, detail=""):
    print(f"[SMOKE] {'PASS' if condition else 'FAIL'}: {label} {detail}")
    if not condition:
        FAILURES.append(label)


def sha(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


names = [n for n in sys.modules if n.endswith(".graph_origins") and n.startswith("bl_ext.")]
PKG = names[0].rsplit(".graph_origins", 1)[0]
rs = importlib.import_module(PKG + ".sync_manager.room_session")
room_cfg = importlib.import_module(PKG + ".sync_manager.room")
entry = importlib.import_module(PKG + ".sync_manager.entry")
if not (TOKEN and ROOM):
    print("[SMOKE] aborting: set EM_DEV_TOKEN and EM_ROOM")
    sys.exit(1)

COPY = bpy.data.filepath
before = sha(COPY)
scene = bpy.context.scene
# the study of slot 0 loaded, as a person would have it (GraphML copied first)
import shutil, tempfile  # noqa: E401,E402
row0 = scene.em_tools.graphml_files[0]
src0 = bpy.path.abspath(row0.graphml_path)
if src0.lower().endswith(".graphml"):
    dst0 = os.path.join(tempfile.mkdtemp(prefix="em-j1-"), os.path.basename(src0))
    shutil.copy2(src0, dst0)
    row0.graphml_path = dst0
scene.em_tools.active_file_index = 0
getattr(bpy.ops, "import").em_graphml(graphml_index=0)
state = entry.read_file_state(bpy.context)
copy_graphs = {row.name for row in scene.em_tools.graphml_files}
print("[SMOKE] the copy holds:", state)
check("the copy is not empty", bool(state["graphs"]) or bool(state["linked_objects"]))

# ── (1) the entry asks ─────────────────────────────────────────────────────
scene.em_room_url = NODE
room_cfg.set_room(NODE, None, TOKEN)
r = bpy.ops.em.room_pick(room_id=ROOM)
check("entering asks first", r == {"FINISHED"} and entry.PENDING.get("asked")
      and entry.PENDING.get("room_id") == ROOM, str(entry.PENDING))
check("…and joins nothing before the answer", not rs.SESSION.joined)

# ── (2) start a new file ───────────────────────────────────────────────────
r = bpy.ops.em.room_enter_choice(base=NODE, room_id=ROOM, choice="NEW")
check("start a new file: entered", r == {"FINISHED"} and rs.SESSION.joined, str(r))
check("…in a new file", bpy.data.filepath == "", bpy.data.filepath)
rows = [row.name for row in bpy.context.scene.em_tools.graphml_files]
check("…with the room's graphs", bool(rows), str(rows))
check("…and none of the copy's", not (set(rows) & copy_graphs), str(set(rows) & copy_graphs))
check("the copy on disk is intact", sha(COPY) == before, f"{before[:12]} → {sha(COPY)[:12]}")
importlib.import_module(PKG + ".sync_manager.operators").leave_room()
print("[SMOKE] RESULT:", "ALL PASS" if not FAILURES else f"FAILED {FAILURES}")
sys.stdout.flush()
sys.exit(0 if not FAILURES else 1)
