"""Headless smoke · T-E4, half A: «Edit in EMStudio» names the unit, against a
LIVE node (the dev stack, user `dev` of the realm `em-dev`).

    cd ~/Documents/GitHub/stratigraph-server/dev-stack
    EM_DEV_TOKEN=$(./token.sh) EM_NODE=http://localhost:8000 \\
    PYTHONPATH=~/Documents/GitHub/s3Dgraphy/src \\
    "/Applications/Blender 520.app/Contents/MacOS/Blender" -b --python-use-system-env \\
        --python ~/Documents/GitHub/EM-blender-tools/tests/blender_smoke_open_node_link.py -- /tmp/te4

(1) a graph from s3Dgraphy's example xlsx (Import from tables, on a copy);
with no Sidecar and no room the button is grey and says how to turn it on;
(2) «Bring into a room…» seats it in a NEW room of the node and Blender is in
it; (3) «Edit USM02 in EMStudio» produces `stratigraph://open?server=…&room=…
&node=<USM02's id>` — written to <work>/link.txt for half B, EMStudio's
`scripts/check-handoff-node-live.mjs`, which opens it in a browser, signs in
as `dev` and checks EMStudio lands on USM02.
"""
import json
import os
import shutil
import sys
import time
import urllib.parse

import bpy

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
WORK = ARGS[0] if ARGS else "/tmp/te4"
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


os.makedirs(WORK, exist_ok=True)
for f in os.listdir(WORK):
    if f.endswith((".em.json", ".txt")):
        os.remove(os.path.join(WORK, f))
scene = bpy.context.scene
em = scene.em_tools

# ── (1) the graph, and the grey button ─────────────────────────────────────
xlsx = os.path.join(WORK, "example_stratigraphy.xlsx")
shutil.copyfile(os.path.expanduser("~/Documents/GitHub/s3Dgraphy/example_stratigraphy.xlsx"), xlsx)
em.table_import_type = "emdb_xlsx"
em.emdb_xlsx_file = xlsx
em.emdb_mapping = "excel_to_graphml_mapping"
r = bpy.ops.em.import_from_table()
check("the graph from the table", r == {"FINISHED"}, str(r))
from s3dgraphy import get_graph  # noqa: E402
graph = get_graph(em.graphml_files[em.active_file_index].name)
oe = mod(".sync_manager.open_in_emstudio")
check("no Sidecar, no room: Edit in EMStudio is grey", not bpy.ops.em.open_in_emstudio.poll())
check("…and its sentence says how to turn it on", "Sidecar" in oe.OFF and "room" in oe.OFF, oe.OFF)

# ── (2) into a new room of the node ────────────────────────────────────────
if not TOKEN:
    print("[SMOKE] no EM_DEV_TOKEN: the room half is skipped")
    print("[SMOKE] RESULT:", "ALL PASS" if not FAILURES else f"FAILED {FAILURES}")
    sys.exit(0)
room_cfg = mod(".sync_manager.room")
scene.em_room_url = NODE
room_cfg.set_room(NODE, None, TOKEN)
ROOM_NAME = f"T-E4 {int(time.time())}"
r = bpy.ops.em.room_bring(name=ROOM_NAME, confirm=True)
check("Bring into a room", r == {"FINISHED"}, str(r))
where = room_cfg.room()
check("Blender is in the room", bool(where.get("room_id")) and bool(where.get("base_url")), str(where))

# ── (3) the unit, and its link ─────────────────────────────────────────────
unit = next(n for n in graph.nodes if getattr(n, "name", "") == "USM02")
check("Edit in EMStudio is on in the room", bpy.ops.em.open_in_emstudio.poll())
r = bpy.ops.em.open_in_emstudio(node_id=unit.node_id, unit_name=unit.name)
check("Edit USM02 in EMStudio", r == {"FINISHED"}, str(r))
link = bpy.context.window_manager.get("em_last_emstudio_link", "")
q = urllib.parse.parse_qs(urllib.parse.urlsplit(link).query)
print("[SMOKE] link:", link)
check("the link is stratigraph://open", link.startswith("stratigraph://open?"), link)
check("…it names the room and its server", q.get("room") == [where["room_id"]]
      and q.get("server") == [where["base_url"]], str(q))
check("…and the node of USM02", q.get("node") == [unit.node_id], str(q.get("node")))
with open(os.path.join(WORK, "link.txt"), "w") as fh:
    fh.write(link)
with open(os.path.join(WORK, "unit.json"), "w") as fh:
    json.dump({"node": unit.node_id, "name": unit.name, "room": where["room_id"]}, fh)
print("[SMOKE] RESULT:", "ALL PASS" if not FAILURES else f"FAILED {FAILURES}")
sys.stdout.flush()
