"""GUI smoke + screenshots: the seal in Resources & Shelf (MICRO-EMTOOLS-DEV26, parte 2).

NOT headless — the panel must be drawn to be photographed. Run in a CLEAN user
folder with the extension installed (see tests/blender_smoke_dev26.py), with
the sidebar at its default width, the real case:

    BLENDER_USER_RESOURCES=<clean> /Applications/Blender\\ 520.app/Contents/MacOS/Blender \\
        --python tests/blender_shots_seal.py -- <out_dir>

Three stamped resources: a file set whose bytes match (✓), the same file set
with one texture changed behind an untouched door (▲), and a single file.
Writes seal_closed.png, seal_open.png, seal_differs.png in <out_dir> and
exits non-zero if a check fails.
"""
import base64
import json
import os
import shutil
import sys
import tempfile

import bpy

OUT = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else tempfile.mkdtemp()
os.makedirs(OUT, exist_ok=True)
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CASE = os.path.join(REPO, "tests", "fixtures", "dtcstamp", "19-file-set-obj.json")
FAILURES = []


def check(label, condition, detail=""):
    print(f"[SMOKE] {'PASS' if condition else 'FAIL'}: {label} {detail}")
    if not condition:
        FAILURES.append(label)
    return condition


def build_files():
    import dtcstamp
    case = json.load(open(CASE, encoding="utf-8"))
    root = tempfile.mkdtemp(prefix="em_seal_")
    blocks = {
        "from": [{"resource_id": "urn:em:rm:podio_lod0", "label": "OB_PODIO_LOD0"}],
        "how": {"dtc_kind": "decimation",
                "software": [{"name": "Blender", "version": bpy.app.version_string},
                             {"name": "EMtools", "version": "1.6.0-dev.10"}]},
        "by": {"at": "2026-10-01T15:00:00Z",
               "operator": {"id": "https://orcid.org/0000-0002-1825-0097",
                            "label": "Emanuel Demetrescu"}},
    }
    doors = {}
    for name in ("OB_PODIO_LOD1", "OB_PODIO_LOD2"):
        folder = os.path.join(root, name)
        for rel, spec in case["file_set"]["files"].items():
            target = os.path.join(folder, *rel.split("/"))
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "wb") as fh:
                fh.write(base64.b64decode(spec["base64"]) if "base64" in spec
                         else spec["text"].encode("utf-8"))
        door = os.path.join(folder, "model.obj")
        stamp = dtcstamp.new_file_set_stamp(door, f"urn:em:rm:{name.lower()}", **blocks)
        stamp["self"]["label"] = name
        dtcstamp.write_stamp(stamp, dtcstamp.file_set_stamp_path(door))
        doors[name] = door
    # LOD2: a texture changes behind the door, which stays as it was
    with open(os.path.join(root, "OB_PODIO_LOD2", "textures", "stone normal.png"), "wb") as fh:
        fh.write(b"repainted")
    doc = os.path.join(root, "Relazione_2026.pdf")
    with open(doc, "wb") as fh:
        fh.write(b"%PDF-1.7 la relazione di scavo")
    dtcstamp.write_stamp({"stamp": dtcstamp.STAMP_VERSION,
                          "self": {"resource_id": "urn:em:doc:rel2026",
                                   "label": "Relazione di scavo 2026",
                                   "digest": dtcstamp.file_digest(doc),
                                   "digest_covers": "artifact", "packaging": "file"},
                          "by": blocks["by"]},
                         doc + ".stamp.json")
    return doors, doc


def setup():
    from s3dgraphy import api
    from s3dgraphy.graph import Graph
    from s3dgraphy.multigraph.multigraph import multi_graph_manager
    doors, doc = build_files()
    g = Graph("smoke_seal")
    ids = {}
    for name, door in doors.items():
        folder = os.path.dirname(door)
        files = []
        for rel in ("model.obj", "model.mtl", "textures/stone_diffuse.png",
                    "textures/stone normal.png"):
            import dtcstamp
            full = os.path.join(folder, *rel.split("/"))
            files.append({"role": "entry_point" if rel == "model.obj" else "member",
                          "path": full, "checksum": dtcstamp.file_digest(full)})
        ids[name] = api.add_resource(g, name=name, kind="model", packaging="file_set",
                                     files=files).node_id
    ids["doc"] = api.add_resource(g, name="Relazione_2026.pdf", kind="document",
                                  files=[{"path": doc}]).node_id
    multi_graph_manager.graphs["smoke_seal"] = g
    scene = bpy.context.scene
    row = scene.em_tools.graphml_files.add()
    row.name = "smoke_seal"
    scene.em_tools.active_file_index = 0
    return ids


def open_panel():
    """EM_PT_resources is DEFAULT_CLOSED: register it again, open (children too)."""
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
        return 0.5
    if s == 3:
        p.active_seal = STATE["ids"]["OB_PODIO_LOD1"]
        p.show_seal_tech = False
        area.tag_redraw()
        return 1.0
    if s == 4:
        shot("seal_closed.png")
        p.show_seal_tech = True
        area.tag_redraw()
        return 1.0
    if s == 5:
        shot("seal_open.png")
        p.active_seal = STATE["ids"]["OB_PODIO_LOD2"]
        p.show_seal_tech = False
        area.tag_redraw()
        return 1.0
    if s == 6:
        shot("seal_differs.png")
        finish()
    return None


def finish():
    import importlib
    pkg = bpy.types.EM_PT_resources.__module__.rsplit(".", 2)[0]
    ops = importlib.import_module(pkg + ".resources_tab.operators")
    seals = {r["name"]: seal for r, _p, seal in
             ops.stamped_resources(bpy.context, ops._active(bpy.context)[1])}
    check("three seals found", len(seals) == 3, str(sorted(seals)))
    lod1, lod2 = seals.get("OB_PODIO_LOD1", {}), seals.get("OB_PODIO_LOD2", {})
    check("LOD1 ✓", lod1.get("check", {}).get("state") == "ok", lod1.get("check", {}).get("line", ""))
    check("LOD2 ▲ member by member", lod2.get("check", {}).get("changed")
          == ["textures/stone normal.png"], lod2.get("check", {}).get("line", ""))
    check("the single file ✓", seals.get("Relazione_2026.pdf", {}).get("check", {}).get("state") == "ok")
    bpy.ops.em.seal_copy_json(resource_id=STATE["ids"]["OB_PODIO_LOD1"])
    clip = bpy.context.window_manager.clipboard
    check("Copy JSON copies the .stamp.json", clip == lod1.get("raw"), f"{len(clip)} chars")
    print(f"[SMOKE] {'OK' if not FAILURES else 'FAILED: ' + ', '.join(FAILURES)}")
    sys.stdout.flush()
    os._exit(1 if FAILURES else 0)


def start():
    try:
        STATE["ids"] = setup()
        open_panel()
    except Exception as exc:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        check("setup", False, repr(exc))
        os._exit(1)
    bpy.app.timers.register(step, first_interval=0.5)
    return None


bpy.app.timers.register(start, first_interval=1.5)
