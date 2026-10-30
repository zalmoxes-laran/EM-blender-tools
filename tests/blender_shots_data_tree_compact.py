"""Shots and measure · MICRO-EMTOOLS-PANNELLO (E.D., 30 Oct 2026): the head of
the tab EM — «Where you work» (while it existed) and the EM Data Tree — in ONE
state: an em.json open, one graph, one warning (the graph's code left as the
placeholder ``site_id``). The «before» and the «after» are this script on two
commits. GUI, the panels cloned alone in a tab of the sidebar with their
sub-panels as they open (closed); the height is read off the screenshot (the
last line of the sidebar that is not its background). A COPY of a fixture
only, in /tmp.

    "/Applications/Blender 520.app/Contents/MacOS/Blender" --python-use-system-env \\
        --enable-event-simulate \\
        --python ~/Documents/GitHub/EM-blender-tools/tests/blender_shots_data_tree_compact.py \\
        -- <out_dir> <copy>.em.json [tag]
"""
import json
import os
import sys
import traceback

import bpy

ARGS = sys.argv[sys.argv.index("--") + 1:]
OUT, EMJSON = ARGS[0], ARGS[1]
TAG = ARGS[2] if len(ARGS) > 2 else "shot"
#: «…_open»: the sub-panels open, the warnings' list open, then EM ▸ Mode
#: (the menu the chip opens) shot on its own
OPEN = TAG.endswith("_open")
PANELS = ("VIEW3D_PT_em_sync", "VIEW3D_PT_EM_Tools_Setup")
os.makedirs(OUT, exist_ok=True)
STATE = {"step": 0}
RESULT = {"tag": TAG, "log": []}


def mod(suffix):
    names = [n for n in sys.modules if n.endswith("." + suffix) and n.startswith("bl_ext.")]
    return sys.modules[names[0]]


def view3d():
    win = bpy.context.window_manager.windows[0]
    area = max((a for a in win.screen.areas if a.type == 'VIEW_3D'),
               key=lambda a: a.width * a.height)
    return win, area


def load():
    sc = bpy.context.scene
    win, area = view3d()
    with bpy.context.temp_override(window=win, area=area):
        bpy.ops.em.set_mode(mode=mod("sync_manager.operators").MODE_STANDALONE)
        sc.em_tools.graphml_files.clear()
        bpy.ops.em_tools.add_file()
        row = sc.em_tools.graphml_files[0]
        row.graphml_path = EMJSON
        row.file_format = "EMJSON"
        sc.em_tools.active_file_index = 0
        getattr(bpy.ops, "import").em_emjson(file_index=0)
        # the row add_file made stays empty when the em.json lists its graph
        # in a row of its own: away, so the state is ONE graph
        files = sc.em_tools.graphml_files
        active = files[sc.em_tools.active_file_index].name
        for i in reversed(range(len(files))):
            if files[i].name != active and len(files) > 1:
                files.remove(i)
        sc.em_tools.active_file_index = 0
        # the one warning: the graph's code is the placeholder
        row = files[0]
        row.graph_code = "site_id"
    RESULT["graph"] = row.name
    RESULT["rows"] = len(sc.em_tools.graphml_files)


def clones():
    present = [p for p in PANELS if hasattr(bpy.types, p)]
    RESULT["panels"] = present
    made = {}
    for panel in present:
        base = getattr(bpy.types, panel)
        name = "EMSHOT_PT_" + panel.split("_PT_")[-1]
        made[base.bl_idname] = name
        bpy.utils.register_class(type(name, (base,), {
            "bl_idname": name, "bl_category": "EMSHOT", "bl_options": set()}))
    subs = []
    for cls in list(bpy.types.Panel.__subclasses__()):
        parent = getattr(cls, "bl_parent_id", "")
        if parent in made and not cls.__name__.startswith("EMSHOT"):
            name = "EMSHOT_PT_sub_" + cls.__name__
            subs.append(cls.bl_label)
            bpy.utils.register_class(type(name, (cls,), {
                "bl_idname": name, "bl_category": "EMSHOT",
                "bl_parent_id": made[parent],
                "bl_options": set() if OPEN else set(getattr(cls, "bl_options", set()))}))
    RESULT["sub_panels"] = subs


