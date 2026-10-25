"""Headless smoke · MICRO tileset, shift e epoche (25 Oct 2026): E.D.'s case on
a COPY — the RM container «tls» with 0 meshes, its alternative the Basilica
Iulia's tileset, its epoch said by the document D.1 — and the frame of the
tileset's file. Never the originals on the Desktop::

    mkdir -p /tmp/ed-tss2 && cp ~/Desktop/Untitled.blend ~/Desktop/untitled_graph.em.json /tmp/ed-tss2/
    cp -c -R ~/Desktop/tilesets /tmp/ed-tss2/tilesets          # an APFS clone
    EM_TSS_DIR=/tmp/ed-tss2 PYTHONPATH=~/Documents/GitHub/s3Dgraphy/src \\
    "/Applications/Blender 520.app/Contents/MacOS/Blender" -b --python-use-system-env \\
        /tmp/ed-tss2/Untitled.blend \\
        --python ~/Documents/GitHub/EM-blender-tools/tests/blender_smoke_tileset_shift_epochs.py

``PYTHONPATH`` puts the s3Dgraphy working tree before the bundled wheel (the
rule of the container's own epochs and ``geometry.frame`` are newer than it).
The rows of ``em_tools.graphml_files`` are cleared before the copy's em.json
is opened, so no original is written; the .blend is never saved.

(1) the em.json opened: «tls» finds its group, its alternative and Epoch 1
(the container's own, from D.1); Automatic is the tileset; the box is seen in
Epoch 1 and not in another epoch. (2) «Use the graph's shift» on a graph
without one says so; the SHIFT file writes ``data.frame`` on the tileset's
asset and the box lands in the file's shifted grid, the residual said; the
graph's geo_position then gives the same frame with source «graph»; Edit
writes a manual frame; Remove takes it away. (3) A Cesium tileset object
carries its frame on its RM. (4) Saved as a new em.json: the frame travels.
"""
import importlib
import json
import os
import sys
import types

import bpy

FAILURES = []
DIR = os.environ.get("EM_TSS_DIR", "/tmp/ed-tss2")
EMJSON = os.path.join(DIR, "untitled_graph.em.json")
SAVED = os.path.join(DIR, "tss_smoke_saved.em.json")
SHIFT = os.path.join(DIR, "SHIFT6708.txt")
ASSET = "e8a7e275-8452-48a6-920a-f6aebc3efd18"


def check(label, condition, detail=""):
    print(f"[SMOKE] {'PASS' if condition else 'FAIL'}: {label} {detail}")
    if not condition:
        FAILURES.append(label)


assert os.path.realpath(DIR).startswith(("/tmp/", "/private/tmp/")), "a copy in /tmp only"
names = [n for n in sys.modules if n.endswith(".rm_manager.alternative_operators")
         and n.startswith("bl_ext.")]
PKG = names[0].rsplit(".rm_manager.alternative_operators", 1)[0]
print("[SMOKE] package:", PKG)
ao = importlib.import_module(PKG + ".rm_manager.alternative_operators")
tf = importlib.import_module(PKG + ".rm_manager.tileset_frame")
fo = importlib.import_module(PKG + ".rm_manager.frame_operators")
import s3dgraphy  # noqa: E402
print("[SMOKE] s3dgraphy:", s3dgraphy.__file__)
check("the s3Dgraphy with the rule and the frame", tf.has_container_rule()
      and importlib.util.find_spec("s3dgraphy.geometry.frame") is not None)

scene = bpy.context.scene
em = scene.em_tools
print("[SMOKE] rows before:", [(r.name, r.graphml_path) for r in em.graphml_files])
em.graphml_files.clear()
em.active_file_index = -1

# ── (1) the em.json of the copy ─────────────────────────────────────────────
r = getattr(bpy.ops, "import").em_emjson(filepath=EMJSON)
graph = ao._graph(bpy.context)
check("the copy's em.json is loaded", r == {"FINISHED"} and graph is not None, str(r))
row = em.graphml_files[em.active_file_index]
check("its row is in /tmp", os.path.realpath(bpy.path.abspath(row.graphml_path)).startswith(
    ("/tmp/", "/private/tmp/")), row.graphml_path)
