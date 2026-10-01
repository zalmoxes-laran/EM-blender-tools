"""Headless smoke: the stamp born in Blender (VLONG-DEV27, part D).

NOT a pytest test (needs bpy) — run it inside Blender with EM Tools AND 3D
Survey Collection installed from their built packages, in a CLEAN user folder:

    export BLENDER_USER_RESOURCES=$(mktemp -d)
    B=/Applications/Blender\\ 520.app/Contents/MacOS/Blender
    $B --background --command extension install-file -r user_default -e <em_tools-….blext>
    $B --background --command extension install-file -r user_default -e <dsc_tools-….blext>
    $B --background --python tests/blender_smoke_birth_stamp.py

Everything is written in a temporary folder, from a .blend the smoke makes.

* 3DSC ``glb.exportbatch`` → ``<obj>.glb.stamp.json``: ``file``, the master
  by identity (its ``blend://`` in the private hints), the ``.blend`` digest and
  «saved», Blender / 3DSC / EM Tools / dtcstamp in ``how.software``;
* 3DSC ``obj.exportbatch`` → a ``file_set`` (obj, mtl, texture) whose digest is
  ``dtcstamp.members_digest``;
* a second glb with other bytes, the ``.blend`` NOT saved → a revision
  (``was_revision_of``), the previous stamp kept, «not saved» said;
* 3DSC Cesium export, Folder + .3tz → ``directory`` and ``archive`` with the
  same ``content_digest``, the folder's; ``cesium_pack_3tz`` names the folder;
* the preference off → no stamp;
* the Heriverse bake (``_registra_bake`` → ``_timbra_in_attesa``) stamps with
  the graph's ids; a 3DSC export of an RM enters the graph
  (``register_distribution``) and the stamp takes the node's id;
* the small seal's lookup (``stamp_path_of_resource``) finds the stamp.

Exits non-zero on failure.
"""
import importlib
import json
import os
import sys
import tempfile
import types

import bpy

FAILURES = []


def check(label, condition, detail=""):
    print(f"[SMOKE] {'PASS' if condition else 'FAIL'}: {label} {detail}")
    if not condition:
        FAILURES.append(label)
    return condition


def addon_module():
    for name in list(sys.modules):
        if name.endswith(".graph_updaters") and name.startswith("bl_ext."):
            return name.rsplit(".", 1)[0]
    return None


