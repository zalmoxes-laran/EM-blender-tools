"""Headless smoke · T-U5, the images of three units, on a project made for it.

    PYTHONPATH=~/Documents/GitHub/s3Dgraphy/src \\
    "/Applications/Blender 520.app/Contents/MacOS/Blender" -b --python-use-system-env \\
        --python tests/blender_smoke_unit_images.py -- <work_dir> make
    … -- <work_dir> reload

`make`: a project tree <work>/Prova/EM/ with the graph of s3Dgraphy's example
xlsx (USM01…USM05) as em.json and, in EM/DosCo, five images: USM01_north,
USM02_a, USM002_b (the same unit, zero-padded), USM03_c and one of a unit that
does not exist. «Propose images» proposes four for three units; one is
unticked; «Link» makes three resources with their sha256, linked to their
units, and their thumbnails in the cache (EM_THUMBS_DIR); the graph is saved.
`reload`: a new Blender opens the em.json; the images are there, linked, with
their state, and their thumbnails come from the cache (not rebuilt).
"""
import json
import os
import shutil
import sys
import time

import bpy

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
WORK = ARGS[0] if ARGS else "/tmp/tu5"
PHASE = ARGS[1] if len(ARGS) > 1 else "make"
os.environ["EM_THUMBS_DIR"] = os.path.join(WORK, "thumbs-cache")
PROJ = os.path.join(WORK, "Prova")
EMJSON = os.path.join(PROJ, "EM", "prova.em.json")
FAILURES = []


def check(label, condition, detail=""):
    print(f"[SMOKE] {'PASS' if condition else 'FAIL'}: {label} {detail}")
    if not condition:
        FAILURES.append(label)


em = bpy.context.scene.em_tools
names = [n for n in sys.modules if n.endswith(".graph_origins") and n.startswith("bl_ext.")]
PKG = names[0].rsplit(".graph_origins", 1)[0]
import importlib  # noqa: E402
ub = importlib.import_module(PKG + ".unit_images.blender")
core = importlib.import_module(PKG + ".unit_images.core")

if PHASE == "make":
    shutil.rmtree(WORK, ignore_errors=True)
    os.makedirs(os.path.join(PROJ, "EM", "DosCo"))
    shutil.copyfile("/tmp/tu4/example_stratigraphy.em.json", EMJSON)
    from PIL import Image
    for i, name in enumerate(["USM01_north.jpg", "USM02_a.jpg", "USM002_b.png", "USM03_c.jpg", "USM99_x.jpg"]):
        Image.new("RGB", (640, 480), (40 * i, 120, 200 - 30 * i)).save(os.path.join(PROJ, "EM", "DosCo", name))
    r = getattr(bpy.ops, "import").em_emjson(filepath=EMJSON)
    check("the project's em.json is loaded", r == {"FINISHED"}, str(r))
    st = bpy.context.scene.em_unit_images
    r = bpy.ops.em.unit_images_propose()
    props = [(os.path.basename(p.path), p.unit_name) for p in st.proposals]
    print("[SMOKE] proposed:", props)
    check("four images proposed for three units, from EM/DosCo", r == {"FINISHED"} and len(props) == 4
          and len({u for _, u in props}) == 3, str(props))
    check("the image of a unit that does not exist is not proposed", not any(n.startswith("USM99") for n, _ in props))
    for p in st.proposals:
        if os.path.basename(p.path) == "USM002_b.png":
            p.take = False          # the person does not want this one
    r = bpy.ops.em.unit_images_confirm()
    check("Link finished", r == {"FINISHED"}, str(r))
    from s3dgraphy import get_graph
    graph = get_graph(em.graphml_files[em.active_file_index].name)
    linked = {}
    for uid, uname in ub.units_of(graph):
        imgs = ub.linked_images(graph, uid)
        if imgs:
            linked[uname] = [(i.name, ub._checksum(i), ub._locator(i)) for i in imgs]
    print("[SMOKE] linked:", json.dumps(linked, indent=1))
    check("three units have their image", sorted(linked) == ["USM01", "USM02", "USM03"], str(sorted(linked)))
    check("USM02 has only the ticked one", [x[0] for x in linked.get("USM02", [])] == ["USM02_a.jpg"])
    check("each image is a resource with its sha256", all(c.startswith("sha256:") and len(c) == 71
                                                         for v in linked.values() for _, c, _ in v))
    check("its position is a path of the study", all(l.startswith("/EM/DosCo/") for v in linked.values()
                                                     for _, _, l in v), str([l for v in linked.values() for *_, l in v]))
    thumbs = [core.thumb_path(ub.cache_root(), c) for v in linked.values() for _, c, _ in v]
    check("the thumbnails are in the cache, by sha256", all(os.path.isfile(t) for t in thumbs), str(thumbs))
    check("the cache is outside the project", not ub.cache_root().startswith(PROJ))
    with open(os.path.join(WORK, "thumbs.json"), "w") as fh:
        json.dump({t: os.path.getmtime(t) for t in thumbs}, fh)
    # the state of each, with the one resolver
    node = ub.linked_images(graph, next(uid for uid, n in ub.units_of(graph) if n == "USM01"))[0]
    state, path = ub.resolve(bpy.context, node)
    check("the resolver finds it on this computer", state == "on_disk" and path.endswith("USM01_north.jpg"),
          f"{state} {path}")
    r = getattr(bpy.ops, "export").em_save()          # «Save», the graph's own em.json
    check("Save writes the graph back to its em.json", r == {"FINISHED"}, str(r))
    check("the graph is saved with its images", '"has_linked_resource"' in open(EMJSON).read())