ci = next(i for i, c in enumerate(scene.rm_containers) if c.label == "tls")
tls = scene.rm_containers[ci]
scene.rm_containers_index = ci
check("«tls» finds its group in the graph", tls.group_node_id == "rmgroup_tls", tls.group_node_id)
check("…its document", tls.doc_node_id == "111aa756-101f-406a-9d55-56a3ce707c6b", tls.doc_name)
check("…and its alternative, the Basilica's tileset", tls.alt_asset_id == ASSET, tls.alt_name)
check("0 meshes", len(tls.mesh_names) == 0)
box = bpy.data.objects.get(ao.box_name(tls))
check("the box of the tileset stands in the scene", box is not None)
if box is not None:
    print("[SMOKE] the box, no frame:", [round(x, 2) for x in box.location],
          [round(x, 2) for x in box.scale])
    check("without a frame it is where the root's transform puts it (ECEF)",
          box.location.x > 6.2e6, str(box.location))

tls.alt_mode = 'AUTO'
st = ao.view_state(tls, bpy.context)
check("Automatic is the tileset (0 meshes)", st["mode"] == 'TILESET', str(st))
check("its epoch is Epoch 1, the container's own (D.1)",
      st["epochs"] == ["Epoch 1"] and st["source"] == "own", str(st))
check("the panel's copy says it", tls.alt_epochs == "Epoch 1" and tls.alt_epochs_source == "own")

eps = em.epochs
ep1 = next(i for i, e in enumerate(eps.list) if e.name == "Epoch 1")
eps.list_index = ep1
scene.sync_rm_visibility = True
bpy.ops.em.strat_sync_visibility()
box = bpy.data.objects.get(ao.box_name(tls))
check("Epoch 1 shows the Basilica's box", box is not None and not box.hide_get()
      and not box.hide_viewport)
other = eps.list.add()
other.name = "Epoch X (smoke)"
eps.list_index = len(eps.list) - 1
bpy.ops.em.strat_sync_visibility()
check("another epoch does not", box is not None and box.hide_get())
eps.list.remove(len(eps.list) - 1)
eps.list_index = ep1
bpy.ops.em.strat_sync_visibility()
check("back in Epoch 1, seen again", box is not None and not box.hide_get())

# ── (2) the frame ───────────────────────────────────────────────────────────
r = bpy.ops.rm.tileset_frame_from_graph('EXEC_DEFAULT', container_index=ci)
check("«Use the graph's shift» on a graph without one: cancelled, said", r == {'CANCELLED'}, str(r))
with open(SHIFT, "w") as fh:
    fh.write("EPSG::6708 291407 4640813 0\n")
r = bpy.ops.rm.tileset_frame_from_file('EXEC_DEFAULT', container_index=ci, filepath=SHIFT)
node = graph.find_node_by_id(ASSET)
fr = (node.data or {}).get("frame")
check("the SHIFT file writes data.frame on the tileset's asset", r == {'FINISHED'} and fr ==
      {"crs": "EPSG:6708", "shift": [291407.0, 4640813.0, 0.0], "note": "SHIFT6708.txt",
       "source": "file"}, f"{r} {fr}")
check("the panel's copy", tf.loads(tls.alt_frame) == fr)
box = bpy.data.objects.get(ao.box_name(tls))
print("[SMOKE] the box, relocated:", [round(x, 2) for x in box.location],
      [round(x, 2) for x in box.scale], "·", tls.alt_place_note)
check("the box lands in the file's shifted grid (the scene's frame)",
      all(abs(v) < 300 for v in box.location) and 80 < box.scale.x < 120, str(box.location))
check("the residual is said", tls.alt_place_note.startswith("Relocated by the frame")
      and "mm" in tls.alt_place_note, tls.alt_place_note)
check("still seen in Epoch 1", not box.hide_get())

geo = next(n for n in graph.nodes if getattr(n, "node_type", "") == "geo_position")
saved_geo = dict(geo.data)
geo.data.update({"epsg": 6708, "shift_x": 291407.0, "shift_y": 4640813.0, "shift_z": 0.0})
r = bpy.ops.rm.tileset_frame_from_graph('EXEC_DEFAULT', container_index=ci)
fr = graph.find_node_by_id(ASSET).data.get("frame")
check("with the graph's geo_position: the same frame, source «graph»", r == {'FINISHED'}
      and fr["shift"] == [291407.0, 4640813.0, 0.0] and fr["source"] == "graph", str(fr))
print("[SMOKE] the box in the study's frame:", [round(x, 2) for x in box.location], "·",
      tls.alt_place_note)
check("the study's frame is the file's: the same place", all(abs(v) < 300 for v in box.location))
geo.data.clear()
geo.data.update(saved_geo)

r = bpy.ops.rm.tileset_frame_edit('EXEC_DEFAULT', container_index=ci, crs="6708",
                                  shift_x="291407", shift_y="4640813,0", shift_z="0",
                                  note="by hand")
