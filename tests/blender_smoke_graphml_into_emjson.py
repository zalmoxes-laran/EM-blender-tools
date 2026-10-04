"""Headless smoke · G1 on the COPY of Templu Mare: loading the GraphML turns it
into an em.json, with the scene's models and proxies in it.

    PYTHONPATH=~/Documents/GitHub/s3Dgraphy/src \\
    "/Applications/Blender 520.app/Contents/MacOS/Blender" -b --python-use-system-env \\
        <copy>.blend --python tests/blender_smoke_graphml_into_emjson.py

The GraphML of slot 0 is COPIED into a temporary folder first (the slot of the
copy points at E.D.'s examples, and the em.json is written beside the GraphML),
so nothing of E.D.'s is touched; the .blend is NOT saved.

Checks: the slot is the em.json afterwards; the GraphML is byte-for-byte the
same; the em.json carries the representation models under their epochs and
documents and the units' proxies (what EMStudio's Models sheet reads); the five
document→dating edges are has_property, not generic_connection; no operator
writing a GraphML is registered; the em.json reloads with `import.em_emjson`.
"""
import hashlib
import json
import os
import shutil
import sys
import tempfile

import bpy

FAILURES = []


def check(label, condition, detail=""):
    print(f"[SMOKE] {'PASS' if condition else 'FAIL'}: {label} {detail}")
    if not condition:
        FAILURES.append(label)


def sha(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


et = bpy.context.scene.em_tools
row = et.graphml_files[0]
source = bpy.path.abspath(row.graphml_path)
check("slot 0 is a GraphML before", source.lower().endswith(".graphml"), source)
work = tempfile.mkdtemp(prefix="emjson-g1-")
copy = os.path.join(work, os.path.basename(source))
shutil.copy2(source, copy)
before = sha(copy)
row.graphml_path = copy
et.active_file_index = 0

check("no Save GraphML operator", not hasattr(bpy.ops.export, "graphml_update")
      or "graphml_update" not in dir(bpy.ops.export))
check("no Save GraphML As operator", "graphml_saveas" not in dir(bpy.ops.export))
check("no Bake Paradata into GraphML", "bake_to_graphml" not in dir(bpy.ops.paradata))

result = getattr(bpy.ops, "import").em_graphml(graphml_index=0)
check("import.em_graphml finished", result == {"FINISHED"}, str(result))

expected = os.path.join(work, os.path.splitext(os.path.basename(copy))[0] + ".em.json")
row = et.graphml_files[0]
check("the slot is the em.json now", bpy.path.abspath(row.graphml_path) == expected,
      row.graphml_path)
check("the slot's format is EMJSON", getattr(row, "file_format", "") == "EMJSON",
      getattr(row, "file_format", "?"))
check("the em.json exists beside the GraphML", os.path.isfile(expected))
check("the GraphML is untouched", sha(copy) == before)

with open(expected, encoding="utf-8") as fh:
    doc = json.load(fh)
graphs = doc.get("graphs") or {}
section = graphs.get(row.name) or next(iter(graphs.values()))
nodes = {n["id"]: n for n in section["nodes"]}
edges = section["edges"]
rms = [n for n in nodes.values() if n["node_type"] == "representation_model"]
check("the models are in the em.json", len(rms) >= 90, f"{len(rms)} RM")


def from_type(edge, t):
    return (nodes.get(edge["source"]) or {}).get("node_type") == t


epoch_rm = {e["target"] for e in edges if e["edge_type"] == "has_representation_model"
            and from_type(e, "EpochNode") and e["target"] in {r["id"] for r in rms}}
doc_rm = {e["target"] for e in edges if e["edge_type"] == "has_representation_model"
          and from_type(e, "document")}
check("models under their epochs (the Models sheet's RM by epoch)",
      len(epoch_rm) >= 90, f"{len(epoch_rm)}")
check("models under their documents (the containers)", len(doc_rm) >= 90, f"{len(doc_rm)}")
ids = {str(o.get("em_rm_node_id")) for o in bpy.data.objects if o.get("em_rm_node_id")}
rm_ids = {r["id"] for r in rms}
check("every model keeps its own id (em_rm_node_id is the RM's id)",
      ids <= rm_ids, f"{len(ids - rm_ids)} missing: {sorted(ids - rm_ids)[:3]}")
podio = bpy.data.objects.get("ME_PODIO")
print(f"[SMOKE] ME_PODIO em_rm_node_id = {podio.get('em_rm_node_id') if podio else None}")

geometry = {n["id"] for n in nodes.values() if n["node_type"] == "property"
            and (n.get("data") or {}).get("property_type") == "geometry"}
shapes = {n["id"] for n in nodes.values() if n["node_type"] == "semantic_shape"}
with_shape = {e["source"] for e in edges if e["edge_type"] == "has_semantic_shape"
              and e["source"] in geometry and e["target"] in shapes}
units = {e["source"] for e in edges if e["edge_type"] == "has_property"
         and e["target"] in with_shape}
check("units with a proxy (the Models sheet's proxies)", len(units) > 0, f"{len(units)}")

generic = [e for e in edges if e["edge_type"] == "generic_connection"]
doc_prop = [e for e in edges if e["edge_type"] == "has_property" and from_type(e, "document")]
check("the documents' dating is has_property", len(doc_prop) >= 5, f"{len(doc_prop)}")
check("seven drawing anomalies left generic (not twelve)", len(generic) == 7, f"{len(generic)}")

result = getattr(bpy.ops, "import").em_emjson(file_index=0)
check("the em.json reloads", result == {"FINISHED"}, str(result))

print(f"[SMOKE] counts: RM {len(rms)}, epoch→RM {len(epoch_rm)}, doc→RM {len(doc_rm)}, "
      f"units with proxy {len(units)}, generic {len(generic)} · {expected}")
print("[SMOKE] ALL PASS" if not FAILURES else f"[SMOKE] FAILED: {FAILURES}")
sys.exit(1 if FAILURES else 0)
