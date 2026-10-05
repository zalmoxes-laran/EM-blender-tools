"""Screenshots · the clean panels (MICRO pannelli puliti, 6 Oct 2026): «Where you
work» on this computer and in a room, the EM Data Tree (graphs not loaded, then
one loaded), the Visual Manager, and the tab EM Scene. The same method as
`blender_shots_where_you_work.py` (GUI, --enable-event-simulate, each panel
cloned alone in a tab of its own). A COPY of Templu Mare, never saved; the room
on the dev node as `dev`, archived at the end.

    cd ~/Documents/GitHub/stratigraph-server/dev-stack
    EM_NODE=http://localhost:8000 EM_DEV_TOKEN=$(./token.sh) \\
    PYTHONPATH=~/Documents/GitHub/s3Dgraphy/src \\
    "/Applications/Blender 520.app/Contents/MacOS/Blender" --python-use-system-env \\
        --enable-event-simulate <copy>.blend \\
        --python ~/Documents/GitHub/EM-blender-tools/tests/blender_shots_clean_panels.py -- <out_dir> [noroom]
"""
import json
import os
import shutil
import sys
import tempfile
import time
import traceback
import urllib.request

import bpy

ARGS = sys.argv[sys.argv.index("--") + 1:]
OUT = ARGS[0]
NOROOM = "noroom" in ARGS[1:]
NODE = os.environ.get("EM_NODE", "http://localhost:8000")
TOKEN = os.environ.get("EM_DEV_TOKEN", "")
os.makedirs(OUT, exist_ok=True)
STATE = {"step": 0, "phase": "move", "room": ""}
LOG = []


def mod(suffix):
    names = [n for n in sys.modules if n.endswith("." + suffix) and n.startswith("bl_ext.")]
    return sys.modules[names[0]]


def view3d():
    win = bpy.context.window_manager.windows[0]
    area = max((a for a in win.screen.areas if a.type == 'VIEW_3D'),
               key=lambda a: a.width * a.height)
    return win, area


def ui_region():
    return next(r for r in view3d()[1].regions if r.type == 'UI')


def clone(panel):
    """The panel alone in a tab of its own: `EMSHOT_<panel>`."""
    base = getattr(bpy.types, panel)
    cat = "SHOT_" + panel.split("_PT_")[-1][:18]
    name = "EMSHOT_PT_" + panel.split("_PT_")[-1]
    if not hasattr(bpy.types, name):
        bpy.utils.register_class(type(name, (base,), {
            "bl_idname": name, "bl_category": cat, "bl_options": set()}))
    return cat


