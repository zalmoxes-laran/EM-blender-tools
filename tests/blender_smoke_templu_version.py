"""Headless smoke · Q1/Q2/Q3 on the COPY of Templu Mare: «Add version…» on
ME_PODIO, whose master `ME_PODIO_LOD0` is linked from `RB/TempluMare_2021.blend`
and whose model (`em_rm_node_id`) the GraphML does not carry.

    PYTHONPATH=~/Documents/GitHub/s3Dgraphy/src \\
    "/Applications/Blender 520.app/Contents/MacOS/Blender" -b --python-use-system-env \\
        <copy>.blend --python tests/blender_smoke_templu_version.py

Checks: the object keeps its identity (same `em_rm_node_id`, its model under
D.01 in the graph, no model more than before — whatever the copy's state:
an earlier run may have saved it with `ME_PODIO_model`), stays selected and active, and «LOD ▸»
/ «◂ LOD» walk master ⇄ version both ways. The .blend is NOT saved.
"""
import importlib
import sys

import bpy

FAILURES = []


def check(label, condition, detail=""):
    print(f"[SMOKE] {'PASS' if condition else 'FAIL'}: {label} {detail}")
    if not condition:
        FAILURES.append(label)


names = [n for n in sys.modules if n.endswith(".graph_origins") and n.startswith("bl_ext.")]
PKG = names[0].rsplit(".graph_origins", 1)[0]
av = importlib.import_module(PKG + ".sync_manager.asset_versions")
# the copy may have been saved with another slot active (14:32 on 4 Oct: slot 2)
# G1 · loading the GraphML writes an em.json BESIDE it: the GraphML of the
# copy's slot 0 is in E.D.'s examples, so it is copied to a temporary folder
# first and the slot points at the copy (the .blend is not saved)
import os as _os, shutil as _shutil, tempfile as _tempfile  # noqa: E401,E402
_row0 = bpy.context.scene.em_tools.graphml_files[0]
_src0 = bpy.path.abspath(_row0.graphml_path)
if _src0.lower().endswith(".graphml"):
    _dst0 = _os.path.join(_tempfile.mkdtemp(prefix="em-smoke-"), _os.path.basename(_src0))
    _shutil.copy2(_src0, _dst0)
    _row0.graphml_path = _dst0
bpy.context.scene.em_tools.active_file_index = 0
getattr(bpy.ops, "import").em_graphml(graphml_index=0)
from s3dgraphy import get_graph  # noqa: E402
graph = get_graph(bpy.context.scene.em_tools.graphml_files[0].name)
# Q8 · the auxiliary files of a .blend that moved are found in the EM tree
import os  # noqa: E402
for aux in bpy.context.scene.em_tools.graphml_files[0].auxiliary_files:
    raw = aux.dosco_folder if aux.file_type == "dosco" else aux.filepath
    check(f"the auxiliary '{aux.name}' is found where it is",
          bool(raw) and os.path.exists(bpy.path.abspath(raw)), bpy.path.abspath(raw))

obj = bpy.data.objects["ME_PODIO"]
rm_before = obj["em_rm_node_id"]
doc = obj.get("em_rm_container_doc_id")
master_mesh = obj.data.name
print("[SMOKE] before:", obj.name, master_mesh, rm_before, doc,
      obj.data.library and obj.data.library.filepath)
for o in bpy.context.view_layer.objects:
    o.select_set(False)
obj.select_set(True)
bpy.context.view_layer.objects.active = obj
# E5 · «no new model» measured against THIS file, not against a name: the copy
# saved after an earlier run already carries ME_PODIO_model as its model id
rm_ids_before = {n.node_id for n in graph.nodes
                 if getattr(n, "node_type", "") == "representation_model"
                 or type(n).__name__ == "RepresentationModelNode"}

result = bpy.ops.em.asset_add_version(source="DECIMATE", ratio=0.25, use={"web"})
check("«Add version…» finished", result == {"FINISHED"}, str(result))

# Q2 · identity
check("the object keeps its model id", obj.get("em_rm_node_id") == rm_before,
      f"{obj.get('em_rm_node_id')} vs {rm_before}")
node = graph.find_node_by_id(rm_before)
check("its model is in the graph with its own id", node is not None)
check("…under its document D.01",
      any(e.edge_type == "has_representation_model" and e.edge_source == doc
          and e.edge_target == rm_before for e in graph.edges))
rm_ids_after = {n.node_id for n in graph.nodes
                if getattr(n, "node_type", "") == "representation_model"
                or type(n).__name__ == "RepresentationModelNode"}
check("no new model", rm_ids_after == rm_ids_before,
      f"new: {sorted(rm_ids_after - rm_ids_before)}; the object's: {rm_before}")
asset = obj.get("em_asset_id")
linked = [e.edge_target for e in graph.edges
          if e.edge_type == "has_linked_resource" and e.edge_source == rm_before]
check("the chain hangs off that model", asset in linked or bool(linked),
      f"asset {asset}, linked {linked}")

# Q3 · still selected
check("the master is still selected and active",
      obj.select_get() and bpy.context.view_layer.objects.active == obj)

# Q1 · both ways
levels = av.levels_of(obj)
print("[SMOKE] levels:", {k: (m.name, m.library and m.library.filepath) for k, m in levels.items()})
check("two levels: the master by reference and the version", len(levels) >= 2, str(list(levels)))
shown = obj.get("em_level")
r1 = bpy.ops.em.asset_lod_step(direction=1)
after_fwd = obj.data.name
check("LOD ▸ moves to the version", r1 == {"FINISHED"} and after_fwd != master_mesh,
      f"{shown} → {obj.get('em_level')} ({after_fwd})")
r2 = bpy.ops.em.asset_lod_step(direction=-1)
check("◂ LOD comes back to the master", obj.data.name == master_mesh,
      f"→ {obj.get('em_level')} ({obj.data.name})")
r3 = bpy.ops.em.asset_lod_step(direction=1)
check("…and forward again", obj.data.name == after_fwd, obj.data.name)

# Q4 · a reload does not drop the version in silence. G1 · the slot is the
# em.json the GraphML became: the reload is import.em_emjson, whose dialog
# names the unsaved versions; the GraphML importer refuses an em.json slot
check("the reload's warning names the unsaved version",
      bool(av.reload_warning(graph.graph_id)), av.reload_warning(graph.graph_id)[:90])
try:
    r = getattr(bpy.ops, "import").em_graphml()
except RuntimeError as exc:          # a CANCELLED with an ERROR, headless
    r = {"CANCELLED"}
    print("[SMOKE] the sentence:", str(exc)[:160])
check("the GraphML importer refuses the em.json slot", r == {"CANCELLED"}, str(r))
r = getattr(bpy.ops, "import").em_emjson(file_index=0)
check("…and the em.json reloads", r == {"FINISHED"}, str(r))
print(f"[SMOKE] {'ALL PASS' if not FAILURES else 'FAILURES: ' + ', '.join(FAILURES)}")
sys.exit(1 if FAILURES else 0)
