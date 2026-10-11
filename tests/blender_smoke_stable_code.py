"""Headless smoke · the study's code re-attaches the proxies (E.D., 11 Oct 2026).

    PYTHONPATH=~/Documents/GitHub/s3Dgraphy/src \\
    "/Applications/Blender 520.app/Contents/MacOS/Blender" -b --python-use-system-env \\
        --python tests/blender_smoke_stable_code.py

A scene with one proxy per unit, named ``GT16.<unit>``, and three files of the
same units, all made in a temporary folder:

1. a GraphML whose header says ``ID:GT16`` (s3Dgraphy's canvas fixture);
2. the em.json EM-tools turns it into (G1) — where the code lives only on the
   study, because an em.json does not carry ``graph.attributes``;
3. an em.json with only the retired ``em_id`` GT16 on the graph-self node.

Each one, loaded alone in a clean scene, must give the slot the code GT16 and
find EVERY proxy (the unit's icon LINKED, ``node_name_to_proxy_name`` →
``GT16.<unit>``). The objects are the same ones each time. Nothing is saved.
Exits non-zero on failure.
"""
import importlib
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
    return condition


def addon_module():
    for name in list(sys.modules):
        if name.endswith(".graph_updaters") and name.startswith("bl_ext."):
            return name.rsplit(".", 1)[0]
    return None


pkg = addon_module()
if not check("addon loaded", pkg is not None and hasattr(bpy.context.scene, "em_tools")):
    sys.exit(1)
functions = importlib.import_module(pkg + ".functions")
helpers = importlib.import_module(pkg + ".operators.addon_prefix_helpers")

import s3dgraphy  # noqa: E402
from s3dgraphy import api  # noqa: E402
check("s3dgraphy knows the stable code", hasattr(api, "propose_study_code"),
      s3dgraphy.__file__)

from s3dgraphy.container import build_container, container_of  # noqa: E402
from s3dgraphy.graph import Graph  # noqa: E402
from s3dgraphy.importer.emjson_importer import materialize_graph_scope  # noqa: E402
from s3dgraphy.importer.import_graphml import GraphMLImporter  # noqa: E402
from s3dgraphy.multigraph.multigraph import multi_graph_manager  # noqa: E402
from s3dgraphy.nodes.stratigraphic_node import StratigraphicNode, StratigraphicUnit  # noqa: E402

S3D = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(s3dgraphy.__file__))))
FIXTURE = os.path.join(S3D, "tests", "fixtures", "canvas_metadata.graphml")
work = tempfile.mkdtemp(prefix="em_stable_code_")

graphml = os.path.join(work, "GT16.graphml")
with open(FIXTURE, encoding="utf-8") as fh:
    text = fh.read().replace("ID:TestSite", "ID:GT16")
with open(graphml, "w", encoding="utf-8") as fh:
    fh.write(text)

probe = GraphMLImporter(graphml, Graph(graph_id="probe")).parse()
UNITS = sorted(n.name for n in probe.nodes if isinstance(n, StratigraphicNode)
               and getattr(n, "node_type", "") in ("US", "USVs", "USVn", "SF",
                                                   "USM", "USD", "VSF", "serSU"))
check("the fixture has units", len(UNITS) > 0, str(UNITS))

# the scene's proxies: one per unit, named as Blender has them since 1.5
objects = {}
for name in UNITS:
    mesh = bpy.data.meshes.new(f"GT16.{name}")
    obj = bpy.data.objects.new(f"GT16.{name}", mesh)
    bpy.context.scene.collection.objects.link(obj)
    objects[name] = obj.as_pointer()


def clean_scene():
    et = bpy.context.scene.em_tools
    while len(et.graphml_files):
        row = et.graphml_files[0]
        try:
            multi_graph_manager.remove_graph(row.name)
        except Exception:  # noqa: BLE001
            pass
        et.graphml_files.remove(0)
    et.active_file_index = -1


def attached(label):
    """The slot's code, and the units whose proxy the addon finds."""
    et = bpy.context.scene.em_tools
    row = et.graphml_files[et.active_file_index]
    graph = multi_graph_manager.get_graph(row.name)
    check(f"{label}: the slot's code is GT16", row.graph_code == "GT16",
          repr(row.graph_code))
    check(f"{label}: the graph's code is GT16",
          helpers.get_graph_code_from_graph(graph) == "GT16")
    found = []
    for name in UNITS:
        proxy = helpers.node_name_to_proxy_name(name, graph=graph)
        obj = bpy.data.objects.get(proxy)
        icon = functions.check_objs_in_scene_and_provide_icon_for_list_element(
            name, graph=graph)
        if obj is not None and obj.as_pointer() == objects[name] and icon == "LINKED":
            found.append(name)
    check(f"{label}: every proxy re-attached ({len(found)}/{len(UNITS)})",
          found == UNITS, str(sorted(set(UNITS) - set(found))))
    return row, graph


# ── 1 · the GraphML with ID GT16 (EM-tools turns it into an em.json) ──────────
clean_scene()
et = bpy.context.scene.em_tools
row = et.graphml_files.add()
row.name = "slot"
row.graphml_path = graphml
et.active_file_index = 0
result = getattr(bpy.ops, "import").em_graphml(graphml_index=0)
check("import.em_graphml finished", result == {"FINISHED"}, str(result))
row, graph = attached("GraphML")
emjson = bpy.path.abspath(row.graphml_path)
check("the slot is the em.json made from the GraphML",
      emjson.lower().endswith(".json") and os.path.isfile(emjson), emjson)
with open(emjson, encoding="utf-8") as fh:
    doc = json.load(fh)
codes = [((n.get("data") or {}).get("code"))
         for sec in (doc.get("graphs") or {}).values() if isinstance(sec, dict)
         for n in sec.get("nodes") or [] if n.get("node_type") == "study"]
check("the em.json carries GT16 on the study", "GT16" in codes, str(codes))

# ── 2 · that em.json, alone, in a clean scene ────────────────────────────────
copy = os.path.join(work, "copy", "GT16.em.json")
os.makedirs(os.path.dirname(copy))
shutil.copy2(emjson, copy)
clean_scene()
result = getattr(bpy.ops, "import").em_emjson(filepath=copy)
check("import.em_emjson (the derived em.json) finished", result == {"FINISHED"},
      str(result))
attached("em.json from the GraphML")

# ── 3 · an em.json with only the retired em_id ───────────────────────────────
old = Graph(graph_id="old-em-id")
for i, name in enumerate(UNITS):
    old.add_node(StratigraphicUnit(f"old_u{i}", name=name))
materialize_graph_scope(old, em_id="GT16")
legacy = os.path.join(work, "legacy", "old.em.json")
os.makedirs(os.path.dirname(legacy))
with open(legacy, "w", encoding="utf-8") as fh:
    json.dump(build_container(container_of(old)), fh)
clean_scene()
result = getattr(bpy.ops, "import").em_emjson(filepath=legacy)
check("import.em_emjson (only em_id) finished", result == {"FINISHED"}, str(result))
_row, legacy_graph = attached("em.json with only em_id")
check("the em_id was read, not written: no study made",
      not [n for n in legacy_graph.nodes if n.node_type == "study"])

shutil.rmtree(work, ignore_errors=True)
print(f"[SMOKE] {len(FAILURES)} failure(s)")
sys.exit(1 if FAILURES else 0)
