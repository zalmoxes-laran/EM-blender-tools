"""Headless smoke · T-C1 and T-S1, a collaborative room built around a STUDY —
LIVE against the dev node (user `dev` of the realm `em-dev`).

    cd ~/Documents/GitHub/stratigraph-server/dev-stack
    EM_DEV_TOKEN=$(./token.sh) EM_NODE=http://localhost:8000 \\
    PYTHONPATH=~/Documents/GitHub/s3Dgraphy/src \\
    "/Applications/Blender 520.app/Contents/MacOS/Blender" -b --python-use-system-env \\
        --python ~/Documents/GitHub/EM-blender-tools/tests/blender_smoke_study_room.py -- /tmp/ts1

(1) a study of TWO graphs and a shelf, written as one em.json (the example
xlsx's graph and a «Saggio 30 m» of two units), opened in Blender; (2) «Create
a collaborative room from this study…» with a viewer by ORCID, an editor link
and who sees (restricted, an embargo); (3) the room holds the two graphs and
the shelf (S1), the members and the invitation are read from the node, the
visibility and the embargo are in the study's header (C1); (4) an edit of the
second graph goes out naming it, and lands in its section; (5) the gesture
again does not make a second room: it enters the one that writes the study.
"""
import json
import os
import shutil
import sys
import time
import uuid

import bpy

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
WORK = ARGS[0] if ARGS else "/tmp/ts1"
NODE = os.environ.get("EM_NODE", "http://localhost:8000")
TOKEN = os.environ.get("EM_DEV_TOKEN", "")
VIEWER = "0000-0001-5109-3700"
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


if not TOKEN:
    print("[SMOKE] aborting: set EM_DEV_TOKEN")
    sys.exit(1)
shutil.rmtree(WORK, ignore_errors=True)
os.makedirs(WORK)
scene = bpy.context.scene
em = scene.em_tools
ops = mod(".sync_manager.operators")
rs = mod(".sync_manager.room_session")
room_cfg = mod(".sync_manager.room")
room_access = mod(".sync_manager.room_access")
bring = mod(".sync_manager.bring")

# ── (1) a study of two graphs and a shelf ──────────────────────────────────
xlsx = os.path.join(WORK, "example_stratigraphy.xlsx")
shutil.copyfile(os.path.expanduser("~/Documents/GitHub/s3Dgraphy/example_stratigraphy.xlsx"), xlsx)
em.table_import_type = "emdb_xlsx"
em.emdb_xlsx_file = xlsx
em.emdb_mapping = "excel_to_graphml_mapping"
check("graph A from the table", bpy.ops.em.import_from_table() == {"FINISHED"})
from s3dgraphy import api, get_graph  # noqa: E402
from s3dgraphy.container import Container, save_container_file  # noqa: E402
from s3dgraphy.graph import Graph  # noqa: E402
from s3dgraphy.nodes.stratigraphic_node import StratigraphicNode  # noqa: E402

graph_a = get_graph(em.graphml_files[em.active_file_index].name)
graph_b = Graph(graph_id=str(uuid.uuid4()), name="Saggio 30 m",
                description="a trench 30 m further, older phases")
for i in (1, 2):
    graph_b.add_node(StratigraphicNode(node_id=str(uuid.uuid4()), name=f"SG{i:02d}",
                                       description=f"saggio unit {i}"))
shelf = api.new_shelf()
api.add_to_shelf(shelf, "shelf/photo_001.jpg")
study_path = os.path.join(WORK, "Two graphs.em.json")
save_container_file(Container(graphs={graph_a.graph_id: graph_a, graph_b.graph_id: graph_b},
                              shelf=shelf, active_graph_id=graph_a.graph_id), study_path)
while len(em.graphml_files):
    em.graphml_files.remove(0)
r = getattr(bpy.ops, "import").em_emjson(filepath=study_path)
check("the em.json of two graphs opens", r == {"FINISHED"} and len(em.graphml_files) == 2,
      f"{r} rows={len(em.graphml_files)}")
ids = [row.name for row in em.graphml_files]
check("…with its two graphs", set(ids) == {graph_a.graph_id, graph_b.graph_id}, str(ids))
em.active_file_index = ids.index(graph_a.graph_id)

# ── (2) Create a collaborative room from this study ────────────────────────
scene.em_room_url = NODE
room_cfg.set_room(NODE, None, TOKEN)
name = f"T-S1 {int(time.time())}"
r = bpy.ops.em.room_bring(name=name, confirm=True, people=f"{VIEWER} viewer",
                          invite=True, invite_role="editor", invite_days=7,
                          invite_uses=3, visibility="restricted", embargo="2027-06-30")
