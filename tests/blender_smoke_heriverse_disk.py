"""Headless smoke · H4, the package for Heriverse ON DISK, on the COPY of Templu
Mare (never saved). The versions made go into the copy's `em_cache/` (a cache,
beside the copy); the package into the folder given after `--`.

    PYTHONPATH=~/Documents/GitHub/s3Dgraphy/src \\
    "/Applications/Blender 520.app/Contents/MacOS/Blender" -b --python-use-system-env \\
        ~/Documents/GitHub/_datasets/templu-mare-prove/GreatTemple_2026_v3_multigraph_test_CLAUDE.blend \\
        --python ~/Documents/GitHub/EM-blender-tools/tests/blender_smoke_heriverse_disk.py -- /tmp/h4

Three published models: ME_PODIO with a web version («Prepare for a use…»,
decimated), Podio_2_BAKE with none — «Make the missing versions» gives it one
for Heriverse, as it is — and a third left with its master only. Then «Write
the package on disk»: em.json + project.json + versions/, each version's bytes
checked against its sha256, the urls relative; the rule read back from the
package picks what the Deck said.
"""
import hashlib
import importlib
import json
import os
import shutil
import sys
import tempfile

import bpy

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
WORK = ARGS[0] if ARGS else "/tmp/h4"
FAILURES = []


def check(label, condition, detail=""):
    print(f"[SMOKE] {'PASS' if condition else 'FAIL'}: {label} {detail}")
    if not condition:
        FAILURES.append(label)


shutil.rmtree(WORK, ignore_errors=True)
os.makedirs(WORK)
names = [n for n in sys.modules if n.endswith(".graph_origins") and n.startswith("bl_ext.")]
PKG = names[0].rsplit(".graph_origins", 1)[0]
print("[SMOKE] package:", PKG, sys.modules[PKG].__file__)
av = importlib.import_module(PKG + ".sync_manager.asset_versions")
heri = importlib.import_module(PKG + ".publication_deck_ui.heriverse")
PH = importlib.import_module(PKG + ".publication_heriverse")
scene = bpy.context.scene
row0 = scene.em_tools.graphml_files[0]
src0 = bpy.path.abspath(row0.graphml_path)
if src0.lower().endswith(".graphml"):
    dst0 = os.path.join(tempfile.mkdtemp(prefix="em-h4-"), os.path.basename(src0))
    shutil.copy2(src0, dst0)
    row0.graphml_path = dst0
scene.em_tools.active_file_index = 0
for i, item in enumerate(scene.em_tools.graphml_files):
    item.is_publishable = (i == 0)
getattr(bpy.ops, "import").em_graphml(graphml_index=0)
from s3dgraphy import api, get_graph  # noqa: E402
graph = get_graph(scene.em_tools.graphml_files[0].name)

WEB, HERI = "ME_PODIO", "Podio_2_BAKE_SM_Podio_2_BAKE"
rows = {r.name: r for r in scene.rm_list}
print("[SMOKE] rm_list:", len(rows), "rows;", [n for n in rows][:8])
mesh_rows = [n for n, r in rows.items() if n not in (WEB, HERI)
             and bpy.data.objects.get(n) is not None and bpy.data.objects[n].type == "MESH"]
THIRD = sorted(mesh_rows)[0] if mesh_rows else ""
for name, r in rows.items():
    r.is_publishable = name in (WEB, HERI)


def select(name):
    obj = bpy.data.objects[name]
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    return obj


# ── (1) ME_PODIO: a web version, decimated ─────────────────────────────────
select(WEB)
r = bpy.ops.em.asset_prepare_for_use(use={"web"}, ratio=0.5, max_texture=1024, draco=True)
check("Prepare for a use… (web) on ME_PODIO", r == {"FINISHED"}, str(r))
web_vid = av.PREPARED.get("version_id")

# ── (2) the plan before: ME_PODIO ready, Podio_2 missing ───────────────────
plan = heri.make_plan(bpy.context)
print("[SMOKE] plan:", PH.summary(plan))
for row in plan["ready"] + plan["missing"]:
    print("[SMOKE]   ", PH.row_line(row), "·", row["on_node_said"])
ready = {r["object"]: r for r in plan["ready"]}
missing = {r["object"]: r for r in plan["missing"]}
check("ME_PODIO → its web version", ready.get(WEB, {}).get("version_id") == web_vid,
      str(ready.get(WEB)))
check("Podio_2 has no version for a viewer", HERI in missing, str(list(missing)))

# ── (3) Make the missing versions: Podio_2 gets one for Heriverse ──────────
r = bpy.ops.em.deck_heriverse_make_missing()
check("Make the missing versions", r == {"FINISHED"}, f"{r} {heri.LAST.get('made')}")
plan = heri.make_plan(bpy.context)
ready = {r["object"]: r for r in plan["ready"]}
h = ready.get(HERI) or {}
check("Podio_2 → heriverse version", h.get("use") == "heriverse", str(h))
hnode = graph.find_node_by_id(h.get("version_id") or "")
hdata = (hnode.data or {}) if hnode is not None else {}
check("…a version in the graph with its sha256 and its uses",
      str(hdata.get("checksum", "")).startswith("sha256:")
      and set(hdata.get("use") or []) == {"heriverse", "aton"}, str(hdata.get("use")))
