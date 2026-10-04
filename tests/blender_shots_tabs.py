"""GUI screenshots of the EM tabs of the 3D sidebar, and the inventory of the
panels per tab (U6, MICRO-EMTOOLS-MENO-E-MEGLIO). NOT headless: the sidebar
must be drawn. Opens whatever .blend is given and never saves it.

    "/Applications/Blender 520.app/Contents/MacOS/Blender" --python-use-system-env \\
        <copy>.blend --python tests/blender_shots_tabs.py -- <out_dir> <phase>

Writes `tabs_<phase>.json` (every registered panel of the VIEW_3D sidebar
whose category starts with «EM», with its label, order and parent) and
`tabs_<phase>_<category>.png`, one per tab, the sidebar wide open.
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


STATE = {"queue": None}


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
