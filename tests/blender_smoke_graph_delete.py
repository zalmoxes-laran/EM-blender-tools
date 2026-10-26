"""Headless smoke · «Delete the graph from its em.json…» (MICRO contenuti-
workspace-elimina-grafo, 26 Oct 2026), on a COPY of GT16_piu_SaggioB.

    EM_GDEL_DIR=/tmp/grm/gdel-emt \\
    "/Applications/Blender 520.app/Contents/MacOS/Blender" -b --python-use-system-env \\
        --python ~/Documents/GitHub/EM-blender-tools/tests/blender_smoke_graph_delete.py

``$EM_GDEL_DIR/GT16_piu_SaggioB.source.em.json`` is the copy (never the
OneDrive original); the smoke writes ``GT16_piu_SaggioB.em.json`` beside it,
with one link added: a unit of Saggio B «is after» a unit of the Temple.

(0) with the bundled s3Dgraphy (older than the operation) the command is off
and says why; then the working tree's `s3dgraphy.graph_removal` is put on the
package's path (EM_GDEL_S3D, default ~/Documents/GitHub/s3Dgraphy/src). (1)
the report on the Temple: its nodes, Saggio B's link that would hang, the
Blender objects tied to it by name. (2) deleted: off the list and the manager,
the objects stay, the file says it is behind. (3) «Save em.json»: the file
holds Saggio B, the shelf and the periodizations, Saggio B's link marked. (4)
reopened in an empty scene: one graph. (5) the last graph is refused.
"""
import importlib
import json
import os
import shutil
import sys

import bpy

FAILURES = []
DIR = os.environ.get("EM_GDEL_DIR", "/tmp/grm/gdel-emt")
SOURCE = os.path.join(DIR, "GT16_piu_SaggioB.source.em.json")
WORK = os.path.join(DIR, "GT16_piu_SaggioB.em.json")
S3D = os.environ.get("EM_GDEL_S3D", os.path.expanduser("~/Documents/GitHub/s3Dgraphy/src"))
TEMPLE = "6af9866e-96a9-5c99-a6b1-78524ae2e2c2"
SAGGIO = "226e2d45-83d1-59d8-a912-b576141d7680"


def check(label, condition, detail=""):
    print(f"[SMOKE] {'PASS' if condition else 'FAIL'}: {label} {detail}")
    if not condition:
        FAILURES.append(label)
    return condition


def module(suffix):
    names = [n for n in sys.modules if n.endswith(suffix) and n.startswith("bl_ext.")]
    if not names:
        print(f"[SMOKE] aborting: {suffix} not loaded — enable the extension")
        sys.exit(1)
    return sys.modules[names[0]]


origins = module(".graph_origins")
PKG = origins.__name__.rsplit(".graph_origins", 1)[0]
tree_mod = importlib.import_module(PKG + ".em_setup.graph_tree")
state = importlib.import_module(PKG + ".emjson_state")
IMPORT = getattr(bpy.ops, "import")

# ── the copy, with a link Saggio B → Temple ──────────────────────────────────
doc = json.load(open(SOURCE, encoding="utf-8"))
units = lambda gid: [n for n in doc["graphs"][gid]["nodes"]
                     if n.get("node_type") in ("US", "USVs", "USVn", "SF")]
t_unit, s_unit = units(TEMPLE)[0], units(SAGGIO)[0]
doc["graphs"][SAGGIO]["links"] = [{
    "id": "smoke-link", "edge_type": "is_after", "source": s_unit["id"],
    "target": {"graph_id": TEMPLE, "node_id": t_unit["id"]}}]
json.dump(doc, open(WORK, "w", encoding="utf-8"), ensure_ascii=False)

scene = bpy.context.scene
em = scene.em_tools
while len(em.graphml_files):
    em.graphml_files.remove(0)
origins.forget_all()
r = IMPORT.em_emjson(filepath=WORK)
check("the copy loads", r == {"FINISHED"}, str(r))
ids = [row.name for row in em.graphml_files]
check("two graphs in the tree", sorted(ids) == sorted([TEMPLE, SAGGIO]), str(ids))
i_temple = ids.index(TEMPLE)
bpy.ops.em.graph_activate(index=i_temple)

# ── (0) the bundled s3Dgraphy ────────────────────────────────────────────────
import s3dgraphy  # noqa: E402
bundled = origins.removal_api() is not None
print(f"[SMOKE] s3dgraphy {getattr(s3dgraphy, '__version__', '?')} from {s3dgraphy.__file__}; "
      f"graph_removal bundled: {bundled}")
if not bundled:
    check("the command is off with the bundled s3Dgraphy", not tree_mod.EM_OT_graph_delete.poll(bpy.context))
    s3dgraphy.__path__.append(os.path.join(S3D, "s3dgraphy"))
check("graph_removal reachable", origins.removal_api() is not None)
check("the command is on for the Temple", tree_mod.EM_OT_graph_delete.poll(bpy.context))