proc = next((graph.find_node_by_id(e.edge_source) for e in graph.edges
             if e.edge_type == "dtc_had_output" and e.edge_target == h.get("version_id")), None)
params = ((proc.data or {}).get("parameters") or {}) if proc is not None else {}
check("…made as it is (no decimation, textures kept, no Draco)",
      params.get("ratio") == 1.0 and params.get("max_texture_px") == 0
      and params.get("draco") is False, str(params))

# ── (4) a third model, published with its master only ──────────────────────
if THIRD:
    rows[THIRD].is_publishable = True
plan = heri.make_plan(bpy.context)
disk = heri.make_disk_plan(bpy.context, plan)
for row in disk["rows"]:
    print("[SMOKE] disk:", PH.row_line(row), "·", row.get("local_said"), "→", row.get("rel"))
third = next((r for r in disk["rows"] if r["object"] == THIRD), None)
check("the third model is said, without a version", THIRD == "" or (
      third is not None and third["reason"] not in PH.READY), str(third))

# ── (4b) the same preparation as the measure from the node (5 Oct): in this
# copy ME_PODIO's model hangs on no epoch, and Heriverse draws a model under
# its epoch — it is hung on «II A.D.», in memory (the .blend is not saved)
rm_web = ready[WEB]["rm_id"]
if not any(e.edge_type == "has_representation_model" and e.edge_target == rm_web
           and getattr(graph.find_node_by_id(e.edge_source), "node_type", "") == "EpochNode"
           for e in graph.edges):
    epoch = next(n for n in graph.nodes if getattr(n, "node_type", "") == "EpochNode"
                 and n.name == "II A.D.")
    graph.add_edge(f"{epoch.node_id}_has_representation_model_{rm_web}", epoch.node_id,
                   rm_web, "has_representation_model")
    print("[SMOKE] ME_PODIO's model hung on the epoch II A.D. (as in the node copy)")

# ── (5) Write the package on disk ──────────────────────────────────────────
dest = os.path.join(WORK, "TempluMare_heriverse")
r = bpy.ops.em.deck_heriverse_write_disk(folder=dest, make_zip=True, from_node=False)
rep = heri.LAST.get("package") or {}
print("[SMOKE] package:", PH.package_sentence(rep))
check("the package is written", r == {"FINISHED"} and os.path.isfile(os.path.join(dest, "em.json")),
      str(r))
written = {w["rm_name"]: w for w in rep.get("written") or []}
print("[SMOKE] written:", json.dumps(rep.get("written"), indent=1))
em = json.load(open(os.path.join(dest, "em.json"), encoding="utf-8"))
nodes = {n["id"]: n for g in em["graphs"].values() if isinstance(g.get("nodes"), list)
         for n in g["nodes"]}
for vid in (web_vid, h.get("version_id")):
    d = (nodes.get(vid) or {}).get("data") or {}
    url = d.get("url", "")
    path = os.path.join(dest, *url.split("/"))
    ok = (url.startswith("versions/") and os.path.isfile(path) and "sha256:" +
          hashlib.sha256(open(path, "rb").read()).hexdigest() == d.get("checksum"))
    check(f"{vid[:8]}: url relative, bytes = registered sha256", ok, url)
check("project.json is the same document",
      open(os.path.join(dest, "project.json")).read() == open(os.path.join(dest, "em.json")).read())
check("the zip is there", os.path.isfile(rep.get("zip") or ""), str(rep.get("zip")))

# ── (6) read back, the package gives the same choice ───────────────────────
from s3dgraphy.container import parse_container  # noqa: E402
back, _w = parse_container(em)
bg = back.active()
for obj_name, row in ready.items():
    if obj_name not in (WEB, HERI):
        continue
    again = api.version_for(bg, row["rm_id"], list(PH.USES))
    check(f"{obj_name}: the rule reads the package and picks the same version",
          again and again["entry"]["id"] == row["version_id"]
          and again["entry"]["url"].startswith("versions/"), str(again and again["entry"]["url"]))

with open(os.path.join(WORK, "h4.json"), "w") as fh:
    json.dump({"web_version": web_vid, "heriverse_version": h.get("version_id"),
               "third": THIRD, "package": rep,
               "rms": {r["object"]: {"rm_id": r["rm_id"], "reason": r["reason"],
                                     "use": r["use"], "rel": r.get("rel"),
                                     "said": r.get("local_said")} for r in disk["rows"]}},
              fh, indent=1, default=str)
print("[SMOKE] RESULT:", "ALL PASS" if not FAILURES else f"FAILED {FAILURES}")
sys.stdout.flush()
sys.exit(0 if not FAILURES else 1)