def read(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


pkg = addon_module()
if not check("EM Tools loaded", pkg is not None and hasattr(bpy.context.scene, "em_tools"),
             f"({pkg}, Blender {bpy.app.version_string})"):
    sys.exit(1)
dsc_key = next((k for k in bpy.context.preferences.addons.keys()
                if k.endswith("dsc_tools")), None)
check("3D Survey Collection loaded", dsc_key is not None, str(dsc_key))

bs = importlib.import_module(pkg + ".birth_stamp")
containers = importlib.import_module(pkg + ".rm_manager.containers")
heriverse = importlib.import_module(pkg + ".export_operators.heriverse.operator")
gltf_mod = importlib.import_module(pkg + ".export_operators.heriverse.gltf")
res_ops = importlib.import_module(pkg + ".resources_tab.operators")
import dtcstamp  # noqa: E402
from s3dgraphy import api  # noqa: E402
from s3dgraphy.graph import Graph  # noqa: E402

TMP = tempfile.mkdtemp(prefix="em_birth_stamp_")
OUT = os.path.join(TMP, "out")
os.makedirs(os.path.join(OUT, "tex"))
scene = bpy.context.scene

# ── a .blend made here: a cube with a texture beside the exports ────────────
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o, do_unlink=True)
bpy.ops.mesh.primitive_cube_add(size=1.0)
obj = bpy.context.active_object
obj.name = "TILE"
img = bpy.data.images.new("TILE_tex", 8, 8)
img.filepath_raw = os.path.join(OUT, "tex", "TILE_tex.png")
img.file_format = "PNG"
img.save()
mat = bpy.data.materials.new("TILE_mat")
mat.use_nodes = True
tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
tex.image = img
mat.node_tree.links.new(tex.outputs["Color"],
                        mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"])
obj.data.materials.append(mat)
if dsc_key:
    #: set BEFORE saving: in 5.0.1 a property set from Python marks the file
    #: modified (in 5.2 it does not — measured), and «saved» must be true
    scene.model_export_dir = OUT
    scene.author_sign_model = "CC-BY smoke"
BLEND = os.path.join(TMP, "scavo.blend")
bpy.ops.wm.save_as_mainfile(filepath=BLEND)
scene = bpy.context.scene
obj = bpy.data.objects["TILE"]


def select_only(o):
    bpy.ops.object.select_all(action="DESELECT")
    o.select_set(True)
    bpy.context.view_layer.objects.active = o


if dsc_key:
    # ── 1 · glb: a file, its master by identity ─────────────────────────────
    select_only(obj)
    r = bpy.ops.glb.exportbatch()
    glb = os.path.join(OUT, "TILE.glb")
    sp = glb + ".stamp.json"
    check("glb exported and stamped", r == {"FINISHED"} and os.path.isfile(sp), str(r))
    if os.path.isfile(sp):
        st = read(sp)
        me = st["self"]
        check("glb: packaging file, tier distribution",
              me["packaging"] == "file" and me["tier"] == "distribution", me["packaging"])
        check("glb: digest of the bytes", me["digest"] == dtcstamp.file_digest(glb))
        parent = st["from"][0] if st["from"] else {}
        check("glb: from the master TILE", parent.get("label") == "TILE"
              and parent.get("tier") == "master", json.dumps(parent)[:160])
        #: MEASURED: Blender 5.0.1 --background (also --factory-startup, no
        #: add-on) reports `is_dirty` True right after `save_as_mainfile`; 5.2
        #: does not. There the stamp says «not saved» — the safe direction —
        #: and the smoke can only check the digest.
        dirty_after_save = bpy.data.is_dirty
        check("glb: .blend digest and saved",
              parent.get("state", {}).get("sha256") == dtcstamp.file_digest(BLEND)
              and parent["state"].get("saved") is (not dirty_after_save),
              json.dumps(parent.get("state")) + (" (this Blender: dirty after save)"
                                                 if dirty_after_save else ""))
        check("glb: no path in from", "blend://" not in json.dumps(st["from"])
              and TMP not in json.dumps(st["from"]))
        # dtcstamp 0.1.3: ONE <asset>.hints.json, the master under `from`
        hints = read(glb + ".hints.json")
        master_seen = (hints.get("from") or {}).get(parent.get("resource_id"), [])
        check("glb: blend:// in the private hints, under from",
              bool(master_seen) and master_seen[0]["locator"].startswith("blend://")
              and master_seen[0]["scope"] == "private"
              and not os.path.exists(glb + ".from.hints.json"),
              master_seen[0]["locator"] if master_seen else json.dumps(hints)[:160])
        names = [s["name"] for s in st["how"]["software"]]
        check("glb: software Blender, 3DSC, EM Tools, dtcstamp",
              names == ["Blender", "3D Survey Collection", "EM Tools", "dtcstamp"], str(names))
        emt = st["how"]["software"][2]
        check("glb: EM Tools has a version and a commit", bool(emt.get("version"))
              and bool(emt.get("commit")), json.dumps(emt))
        check("glb: dtc_kind and operator", st["how"]["dtc_kind"] == bs.resolve_kind(bs.KIND_EXPORT)
              and st["how"]["parameters"]["operator"] == "glb.exportbatch",
              f"({st['how']['dtc_kind']}; the bundled vocabulary has export: "
              f"{'export' in bs.process_kinds()})")
        check("glb: dtcstamp validates it", dtcstamp.validate_stamp(st) is st)
        FIRST = st

    # ── 2 · obj + mtl + texture: a file_set ─────────────────────────────────
    select_only(obj)
    r = bpy.ops.obj.exportbatch()
    door = os.path.join(OUT, "TILE.obj")
    sp = door + ".stamp.json"
    check("obj exported and stamped", r == {"FINISHED"} and os.path.isfile(sp), str(r))
    if os.path.isfile(sp):
        me = read(sp)["self"]
        paths = [m["path"] for m in me.get("members") or []]
        check("obj: a file_set of obj, mtl, texture", me["packaging"] == "file_set"
              and paths == ["TILE.mtl", "TILE.obj", "tex/TILE_tex.png"], str(paths))
        check("obj: digest == dtcstamp.members_digest",
              me["digest"] == dtcstamp.members_digest(me["members"]))
        check("obj: verify_members ok", dtcstamp.verify_members(read(sp), door)["ok"])

    # ── 3 · new bytes, .blend not saved: a revision ─────────────────────────
    obj.data.vertices[0].co.x += 0.25
    obj.data.update()
    #: measured in 5.2 --background: an edit through the data API (or even an
    #: operator) does not mark the file modified until an undo step is pushed,
    #: which the UI does after every edit — so the smoke pushes one
    bpy.ops.ed.undo_push(message="edit TILE")
    select_only(obj)
    bpy.ops.glb.exportbatch()
    st2 = read(glb + ".stamp.json")
    old = FIRST["self"]
    check("revision: was_revision_of the first",
          st2["self"].get("was_revision_of") == {"resource_id": old["resource_id"],
                                                 "digest": old["digest"]},
          json.dumps(st2["self"].get("was_revision_of")))
    prev = os.path.join(OUT, f"TILE.glb.prev-{old['digest'][7:19]}.stamp.json")
    check("revision: the previous stamp kept", os.path.isfile(prev)
          and read(prev)["self"]["digest"] == old["digest"])
    state = st2["from"][0].get("state", {})
    check("revision: the .blend not saved, said", state.get("saved") is False
          and "unsaved" in state.get("note", ""), json.dumps(state))
    check("revision: the same master", st2["from"][0]["resource_id"]
          == FIRST["from"][0]["resource_id"])
    bpy.ops.wm.save_mainfile()

    # ── 4 · Cesium, Folder + .3tz: two forms of one content ─────────────────
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=3, radius=2.0)
    sphere = bpy.context.active_object
    sphere.name = "TZ_probe"
    select_only(sphere)
    scene.cesium_source_mode = 'ACTIVE_MESH'
    scene.cesium_export_selected_meshes = False
    scene.cesium_create_object_subdir = True
    scene.cesium_coordinates_mode = 'LOCAL_COORDS'
    scene.cesium_native_hierarchy_layout = 'SINGLE_JSON'
    scene.cesium_native_bake_texture_atlas = False
    scene.cesium_lod_mode = False
    scene.cesium_native_min_depth = 1
    scene.cesium_native_max_depth = 2
    scene.cesium_features_per_tile = 500
    scene.cesium_auto_stitch_parent = False
    scene.cesium_output_dir = os.path.join(TMP, "tiles")
    scene.cesium_archive_mode = 'FOLDER_3TZ'
    try:
        r = bpy.ops.object.export_cesium_tiles()
    except Exception as exc:                        # noqa: BLE001
        r = str(exc)
    folder = os.path.join(TMP, "tiles", "TZ_probe")
    check("cesium export finished", r == {"FINISHED"}, str(r))
    fs, ts = folder + ".stamp.json", folder + ".3tz.stamp.json"
    if check("cesium: folder and .3tz stamped", os.path.isfile(fs) and os.path.isfile(ts)):
        f, t = read(fs), read(ts)
        check("cesium: directory + archive", f["self"]["packaging"] == "directory"
              and t["self"]["packaging"] == "archive")
        content = dtcstamp.content_digest(folder)
        check("cesium: archive content_digest == the folder's",
              t["self"]["content_digest"]["digest"] == content
              == f["self"]["content_digest"]["digest"], content[:23])
        check("cesium: same_content", dtcstamp.same_content(f, t))
        check("cesium: archive digest is the file's",
              t["self"]["digest"] == dtcstamp.file_digest(folder + ".3tz"))
        check("cesium: from the sphere, dtc_kind tiling (or its dev27 equivalent)",
              f["from"][0]["label"] == "TZ_probe"
              and f["how"]["dtc_kind"] == bs.resolve_kind(bs.KIND_TILING), f["how"]["dtc_kind"])
        CONTENT = content

    # ── 5 · pack an existing folder: the .3tz names the folder ──────────────
    scene.cesium_output_dir = os.path.join(TMP, "tiles_folder")
    scene.cesium_archive_mode = 'FOLDER'
    select_only(sphere)
    bpy.ops.object.export_cesium_tiles()
    src = os.path.join(TMP, "tiles_folder", "TZ_probe")
    r = bpy.ops.object.cesium_pack_3tz(directory=src + os.sep, verify=True)
    tsp = src + ".3tz.stamp.json"
    if check("pack_3tz stamped", r == {"FINISHED"} and os.path.isfile(tsp), str(r)):
        t = read(tsp)
        folder_stamp = read(src + ".stamp.json")
        check("pack_3tz: from the folder, by its id and content",
              t["from"][0]["resource_id"] == folder_stamp["self"]["resource_id"]
              and t["from"][0]["digest"] == folder_stamp["self"]["digest"],
              json.dumps(t["from"][0])[:160])

    # ── 6 · the preference off: no stamp ────────────────────────────────────
    prefs = bpy.context.preferences.addons[pkg].preferences
    prefs.stamp_exports = False
    obj.name = "TILE_OFF"
    select_only(obj)
    bpy.ops.glb.exportbatch()
    check("preference off: no stamp", os.path.isfile(os.path.join(OUT, "TILE_OFF.glb"))
          and not os.path.isfile(os.path.join(OUT, "TILE_OFF.glb.stamp.json")))
    prefs.stamp_exports = True
    obj.name = "TILE"

    # ── 6b · VLONG-DEV28/E2 · the local identity signs: declared, not verified
    prefs.local_orcid = "https://orcid.org/0000-0002-1825-0097"
    prefs.local_name = "Emanuel Demetrescu"
    obj.name = "TILE_ME"
    select_only(obj)
    bpy.ops.glb.exportbatch()
    me_sp = os.path.join(OUT, "TILE_ME.glb.stamp.json")
    op = read(me_sp)["by"].get("operator") if os.path.isfile(me_sp) else None
    check("identity: by.operator is the local identity, declared", op == {
        "id": "https://orcid.org/0000-0002-1825-0097", "label": "Emanuel Demetrescu",
        "auth": {"mode": "declared"}}, json.dumps(op))
    prefs.local_orcid = "0000-0002-1825-0079"          # two digits swapped
    obj.name = "TILE_BAD"
    select_only(obj)
    bpy.ops.glb.exportbatch()
    bad_sp = os.path.join(OUT, "TILE_BAD.glb.stamp.json")
    check("identity: a wrong check digit signs nothing", os.path.isfile(bad_sp)
          and "operator" not in read(bad_sp)["by"])
    prefs.local_orcid = ""
    prefs.local_name = ""
    obj.name = "TILE"