def show_tab(cat):
    win, area = view3d()
    area.spaces.active.show_region_ui = True
    ui = ui_region()
    try:
        ui.active_panel_category = cat
    except Exception as exc:  # noqa: BLE001
        LOG.append(f"category {cat} not set: {exc}")
    area.tag_redraw()
    # the sidebar draws the tab it was given only after an event over it
    # (measured: without, the first shots kept the tab EM)
    for dx in (40, 60):
        win.event_simulate(type='MOUSEMOVE', value='NOTHING',
                           x=ui.x + dx, y=ui.y + ui.height // 2)


def shot(name):
    win, area = view3d()
    with bpy.context.temp_override(window=win, area=area):
        bpy.ops.screen.screenshot_area(filepath=os.path.join(OUT, name))
    LOG.append(f"{name} · tab {ui_region().active_panel_category}")


def api(method, path, body=None):
    req = urllib.request.Request(NODE.rstrip("/") + "/v1" + path, method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": "Bearer " + TOKEN,
                                          "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read() or b"{}")


def act(what):
    ops = mod("sync_manager.operators")
    sc = bpy.context.scene
    win, area = view3d()
    with bpy.context.temp_override(window=win, area=area):
        if what == "here":
            bpy.ops.em.set_mode(mode=ops.MODE_STANDALONE)
        elif what == "load":
            # the first row's graph from a copy of its file, never the original
            row0 = sc.em_tools.graphml_files[0]
            src0 = bpy.path.abspath(row0.graphml_path)
            if src0.lower().endswith(".graphml"):
                dst0 = os.path.join(tempfile.mkdtemp(prefix="em-shots-"),
                                    os.path.basename(src0))
                shutil.copy2(src0, dst0)
                row0.graphml_path = dst0
            sc.em_tools.active_file_index = 0
            getattr(bpy.ops, "import").em_graphml(graphml_index=0)
        elif what == "room":
            bpy.ops.em.set_mode(mode=ops.MODE_STANDALONE)
            sc.em_room_url = NODE
            mod("sync_manager.room").set_room(NODE, None, TOKEN)
            STATE["room"] = f"Templu Mare shots {int(time.time())}"
            bpy.ops.em.room_bring(name=STATE["room"], confirm=True)
            bpy.ops.em.scene_check(send="NONE")
        elif what == "alpha":
            # P4 · the case measured on 5 Oct: the mode «select», slider to 0.2
            sc.em_tools.proxy_display_mode = "select"
            sc.em_tools.proxy_display_alpha = 0.2
            LOG.append(f"alpha 0.2 · mode now {sc.em_tools.proxy_display_mode}")
        elif what == "esc":
            win.event_simulate(type='ESC', value='PRESS')
        elif what == "leave":
            status = ops.room_status(bpy.context)
            STATE["room_id"] = status.get("room_id") or ""
            ops.leave_room()
            if STATE["room_id"]:
                try:
                    api("POST", f"/rooms/{STATE['room_id']}/archive", {"archived": True})
                    LOG.append(f"room {STATE['room_id']} archived")
                except Exception as exc:  # noqa: BLE001
                    LOG.append(f"room not archived: {exc}")


PANELS = ("VIEW3D_PT_em_sync", "VIEW3D_PT_EM_Tools_Setup", "VIEW3D_PT_visual_panel")

Q = [("act", "here"), ("wait", 1),
     ("shot", "1_where_here.png", "VIEW3D_PT_em_sync"),
     ("shot", "2_data_tree.png", "VIEW3D_PT_EM_Tools_Setup"),
     ("shot", "4_visual_manager.png", "VIEW3D_PT_visual_panel"),
     ("tab", "3_em_scene.png", "EM Scene"),
     ("act", "load"), ("wait", 2),
     ("shot", "2_data_tree_loaded.png", "VIEW3D_PT_EM_Tools_Setup"),
     ("shot", "1_where_here_loaded.png", "VIEW3D_PT_em_sync"),
     ("tab", "2_em_tab_loaded.png", "EM"),
     ("act", "alpha"), ("wait", 2),
     ("shot", "4_visual_manager_alpha_02.png", "VIEW3D_PT_visual_panel")]
if not NOROOM:
    Q += [("act", "room"), ("wait", 4), ("act", "esc"), ("wait", 1),
          ("shot", "1_where_room.png", "VIEW3D_PT_em_sync"),
          ("shot", "2_data_tree_room.png", "VIEW3D_PT_EM_Tools_Setup"),
          ("act", "leave"), ("wait", 1)]


def finish():
    with open(os.path.join(OUT, "shots.json"), "w") as fh:
        json.dump({"shots": LOG}, fh, indent=1)
    sys.stdout.flush()
    os._exit(0)


def step():
    try:
        s = STATE["step"]
        if s == 0:
            STATE["step"] = 1
            win, area = view3d()
            with bpy.context.temp_override(window=win, area=area):
                bpy.ops.screen.screen_full_area()
            return 0.6
        if s == 1:
            STATE["step"] = 2
            win, area = view3d()
            area.spaces.active.overlay.show_overlays = False
            for panel in PANELS:
                clone(panel)
            area.spaces.active.show_region_ui = True
            area.tag_redraw()
            return 1.0
        if not Q:
            finish()
        item = Q[0]
        if item[0] == "act":
            Q.pop(0)
            act(item[1])
            return 1.0
        if item[0] == "wait":
            Q.pop(0)
            return float(item[1])
        _k, name, what = item
        if STATE["phase"] == "move":
            show_tab(what if _k == "tab" else clone(what))
            STATE["phase"] = "settle"
            return 1.0
        if STATE["phase"] == "settle":
            # measured: the tab set is drawn one event later — without this
            # step every shot showed the tab of the one before
            show_tab(what if _k == "tab" else clone(what))
            STATE["phase"] = "shot"
            return 1.5
        shot(name)
        Q.pop(0)
        STATE["phase"] = "move"
        return 0.5
    except Exception:
        traceback.print_exc()
        LOG.append("EXC " + traceback.format_exc()[-400:])
        Q.pop(0) if Q else None
        STATE["phase"] = "move"
        return 0.5


bpy.app.timers.register(step, first_interval=2.0)
