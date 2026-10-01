"""GUI screenshots for VLONG-DEV28 part E: the drop-downs, the local identity, a stamp.

NOT headless — run in a CLEAN user folder with the extension installed (see
tests/blender_smoke_birth_stamp.py), Blender 5.2, its default (dark) theme:

    BLENDER_USER_RESOURCES=<clean> /Applications/Blender\\ 520.app/Contents/MacOS/Blender \\
        --python tests/blender_shots_dev28.py -- <out_dir>

Writes ``dev28_dtc_dropdowns.png`` (the DTC section of the EM Scene sidebar
with a process, and beside it the three kind enums drawn expanded, so every
item they offer is on screen), ``dev28_prefs_identity.png`` (Preferences ▸
Add-ons ▸ EM Tools, Provenance with the local identity, «declared, not
verified») and ``dev28_stamp_operator.png`` (a .stamp.json written under that
identity, opened in the Text Editor: ``by.operator`` with ``auth: declared``).
Exits non-zero if a check fails.
"""
import json
import os
import sys
import tempfile

import bpy

OUT = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else tempfile.mkdtemp()
os.makedirs(OUT, exist_ok=True)
FAILURES = []
STATE = {"step": 0}
ORCID = "0000-0002-1825-0097"


def check(label, condition, detail=""):
    print(f"[SMOKE] {'PASS' if condition else 'FAIL'}: {label} {detail}")
    if not condition:
        FAILURES.append(label)
    return condition


def pkg():
    return bpy.types.EM_PT_resources.__module__.rsplit(".", 2)[0]


class EM_PT_dev28_kinds(bpy.types.Panel):
    """Every item of the three kind enums, expanded — the drop-downs, opened."""
    bl_label = "DTC kinds (dev28 shot: every item)"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "EM Scene"

    def draw(self, context):
        p = context.scene.em_dtc
        for name in ("process_kind", "input_kind", "output_kind"):
            col = self.layout.column(align=True)
            col.label(text=name.replace("_", " "))
            col.prop(p, name, expand=True)


def setup():
    import importlib
    bs = importlib.import_module(pkg() + ".birth_stamp")
    dtc = importlib.import_module(pkg() + ".dtc_authoring.dtc_graph")
    from s3dgraphy.graph import Graph
    from s3dgraphy.multigraph.multigraph import multi_graph_manager
    g = Graph("smoke_dev28")
    pid = dtc.add_process(g, bs.resolve_kind(bs.KIND_LOD), name="LOD1 of OB_PODIO")
    multi_graph_manager.graphs["smoke_dev28"] = g
    scene = bpy.context.scene
    row = scene.em_tools.graphml_files.add()
    row.name = "smoke_dev28"
    scene.em_tools.active_file_index = 0
    scene.em_dtc.show = True
    scene.em_dtc.active_process = pid
    scene.em_dtc.process_kind = bs.resolve_kind(bs.KIND_LOD)
    bpy.utils.register_class(EM_PT_dev28_kinds)
    # the local identity, as a person types it in the preferences
    prefs = bpy.context.preferences.addons[pkg()].preferences
    prefs.local_orcid = f"https://orcid.org/{ORCID}"
    prefs.local_name = "Emanuel Demetrescu"
    root = tempfile.mkdtemp(prefix="em_dev28_")
    glb = os.path.join(root, "OB_PODIO_LOD1.glb")
    with open(glb, "wb") as fh:
        fh.write(b"glTF\x02\x00\x00\x00" + b"\x09" * 300)
    master = {"resource_id": "blend:72474475-6f84-589a-b600-eea12f464279", "label": "OB_PODIO",
              "locator": "blend://scavo.blend#Object/OB_PODIO",
              "blend_digest": "sha256:" + "c" * 64, "blend_saved": False,
              "fingerprint": "struct:f=6:mat=OB_PODIO_mat:v=8"}
    res = bs.stamp_export(glb, masters=[master], operator=bs.current_operator(),
                          how={"dtc_kind": bs.KIND_LOD, "technique": "LOD generation (LOD1)",
                               "parameters": {"operator": "lod.creation", "lod": "LOD1"},
                               "software": bs.blender_software({"name": "3D Survey Collection",
                                                                "version": "1.7.0-dev.15"})})
    stamp = json.load(open(res["stamp_path"], encoding="utf-8"))
    check("the stamp names the local identity, declared", stamp["by"].get("operator") == {
        "id": f"https://orcid.org/{ORCID}", "label": "Emanuel Demetrescu",
        "auth": {"mode": "declared"}}, json.dumps(stamp["by"]))
    STATE["stamp_path"] = res["stamp_path"]


def view3d():
    win = bpy.context.window_manager.windows[0]
    area = max(win.screen.areas, key=lambda a: a.width * a.height)
    return win, area


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
        area.type = 'VIEW_3D'
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
        ui.active_panel_category = "EM Scene"
        return 1.0
    if s == 3:
        area.tag_redraw()
        return 0.5
    if s == 4:
        shot("dev28_dtc_dropdowns.png")
        # the real Preferences, Add-ons, EM Tools expanded
        area.type = 'PREFERENCES'
        bpy.context.preferences.active_section = 'ADDONS'
        bpy.context.window_manager.addon_search = "EM Tools"
        try:
            bpy.ops.preferences.addon_expand(module=pkg())
        except Exception as exc:
            print("[SMOKE] addon_expand:", exc)
        return 1.5
    if s == 5:
        area.tag_redraw()
        return 0.5
    if s == 6:
        #: measured: screenshot_area takes the area as last drawn, so every
        #: shot waits one step after its area changed
        area.tag_redraw()
        return 0.5
    if s == 7:
        shot("dev28_prefs_identity.png")
        area.type = 'TEXT_EDITOR'
        text = bpy.data.texts.load(STATE["stamp_path"])
        area.spaces.active.text = text
        area.spaces.active.show_line_numbers = True
        area.spaces.active.font_size = 9
        return 1.0
    if s == 8:
        win, area = view3d()
        text = area.spaces.active.text
        line = next((i for i, l in enumerate(text.lines) if '"by"' in l.body), 0)
        area.spaces.active.top = max(0, line - 12)
        area.tag_redraw()
        return 0.8
    if s == 9:
        area.tag_redraw()
        return 0.8
    if s == 10:
        shot("dev28_stamp_operator.png")
        finish()
    return None


def finish():
    print(f"[SMOKE] {'ALL PASS' if not FAILURES else 'FAILURES: ' + ', '.join(FAILURES)}")
    bpy.ops.wm.quit_blender()


def start():
    setup()
    bpy.app.timers.register(step, first_interval=0.5)
    return None


bpy.app.timers.register(start, first_interval=1.5)
