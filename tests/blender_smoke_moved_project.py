"""Headless smoke · a project folder handed on: its .blend opens its em.json.

NOT a pytest test. Run in a background Blender with EM Tools enabled:

    "/Applications/Blender 520.app/Contents/MacOS/Blender" -b --python-use-system-env \\
        --python tests/blender_smoke_moved_project.py

Templu Mare v2 (6 Oct 2026): a dataset folder carries `EM/x.em.json` and
`SB/x.blend`, whose graph slot says `//../EM/x.em.json` — relative to the .blend,
so the folder can be copied anywhere. The slot was born elsewhere (its recorded
origin is the folder it was made in). Reloading the slot must

* find the em.json by the slot's path made absolute (`bpy.path.abspath`): it
  said «em.json file not found: //../EM/x.em.json»;
* not take the slot's own older origin for «another file»: it said «graph … is
  already open from x.em.json: the same graph cannot come from two files».

Everything happens in a temporary folder; nothing of the repo is written.
"""
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


HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURE = os.path.join(HERE, "fixtures", "emtools_cb25e71_dev23.em.json")
tmp = tempfile.mkdtemp(prefix="em-moved-")
born = os.path.join(tmp, "born", "Study")
moved = os.path.join(tmp, "handed-on", "Study v2")
for d in (os.path.join(born, "EM"), os.path.join(born, "SB")):
    os.makedirs(d)
shutil.copy2(FIXTURE, os.path.join(born, "EM", "study.em.json"))

# 1 · the study is opened where it was born, and the .blend saved beside it
imp = getattr(bpy.ops, "import")
check("opened where it was born", imp.em_emjson(filepath=os.path.join(born, "EM", "study.em.json")) == {"FINISHED"})
em = bpy.context.scene.em_tools
row = em.graphml_files[0]
row.graphml_path = "//../EM/study.em.json"
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(born, "SB", "study.blend"))

# 2 · the folder is handed on; the copy's .blend is opened
shutil.copytree(born, moved)
bpy.ops.wm.open_mainfile(filepath=os.path.join(moved, "SB", "study.blend"))
em = bpy.context.scene.em_tools
row = em.graphml_files[0]
check("the slot keeps its path relative to the .blend", row.graphml_path == "//../EM/study.em.json", row.graphml_path)

# 2b · before any Load, the tree, «Save» and the study name the em.json beside
#      the moved .blend, not the one where the folder was born (its recorded
#      origin_path is absolute and stays there)
import importlib
_pkg = next(m for m in sys.modules if m.endswith("EM-blender-tools") or m.endswith("em_tools"))
go = importlib.import_module(_pkg + ".graph_origins")
here = os.path.normpath(os.path.join(moved, "EM", "study.em.json"))
check("the recorded origin is still where it was born",
      os.path.normpath(row.origin_path) == os.path.normpath(os.path.join(born, "EM", "study.em.json")),
      row.origin_path)
origin = go.origin_of(row, abspath=bpy.path.abspath)
check("the origin (tree, Save) is the slot beside the moved .blend", origin.path == here, origin.path)
study = importlib.import_module(_pkg + ".sync_manager.study").study_of(bpy.context, None)
check("the study reads the em.json beside the moved .blend", study.get("path") == here, str(study.get("path")))

# 3 · the slot is reloaded from where the folder is now
em.active_file_index = 0
result = imp.em_emjson(file_index=0)
check("reloading the slot finds the em.json beside the moved .blend", result == {"FINISHED"}, str(result))
from s3dgraphy import get_graph
graph = get_graph(row.name)
check("the graph is loaded", graph is not None and len(graph.nodes) > 0,
      f"{len(graph.nodes) if graph is not None else 0} nodes")

shutil.rmtree(tmp, ignore_errors=True)
print("[SMOKE]", "ALL PASS" if not FAILURES else f"FAILED: {FAILURES}")
sys.exit(1 if FAILURES else 0)