check("Create a collaborative room from this study", r == {"FINISHED"}, str(r))
ROOM = room_cfg.room().get("room_id")
report = bring.ULTIMO_REFERTO
print("[SMOKE] report:", report.get("sentence"))
check("Blender is in the room", rs.SESSION.joined and bool(ROOM), str(ROOM))
check("both graphs seeded", set(report.get("seeded_graphs") or []) >= set(ids),
      str(report.get("seeded_graphs")))

# ── (3) what the room holds, who takes part, who sees ──────────────────────
reader = rs.RoomSession()
room_cfg.set_room(NODE, ROOM, TOKEN)
doc = reader.join()["snapshot"]["payload"]["doc"]
reader.leave()
sections = doc.get("graphs") or {}
check("the room holds the two graphs", {graph_a.graph_id, graph_b.graph_id} <= set(sections),
      str(list(sections)))
check("…and the shelf", any((s.get("data") or {}).get("em_collection") == "ShelfGraph"
                            for s in sections.values() if isinstance(s, dict)))
units_b = {n.get("name") for n in (sections.get(graph_b.graph_id) or {}).get("nodes") or []}
check("graph B's units in graph B's section", {"SG01", "SG02"} <= units_b, str(units_b))
check("…and not in graph A's",
      not ({"SG01", "SG02"} & {n.get("name") for n in
                                (sections.get(graph_a.graph_id) or {}).get("nodes") or []}))
members = room_access.members(NODE, TOKEN, ROOM)
check("the viewer by ORCID, read from the node",
      {"orcid": VIEWER, "role": "viewer"} in members.get("members", []), str(members.get("members")))
invites = room_access.invites(NODE, TOKEN, ROOM)
check("the editor link, read from the node",
      any(i.get("role") == "editor" and i.get("max_uses") == 3 and i.get("state") == "live"
          for i in invites), str([(i.get("role"), i.get("state"), i.get("max_uses")) for i in invites]))
link = (report.get("access") or {}).get("link") or ""
check("…and its link is the room's door with join=", "join=" in link and ROOM in link, link[:100])
header = doc.get("header") or {}
access = room_access.study_access(NODE, TOKEN, ROOM)
check("who sees, in the study's header",
      header.get("visibility") == "restricted" and header.get("embargo") == "2027-06-30",
      str({k: header.get(k) for k in ("visibility", "embargo")}))
check("…as the node says it", access == {"room_id": ROOM, "visibility": "restricted",
                                          "embargo": "2027-06-30"}, str(access))

# ── (4) an edit of graph B names graph B ───────────────────────────────────
observer = rs.RoomSession()
room_cfg.set_room(NODE, ROOM, TOKEN)
observer.join()
time.sleep(0.3)
observer.drain()
bpy.ops.em.graph_activate(index=ids.index(graph_b.graph_id))
check("writing in graph B", rs.SESSION.writing_graph == graph_b.graph_id
      and graph_b.graph_id in rs.SESSION.room_graphs, str(rs.SESSION.writing_graph))
unit = next(n for n in get_graph(graph_b.graph_id).nodes if getattr(n, "name", "") == "SG02")
unit.description = "edited in Blender"
ops.emit_op({"op": "update_node", "node_id": unit.node_id,
             "patch": {"description": "edited in Blender"}})
got = None
deadline = time.time() + 8
while time.time() < deadline and got is None:
    for m in observer.drain():
        if m.get("type") == "op" and (m.get("payload") or {}).get("node_id") == unit.node_id:
            got = m
    time.sleep(0.1)
check("the op names its graph", got is not None and got.get("graph_id") == graph_b.graph_id,
      str(got and got.get("graph_id")))
reader = rs.RoomSession()
doc = reader.join()["snapshot"]["payload"]["doc"]
reader.leave()
landed = {n.get("name"): n.get("description") for n in
          (doc["graphs"].get(graph_b.graph_id) or {}).get("nodes") or []}
check("…and lands in graph B's section", landed.get("SG02") == "edited in Blender", str(landed))
observer.leave()

# ── (5) the same gesture again: no second room ─────────────────────────────
before = len(mod(".sync_manager.rooms_list").list_rooms(NODE, TOKEN))
ops.leave_room()
r = bpy.ops.em.room_bring(name=f"{name} again", confirm=True)
after = len(mod(".sync_manager.rooms_list").list_rooms(NODE, TOKEN))
check("a study in a room does not make a second one", after == before,
      f"rooms {before} → {after}")
check("…it enters the room that writes it", rs.SESSION.joined and rs.SESSION.room_id == ROOM,
      f"{rs.SESSION.room_id}")
ops.leave_room()
with open(os.path.join(WORK, "room.json"), "w") as fh:
    json.dump({"room": ROOM, "link": link, "viewer": VIEWER}, fh)
finish()
