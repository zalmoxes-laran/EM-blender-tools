"""GUI smoke + screenshots: the small seal in the DTC and in the Shelf (VLONG-DEV27, D4).

NOT headless — the panel must be drawn to be photographed. Run in a CLEAN user
folder with the extension installed (see tests/blender_smoke_birth_stamp.py):

    BLENDER_USER_RESOURCES=<clean> /Applications/Blender\\ 520.app/Contents/MacOS/Blender \\
        --python tests/blender_shots_birth_seal.py -- <out_dir>

Files made here and stamped with ``birth_stamp`` (the way an export stamps
them): a glb, the output of a DTC process; an OBJ file set and a single file on
the Shelf, and one Shelf entry without a stamp. Writes
``birth_seal_rows.png`` (the seal beside the DTC row),
``birth_seal_shelf_rows.png`` (beside the Shelf rows), ``birth_seal_from_shelf.png``
(the card opened from a Shelf row) and ``birth_seal_from_dtc.png`` (from the
DTC row), and exits non-zero if a check fails.
"""
import base64
import json
import os
import sys
import tempfile

import bpy

OUT = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else tempfile.mkdtemp()
os.makedirs(OUT, exist_ok=True)
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CASE = os.path.join(REPO, "tests", "fixtures", "dtcstamp", "19-file-set-obj.json")
FAILURES = []
STATE = {"step": 0}


def check(label, condition, detail=""):
    print(f"[SMOKE] {'PASS' if condition else 'FAIL'}: {label} {detail}")
    if not condition:
        FAILURES.append(label)
    return condition


def pkg():
    return bpy.types.EM_PT_resources.__module__.rsplit(".", 2)[0]


def setup():
    import importlib
    bs = importlib.import_module(pkg() + ".birth_stamp")
    dtc = importlib.import_module(pkg() + ".dtc_authoring.dtc_graph")
    from s3dgraphy.graph import Graph
    from s3dgraphy.multigraph.multigraph import multi_graph_manager
    root = tempfile.mkdtemp(prefix="em_birth_seal_")
    master = {"resource_id": "OB_PODIO_model_res_blend", "label": "OB_PODIO",
              "locator": "blend://scavo.blend#Object/OB_PODIO",
              "blend_digest": "sha256:" + "c" * 64, "blend_saved": True}
    how = {"dtc_kind": "decimation", "technique": "LOD generation (LOD1)",
           "parameters": {"operator": "lod.creation", "lod": "LOD1"},
           "software": bs.blender_software({"name": "3D Survey Collection",
                                            "version": "1.7.0-dev.15"})}
    # the glb a DTC process produced
    glb = os.path.join(root, "OB_PODIO_LOD1.glb")
    with open(glb, "wb") as fh:
        fh.write(b"glTF\x02\x00\x00\x00" + b"\x07" * 400)
    bs.stamp_export(glb, masters=[master], how=how, label="OB_PODIO · LOD1 for the web")
    # an OBJ file set and a single file on the Shelf
    case = json.load(open(CASE, encoding="utf-8"))
    folder = os.path.join(root, "OB_PODIO_LOD2")
    for rel, spec in case["file_set"]["files"].items():
        target = os.path.join(folder, *rel.split("/"))
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "wb") as fh:
            fh.write(base64.b64decode(spec["base64"]) if "base64" in spec
                     else spec["text"].encode("utf-8"))
    door = os.path.join(folder, "model.obj")
    bs.stamp_export(door, masters=[master], how=dict(how, technique="LOD generation (LOD2)"),
                    label="OB_PODIO · LOD2")
    tif = os.path.join(root, "ortho_2026.tif")
    with open(tif, "wb") as fh:
        fh.write(b"II*\x00 an orthophoto")
    bs.stamp_export(tif, masters=[master], how=dict(how, dtc_kind="format_conversion",
                                                    technique="orthographic render"))
    plain = os.path.join(root, "notes.pdf")
    with open(plain, "wb") as fh:
        fh.write(b"%PDF-1.7 no stamp")

    g = Graph("smoke_birth_seal")
    pid = dtc.add_process(g, "decimation", name="LOD1 for the web")
    out_id = dtc.add_output(g, pid, "mesh", url=glb, derive_from_inputs=False)
    g.find_node_by_id(out_id).name = "OB_PODIO_LOD1.glb"
    multi_graph_manager.graphs["smoke_birth_seal"] = g
    scene = bpy.context.scene
    row = scene.em_tools.graphml_files.add()
    row.name = "smoke_birth_seal"
    scene.em_tools.active_file_index = 0
    scene.em_dtc.show = True
    scene.em_dtc.active_process = pid
    p = scene.em_resources
    p.show_dtc = True
    p.show_seals = True
    p.active_seal = ""
    shelf = scene.em_shelf
    shelf.items.clear()
    for name, path in (("OB_PODIO_LOD2 (obj)", door), ("ortho_2026.tif", tif),
                       ("notes.pdf", plain)):
        it = shelf.items.add()
        it.resource_id = "shelf:" + name
        it.name = name
        it.locator = path
        it.exists = True
        it.residence = "disk"
        it.tier_short = "T0"
        it.size_text = f"{os.path.getsize(path)} B"
    shelf.active_index = 0
    return {"pid": pid, "out_id": out_id, "door": door, "glb": glb, "plain": plain}


