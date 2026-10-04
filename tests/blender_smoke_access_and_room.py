"""Live smoke · G2, X1, X2 on the COPY of Templu Mare, against the dev node.

    BROWSER="<chatbot .venv python> tests/browser_fill_keycloak.py %s" \\
    EM_SHOTS=<out_dir> PYTHONPATH=~/Documents/GitHub/s3Dgraphy/src \\
    "/Applications/Blender 520.app/Contents/MacOS/Blender" -b --python-use-system-env \\
        <copy>.blend --python tests/blender_smoke_access_and_room.py -- <out_dir> <room name>

Headless; the browser is the Playwright filler with the realm's TEST user `dev`.
The .blend is NOT saved, the GraphML of slot 0 is copied into a temporary folder
first (E.D.'s examples are not touched).

0. the `em-tools` client's access lives 60 s for the run (Keycloak admin API on
   the dev realm), and 900 s again at the end, whatever happens;
1. G1 · the GraphML slot becomes an em.json with the scene's models;
2. the sign-in is the real one (Authorization Code + PKCE, `handoff.sign_in`):
   the refresh token is kept;
3. G2/X2 · «Bring into a room…» into a NEW room — longer than the access's
   life, so it also crosses a renewal — and the report's sentence;
4. X1a · the access has run out: «Archive this .blend»'s call
   (`room.put_blend_backup`, the bytes of the .blend on disk) succeeds through a
   renewal;
5. X1b · the realm's sessions of `dev` are ended (admin logout): the access
   runs out and cannot be renewed — the call says «has expired: sign in again»,
   and the panel's «Sign in again» knows the node.

Writes <out_dir>/access_and_room.json for the referto.
"""
import importlib
import json
import os
import shutil
import sys
import tempfile
import time
import urllib.parse
import urllib.request

import bpy

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = ARGS[0] if ARGS else "/tmp"
ROOM = ARGS[1] if len(ARGS) > 1 else f"Templu Mare G2 {time.strftime('%H%M%S')}"
BASE = "https://em.localhost:8443/em"
KC = "http://localhost:8085/auth"
LIFE = 60
FAILURES = []
RESULT = {"room_name": ROOM}


def check(label, condition, detail=""):
    print(f"[SMOKE] {'PASS' if condition else 'FAIL'}: {label} {detail}")
    sys.stdout.flush()
    if not condition:
        FAILURES.append(label)


_PKG = [n for n in sys.modules if n.endswith(".graph_origins")
        and n.startswith("bl_ext.")][0].rsplit(".graph_origins", 1)[0]


def mod(suffix):
    return importlib.import_module(_PKG + suffix)


# ── the realm, through its admin API (dev stack only) ────────────────────────

def kc_admin():
    body = urllib.parse.urlencode({"grant_type": "password", "client_id": "admin-cli",
                                   "username": "admin", "password": "admin"}).encode()
    with urllib.request.urlopen(f"{KC}/realms/master/protocol/openid-connect/token",
                                data=body, timeout=10) as answer:
        return json.loads(answer.read())["access_token"]


