"""GUI screenshots of the EM tabs of the 3D sidebar, and the inventory of the
panels per tab (U6, MICRO-EMTOOLS-MENO-E-MEGLIO). NOT headless: the sidebar
must be drawn. Opens whatever .blend is given and never saves it.

    "/Applications/Blender 520.app/Contents/MacOS/Blender" --python-use-system-env \\
        <copy>.blend --python tests/blender_shots_tabs.py -- <out_dir> <phase>

Writes `tabs_<phase>.json` (every registered panel of the VIEW_3D sidebar
whose category starts with «EM», with its label, order and parent) and
`tabs_<phase>_<category>.png`, one per tab, the sidebar wide open. The
sidebar draws only the tab it already had (setting `active_panel_category`
is accepted and not drawn, measured): the tab NAMES are in the strip on its
right. With `--enable-event-simulate`, the panels named after the phase are
photographed whole as popups too: `panel_<phase>_<idname>.png`.
"""
import json
import os
import sys

import bpy

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = ARGS[0] if ARGS else "/tmp/emtools-tabs"
PHASE = ARGS[1] if len(ARGS) > 1 else "after"
os.makedirs(OUT, exist_ok=True)


def inventory():
    rows = []
    for cls in bpy.types.Panel.__subclasses__():
        cat = getattr(cls, "bl_category", "")
        if getattr(cls, "bl_space_type", "") != "VIEW_3D" or not str(cat).startswith("EM"):
            continue
        rows.append({"category": cat, "label": getattr(cls, "bl_label", ""),
                     "idname": getattr(cls, "bl_idname", cls.__name__),
                     "order": getattr(cls, "bl_order", 0),
                     "parent": getattr(cls, "bl_parent_id", "")})
    rows.sort(key=lambda r: (r["category"], r["parent"] != "", r["order"], r["label"]))
    return rows


def view3d():
    win = bpy.context.window_manager.windows[0]
    area = max((a for a in win.screen.areas if a.type == 'VIEW_3D'), key=lambda a: a.width * a.height)
    return win, area


STATE = {"queue": None, "popups": None}
POPUPS = sys.argv[sys.argv.index("--") + 3:] if "--" in sys.argv and len(sys.argv) > sys.argv.index("--") + 3 else []


def popup_step():
    """One popup per call: move the mouse, call the panel, shoot, close."""
    win, area = view3d()
    region = next(r for r in area.regions if r.type == 'WINDOW')
    q = STATE["popups"]
    if not q:
        sys.stdout.flush()
        os._exit(0)
    name, phase = q[0]
    if phase == "move":
        win.event_simulate(type='MOUSEMOVE', value='NOTHING', x=region.x + 140, y=region.y + region.height - 60)
        q[0] = (name, "call")
        return 0.4
    if phase == "call":
        cls = getattr(bpy.types, name, None)
        if cls is None:
            print("[SHOTS] no panel", name)
            q.pop(0)
            return 0.1
        if getattr(cls, "bl_ui_units_x", None) != 22:
            bpy.utils.unregister_class(cls)
            cls.bl_ui_units_x = 22
            bpy.utils.register_class(cls)
        with bpy.context.temp_override(window=win, area=area, region=region):
            bpy.ops.wm.call_panel(name=name, keep_open=True)
        q[0] = (name, "shot")
        return 1.2
    path = os.path.join(OUT, f"panel_{PHASE}_{name}.png")
    with bpy.context.temp_override(window=win, area=area):
        bpy.ops.screen.screenshot_area(filepath=path)
    print("[SHOTS] wrote", path)
    win.event_simulate(type='ESC', value='PRESS')
    q.pop(0)
    return 0.6


def step():
    try:
        win, area = view3d()
        space = area.spaces.active
        if STATE["queue"] is None:
            rows = inventory()
            with open(os.path.join(OUT, f"tabs_{PHASE}.json"), "w") as fh:
                json.dump(rows, fh, indent=1)
            space.show_region_ui = True
            ui = next(r for r in area.regions if r.type == 'UI')
            with bpy.context.temp_override(window=win, area=area, region=ui):
                for _ in range(8):
                    try:
                        bpy.ops.view2d.scroll_left()
                    except Exception:  # noqa: BLE001
                        pass
            STATE["queue"] = sorted({r["category"] for r in rows})
            print("[SHOTS] tabs:", STATE["queue"])
            return 0.8
        if not STATE["queue"]:
            if POPUPS and bpy.app.use_event_simulate:
                if STATE["popups"] is None:
                    win.screen.areas  # noqa: B018
                    space.show_region_ui = False
                    STATE["popups"] = [(n, "move") for n in POPUPS]
                return popup_step()
            sys.stdout.flush()
            os._exit(0)
        cat = STATE["queue"][0]
        ui = next(r for r in area.regions if r.type == 'UI')
        if STATE.get("set") != cat:
            try:
                ui.active_panel_category = cat
            except Exception as e:  # noqa: BLE001
                print("[SHOTS] cannot set the tab", cat, e)
            area.tag_redraw()
            STATE["set"] = cat
            return 1.0
        path = os.path.join(OUT, f"tabs_{PHASE}_{cat.replace(' ', '_')}.png")
        with bpy.context.temp_override(window=win, area=area):
            bpy.ops.screen.screenshot_area(filepath=path)
        print("[SHOTS] wrote", path, "drawn tab:", ui.active_panel_category)
        STATE["queue"].pop(0)
        return 0.3
    except Exception:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        os._exit(1)


bpy.app.timers.register(step, first_interval=3.0)
