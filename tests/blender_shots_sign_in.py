"""GUI proof + screenshots · Q11: Blender signs in to the dev node and brings
Templu Mare into a room — without freezing, with a Cancel, and the browser's
return page saying the true outcome.

NOT headless (the panel must be drawn, the timer must run). On the COPY of
Templu Mare, with the dev stack up:

    BROWSER="<chatbot .venv python> tests/browser_fill_keycloak.py %s" \\
    EM_SHOTS=<out_dir> PYTHONPATH=~/Documents/GitHub/s3Dgraphy/src \\
    "/Applications/Blender 520.app/Contents/MacOS/Blender" --python-use-system-env \\
        <copy>.blend --python tests/blender_shots_sign_in.py -- <out_dir> <room name>

1. «Find» proposes the address behind Caddy (`https://em.localhost:8443/em`);
2. «Bring into a room…» starts the sign-in and RETURNS: the panel shows the wait
   and its Cancel while the browser (the test user `dev` of realm em-dev) signs in;
3. the door opens again by itself: the room is created, the graph seated,
   Blender inside. Writes q11_*.png and q11_result.json.
"""
import importlib
import json
import os
import sys
import time

import bpy

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = ARGS[0] if ARGS else "/tmp"
ROOM = ARGS[1] if len(ARGS) > 1 else f"Templu Mare Q11 {time.strftime('%H%M%S')}"
CADDY = "https://em.localhost:8443/em"
FAILURES = []
RESULT = {"room_name": ROOM}
STATE = {"step": 0, "t0": 0.0, "ticks": 0}


def check(label, condition, detail=""):
    print(f"[SMOKE] {'PASS' if condition else 'FAIL'}: {label} {detail}")
    sys.stdout.flush()
    if not condition:
        FAILURES.append(label)


def pkg():
    names = [n for n in sys.modules if n.endswith(".graph_origins") and n.startswith("bl_ext.")]
    return names[0].rsplit(".graph_origins", 1)[0]


def mod(name):
    return importlib.import_module(pkg() + "." + name)


def view3d():
    win = bpy.context.window_manager.windows[0]
    area = max((a for a in win.screen.areas if a.type == 'VIEW_3D'),
               key=lambda a: a.width * a.height)
    return win, area


def shot(name):
    win, area = view3d()
    path = os.path.join(OUT, name)
    with bpy.context.temp_override(window=win, area=area):
        bpy.ops.screen.screenshot_area(filepath=path)
    check(f"screenshot {name}", os.path.isfile(path), path)


def finish():
    RESULT["failures"] = FAILURES
    with open(os.path.join(OUT, "q11_result.json"), "w") as fh:
        json.dump(RESULT, fh, indent=1, default=str)
    print(f"[SMOKE] {'ALL PASS' if not FAILURES else 'FAILURES: ' + ', '.join(FAILURES)}")
    sys.stdout.flush()
    os._exit(1 if FAILURES else 0)


def step():
    win, area = view3d()
    s = STATE["step"]
    STATE["step"] += 1
    try:
        if s == 0:
            with bpy.context.temp_override(window=win, area=area):
                bpy.ops.screen.screen_full_area()
            return 0.5
        if s == 1:
            win, area = view3d()
            area.spaces.active.show_region_ui = True
            area.spaces.active.overlay.show_overlays = False
            ui = next(r for r in area.regions if r.type == 'UI')
            try:
                ui.active_panel_category = "EM Bridge"
            except AttributeError:
                print("[SMOKE] note: cannot switch the sidebar tab here")
            return 0.5
        if s == 2:
            getattr(bpy.ops, "import").em_graphml(graphml_index=0)
            g = mod("functions").is_graph_available(bpy.context)
            check("Templu Mare's graph is loaded", g[0], str(g[1] and len(g[1].nodes)))
            bpy.context.scene.em_room_url = ""
            bpy.ops.em.server_discover()
            url = bpy.context.scene.em_room_url
            RESULT["found"] = url
            check("Find proposes the address behind Caddy", url == CADDY, url)
            bpy.context.scene.em_room_url = CADDY
            area.tag_redraw()
            return 1.0
        if s == 3:
            shot("q11_find.png")
            STATE["t0"] = time.monotonic()
            with bpy.context.temp_override(window=win, area=area):
                bpy.ops.em.room_bring(name=ROOM, confirm=True)
            back = time.monotonic() - STATE["t0"]
            RESULT["bring_returned_after_s"] = round(back, 3)
            ui = mod("sync_manager.signin_ui")
            running = ui.PENDING.get("signin")
            check("«Bring into a room…» returned at once, the sign-in waits in the browser",
                  back < 5 and running is not None, f"{back:.2f}s")
            RESULT["client_id"] = getattr(running, "client_id", "")
            RESULT["redirect_uri"] = getattr(running, "redirect_uri", "")
            area.tag_redraw()
            return 0.4
        if s == 4:
            shot("q11_waiting.png")          # the wait and its Cancel, Blender alive
            return 0.5
        if s == 5:
            ui = mod("sync_manager.signin_ui")
            STATE["ticks"] += 1
            running = ui.PENDING.get("signin")
            if running is not None and STATE["ticks"] < 240:
                STATE["step"] = 5            # Blender keeps drawing while it waits
                return 0.5
            RESULT["sign_in_line"] = ui.PENDING.get("line")
            RESULT["signed_in_after_s"] = round(time.monotonic() - STATE["t0"], 1)
            check("signed in as dev", "as dev" in (ui.PENDING.get("line") or ""),
                  ui.PENDING.get("line"))
            return 1.0
        if s == 6:
            from_session = mod("sync_manager.room_session").SESSION
            bring = mod("sync_manager.bring")
            RESULT["room_id"] = bring.STATE.get("room_id")
            RESULT["joined"] = bool(from_session.joined)
            RESULT["session_room"] = from_session.room_id
            check("Blender is in the room it brought", from_session.joined
                  and from_session.room_id == bring.STATE.get("room_id"),
                  f"{from_session.room_id} vs {bring.STATE.get('room_id')}")
            area.tag_redraw()
            return 1.0
        if s == 7:
            shot("q11_in_room.png")
            finish()
    except Exception as exc:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        check(f"step {s}", False, repr(exc))
        finish()
    return None


bpy.app.timers.register(step, first_interval=2.0)
