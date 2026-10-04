"""GUI screenshot · T-U5, the images of a unit with their thumbnails, in the
Stratigraphy Manager. Run after `blender_smoke_unit_images.py … make`.

    "/Applications/Blender 520.app/Contents/MacOS/Blender" --python-use-system-env \\
        --enable-event-simulate --python tests/blender_shots_unit_images.py -- <work_dir> <out_dir>

Opens <work>/Prova/EM/prova.em.json, selects USM01, opens «Images of the
unit» and photographs the Stratigraphy Manager as a popup:
`unit_images_USM01.png`.
"""
import os
import sys

import bpy

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
WORK = ARGS[0] if ARGS else "/tmp/tu5"
OUT = ARGS[1] if len(ARGS) > 1 else "/tmp/tu5-shots"
os.environ["EM_THUMBS_DIR"] = os.path.join(WORK, "thumbs-cache")
os.makedirs(OUT, exist_ok=True)
STATE = {"step": 0}


def view3d():
    win = bpy.context.window_manager.windows[0]
    area = max((a for a in win.screen.areas if a.type == 'VIEW_3D'), key=lambda a: a.width * a.height)
    return win, area


def step():
    try:
        s = STATE["step"]
        win, area = view3d()
        region = next(r for r in area.regions if r.type == 'WINDOW')
        if s == 0:
            getattr(bpy.ops, "import").em_emjson(filepath=os.path.join(WORK, "Prova", "EM", "prova.em.json"))
            strat = bpy.context.scene.em_tools.stratigraphy
            strat.units_index = next(i for i, u in enumerate(strat.units) if u.name == "USM01")
            strat.show_documents = True
            cls = bpy.types.VIEW3D_PT_ToolsPanel
            bpy.utils.unregister_class(cls)
            cls.bl_ui_units_x = 22
            bpy.utils.register_class(cls)
            win.event_simulate(type='MOUSEMOVE', value='NOTHING', x=region.x + 140, y=region.y + region.height - 100)
            STATE["step"] = 1
            return 1.0
        if s == 1:
            with bpy.context.temp_override(window=win, area=area, region=region):
                bpy.ops.wm.call_panel(name="VIEW3D_PT_ToolsPanel", keep_open=True)
            STATE["step"] = 2
            return 2.0
        path = os.path.join(OUT, "unit_images_USM01.png")
        with bpy.context.temp_override(window=win, area=area):
            bpy.ops.screen.screenshot_area(filepath=path)
        print("[SHOTS] wrote", path)
        sys.stdout.flush()
        os._exit(0)
    except Exception:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        sys.stdout.flush()
        os._exit(1)


bpy.app.timers.register(step, first_interval=2.0)