# ── 7 · the Heriverse bake stamps with the graph's ids ──────────────────────
graph = Graph("smoke")
rm_id, master_id, _w = containers.ensure_rm_and_internal_resource(scene, graph, obj)
models = os.path.join(TMP, "heriverse", "models")
os.makedirs(models)
select_only(obj)
stem = os.path.join(models, "TILE")
gltf_mod.export_gltf_with_animation_support(filepath=stem, export_vars=bpy.context.window_manager.export_vars,
                                            scene=scene, use_selection=True)
Op = heriverse.EXPORT_OT_heriverse
fake = types.SimpleNamespace(_misure_insieme=Op._misure_insieme, bl_idname=Op.bl_idname,
                             _timbri_in_attesa=[], _timbri=[],
                             report=lambda level, text: print(f"[report] {level} {text}"))
fake._accoda_timbro = types.MethodType(Op._accoda_timbro, fake)
fake._timbra_in_attesa = types.MethodType(Op._timbra_in_attesa, fake)
ok = Op._registra_bake(fake, graph, rm_id, obj, url="models/TILE.gltf",
                       file_esportato=stem + ".gltf", etichetta="GLTF for TILE")
check("heriverse: bake registered and stamp queued", ok and len(fake._timbri_in_attesa) == 1)
fake._timbra_in_attesa(bpy.context)
sp = stem + ".gltf.stamp.json"
if check("heriverse: stamped after the queue", os.path.isfile(sp)):
    st = read(sp)
    check("heriverse: the stamp has the graph's id", st["self"]["resource_id"]
          == api.current_revision(graph, f"{rm_id}_link"), st["self"]["resource_id"])
    check("heriverse: from the internal master", st["from"][0]["resource_id"] == master_id,
          st["from"][0]["resource_id"])
    check("heriverse: a file_set like the node", st["self"]["packaging"] == "file_set"
          and graph.find_node_by_id(f"{rm_id}_link").data.get("packaging") == "file_set")
    check("heriverse: the stamp's digest is the node's", st["self"]["digest"]
          == graph.find_node_by_id(f"{rm_id}_link").data.get("checksum"))