def open_panels():
    """Resources & Shelf and its Shelf child are DEFAULT_CLOSED: re-register open."""
    parent = bpy.types.EM_PT_resources
    children = [c for c in bpy.types.Panel.__subclasses__()
                if getattr(c, "bl_parent_id", "") == "EM_PT_resources"]
    for c in children:
        bpy.utils.unregister_class(c)
    bpy.utils.unregister_class(parent)
    parent.bl_options = set()
    bpy.utils.register_class(parent)
    for c in children:
        c.bl_options = set()
        bpy.utils.register_class(c)


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


def step():
    win, area = view3d()
    s = STATE["step"]
    STATE["step"] += 1
    p = bpy.context.scene.em_resources
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
        ui.active_panel_category = "EM Scene"
        return 1.0
    if s == 3:
        shot("birth_seal_rows.png")
        #: the Shelf sits under the fold while the DTC is open: close the
        #: sections above it for the Shelf's own shot
        p.show_dtc = False
        p.show_seals = False
        area.tag_redraw()
        return 1.0
    if s == 4:
        shot("birth_seal_shelf_rows.png")
        bpy.ops.em.seal_show(resource_id="shelf:OB_PODIO_LOD2 (obj)",
                             path=STATE["ids"]["door"], name="OB_PODIO_LOD2 (obj)")
        p.show_dtc = False
        area.tag_redraw()
        return 1.0
    if s == 5:
        shot("birth_seal_from_shelf.png")
        bpy.ops.em.seal_show(resource_id=STATE["ids"]["out_id"])
        area.tag_redraw()
        return 1.0
    if s == 6:
        shot("birth_seal_from_dtc.png")
        finish()
    return None


def finish():
    import importlib
    ops = importlib.import_module(pkg() + ".resources_tab.operators")
    graph = ops._active(bpy.context)[1]
    seals = {r["id"]: seal for r, _p, seal in ops.stamped_resources(bpy.context, graph)}
    ids = STATE["ids"]
    check("the DTC output has a seal", ids["out_id"] in seals)
    check("the Shelf entry opened is in the Seals section", "shelf:OB_PODIO_LOD2 (obj)" in seals)
    door_seal = seals.get("shelf:OB_PODIO_LOD2 (obj)", {})
    check("the Shelf file set verifies ✓", door_seal.get("check", {}).get("state") == "ok",
          door_seal.get("check", {}).get("line", ""))
    check("the row lookup finds the DTC stamp",
          ops.stamp_path_of_resource(bpy.context, graph, ids["out_id"], ids["glb"])
          == ids["glb"] + ".stamp.json")
    from importlib import import_module
    rs = import_module(pkg() + ".resource_seal")
    check("an entry without a stamp has no seal", rs.find_stamp(ids["plain"]) is None)
    check("the card opened is the DTC one", bpy.context.scene.em_resources.active_seal == ids["out_id"])
    print(f"[SMOKE] {'OK' if not FAILURES else 'FAILED: ' + ', '.join(FAILURES)}")
    sys.stdout.flush()
    os._exit(1 if FAILURES else 0)


def start():
    try:
        STATE["ids"] = setup()
        open_panels()
    except Exception as exc:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        check("setup", False, repr(exc))
        os._exit(1)
    bpy.app.timers.register(step, first_interval=0.5)
    return None


bpy.app.timers.register(start, first_interval=1.5)
