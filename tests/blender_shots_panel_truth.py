"""Screenshots · V1/V2 of MICRO-IL-PANNELLO-DICE-IL-VERO: «Where you work» and
the EM Data Tree TOGETHER, in the three places (the «before» and the «after»
are this script on two commits), and a .blend reopened in its room before and
after «Sync the scene…». GUI, --enable-event-simulate, the panels cloned alone
in a tab of the sidebar (the EM Data Tree with its sub-panels). COPIES only.

    cd ~/Documents/GitHub/stratigraph-server/dev-stack
    EM_NODE=http://localhost:8000 EM_DEV_TOKEN=$(./token.sh) \\
    PYTHONPATH=~/Documents/GitHub/s3Dgraphy/src \\
    "/Applications/Blender 520.app/Contents/MacOS/Blender" --python-use-system-env \\
        --enable-event-simulate <copy>.blend \\
        --python ~/Documents/GitHub/EM-blender-tools/tests/blender_shots_panel_truth.py \\
        -- <out_dir> places|reopened
"""
import json
import os
import shutil
import sys
import tempfile
import time
import traceback

import bpy

ARGS = sys.argv[sys.argv.index("--") + 1:]
OUT = ARGS[0]
WHICH = ARGS[1] if len(ARGS) > 1 else "places"
PANELS = ("VIEW3D_PT_em_sync", "VIEW3D_PT_EM_Tools_Setup")
NODE = os.environ.get("EM_NODE", "http://localhost:8000")
TOKEN = os.environ.get("EM_DEV_TOKEN", "")
os.makedirs(OUT, exist_ok=True)
STATE = {"step": 0, "phase": "move"}
LOG = []


def mod(suffix):
    names = [n for n in sys.modules if n.endswith("." + suffix) and n.startswith("bl_ext.")]
    return sys.modules[names[0]]


def view3d():
    win = bpy.context.window_manager.windows[0]
    area = max((a for a in win.screen.areas if a.type == 'VIEW_3D'),
               key=lambda a: a.width * a.height)
    return win, area


def mouse_top_left():
    win, area = view3d()
    region = next(r for r in area.regions if r.type == 'WINDOW')
    win.event_simulate(type='MOUSEMOVE', value='NOTHING', x=region.x + 160,
                       y=region.y + region.height - 60)


def sidebar(panel):
    """The panel in the 3D view's sidebar, alone in a tab of the shots: a clone
    registered under the category EMSHOT, the tab made active."""
    win, area = view3d()
    area.spaces.active.show_region_ui = True
    ui = next(r for r in area.regions if r.type == 'UI')
    try:
        ui.active_panel_category = "EMSHOT"
    except Exception as exc:  # noqa: BLE001
        LOG.append(f"category not set: {exc}")
    area.tag_redraw()


def popup(what):
    win, area = view3d()
    region = next(r for r in area.regions if r.type == 'WINDOW')
    with bpy.context.temp_override(window=win, area=area, region=region):
        if what.startswith("side:"):
            sidebar(what[5:])
        elif what.startswith("op:"):
            idname = what[3:]
            group, name = idname.split(".")
            getattr(getattr(bpy.ops, group), name)("INVOKE_DEFAULT")
        elif what.startswith("menu:"):
            bpy.ops.wm.call_menu(name=what[5:])
        else:
            bpy.ops.wm.call_panel(name=what, keep_open=True)


def shot(name):
    win, area = view3d()
    with bpy.context.temp_override(window=win, area=area):
        bpy.ops.screen.screenshot_area(filepath=os.path.join(OUT, name))
    LOG.append(name)


def act(what):
    ops = mod("sync_manager.operators")
    sc = bpy.context.scene
    win, area = view3d()
    with bpy.context.temp_override(window=win, area=area):
        if what == "here":
            bpy.ops.em.set_mode(mode=ops.MODE_STANDALONE)
        elif what == "emstudio":
            bpy.ops.em.set_mode(mode=ops.MODE_SIDECAR)
        elif what == "load":
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
            bpy.ops.em.room_bring(name=f"Templu Mare shots {int(time.time())}",
                                  confirm=True)
            bpy.ops.em.scene_check(send="NONE")
        elif what == "esc":
            # the gesture offers a .blend snapshot at its end: closed, unanswered
            win.event_simulate(type='ESC', value='PRESS')
        elif what == "leave":
            ops.leave_room()
        elif what == "token":
            mod("sync_manager.room").set_room(sc.em_room_url, sc.em_room_id, TOKEN)
        elif what == "sync":
            bpy.ops.em.scene_check(download=True)


if WHICH == "reopened":
    Q = [("shot", "0_reopened_not_connected.png", "side:both"),
         ("act", "token"), ("act", "sync"), ("wait", 8),
         ("shot", "0_reopened_after_sync.png", "side:both")]
else:
    Q = [("act", "here"), ("act", "load"), ("wait", 2),
         ("shot", "1_on_this_computer.png", "side:both"),
         ("act", "emstudio"), ("wait", 1), ("shot", "2_with_emstudio.png", "side:both"),
         ("act", "here"), ("act", "room"), ("wait", 4), ("act", "esc"), ("wait", 1),
         ("shot", "3_in_a_room.png", "side:both"),
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
            # the clones of the panels the sidebar shows, registered early: a
            # tab exists for the sidebar only after a redraw
            clones = {}
            for panel in PANELS:
                base = getattr(bpy.types, panel)
                name = "EMSHOT_PT_" + panel.split("_PT_")[-1]
                clones[base.bl_idname] = name
                bpy.utils.register_class(type(name, (base,), {
                    "bl_idname": name, "bl_category": "EMSHOT", "bl_options": set()}))
            # the EM Data Tree's sub-panels, under the clone, open
            for cls in list(bpy.types.Panel.__subclasses__()):
                parent = getattr(cls, "bl_parent_id", "")
                if parent in clones and not cls.__name__.startswith("EMSHOT"):
                    name = "EMSHOT_PT_sub_" + cls.__name__
                    bpy.utils.register_class(type(name, (cls,), {
                        "bl_idname": name, "bl_category": "EMSHOT",
                        "bl_parent_id": clones[parent], "bl_options": set()}))
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
            mouse_top_left()
            STATE["phase"] = "call"
            return 0.4
        if STATE["phase"] == "call":
            popup(what)
            STATE["phase"] = "shot"
            return 2.5
        shot(name)
        view3d()[0].event_simulate(type='ESC', value='PRESS')
        Q.pop(0)
        STATE["phase"] = "move"
        return 1.5
    except Exception:
        traceback.print_exc()
        LOG.append("EXC " + traceback.format_exc()[-400:])
        Q.pop(0) if Q else None
        STATE["phase"] = "move"
        return 0.5


bpy.app.timers.register(step, first_interval=2.0)
