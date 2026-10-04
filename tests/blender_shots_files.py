"""GUI smoke + screenshots: R1/R2/I1 · the files of San Pietro in «Resources & Shelf».

NOT headless (the panel must be drawn to be photographed). With s3Dgraphy from
source and the copy of San Pietro next door:

    PYTHONPATH=~/Documents/GitHub/s3Dgraphy/src \\
    "/Applications/Blender 520.app/Contents/MacOS/Blender" --python-use-system-env \\
        --python tests/blender_shots_files.py -- <out_dir>

The graph of San Pietro (from its GraphML), its DosCo the copy of the case
study: «Check files» through the ONE resolver; D.32 is on the disk (the old
reading said missing), the 22 zeroed files are «empty copy». Writes
emtools_files.png and emtools_files_empty.png (the filter on «empty copy»),
and states.json with the state of every resource (for T-R1, compared with
EMStudio's and StratiField's). Exits non-zero if a check fails.
"""
import json
import os
import sys
import tempfile

import bpy

OUT = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else tempfile.mkdtemp()
os.makedirs(OUT, exist_ok=True)
GH = os.path.expanduser("~/Documents/GitHub")
SP = os.path.join(GH, "_datasets", "SegniSanPietro")
EMJSON = os.path.join(SP, "_lavoro-claude", "risultati", "sp_from_graphml.em.json")
DOSCO = os.path.join(SP, "caso-di-studio-EM", "EM", "DosCo")
FAILURES = []


def check(label, condition, detail=""):
    print(f"[SMOKE] {'PASS' if condition else 'FAIL'}: {label} {detail}")
    if not condition:
        FAILURES.append(label)


def setup():
    em = bpy.context.scene.em_tools
    while len(em.graphml_files):
        em.graphml_files.remove(0)
    getattr(bpy.ops, "import").em_emjson(filepath=EMJSON)
    em.graphml_files[0].dosco_dir = DOSCO
    em.active_file_index = 0


def open_panel():
    parent = bpy.types.EM_PT_resources
    children = [c for c in bpy.types.Panel.__subclasses__()
                if getattr(c, "bl_parent_id", "") == "EM_PT_resources"]
    for c in children:
        bpy.utils.unregister_class(c)
    bpy.utils.unregister_class(parent)
    parent.bl_options = set()
    bpy.utils.register_class(parent)
    for c in children:
        c.bl_options = set(getattr(c, "bl_options", set())) | {"DEFAULT_CLOSED"}
        bpy.utils.register_class(c)


def view3d():
    win = bpy.context.window_manager.windows[0]
    area = max((a for a in win.screen.areas if a.type == 'VIEW_3D'),
               key=lambda a: a.width * a.height)
    return win, area


def fs():
    import importlib
    pkg = bpy.types.EM_PT_resources.__module__.rsplit(".", 2)[0]
    return importlib.import_module(pkg + ".sync_manager.file_states")


STATE = {"step": 0}


def shot(name):
    win, area = view3d()
    path = os.path.join(OUT, name)
    with bpy.context.temp_override(window=win, area=area):
        bpy.ops.screen.screenshot_area(filepath=path)
    check(f"screenshot {name}", os.path.isfile(path), path)


def step():
    win, area = view3d()
    s = STATE["step"]
    STATE["step"] += 1
    if s == 0:
        with bpy.context.temp_override(window=win, area=area):
            bpy.ops.screen.screen_full_area()
        return 0.5
    if s == 1:
        win, area = view3d()
        area.spaces.active.show_region_ui = True
        area.spaces.active.overlay.show_overlays = False
        return 0.5
    if s == 2:
        ui = next(r for r in area.regions if r.type == 'UI')
        try:
            ui.active_panel_category = "EM Scene"
        except AttributeError:          # read-only in this build: the tab stays
            print("[SMOKE] note: cannot switch the sidebar tab here")
        return 0.5
    if s == 3:
        bpy.ops.em.files_check()
        area.tag_redraw()
        return 1.0
    if s == 4:
        shot("emtools_files.png")
        fs().ULTIMI["filter"] = "empty_copy"
        area.tag_redraw()
        return 1.0
    if s == 5:
        shot("emtools_files_empty.png")
        finish()
    return None


def finish():
    results = fs().ULTIMI["results"]
    by = {r["name"]: r for r in results}
    check("D.32 is on the disk", by.get("Link to D.32", {}).get("state") == "on_disk",
          str(by.get("Link to D.32")))
    counts = fs().counts(results)
    print(f"[SMOKE] counts {counts}")
    with open(os.path.join(OUT, "states_emtools.json"), "w") as fh:
        json.dump({r["id"]: r["state"] for r in results}, fh, indent=1, sort_keys=True)
    print(f"[SMOKE] {'OK' if not FAILURES else 'FAILED: ' + ', '.join(FAILURES)}")
    sys.stdout.flush()
    os._exit(1 if FAILURES else 0)


def start():
    try:
        setup()
        open_panel()
    except Exception as exc:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        check("setup", False, repr(exc))
        os._exit(1)
    bpy.app.timers.register(step, first_interval=0.5)
    return None


bpy.app.timers.register(start, first_interval=1.5)
