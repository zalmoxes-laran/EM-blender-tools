"""Headless smoke · T-A2, T-A3, B1 (MICRO-ASSET-VERSIONI-E-SCENE-MULTIGRAFO).

NOT a pytest test (needs bpy, the copy of Templu Mare, and for A3/B1 a node).
Run it inside Blender with the EM-tools extension enabled, with the s3Dgraphy
checkout first on the path (asset versions need s3dgraphy ≥ dev34):

    cd ~/Documents/GitHub/stratigraph-server/dev-stack
    PYTHONPATH=~/Documents/GitHub/s3Dgraphy/src \\
    EM_DEV_TOKEN=$(./token.sh) EM_NODE=http://localhost:8000 \\
    EM_TM=/tmp/micro-asset-versioni \\
    /Applications/Blender\\ 520.app/Contents/MacOS/Blender --background \\
        --python-use-system-env \\
        --python ~/Documents/GitHub/EM-blender-tools/tests/blender_smoke_asset_versions.py

T-A2 · the COPY of Temple_20260930.em.json loaded; OB_PODIO imported from LOD0
as the master (resident, its sha256), hatted by an RM in an epoch; a
«Decoration» cube. «Add version…» twice (LOD1 web, LOD2 preview, from the LOD1
and LOD2 OBJ files): ONE object, three versions in the graph, one library .blend
with three meshes; «LOD ▸» changes the object's mesh, its name and its graph
links stay; the file saved and reopened still shows the level it showed.

T-A3 · (needs EM_DEV_TOKEN) a new room holds the three versions' bytes; the
check builds the room's library (3 fetched), a second check fetches nothing,
LOD2 revised with other bytes is fetched ALONE; the decoration stays «only here».

B1 · (needs EM_DEV_TOKEN) «Archive the scene package» puts the .blend with its
library packed into the room; «Download the package» on «another computer» (a
folder with no cache) unpacks the library beside it and the file opens with
OB_PODIO whole.

Everything is written under $EM_TM/agent-asset/; E.D.'s data is only read.
Exits non-zero on failure.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time

import bpy

FAILURES = []


def check(label, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print(f"[SMOKE] {status}: {label} {detail}")
    if not condition:
        FAILURES.append(label)
    return condition


def mod(suffix):
    names = [n for n in sys.modules if n.endswith(suffix) and n.startswith("bl_ext.")]
    if not names:
        print(f"[SMOKE] aborting: {suffix} not loaded — enable the extension")
        sys.exit(1)
    return sys.modules[names[0]]


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return "sha256:" + h.hexdigest()


TM = os.environ.get("EM_TM", "/tmp/micro-asset-versioni")
NODE = os.environ.get("EM_NODE", "http://localhost:8000")
TOKEN = os.environ.get("EM_DEV_TOKEN", "")
LOD = {lv: os.path.join(TM, "TempluMare_tiles", lv, f"OB_PODIO_{lv}.obj")
       for lv in ("LOD0", "LOD1", "LOD2")}

import s3dgraphy  # noqa: E402
from s3dgraphy import api  # noqa: E402
from s3dgraphy.nodes.representation_node import RepresentationModelNode  # noqa: E402

print("[SMOKE] s3dgraphy from", s3dgraphy.__file__)
if not hasattr(api, "add_version"):
    print("[SMOKE] aborting: this s3dgraphy has no add_version (PYTHONPATH + "
          "--python-use-system-env)")
    sys.exit(1)

av = mod(".sync_manager.asset_versions")
scene_check = mod(".sync_manager.scene_check")
room_cfg = mod(".sync_manager.room")
ops = mod(".sync_manager.operators")

work = os.path.join(TM, "agent-asset", f"run-{int(time.time())}")
os.makedirs(work)
main_blend = os.path.join(work, "templu_scene.blend")
copy = os.path.join(work, "Temple.em.json")
shutil.copyfile(os.path.join(TM, "Temple_20260930.em.json"), copy)

# ── the project: graph, OB_PODIO master, a decoration ───────────────────────
scene = bpy.context.scene
for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
bpy.ops.wm.save_as_mainfile(filepath=main_blend)
em_tools = scene.em_tools
while len(em_tools.graphml_files):
    em_tools.graphml_files.remove(0)
esito = getattr(bpy.ops, "import").em_emjson(filepath=copy)
check("the copy of Temple loads", esito == {"FINISHED"}, repr(esito))
ok, graph = ops.is_graph_available(bpy.context)
epoch = next(n for n in graph.nodes if n.node_type == "EpochNode")

t0 = time.time()
before = set(bpy.data.objects)
bpy.ops.wm.obj_import(filepath=LOD["LOD0"])
podio = [o for o in bpy.data.objects if o not in before][0]
podio.name = "OB_PODIO"
print(f"[SMOKE] LOD0 imported in {time.time() - t0:.1f}s: "
      f"{len(podio.data.vertices)} vertices")
sha0 = sha(LOD["LOD0"])
api.add_resource(graph, resource_id="podio_master", name="OB_PODIO",
                 kind="3d_model", tier="master", residency="resident",
                 files=[{"path": "OB_PODIO_LOD0.obj", "url": LOD["LOD0"],
                         "checksum": sha0, "media_type": "model/obj"}])
graph.add_node(RepresentationModelNode("OB_PODIO_model", name="OB_PODIO"))
graph.add_edge("rm_podio_res", "OB_PODIO_model", "podio_master", "has_linked_resource")
graph.add_edge("rm_podio_ep", "OB_PODIO_model", epoch.node_id, "has_first_epoch")
podio["em_rm_node_id"] = "OB_PODIO_model"
podio["em_resource_id"] = "podio_master"
podio["em_asset_sha256"] = sha0
bpy.ops.mesh.primitive_cube_add(size=1, location=(30, 0, 0))
decoration = bpy.context.active_object
decoration.name = "Decoration"
rm_edges = sorted((e.edge_source, e.edge_target, e.edge_type) for e in graph.edges
                  if "OB_PODIO_model" in (e.edge_source, e.edge_target))


def activate(obj):
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


# ── T-A2 · «Add version…» twice ─────────────────────────────────────────────
n_objects = len(bpy.data.objects)
for level, purpose in (("LOD1", "web"), ("LOD2", "preview")):
    activate(podio)
    t0 = time.time()
    esito = bpy.ops.em.asset_add_version(level=level, purpose=purpose,
                                         master_level="LOD0", source="FILE",
                                         filepath=LOD[level])
    check(f"Add version {level}: FINISHED ({time.time() - t0:.1f}s)",
          esito == {"FINISHED"}, repr(esito))

check("still ONE object for the podium (and the decoration)",
      len(bpy.data.objects) == n_objects and bpy.data.objects.get("OB_PODIO") is podio,
      repr([o.name for o in bpy.data.objects]))
rows = api.versions_of(graph, "podio_master")
print("[SMOKE] versions:", [(r["level"], r["purpose"], r["checksum"][:14]) for r in rows])
check("three versions in the graph: LOD0 master, LOD1 web, LOD2 preview",
      [(r["level"], r["purpose"]) for r in rows]
      == [("LOD0", ""), ("LOD1", "web"), ("LOD2", "preview")])
check("each version is made by lod_generation from the master",
      all(graph.find_node_by_id(r["process_id"]).data.get("dtc_kind") == "lod_generation"
          for r in rows[1:]))
check("the versions carry the digests of their files",
      [r["checksum"] for r in rows] == [sha0, sha(LOD["LOD1"]), sha(LOD["LOD2"])])
lib = av.library_abspath("podio_master", None)
check("ONE library for the asset, beside the .blend", os.path.isfile(lib), lib)
levels = av.levels_of(podio)
check("the library holds the three meshes",
      sorted(levels) == ["LOD0", "LOD1", "LOD2"], repr(sorted(levels)))
check("each mesh carries the digest of its version",
      [levels[lv].get("em_asset_sha256") for lv in ("LOD0", "LOD1", "LOD2")]
      == [r["checksum"] for r in rows])
check("the object shows the master, linked from the library",
      podio.get("em_level") == "LOD0" and podio.data.library is not None,
      repr((podio.get("em_level"), podio.data.name)))
links = api.inherited_links(graph, rows[2]["id"])
check("LOD2 inherits the RM and the epoch of the asset",
      [f["id"] for f in links["facets"]] == ["OB_PODIO_model"]
      and epoch.node_id in [b["id"] for b in links["binds"]], repr(links))

verts = {}
activate(podio)
for expected in ("LOD1", "LOD2", "LOD2"):
    esito = bpy.ops.em.asset_lod_step(direction=1)
    verts[podio.get("em_level")] = len(podio.data.vertices)
    check(f"LOD ▸ → {expected}", podio.get("em_level") == expected
          and podio.data.name == f"OB_PODIO@{expected}",
          repr((podio.get("em_level"), podio.data.name)))
check("the mesh really changed (vertices differ)",
      len(set(verts.values())) == 2, repr(verts))
check("the object's name stays", podio.name == "OB_PODIO")
check("its graph links stay",
      podio.get("em_rm_node_id") == "OB_PODIO_model"
      and sorted((e.edge_source, e.edge_target, e.edge_type) for e in graph.edges
                 if "OB_PODIO_model" in (e.edge_source, e.edge_target)) == rm_edges)
check("the object carries the digest of the level it shows",
      podio.get("em_asset_sha256") == rows[2]["checksum"])
esito = bpy.ops.em.asset_lod_step(direction=-1, whole_scene=True)
check("◂ LOD for the whole scene → LOD1", podio.get("em_level") == "LOD1")
print("[SMOKE] vertices per level:", json.dumps(verts))

bpy.ops.wm.save_mainfile()
size_main = os.path.getsize(main_blend)
size_lib = os.path.getsize(lib)
print(f"[SMOKE] main .blend {size_main / 1e6:.1f} MB · library {size_lib / 1e6:.1f} MB")
check("the working file stays small (the meshes live in the library)",
      size_main < size_lib / 5, f"{size_main} vs {size_lib}")
probe = ("import bpy; o = bpy.data.objects['OB_PODIO']; "
         "print('PROBE', o.get('em_level'), o.data.name, bool(o.data.library), "
         "len(o.data.vertices), o.get('em_rm_node_id'))")
out = subprocess.run([bpy.app.binary_path, "-b", "--factory-startup", main_blend,
                      "--python-expr", probe], capture_output=True, text=True).stdout
line = next((x for x in out.splitlines() if x.startswith("PROBE")), "")
print("[SMOKE] reopened:", line)
check("reopened elsewhere: OB_PODIO still shows LOD1 from the library",
      line.startswith("PROBE LOD1 OB_PODIO@LOD1 True") and line.split()[4] != "0"
      and line.endswith("OB_PODIO_model"), line)

if not TOKEN:
    print("[SMOKE] no EM_DEV_TOKEN: T-A3 and B1 skipped")
else:
    rooms_list = mod(".sync_manager.rooms_list")
    upload = mod(".sync_manager.asset_upload")
    package = mod(".sync_manager.scene_package")
    ROOM_NAME = f"T-A3 {int(time.time())}"
    ROOM = rooms_list.room_id_from_name(ROOM_NAME)
    rooms_list.create_room(NODE, TOKEN, ROOM_NAME)
    for lv in ("LOD0", "LOD1", "LOD2"):
        upload.upload_asset(NODE, ROOM, LOD[lv], None, "model/obj", TOKEN)
    room_cfg.set_room(NODE, ROOM, TOKEN)
    print(f"[SMOKE] room {ROOM}: the three versions' bytes are in its store")

    calls = []

    def counted(checksum):
        calls.append(checksum)
        return room_cfg.get_asset(checksum)

    # ── T-A3 · first check: the room's library is built, three meshes fetched
    t0 = time.time()
    rep = scene_check.check_scene(bpy.context, graph, download=True, fetch_fn=counted)
    for line in scene_check.ULTIMA_VERIFICA.get("sentences") or []:
        print("[SMOKE]   ", line)
    lib_room = av.library_abspath("podio_master", ROOM)
    check(f"A3 cold cache: the three versions fetched ({time.time() - t0:.1f}s)",
          sorted(calls) == sorted(r["checksum"] for r in rows), repr(len(calls)))
    check("…into ONE library of the room", os.path.isfile(lib_room), lib_room)
    check("the same object, now showing LOD1 from the room's library",
          podio.name == "OB_PODIO" and podio.get("em_level") == "LOD1"
          and av._same_file(podio.data.library.filepath, lib_room),
          repr(podio.data.library.filepath))
    check("no second object was created for the asset",
          len([o for o in bpy.data.objects if o.get("em_asset_id")]) == 1)

    calls.clear()
    scene_check.check_scene(bpy.context, graph, download=True, fetch_fn=counted)
    check("A3 second check: nothing fetched", calls == [], repr(calls))

    # LOD2 revised: other bytes, uploaded, the version revised in the graph
    lod2b = os.path.join(work, "OB_PODIO_LOD2_rev.obj")
    with open(LOD["LOD2"], "rb") as src, open(lod2b, "wb") as dst:
        shutil.copyfileobj(src, dst)
        dst.write(b"\n# revised by T-A3\n")
    upload.upload_asset(NODE, ROOM, lod2b, None, "model/obj", TOKEN)
    rev = api.replace_file(graph, rows[2]["id"], None, checksum=sha(lod2b),
                           url=lod2b, media_type="model/obj")
    check("the revision is the current LOD2",
          api.versions_of(graph, "podio_master")[2]["id"] == rev["new_resource_id"])
    old_meshes = {lv: m.get("em_asset_sha256") for lv, m in av.levels_of(podio).items()}
    calls.clear()
    rep3 = scene_check.check_scene(bpy.context, graph, download=True, fetch_fn=counted)
    for line in scene_check.ULTIMA_VERIFICA.get("sentences") or []:
        print("[SMOKE]   ", line)
    check("A3: only the changed mesh is downloaded again", calls == [sha(lod2b)],
          repr(calls))
    new_meshes = {lv: m.get("em_asset_sha256") for lv, m in av.levels_of(podio).items()}
    check("its mesh carries the new digest, the others are untouched",
          new_meshes["LOD2"] == sha(lod2b)
          and new_meshes["LOD0"] == old_meshes["LOD0"]
          and new_meshes["LOD1"] == old_meshes["LOD1"], repr(new_meshes))
    check("the decoration stays «only here»",
          "Decoration" in (scene_check.ULTIMA_VERIFICA.get("only_here") or [])
          and bool(bpy.data.objects["Decoration"].get("em_only_here"))
          and not bpy.data.objects["Decoration"].get("em_asset_sha256"))
    activate(podio)
    bpy.ops.em.asset_set_level(level="LOD2")
    check("LOD2 shows the revised mesh on the same object",
          podio.get("em_asset_sha256") == sha(lod2b) and podio.name == "OB_PODIO")

    # ── B1 · the scene package ────────────────────────────────────────────────
    bpy.ops.wm.save_mainfile()
    t0 = time.time()
    esito = bpy.ops.em.scene_package_archive(label="T-B1", save_first=True)
    check(f"B1 archive: FINISHED ({time.time() - t0:.1f}s)", esito == {"FINISHED"},
          repr(esito))
    listed = package.list_packages()
    mine = [r for r in listed if r.get("filename") == "templu_scene.blend"]
    check("the room lists the package (kind package)",
          len(mine) == 1 and mine[0].get("kind") == "package", repr(listed))
    check("the package is NOT a node of the graph",
          not any(mine[0]["sha256"] in json.dumps(getattr(n, "data", {}) or {})
                  for n in graph.nodes))
    other = os.path.join(work, "other-computer")
    os.makedirs(other)
    data = package.get_package(mine[0]["sha256"])
    target = os.path.join(other, package.package_name("templu_scene.blend",
                                                      mine[0]["sha256"]))
    open(target, "wb").write(data)
    n = package.unpack_beside(bpy.app.binary_path, target)
    print(f"[SMOKE] package {len(data) / 1e6:.1f} MB, {n} librar(ies) unpacked")
    unpacked = os.path.join(other, *av.library_relpath("podio_master", ROOM).split("/"))
    check("on a computer without cache the library is unpacked beside it",
          os.path.isfile(unpacked), unpacked)
    out = subprocess.run([bpy.app.binary_path, "-b", "--factory-startup", target,
                          "--python-expr", probe.replace(
                              "o.get('em_rm_node_id'))",
                              "o.get('em_rm_node_id'), o.get('em_asset_sha256'), "
                              "bpy.path.abspath(o.data.library.filepath))")],
                         capture_output=True, text=True).stdout
    line = next((x for x in out.splitlines() if x.startswith("PROBE")), "")
    print("[SMOKE] the package opened:", line)
    check("…and it opens with OB_PODIO whole, its mesh from that library",
          line.startswith("PROBE LOD2 OB_PODIO@LOD2 True") and sha(lod2b) in line
          and other in line, line)
    room_cfg.forget_token()

if FAILURES:
    print(f"[SMOKE] {len(FAILURES)} failure(s): {FAILURES}")
    sys.exit(1)
print("[SMOKE] all checks passed")