def sidebar():
    win, area = view3d()
    area.spaces.active.show_region_ui = True
    ui = next(r for r in area.regions if r.type == 'UI')
    # 5.2 · active_panel_category is read only: a click on the tab bar at the
    # sidebar's right edge, walking down from the top, until ours is shown
    if ui.active_panel_category != "EMSHOT":
        n = STATE.setdefault("turns", 0)
        scale = bpy.context.preferences.system.ui_scale or 1.0
        x = ui.x + ui.width - int(10 * scale)
        y = ui.y + ui.height - int(30 * scale) - n * int(8 * scale)
        win.event_simulate(type='MOUSEMOVE', value='NOTHING', x=x, y=y)
        win.event_simulate(type='LEFTMOUSE', value='PRESS', x=x, y=y)
        win.event_simulate(type='LEFTMOUSE', value='RELEASE', x=x, y=y)
    area.tag_redraw()
    RESULT["category"] = ui.active_panel_category
    return ui


def measure(path, ui, area):
    """The height of what the sidebar draws: from its top to the last line
    whose pixels are not the region's background (read off the PNG)."""
    img = bpy.data.images.load(path)
    w, h = img.size
    px = list(img.pixels)
    # the region in the area's coordinates (screenshot_area = the area only)
    # (the tab strip at the right edge left out: its tabs run lower than
    # the panels)
    scale = bpy.context.preferences.system.ui_scale or 1.0
    x0, x1 = ui.x - area.x + 4, ui.x - area.x + ui.width - int(30 * scale)
    bg = None
    last = None
    for y in range(max(0, ui.y - area.y + 2), h):   # bottom → top, like Blender
        row = [tuple(round(c, 3) for c in px[(y * w + x) * 4:(y * w + x) * 4 + 3])
               for x in range(max(0, x0), min(w, x1), 3)]
        if bg is None:
            bg = max(set(row), key=row.count)
        if any(abs(a - b) > 0.02 for p in row for a, b in zip(p, bg)):
            last = y
            break
    top = ui.y - area.y + ui.height
    RESULT["region_height_px"] = ui.height
    RESULT["drawn_height_px"] = (top - last) if last is not None else None
    RESULT["ui_scale"] = bpy.context.preferences.system.ui_scale
    bpy.data.images.remove(img)


def step():
    try:
        s = STATE["step"]
        STATE["step"] += 1
        win, area = view3d()
        if s == 0:
            with bpy.context.temp_override(window=win, area=area):
                bpy.ops.screen.screen_full_area()
            return 0.6
        if s == 1:
            area.spaces.active.overlay.show_overlays = False
            load()
            clones()
            sidebar()
            return 1.5
        if s == 2:
            ui = sidebar()
            if ui.active_panel_category != "EMSHOT" and STATE.setdefault("turns", 0) < 120:
                STATE["turns"] += 1
                STATE["step"] = 2
                return 0.15
            return 1.0
        if s == 3 and OPEN and not STATE.get("opened"):
            STATE["opened"] = True
            STATE["step"] = 3
            sc = bpy.context.scene
            sc.em_tools.graphml_files[0].show_warnings_section = True
            area.tag_redraw()
            return 1.0
        if s == 4 and OPEN and not STATE.get("menu"):
            STATE["menu"] = True
            STATE["step"] = 4
            region = next(r for r in area.regions if r.type == 'WINDOW')
            win.event_simulate(type='MOUSEMOVE', value='NOTHING',
                               x=region.x + 300, y=region.y + region.height - 200)
            with bpy.context.temp_override(window=win, area=area, region=region):
                bpy.ops.wm.call_menu(name="EM_MT_mode")
            return 1.5
        if s == 4 and OPEN:
            with bpy.context.temp_override(window=win, area=area):
                bpy.ops.screen.screenshot_area(filepath=os.path.join(OUT, f"{TAG}_menu.png"))
            win.event_simulate(type='ESC', value='PRESS')
            return 0.5
        if s == 3:
            path = os.path.join(OUT, f"{TAG}.png")
            with bpy.context.temp_override(window=win, area=area):
                bpy.ops.screen.screenshot_area(filepath=path)
            ui = next(r for r in area.regions if r.type == 'UI')
            measure(path, ui, area)
            return 0.3
        with open(os.path.join(OUT, f"{TAG}.json"), "w") as fh:
            json.dump(RESULT, fh, indent=1)
        print("[SHOT]", json.dumps(RESULT))
        sys.stdout.flush()
        os._exit(0)
    except Exception:
        traceback.print_exc()
        RESULT["log"].append(traceback.format_exc()[-600:])
        STATE["step"] = 5
        return 0.2


bpy.app.timers.register(step, first_interval=2.0)