# ── 8 · a 3DSC export of an RM enters the graph ─────────────────────────────
glb = os.path.join(OUT, "TILE.glb")
if os.path.isfile(glb):
    os.remove(glb + ".stamp.json")
    result = bs.stamp_export(glb, masters=[bs.master_of(obj, graph=graph, scene=scene)],
                             how={"dtc_kind": bs.KIND_EXPORT})
    line = bs.register_distribution(graph, obj, glb, result, rm_id=rm_id)
    node = graph.find_node_by_id(f"{rm_id}_export_glb")
    check("graph: the distribution entered", node is not None
          and node.data.get("tier") == "distribution", line)
    derived = [e for e in graph.edges if e.edge_source == f"{rm_id}_export_glb"
               and e.edge_type == "dtc_derived_from"]
    check("graph: dtc_derived_from the master", [e.edge_target for e in derived] == [master_id],
          str([e.edge_target for e in derived]))
    check("graph: the stamp takes the node's id",
          read(glb + ".stamp.json")["self"]["resource_id"] == f"{rm_id}_export_glb")

    # ── 9 · the small seal finds it ─────────────────────────────────────────
    found = res_ops.stamp_path_of_resource(bpy.context, graph, f"{rm_id}_export_glb",
                                           glb, basi=[OUT])
    check("seal: stamp_path_of_resource", found == glb + ".stamp.json", found)

print(f"[SMOKE] example stamp: {os.path.join(OUT, 'TILE.obj.stamp.json')}")
print(f"[SMOKE] TMP {TMP}")
print(f"[SMOKE] {'ALL PASS' if not FAILURES else 'FAILURES: ' + ', '.join(FAILURES)}")
sys.exit(1 if FAILURES else 0)