# Blender objects named after Temple units (as proxies are), and one stranger
from s3dgraphy import get_graph  # noqa: E402
gc = importlib.import_module(PKG + ".graph_code")
code = gc.graph_code_of(get_graph(TEMPLE)) or ""
print(f"[SMOKE] the Temple's code: {code!r}")
tied = []
for u in units(TEMPLE)[:3]:
    name = f"{code}.{u['name']}" if code else u["name"]
    ob = bpy.data.objects.new(name, None)
    scene.collection.objects.link(ob)
    tied.append(ob.name)
stranger = bpy.data.objects.new("Camera-smoke", None)
scene.collection.objects.link(stranger)

# ── (1) the report ───────────────────────────────────────────────────────────
members = origins.members_of(em.graphml_files, origins.origin_of(em.graphml_files[i_temple],
                             abspath=bpy.path.abspath), abspath=bpy.path.abspath)
rep = origins.remove_from_file(WORK, TEMPLE, members, get_graph, dry_run=True)
from s3dgraphy.graph_removal import removal_summary  # noqa: E402
for s in removal_summary(rep):
    print(f"[SMOKE]   report: {s}")
check("the report counts the Temple", rep["nodes"] >= 2000 and rep["edges"] >= 4000,
      f"{rep['nodes']} nodes {rep['edges']} edges")
check("Saggio B's link would hang", [l["link_id"] for l in rep["links_in"]] == ["smoke-link"])
check("the graph in front becomes Saggio B", rep["active_graph_id"] == SAGGIO
      and "Saggio B" in (rep.get("active_graph_name") or ""), str(rep.get("active_graph_name")))
objs = origins.objects_of_graph(get_graph(TEMPLE), (o.name for o in bpy.data.objects), code)
check("the objects tied to it are named", set(tied) <= set(objs) and "Camera-smoke" not in objs, str(objs[:5]))

# the dialog draws (recording layout: no region in -b)
class Rec:
    def __init__(self, calls): self.calls = calls
    def _c(self, *a, **k): return Rec(self.calls)
    column = row = box = _c
    def label(self, **k): self.calls.append(k.get("text", ""))
    def prop(self, data, name, **k): self.calls.append(f"prop:{name}")
calls = []
fake = type("Op", (), {"layout": Rec(calls), "index": i_temple, "drop_links": False, "drop_shelf": False,
                       "_objs": objs, "_report": tree_mod.EM_OT_graph_delete._report,
                       "_objects": tree_mod.EM_OT_graph_delete._objects})()
tree_mod.EM_OT_graph_delete.draw(fake, bpy.context)
print("[SMOKE] dialog:", " | ".join(c for c in calls if c)[:600])
check("the dialog says the link, offers to drop it, names the objects",
      any("pointing at it" in c for c in calls) and "prop:drop_links" in calls
      and any("they stay in the scene" in c for c in calls))

# ── (2) delete ───────────────────────────────────────────────────────────────
r = bpy.ops.em.graph_delete(index=i_temple)
check("deleted", r == {"FINISHED"}, str(r))
check("off the list", [row.name for row in em.graphml_files] == [SAGGIO])
check("off the manager", get_graph(TEMPLE) is None)
check("the objects stay", all(n in bpy.data.objects for n in tied) and "Camera-smoke" in bpy.data.objects)
behind = state.unsaved(WORK, {SAGGIO: get_graph(SAGGIO)})
check("the file says it is behind", any("deleted" in s for s in behind), str(behind))
check("the file on disk still holds it before the save",
      TEMPLE in json.load(open(WORK, encoding="utf-8"))["graphs"])

# ── (3) save ─────────────────────────────────────────────────────────────────
em.active_file_index = 0
r = bpy.ops.export.em_save()
check("saved", r == {"FINISHED"}, str(r))
saved = json.load(open(WORK, encoding="utf-8"))
check("the file holds Saggio B, the shelf and the periodizations",
      sorted(saved["graphs"]) == sorted([SAGGIO, "shelf", "periodizations"]), str(sorted(saved["graphs"])))
link = (saved["graphs"][SAGGIO].get("links") or [{}])[0]
check("Saggio B's link stays, marked", link.get("attributes", {}).get("target_graph_removed") == TEMPLE, str(link))
check("the graph in front is Saggio B", saved.get("active_graph_id") == SAGGIO)

# ── (4) reopened ─────────────────────────────────────────────────────────────
while len(em.graphml_files):
    em.graphml_files.remove(0)
origins.forget_all()
from s3dgraphy import remove_graph as unload  # noqa: E402
unload(SAGGIO)
r = IMPORT.em_emjson(filepath=WORK)
check("reopened: one graph", r == {"FINISHED"} and [row.name for row in em.graphml_files] == [SAGGIO])

# ── (5) the last graph ───────────────────────────────────────────────────────
try:
    r = bpy.ops.em.graph_delete(index=0)
except RuntimeError as exc:
    r = {"CANCELLED"}
    print(f"[SMOKE] refused as expected: {str(exc).strip()[:160]}")
check("the last graph is refused", r == {"CANCELLED"} and len(em.graphml_files) == 1)

shutil.copyfile(WORK, os.path.join(DIR, "GT16_piu_SaggioB.after-smoke.em.json"))
print(f"[SMOKE] {'ALL PASS' if not FAILURES else 'FAILURES: ' + ', '.join(FAILURES)}")
sys.exit(1 if FAILURES else 0)
