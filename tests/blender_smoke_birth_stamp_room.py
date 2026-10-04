"""Headless smoke · T1, the birth stamp made in a ROOM carries the room's author.

NOT a pytest test (needs bpy and a running node):

    EM_V1_EMJSON=/tmp/micro-asset-versioni/m1g1/TempioGrande.em.json \\
    EM_ROOM_URL=http://localhost:8000 EM_ROOM_TOKEN=$(stratigraph-server/dev-stack/token.sh) \\
    "/Applications/Blender 520.app/Contents/MacOS/Blender" -b --python-use-system-env \\
        --python tests/blender_smoke_birth_stamp_room.py

`birth_stamp.current_operator` imported `SESSION` from `sync_manager.operators`,
where it does not exist; the ImportError was swallowed and a stamp made in a
room never named the room's author. Here: a NEW room, joined; the operator is
the token's ORCID; a glb stamped there carries it in `by.operator`; out of the
room, it does not. The room is archived at the end.
"""
import importlib
import os
import sys
import tempfile
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
bs = importlib.import_module(PKG + ".birth_stamp")
IMPORT = getattr(bpy.ops, "import")

BASE = os.environ.get("EM_ROOM_URL", "")
TOKEN = os.environ.get("EM_ROOM_TOKEN", "")
if not (BASE and TOKEN):
    print("[SMOKE] aborting: set EM_ROOM_URL and EM_ROOM_TOKEN")
    sys.exit(1)

ctx = bpy.context
em = ctx.scene.em_tools
while len(em.graphml_files):
    em.graphml_files.remove(0)
IMPORT.em_emjson(filepath=os.environ.get(
    "EM_V1_EMJSON", "/tmp/micro-asset-versioni/m1g1/TempioGrande.em.json"))

before = bs.current_operator()
print(f"[SMOKE] operator out of a room: {before}")

tag = uuid.uuid4().hex[:6]
made = rooms_list.create_room(BASE, TOKEN, f"t1 birth stamp {tag}")
room_id = made.get("room_id") or made.get("id")
j = ops.join_room(ctx, BASE, room_id, TOKEN, adopt=True)
check("a new room, joined", j["ok"], j.get("message", ""))
author = rs.SESSION.author
print(f"[SMOKE] the room says the author is {author!r}")
check("the room reports an author for the token", bool(author))
op = bs.current_operator()
check("in the room the operator is the room's author",
      op is not None and op.get("id", "").endswith(str(author).rsplit("/", 1)[-1]), str(op))

with tempfile.TemporaryDirectory() as d:
    glb = os.path.join(d, "probe.glb")
    with open(glb, "wb") as fh:
        fh.write(b"glTF" + b"\x02" * 64)
    how = {"dtc_kind": bs.KIND_EXPORT, "technique": "glTF export (GLB)",
           "parameters": {"operator": "smoke"}, "software": bs.blender_software()}
    res = bs.stamp_export(glb, how=how, operator=bs.current_operator())
    stamp = res.get("stamp") or {}
    print(f"[SMOKE] stamp by: {stamp.get('by')}")
    check("the stamp made in the room carries the author",
          (stamp.get("by") or {}).get("operator") == op, str(stamp.get("by")))

ops._lascia_tutte_le_stanze()
after = bs.current_operator()
check("out of the room again, the room's author is gone", after == before, str(after))
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
