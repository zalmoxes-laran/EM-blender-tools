"""Screenshots · «Where you work» in the three places, and its windows — the
«after» of the desk's shots (`_lavoro-claude/scrivania-room-shots/`, taken with
the same method: GUI, --enable-event-simulate, the panel called as a popup).
The COPY of Templu Mare, never saved; the room on the dev node as `dev`.

    cd ~/Documents/GitHub/stratigraph-server/dev-stack
    EM_NODE=http://localhost:8000 EM_DEV_TOKEN=$(./token.sh) \\
    PYTHONPATH=~/Documents/GitHub/s3Dgraphy/src \\
    "/Applications/Blender 520.app/Contents/MacOS/Blender" --python-use-system-env \\
        --enable-event-simulate <copy>.blend \\
        --python ~/Documents/GitHub/EM-blender-tools/tests/blender_shots_where_you_work.py -- <out_dir>
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
    base = getattr(bpy.types, panel)
    name = "EMSHOT_PT_" + panel.split("_PT_")[-1]
    if not hasattr(bpy.types, name):
        clone = type(name, (base,), {"bl_idname": name, "bl_category": "EMSHOT",
                                     "bl_options": set()})
        bpy.utils.register_class(clone)
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


Q = [("act", "here"), ("shot", "1_on_this_computer.png", "side:VIEW3D_PT_em_sync"),
     ("shot", "1_change.png", "op:em.where_change"),
     ("act", "emstudio"), ("wait", 1), ("shot", "2_with_emstudio.png", "side:VIEW3D_PT_em_sync"),
     ("shot", "2_permissions.png", "op:em.sidecar_permissions"),
     ("act", "here"), ("act", "load"), ("wait", 2), ("act", "room"), ("wait", 4), ("act", "esc"), ("wait", 1),
     ("shot", "3_in_a_room.png", "side:VIEW3D_PT_em_sync"),
     ("shot", "3_room_menu.png", "menu:EM_MT_room_more"),
     ("shot", "3_room_settings.png", "op:em.room_settings"),
     ("shot", "3_the_blend_in_the_room.png", "op:em.room_blend"),
     ("shot", "3_files.png", "side:EM_PT_resources"),
     ("act", "leave"), ("wait", 1),
     ("shot", "4_enter_a_room.png", "op:em.room_enter"),
     ("shot", "5_em_export.png", "menu:EM_MT_export"),
     ("shot", "6_choose_the_node.png", "op:em.node_choose")]


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
            for panel in ("VIEW3D_PT_em_sync", "EM_PT_resources"):
                base = getattr(bpy.types, panel)
                name = "EMSHOT_PT_" + panel.split("_PT_")[-1]
                bpy.utils.register_class(type(name, (base,), {
                    "bl_idname": name, "bl_category": "EMSHOT", "bl_options": set()}))
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