fr = graph.find_node_by_id(ASSET).data.get("frame")
check("Edit writes a manual frame (the comma read as a decimal point)", r == {'FINISHED'}
      and fr == {"crs": "EPSG:6708", "shift": [291407.0, 4640813.0, 0.0], "note": "by hand",
                 "source": "manual"}, str(fr))
try:
    r = bpy.ops.rm.tileset_frame_edit('EXEC_DEFAULT', container_index=ci, crs="", shift_x="abc")
except RuntimeError as exc:         # an ERROR report raises in a script
    r = {'CANCELLED'} if "not a number" in str(exc) else {str(exc)}
check("a shift that is not a number is refused", r == {'CANCELLED'}
      and graph.find_node_by_id(ASSET).data["frame"]["note"] == "by hand")


class StubLayout:
    def __init__(self, calls):
        self.calls = calls
        self.alert = False
        self.enabled = True
        self.scale_y = 1.0

    def _child(self, *a, **k):
        return StubLayout(self.calls)

    box = row = column = split = _child

    def prop(self, data, name, **k):
        self.calls.append(("prop", name))

    def label(self, **k):
        self.calls.append(("label", k.get("text", "")))

    def operator(self, idname, **k):
        self.calls.append(("operator", idname))
        return types.SimpleNamespace()

    def menu(self, *a, **k):
        pass

    def separator(self, *a, **k):
        pass


ui = importlib.import_module(PKG + ".rm_manager.ui")
calls = []
ui._draw_alternative_row(StubLayout(calls), scene, tls)
labels = [c[1] for c in calls if c[0] == "label"]
opids = [c[1] for c in calls if c[0] == "operator"]
print("[SMOKE] the alternative's row:", labels)
check("the row: Automatic is the tileset, its epoch, the frame, the residual",
      any("Automatic is the tileset" in t for t in labels)
      and any(t.startswith("Seen in: Epoch 1") for t in labels)
      and any(t.startswith("Frame: EPSG:6708") for t in labels)
      and any(t.startswith("Relocated by the frame") for t in labels))
check("…and its buttons", {"rm.tileset_frame_edit", "rm.tileset_frame_from_graph",
                           "rm.tileset_frame_from_file", "rm.tileset_frame_clear"} <= set(opids))

# ── (3) a Cesium tileset object ─────────────────────────────────────────────
from s3dgraphy.nodes.representation_node import RepresentationModelNode  # noqa: E402
graph.add_node(RepresentationModelNode("SmokeTileset_model", name="Model for SmokeTileset"))
obj = bpy.data.objects.new("SmokeTileset", None)
obj["tileset_path"] = "//tilesets/tileset_Basilica_TLS_UAV_ED.3tz"
obj["em_rm_node_id"] = "SmokeTileset_model"
scene.collection.objects.link(obj)
r = bpy.ops.rm.tileset_frame_edit('EXEC_DEFAULT', object_name=obj.name, crs="EPSG:6708",
                                  shift_x="291407", shift_y="4640813", shift_z="0", note="")
fr = (graph.find_node_by_id("SmokeTileset_model").data or {}).get("frame")
check("a Cesium tileset object: the frame on its RM, the copy on the object",
      r == {'FINISHED'} and fr and fr["crs"] == "EPSG:6708"
      and obj.get("em_frame_node") == "SmokeTileset_model", f"{r} {fr}")
graph.remove_node("SmokeTileset_model") if hasattr(graph, "remove_node") else None
bpy.data.objects.remove(obj, do_unlink=True)

# ── (4) saved: the frame travels ────────────────────────────────────────────
r = bpy.ops.export.em_saveas(filepath=SAVED)
with open(SAVED, encoding="utf-8") as fh:
    doc = json.load(fh)
res = [n for gd in doc["graphs"].values() if isinstance(gd, dict)
       for n in gd.get("nodes", []) if n.get("id") == ASSET]
check("the saved em.json carries data.frame on the asset", r == {'FINISHED'} and res
      and res[0].get("data", {}).get("frame", {}).get("note") == "by hand", str(r))

r = bpy.ops.rm.tileset_frame_clear('EXEC_DEFAULT', container_index=ci)
check("Remove takes it away", r == {'FINISHED'} and "frame" not in graph.find_node_by_id(ASSET).data
      and tls.alt_frame == "")

print("[SMOKE]", "ALL PASS" if not FAILURES else f"FAILURES: {FAILURES}")
