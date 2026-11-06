"""Headless smoke · MICRO-TIMBRA-MASTER (6 Nov 2026), Blender 5.2, EM Tools as
the working copy, s3Dgraphy from its sources::

    TM_OUT=/tmp/timbra-master/smoke-N PYTHONPATH=~/Documents/GitHub/s3Dgraphy/src \\
    "/Applications/Blender 520.app/Contents/MacOS/Blender" -b --python-use-system-env \\
        --python tests/blender_smoke_timbra_master.py --python-exit-code 1

On the default cube: the master exported and stamped (``tier: master``, its
kind), the cube changed, «Export as a new version of the master» → a new file
beside the old one, stamped as its revision and derived from it, the graph's
new master ``was_revision_of`` the old and hatted by the RM; the old master file
and its stamp untouched. Then «Stamp the master» on a master file that arrived
without a stamp. Nothing outside ``TM_OUT`` is written."""
import json
import os
import sys

import bpy

OUT = os.environ.get("TM_OUT", "/tmp/timbra-master/smoke")
FAILURES = []


def check(label, condition, detail=""):
    print(f"[SMOKE] {'PASS' if condition else 'FAIL'}: {label} {detail}")
    if not condition:
        FAILURES.append(label)
    return condition


def pkg():
    for name in sys.modules:
        if name.endswith(".sync_manager.blend_officina"):
            return sys.modules[name.rsplit(".sync_manager.blend_officina", 1)[0]]
    raise RuntimeError("EM Tools (with blend_officina) is not loaded")


em = pkg()
BO = sys.modules[em.__name__ + ".sync_manager.blend_officina"]
import importlib  # noqa: E402
BS = importlib.import_module(em.__name__ + ".birth_stamp")
from s3dgraphy.graph import Graph  # noqa: E402
from s3dgraphy.nodes.representation_node import RepresentationModelNode  # noqa: E402
from s3dgraphy.nodes.resource_node import ResourceNode  # noqa: E402
import dtcstamp  # noqa: E402

em_json = os.path.join(OUT, "EM", "T.em.json")
master_dir = os.path.join(OUT, "SB", "Cube", "master")
os.makedirs(master_dir, exist_ok=True)
os.makedirs(os.path.dirname(em_json), exist_ok=True)
obj = bpy.data.objects.get("Cube")
if obj is None:
    bpy.ops.mesh.primitive_cube_add()
    obj = bpy.context.active_object
ctx = bpy.context

# the master as it was stamped
old = os.path.join(master_dir, "Cube.glb")
BO._export_one(ctx, obj, old, {"format": "gltf"})
old = os.path.join(master_dir, "Cube.gltf") if os.path.exists(os.path.join(master_dir, "Cube.gltf")) else old
st0 = BS.stamp_export(old, how={"dtc_kind": "export"}, tier="master", master_kind=BO.kind_of_file(old))
check("the master stamped tier master", st0["state"] == "stamped" and st0["stamp"]["self"]["tier"] == "master", st0["line"])
old_stamp_bytes = open(BS.stamp_path_for(old), "rb").read()
old_bytes = open(old, "rb").read()

g = Graph("g")
g.add_node(RepresentationModelNode("rm1", "Cube"))
m = ResourceNode("m1", "Cube master", url=os.path.relpath(old, os.path.dirname(em_json)), tier="master",
                 checksum=st0["digest"])
g.add_node(m)
g.add_edge("rm1_has_linked_resource_m1", "rm1", "m1", "has_linked_resource")
obj["em_asset_id"] = "m1"
sign = BO.master_sign(master_url=m.data["url"], stamp_exists=os.path.isfile(BS.stamp_path_for(old)))
check("the sign says stamped", sign["stamped"] is True, sign)

# changed in Blender after the stamp
for v in obj.data.vertices:
    v.co.z += 0.25
out = BO.export_master_version(ctx, g, obj, em_json)
check("a new master file beside the old", os.path.dirname(out["path"]) == master_dir and "_rev-" in out["path"], out["path"])
new = dtcstamp.read_stamp(BS.stamp_path_for(out["path"]))
me = new["self"]
check("stamped tier master", me.get("tier") == "master", me)
check("a revision of the old master", (me.get("was_revision_of") or {}).get("resource_id") == st0["stamp"]["self"]["resource_id"], me)
check("derived from the old master (from)", any(f.get("resource_id") == st0["stamp"]["self"]["resource_id"] for f in new["from"]), new["from"])
kinds = {(e.edge_source, e.edge_target, e.edge_type) for e in g.edges}
check("graph: was_revision_of", (out["resource_id"], "m1", "was_revision_of") in kinds)
check("graph: the RM hats the new master", ("rm1", out["resource_id"], "has_linked_resource") in kinds)
check("the old master and its stamp untouched", open(old, "rb").read() == old_bytes
      and open(BS.stamp_path_for(old), "rb").read() == old_stamp_bytes)
check("the object now shows the new master", obj.get("em_asset_id") == out["resource_id"])

# a master that arrived without a stamp
arrived = os.path.join(master_dir, "Arrived_VHR.obj")
bpy.ops.wm.obj_export(filepath=arrived, export_selected_objects=False, export_materials=False)
g.add_node(ResourceNode("m2", "Arrived", url=os.path.relpath(arrived, os.path.dirname(em_json)), tier="master"))
g.add_node(RepresentationModelNode("rm2", "Arrived"))
g.add_edge("rm2_has_linked_resource_m2", "rm2", "m2", "has_linked_resource")
bpy.ops.mesh.primitive_uv_sphere_add()
o2 = bpy.context.active_object
o2["em_asset_id"] = "m2"
s2 = BO.master_sign(master_url=g.find_node_by_id("m2").data["url"], stamp_exists=os.path.isfile(BS.stamp_path_for(arrived)))
check("the arrived master: not stamped, gesture stamp", s2["stamped"] is False and s2["gesture"] == "stamp_master", s2)
r = BO.stamp_master(ctx, g, o2, em_json)
st2 = dtcstamp.read_stamp(BS.stamp_path_for(arrived))
check("stamped where it is, tier master, its kind", st2["self"].get("tier") == "master"
      and st2["self"].get("master_kind") == "very_high_resolution" and st2["how"]["dtc_kind"] == "local_import", st2["self"])
ops = dir(bpy.ops.em)
check("the operators are registered", "blend_export_master_version" in ops and "blend_stamp_master" in ops)
json.dump({"failures": FAILURES, "new": out}, open(os.path.join(OUT, "smoke.json"), "w"), indent=1, default=str)
print("[SMOKE] DONE", "OK" if not FAILURES else f"{len(FAILURES)} FAILED")
if FAILURES:
    sys.exit(1)
