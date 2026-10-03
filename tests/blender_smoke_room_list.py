"""Headless smoke · R1, the room list in the Sync panel (MICRO-LA-BARRA-E-LE-STANZE).

NOT a pytest test (needs bpy and a LIVE node) — run it inside Blender with the
EM-tools extension enabled, with two tokens of the dev realm:

    cd ~/Documents/GitHub/stratigraph-server/dev-stack
    EM_DEV_TOKEN=$(./token.sh) EM_VIEWER_TOKEN=$(./token.sh --user viewer) \\
    EM_NODE=http://localhost:8000 \\
    /Applications/Blender\\ 520.app/Contents/MacOS/Blender --background \\
        --python ~/Documents/GitHub/EM-blender-tools/tests/blender_smoke_room_list.py

(`EM_NODE=https://em.localhost:8443/em` works too, with
`SSL_CERT_FILE=~/caddy-em-root.crt`: the TLS is verified, never skipped.)

* with the `dev` token, a room `dev` owns (`EM_OWNED_ROOM`, default
  `scavo-2026`) is in «Your rooms»;
* with the `viewer` token, a room where viewer is a member
  (`EM_SHARED_ROOM`, default `cantiere-demo`) is in «Shared with you», with its
  role (`EM_SHARED_ROLE`, default `viewer`);
* the operator is the panel's button (`em.room_list_refresh`); `wait=True`
  because in `-b` the timer that lands a background fetch does not fire while
  the script runs — the same two functions, called inline.

Exits non-zero on failure.
"""
import os
import sys

import bpy

FAILURES = []


def check(label, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print(f"[SMOKE] {status}: {label} {detail}")
    if not condition:
        FAILURES.append(label)
    return condition


NODE = os.environ.get("EM_NODE", "http://localhost:8000")
DEV = os.environ.get("EM_DEV_TOKEN", "")
VIEWER = os.environ.get("EM_VIEWER_TOKEN", "")
OWNED = os.environ.get("EM_OWNED_ROOM", "scavo-2026")
SHARED = os.environ.get("EM_SHARED_ROOM", "cantiere-demo")
ROLE = os.environ.get("EM_SHARED_ROLE", "viewer")
if not (DEV and VIEWER):
    print("[SMOKE] aborting: set EM_DEV_TOKEN and EM_VIEWER_TOKEN (dev-stack/token.sh)")
    sys.exit(1)

check("em.room_list_refresh registered", hasattr(bpy.ops.em, "room_list_refresh"))
bpy.context.scene.em_room_url = NODE
wm = bpy.context.window_manager


def cache():
    return [(i.room_id, i.group, i.role) for i in wm.em_rooms_cache]


# ── dev: the owner ───────────────────────────────────────────────────────────
esito = bpy.ops.em.room_list_refresh(token=DEV, wait=True)
check("dev: the list arrives", esito == {"FINISHED"}, repr(esito))
rows = cache()
mine = [r for r in rows if r[1] == "mine"]
shared = [r for r in rows if r[1] == "shared"]
print(f"[SMOKE] dev: {len(mine)} yours · {len(shared)} shared")
check(f"dev: {OWNED} is in «Your rooms»", (OWNED, "mine", "owner") in rows)

# ── viewer: a member, not the owner ──────────────────────────────────────────
esito = bpy.ops.em.room_list_refresh(token=VIEWER, wait=True)
check("viewer: the list arrives", esito == {"FINISHED"}, repr(esito))
rows = cache()
mine = [r for r in rows if r[1] == "mine"]
shared = [r for r in rows if r[1] == "shared"]
print(f"[SMOKE] viewer: {len(mine)} yours · {len(shared)} shared")
check(f"viewer: {SHARED} is in «Shared with you» as {ROLE}",
      (SHARED, "shared", ROLE) in rows,
      repr([r for r in rows if r[0] == SHARED]))
check(f"viewer: {OWNED} is NOT in «Your rooms»", (OWNED, "mine", "owner") not in rows)

# the filter narrows without a second fetch
from importlib import import_module  # noqa: E402
_pkg = [n for n in sys.modules if n.endswith(".sync_manager.rooms_list")][0]
rooms_list = sys.modules[_pkg]
check("the filter finds the shared room by a word of its id",
      rooms_list.matches({"room_id": SHARED, "title": ""}, SHARED.split("-")[0]))

# the access stays in memory only: nothing about it is a property of the file
check("no token in the scene", not any("eyJ" in str(getattr(bpy.context.scene, k, ""))
                                       for k in ("em_room_url", "em_room_id")))

if FAILURES:
    print(f"[SMOKE] {len(FAILURES)} failure(s): {FAILURES}")
    sys.exit(1)
print("[SMOKE] all checks passed")