else:
    time.sleep(1.1)
    r = getattr(bpy.ops, "import").em_emjson(filepath=EMJSON)
    check("the saved em.json opens again", r == {"FINISHED"}, str(r))
    from s3dgraphy import get_graph
    graph = get_graph(em.graphml_files[em.active_file_index].name)
    linked = {n: [i.name for i in ub.linked_images(graph, uid)] for uid, n in ub.units_of(graph)
              if ub.linked_images(graph, uid)}
    check("the three units still have their images", sorted(linked) == ["USM01", "USM02", "USM03"], str(linked))
    before = json.load(open(os.path.join(WORK, "thumbs.json")))
    icons = []
    for uid, n in ub.units_of(graph):
        for node in ub.linked_images(graph, uid):
            state, path = ub.resolve(bpy.context, node)
            icons.append(ub.thumb_icon(node, path))
    # headless, Blender makes no icon (icon_id stays 0): what is measured is
    # that each preview was loaded FROM the cache file; the visible thumbnail
    # is photographed in the GUI (tests/blender_shots_unit_images.py)
    loaded = sorted(ub._PREVIEWS.keys()) if ub._PREVIEWS is not None else []
    want = sorted(os.path.basename(t).split("_")[0] for t in before)
    check("each image's preview is loaded from the cache", loaded == want, f"{loaded} vs {want}")
    after = {t: os.path.getmtime(t) for t in before}
    check("the thumbnails come from the cache, not rebuilt", after == before)
    # E5 · «Remove link» for an image linked by mistake: the edge goes, the
    # resource stays, and Save writes it
    uid03 = next(uid for uid, n in ub.units_of(graph) if n == "USM03")
    img03 = ub.linked_images(graph, uid03)[0]
    r = bpy.ops.em.unit_images_unlink(unit_id=uid03, resource_id=img03.node_id)
    check("Remove link finished", r == {"FINISHED"}, str(r))
    check("USM03 has no image any more", not ub.linked_images(graph, uid03))
    check("the image stays a resource of the graph", graph.find_node_by_id(img03.node_id) is not None)
    r = getattr(bpy.ops, "export").em_save()
    doc = open(EMJSON).read()
    check("Save writes the link removed", r == {"FINISHED"}
          and f'"{uid03}_has_linked_resource_{img03.node_id}"' not in doc and img03.node_id in doc)
    # the section draws (a layout is needed: the draw function is called by the panel)
print("[SMOKE] RESULT:", "ALL PASS" if not FAILURES else f"FAILED {FAILURES}")
sys.stdout.flush()
