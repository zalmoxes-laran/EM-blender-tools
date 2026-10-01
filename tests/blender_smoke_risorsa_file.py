"""Headless smoke: la risorsa e i suoi file, in un Blender vero (MICRO risorsa-file).

NOT a pytest test (needs bpy) — run it inside Blender with the EM-tools
extension enabled:

    /Applications/Blender\\ 520.app/Contents/MacOS/Blender --background \\
        --python tests/blender_smoke_risorsa_file.py

* un RM nuovo ha il master `datablock` (`ensure_rm_and_internal_resource`);
* un export glTF separato VERO (l'exporter di Blender, una texture) passa per il
  bake dell'export Heriverse e dà una risorsa `file_set` coi file che il `.gltf`
  nomina, `dtc_derived_from` verso il master.

Exits non-zero on failure. Everything is written in a temporary folder.
"""
import importlib
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


pkg = addon_module()
if not check("addon loaded", pkg is not None and hasattr(bpy.context.scene, "em_tools")):
    sys.exit(1)
containers = importlib.import_module(pkg + ".rm_manager.containers")
heriverse = importlib.import_module(pkg + ".export_operators.heriverse.operator")
gltf_mod = importlib.import_module(pkg + ".export_operators.heriverse.gltf")

from s3dgraphy import api  # noqa: E402
from s3dgraphy.graph import Graph  # noqa: E402

TMP = tempfile.mkdtemp(prefix="em_risorsa_file_")
scene = bpy.context.scene

# ── un oggetto con una texture, in un .blend salvato ─────────────────────────
# (non `read_factory_settings`: spegnerebbe l'estensione, e Blender
# toglierebbe le sue ruote da `.local` a metà prova)
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o, do_unlink=True)
bpy.ops.mesh.primitive_cube_add(size=1.0)
obj = bpy.context.active_object
obj.name = "TILE"
img = bpy.data.images.new("TILE_tex", 8, 8)
img.filepath_raw = os.path.join(TMP, "TILE_tex.png")
img.file_format = "PNG"
img.save()
mat = bpy.data.materials.new("TILE_mat")
mat.use_nodes = True
tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
tex.image = img
mat.node_tree.links.new(tex.outputs["Color"],
                        mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"])
obj.data.materials.append(mat)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(TMP, "scene.blend"))
scene = bpy.context.scene
obj = bpy.data.objects["TILE"]

graph = Graph("smoke")

# ── 1 · un RM nuovo ha il master datablock ───────────────────────────────────
rm_id, res_id, avvisi = containers.ensure_rm_and_internal_resource(scene, graph, obj)
master = graph.find_node_by_id(res_id) if res_id else None
check("internal resource made", master is not None, f"{rm_id} → {res_id} {avvisi}")
if master is not None:
    check("master tier declared", master.data.get("tier") == "master", master.data.get("tier"))
    check("datablock packaging declared", master.data.get("packaging") == "datablock",
          master.data.get("packaging"))
    check("blend:// locator", str(master.data.get("url", "")).startswith("blend://"),
          master.data.get("url"))

# ── 1 · un export glTF separato è un file_set derivato dal master ────────────
models = os.path.join(TMP, "export", "models")
os.makedirs(models)
bpy.ops.object.select_all(action="DESELECT")
obj.select_set(True)
bpy.context.view_layer.objects.active = obj
export_vars = bpy.context.window_manager.export_vars
stem = os.path.join(models, "TILE")
gltf_mod.export_gltf_with_animation_support(filepath=stem, export_vars=export_vars,
                                            scene=scene, use_selection=True)
written = sorted(os.listdir(models))
check("blender wrote gltf + bin + texture", any(f.endswith(".bin") for f in written)
      and any(f.endswith(".png") for f in written), str(written))

Op = heriverse.EXPORT_OT_heriverse if hasattr(heriverse, "EXPORT_OT_heriverse") else None
if Op is None:
    Op = next(v for v in vars(heriverse).values()
              if isinstance(v, type) and hasattr(v, "_registra_bake"))
fake = types.SimpleNamespace(_misure_insieme=Op._misure_insieme)
ok = Op._registra_bake(fake, graph, rm_id, obj, url="models/TILE.gltf",
                       file_esportato=stem + ".gltf", etichetta="GLTF for TILE")
link_id = f"{rm_id}_link"
dist = graph.find_node_by_id(link_id)
check("bake registered", ok and dist is not None)
if dist is not None:
    files = api.resource_files(graph, link_id)
    check("distribution is a file_set", dist.data.get("packaging") == "file_set",
          dist.data.get("packaging"))
    check("files are the ones the gltf names",
          sorted(f["path"] for f in files) == sorted(written), str([f["path"] for f in files]))
    check("entry point is the .gltf", files and files[0]["role"] == "entry_point"
          and files[0]["path"] == "TILE.gltf")
    check("derived from the master", any(
        e.edge_type == "dtc_derived_from" and e.edge_source == link_id
        and e.edge_target == res_id for e in graph.edges))
    check("the door stays where Heriverse looks", dist.data.get("url") == "models/TILE.gltf")

print(f"[SMOKE] {'OK' if not FAILURES else 'FAILED: ' + ', '.join(FAILURES)}")
sys.exit(1 if FAILURES else 0)