def kc(method, path, payload=None):
    req = urllib.request.Request(
        f"{KC}/admin/realms/em-dev{path}", method=method,
        data=None if payload is None else json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {kc_admin()}",
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as answer:
        raw = answer.read()
        return json.loads(raw) if raw else None


def set_life(seconds):
    client = kc("GET", "/clients?clientId=em-tools")[0]
    client.setdefault("attributes", {})["access.token.lifespan"] = str(seconds)
    kc("PUT", f"/clients/{client['id']}", client)
    return kc("GET", f"/clients/{client['id']}")["attributes"]["access.token.lifespan"]


def logout(username):
    user = kc("GET", f"/users?username={username}&exact=true")[0]
    kc("POST", f"/users/{user['id']}/logout")


def wait_until_expired(access, token):
    left = access.expiry_of(token) - time.time()
    print(f"[SMOKE] waiting {max(0, left) + 3:.0f} s for the access to run out")
    sys.stdout.flush()
    time.sleep(max(0, left) + 3)


try:
    RESULT["life_set"] = set_life(LIFE)
    check(f"the em-tools access lives {LIFE} s for the run", RESULT["life_set"] == str(LIFE))

    access = mod(".sync_manager.access")
    room_cfg = mod(".sync_manager.room")
    signin_ui = mod(".sync_manager.signin_ui")
    bring = mod(".sync_manager.bring")

    # ── 1 · G1 ──────────────────────────────────────────────────────────────
    et = bpy.context.scene.em_tools
    row = et.graphml_files[0]
    work = tempfile.mkdtemp(prefix="emjson-g2-")
    copy = os.path.join(work, os.path.basename(bpy.path.abspath(row.graphml_path)))
    shutil.copy2(bpy.path.abspath(row.graphml_path), copy)
    row.graphml_path = copy
    et.active_file_index = 0
    r = getattr(bpy.ops, "import").em_graphml(graphml_index=0)
    check("G1 · the GraphML is now an em.json", r == {"FINISHED"} and
          et.graphml_files[0].graphml_path.endswith(".em.json"),
          et.graphml_files[0].graphml_path)
    RESULT["emjson"] = et.graphml_files[0].graphml_path

    # ── 2 · the real sign-in ───────────────────────────────────────────────
    bpy.context.scene.em_room_url = BASE
    room_cfg.set_room(BASE, None, "")
    token, how = signin_ui.access_or_wait(BASE)
    room_cfg.set_room(BASE, None, token)
    cred = access._creds.get(BASE) or {}
    life = access.expiry_of(token) - time.time()
    check("signed in through the browser", bool(token) and how == "signed-in", how)
    check("the refresh token is kept (in memory)", bool(cred.get("refresh_token")))
    check(f"the access lives about {LIFE} s", 0 < life <= LIFE + 5, f"{life:.0f} s")

    # ── 3 · G2 / X2 · Bring into a room ────────────────────────────────────
    t0 = time.time()
    r = bpy.ops.em.room_bring(name=ROOM, confirm=True)
    report = dict(bring.ULTIMO_REFERTO)
    RESULT["bring"] = {k: report.get(k) for k in (
        "room_id", "sentence", "uploaded", "uploaded_size", "already", "references",
        "missing", "failed", "joined", "ops_applied", "ops_refused", "seconds")}
    print(f"[SMOKE] bring: {report.get('sentence')}")
    check("G2 · Bring into a room… finished", r == {"FINISHED"} and report.get("joined"),
          f"{r} in {time.time() - t0:.0f} s")
    from s3dgraphy import get_graph
    g = get_graph(et.graphml_files[0].name)
    seen, doubles = set(), 0
    for e in g.edges:
        key = (e.edge_source, e.edge_target, e.edge_type)
        doubles += key in seen
        seen.add(key)
    check("G2 · the seeding was accepted (but the GraphML's drawn-twice edges)",
          (report.get("ops_refused") or 0) <= doubles,
          f"applied {report.get('ops_applied')}, refused {report.get('ops_refused')}, "
          f"edges drawn twice {doubles}")
    check("G2 · the published proxies are their chain's files, not «missing»",
          (report.get("missing") or 0) < 66, f"missing {report.get('missing')}")
    sentence = report.get("sentence") or ""
    check("X2 · the sentence counts uploads and files already there apart",
          ("already on the node" in sentence or "uploaded" in sentence)
          and "(0 B)" not in sentence, sentence)
    check("the bring crossed a renewal when it outlived the access",
          time.time() - t0 < LIFE or (room_cfg._session.get("token") != token),
          f"{time.time() - t0:.0f} s")

    # ── 4 · X1a · the backup after the access ran out ──────────────────────
    current = room_cfg._session.get("token")
    wait_until_expired(access, current)
    data = open(bpy.data.filepath, "rb").read()
    try:
        record = room_cfg.put_blend_backup(data, label="G2/X1 renewal",
                                           filename=os.path.basename(bpy.data.filepath))
        check("X1a · the backup succeeds after a renewal", bool(record.get("sha256")),
              f"created={record.get('created')} size={record.get('size')}")
    except Exception as exc:  # noqa: BLE001
        check("X1a · the backup succeeds after a renewal", False, str(exc))
    check("X1a · the access was renewed", room_cfg._session.get("token") != current)
    RESULT["x1a"] = "renewed"

    # ── 5 · X1b · the realm will not renew ─────────────────────────────────
    logout("dev")
    current = room_cfg._session.get("token")
    wait_until_expired(access, current)
    try:
        room_cfg.put_blend_backup(data + b"x", label="G2/X1 expired",
                                  filename=os.path.basename(bpy.data.filepath))
        check("X1b · an access that cannot be renewed is said", False, "no error")
    except Exception as exc:  # noqa: BLE001
        said = str(exc)
        RESULT["x1b_sentence"] = said
        check("X1b · «has expired: sign in again», not Broken pipe",
              "has expired: sign in again" in said and "Broken pipe" not in said, said)
        check("X1b · the panel's Sign in again knows the node",
              access.EXPIRED.get("base") == BASE, access.EXPIRED.get("base"))
except Exception:  # noqa: BLE001 — said, then the lifespan goes back
    import traceback
    traceback.print_exc()
    FAILURES.append("the run stopped on an exception")
finally:
    try:
        RESULT["life_restored"] = set_life(900)
        print(f"[SMOKE] em-tools access lifespan back to {RESULT['life_restored']} s")
    except Exception as exc:  # noqa: BLE001
        print(f"[SMOKE] FAIL: could not restore the lifespan: {exc}")
        FAILURES.append("restore lifespan")
    RESULT["failures"] = FAILURES
    with open(os.path.join(OUT, "access_and_room.json"), "w") as fh:
        json.dump(RESULT, fh, indent=1, default=str)
    print("[SMOKE] ALL PASS" if not FAILURES else f"[SMOKE] FAILED: {FAILURES}")
    sys.stdout.flush()
    os._exit(1 if FAILURES else 0)
