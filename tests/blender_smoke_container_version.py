"""Headless smoke · MICRO-VERSIONE-CONTENITORE (E.D., 30 Oct 2026) on a COPY of
Templu Mare, Blender 5.2, EM Tools as the working copy::

    CV_PROJECT=/tmp/cv/TM PYTHONPATH=~/Documents/GitHub/s3Dgraphy/src \\
    BLENDER_USER_RESOURCES=<profile> \\
    "/Applications/Blender 520.app/Contents/MacOS/Blender" -b --python-use-system-env \\
        /tmp/cv/TM/SB/GreatTemple_2026_v2.blend \\
        --python tests/blender_smoke_container_version.py

``CV_PROJECT``: the copy (``SB/GreatTemple_2026_v2.blend``,
``EM/TempluMare_v6_optimized.em.json`` as E.D. saved it: the container's
version WITHOUT its edge). Opened, the old version gets its container's edge
(in memory); «Prepare for a use» of «Its container» (Reconstruction II AC,
mobile webXR, the safe ticks) writes the version, and the graph has it with
the container's edge, ``data.container``, a url relative to the em.json and
the level of its file's name. The .blend and the em.json are never saved; the
graph is written to ``CV_OUT`` to check what a save would keep."""
import json
import os
import sys

import bpy

PROJECT = os.environ.get("CV_PROJECT", "/tmp/cv/TM")
OUT = os.environ.get("CV_OUT", "/tmp/cv/out")
GID = "rmgroup_Reconstruction_II_AC"
OLD = "fea517cc-f737-5387-8d6e-334a322c369c"
FAILURES = []
os.makedirs(OUT, exist_ok=True)


def check(label, condition, detail=""):
    print(f"[SMOKE] {'PASS' if condition else 'FAIL'}: {label} {detail}")
    if not condition:
        FAILURES.append(label)
    return condition


def pkg():
    for name in sys.modules:
        if name.endswith(".sync_manager.prepare_diagnosis"):
            return sys.modules[name.rsplit(".sync_manager.prepare_diagnosis", 1)[0]]
    raise RuntimeError("EM Tools is not loaded")


def hats(graph, rid):
    return [e.edge_source for e in graph.edges if e.edge_type == "has_linked_resource" and e.edge_target == rid]


em = pkg()
PD = sys.modules[em.__name__ + ".sync_manager.prepare_diagnosis"]
emjson = os.path.join(PROJECT, "EM", "TempluMare_v6_optimized.em.json")
before_bytes = open(emjson, "rb").read()

scene = bpy.context.scene
emt = scene.em_tools
emt.graphml_files.clear()
row = emt.graphml_files.add()
row.name = "TempluMare_v6"
row.graphml_path = emjson
emt.active_file_index = 0
getattr(bpy.ops, "import").em_emjson(file_index=0)
ok_graph, graph = em.functions.is_graph_available(bpy.context)
check("the graph of the copy is loaded", ok_graph and graph is not None)

# ── read: the version written before this MICRO gets its container's edge
check("opened: the old container version is hatted by its container", hats(graph, OLD) == [GID], hats(graph, OLD))

# ── «Prepare for a use» of «Its container»
cont = next((c for c in scene.rm_containers if c.label == "Reconstruction II AC"), None)
check("the container is in the scene", cont is not None and cont.group_node_id == GID,
      getattr(cont, "group_node_id", None))
member = next(bpy.data.objects[e.name] for e in cont.mesh_names if e.name in bpy.data.objects)
for o in bpy.context.view_layer.objects:
    o.select_set(False)
member.select_set(True)
bpy.context.view_layer.objects.active = member
d = PD.diagnose_here(bpy.context, PD.selection(bpy.context, "CONTAINER")[0], "mobile_webxr")
ids = [r["id"] for r in d["improvements"] if r.get("checked") and r.get("available", True)]
r = bpy.ops.em.prepare_diagnose(profile="mobile_webxr", scope="CONTAINER", replace=True,
                                checked_ids=",".join(ids))
check("applied", r == {"FINISHED"}, r)
out = PD.LAST.get("applied") or {}
entry = out.get("entry", "")
rid = (out.get("registered") or {}).get("resource_id")
node = graph.find_node_by_id(rid) if rid else None
check("registered in the graph", node is not None, rid)
if node is not None:
    data = node.data
    check("the container hats it (has_linked_resource)", hats(graph, rid) == [GID], hats(graph, rid))
    check("data.container stays", data.get("container") == GID and data.get("represents") == "container")
    want = "../SB/versions/" + os.path.basename(entry)
    check("its url is relative to the em.json's folder", data.get("url") == want, (data.get("url"), want))
    check("the level of the file's name is the graph's and the dialog's",
          f"@{out.get('level')}-" in os.path.basename(entry) and data.get("level") == out.get("level"),
          (os.path.basename(entry), data.get("level"), out.get("level")))
    # what a save keeps
    from s3dgraphy.exporter.emjson_exporter import build_emjson
    doc = build_emjson(graph)
    edges = {(e["source"], e["target"], e["edge_type"]) for e in doc["graph"]["edges"]}
    n = next(x for x in doc["graph"]["nodes"] if x["id"] == rid)
    check("saved: the edge and the relative url are in the em.json",
          (GID, rid, "has_linked_resource") in edges and n["data"]["url"] == want)
    json.dump({"entry": entry, "rid": rid, "url": n["data"]["url"], "level": data.get("level"),
               "bytes": out.get("bytes"), "measured": out.get("measured")},
              open(os.path.join(OUT, "smoke.json"), "w"), indent=1)

check("the em.json of the copy is not written", open(emjson, "rb").read() == before_bytes)
print(f"[SMOKE] {'OK' if not FAILURES else 'FAILED: ' + ', '.join(FAILURES)}")
sys.exit(1 if FAILURES else 0)
