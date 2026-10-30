"""Headless smoke · MICRO-PREPARA-DIAGNOSI (E.D., 30 Oct 2026) on a COPY of
Templu Mare, Blender 5.2, EM Tools as the working copy and 3D Survey Collection
loaded (its headless ``make_lod_set(normal_map=True)``)::

    PD_PROJECT=/tmp/pd/TM PD_MODELS=/tmp/pd/models.txt PD_OUT=/tmp/pd/out \\
    PYTHONPATH=~/Documents/GitHub/s3Dgraphy/src BLENDER_USER_RESOURCES=<profile> \\
    "/Applications/Blender 520.app/Contents/MacOS/Blender" -b --python-use-system-env \\
        /tmp/pd/TM/SB/GreatTemple_2026_v2.blend \\
        --python tests/blender_smoke_prepare_diagnosis.py

``PD_PROJECT``: the copy (``SB/GreatTemple_2026_v2.blend``, ``EM/TempluMare_v5.em.json``);
``PD_MODELS``: the names of the objects that have a version today (one per
line: the models of ``SB/versions``); the selection is those objects. The
diagnosis is asked for the web and for Heriverse/ATON, then each is APPLIED
through the operator (EXEC: a dialog cannot open in -b), measured, listed in
versions/ and removed with «Remove versions…» in its DISK mode. The .blend is
never saved; the smoke checks that it is left as it was.
"""
import json
import os
import sys
import time

import bpy

PROJECT = os.environ.get("PD_PROJECT", "/tmp/pd/TM")
OUT = os.environ.get("PD_OUT", "/tmp/pd/out")
MODELS = os.environ.get("PD_MODELS", "/tmp/pd/models.txt")
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


def counts():
    return {k: len(getattr(bpy.data, k)) for k in
            ("objects", "meshes", "materials", "images", "collections")}


em = pkg()
PD = sys.modules[em.__name__ + ".sync_manager.prepare_diagnosis"]
from s3dgraphy.resources import use_profiles as UP  # noqa: E402

# ── the graph: the copy of the em.json, the original row never touched
scene = bpy.context.scene
emt = scene.em_tools
emt.graphml_files.clear()
row = emt.graphml_files.add()
row.name = "TempluMare_v5"
row.graphml_path = os.path.join(PROJECT, "EM", "TempluMare_v5.em.json")
emt.active_file_index = 0
t0 = time.time()
getattr(bpy.ops, "import").em_emjson(file_index=0)
print(f"[SMOKE] graph loaded in {time.time() - t0:.1f} s")
ok_graph, graph = em.functions.is_graph_available(bpy.context)
check("the graph of the copy is loaded", ok_graph and graph is not None)

names = [ln.strip() for ln in open(MODELS) if ln.strip()]
objs = [bpy.data.objects[n] for n in names if n in bpy.data.objects]
check("the objects with a version today are in the .blend", len(objs) == len(names),
      f"{len(objs)} of {len(names)}")
for o in bpy.context.view_layer.objects:
    o.select_set(False)
for o in objs:
    o.select_set(True)
bpy.context.view_layer.objects.active = objs[0]
before = counts()

# ── the diagnosis, twice
report = {}
for prof in ("heriverse", "web"):
    t0 = time.time()
    d = PD.diagnose_here(bpy.context, objs, prof)
    report[prof] = {"seconds": round(time.time() - t0, 2),
                    "measure_seconds": PD.LAST.get("measure_seconds"),
                    "totals": d["totals"], "before": d["before"], "after": d["after"],
                    "budget": d["budget"],
                    "duplicates": [(x["copies"], x["meshes"], x["triangles"]) for x in d["duplicates"]],
                    "peaks": len(d["peaks"]),
                    "rows": [{k: r.get(k) for k in ("id", "kind", "problem", "action", "checked",
                                                     "available", "why")}
                             | {"effect": r["effect"]} for r in d["improvements"]],
                    "lines": d["lines"]}
    for ln in d["lines"]:
        print(f"[SMOKE] {prof}: {ln}")
again = PD.diagnose_here(bpy.context, objs, "web")
check("the diagnosis is the same asked twice",
      json.dumps({k: again[k] for k in ("totals", "before", "after")}, sort_keys=True)
      == json.dumps({k: report["web"][k] for k in ("totals", "before", "after")}, sort_keys=True))
check("copies found: the columns", sum(c for c, _m, t in report["web"]["duplicates"] if t > 50000) >= 50,
      report["web"]["duplicates"][:4])
check("web: the columns are peaks (over 25 k) with a decimation row",
      any(r["kind"] == "decimate" and r["available"] for r in report["web"]["rows"]))
check("heriverse: no decimation, no Draco (Q5)",
      not any(r["kind"] in ("decimate",) for r in report["heriverse"]["rows"])
      and not any(r["id"].startswith("geometry:") and r["checked"] for r in report["heriverse"]["rows"]))
check(".blend unchanged by the diagnosis", counts() == before, f"{before} -> {counts()}")

# ── applied, through the operator
folder = UP.versions_folder(bpy.data.filepath)
applied = {}
for prof in ("heriverse", "web"):
    d = PD.diagnose_here(bpy.context, objs, prof)
    ids = [r["id"] for r in d["improvements"] if r.get("checked") and r.get("available", True)]
    t0 = time.time()
    r = bpy.ops.em.prepare_diagnose(profile=prof, scope="SELECTED", model="TempluMare_SB",
                                    level=PD.level_for(x["kind"] for x in d["improvements"]
                                                       if x["id"] in ids),
                                    checked_ids=",".join(ids))
    secs = round(time.time() - t0, 1)
    out = dict(PD.LAST.get("applied") or {})
    check(f"{prof}: applied", r == {"FINISHED"} and out.get("entry"), f"{r} {secs} s")
    if not out.get("entry"):
        continue
    m = UP.measure_gltf(out["entry"])
    applied[prof] = {"entry": out["entry"], "seconds": secs, "bytes": out["bytes"],
                     "files": len(out["files"]), "measured": out["measured"],
                     "instanced": out["instanced"], "decimated": out["decimated"],
                     "resized": out["resized"], "rows": ids, "warnings": out["warnings"],
                     "registered": {k: v for k, v in (out.get("registered") or {}).items()
                                    if k in ("stamp", "resource_id", "missing")},
                     "estimate_after": {k: d["after"][k] for k in ("download_bytes", "gpu_bytes",
                                                                  "triangles", "triangles_stored")}}
    print(f"[SMOKE] {prof}: {json.dumps(applied[prof], default=str)[:600]}")
    check(f"{prof}: the copies are instances in the file",
          m["instancing"] and out["instanced"] >= 50, f"{out['instanced']} instances")
    check(f"{prof}: stamped", bool(UP.sidecars(out["entry"])["stamp"]),
          UP.sidecars(out["entry"]))
    rid = (out.get("registered") or {}).get("resource_id")
    check(f"{prof}: registered in the graph", rid and graph.find_node_by_id(rid) is not None, rid)
    try:
        r2 = bpy.ops.em.prepare_diagnose(profile=prof, scope="SELECTED", model="TempluMare_SB",
                                     level=UP.parse_version_name(
                                         os.path.basename(os.path.dirname(out["entry"]))
                                         if out["entry"].endswith(".gltf")
                                         else os.path.basename(out["entry"]))["level"],
                                     checked_ids=",".join(ids))
    except RuntimeError as exc:          # an operator's ERROR report, in -b
        r2 = {"CANCELLED"} if "already in" in str(exc) else {str(exc)}
    check(f"{prof}: not written again over the file without «replace»", r2 == {"CANCELLED"})
check(".blend left as it was after applying", counts() == before, f"{before} -> {counts()}")
web = applied.get("web") or {}
check("web: columns decimated with a normal map",
      web.get("decimated", 0) >= 1 and web.get("measured", {}).get("compression") == "draco",
      web.get("measured"))

# ── the versions on disk, and their removal
rows = UP.list_versions(folder)
check("versions/ lists both", {r["destination"] for r in rows} >= {"web", "aton-heriverse"},
      [r["name"] for r in rows])
with open(os.path.join(OUT, "versions.json"), "w") as f:
    json.dump([{k: r[k] for k in ("name", "profile", "triangles", "bytes", "stamp", "textures")}
               for r in rows], f, indent=1, default=str)
# kept for the report: a copy of what was made, before the removal
import shutil  # noqa: E402
keep = os.path.join(OUT, "made")
shutil.rmtree(keep, ignore_errors=True)
shutil.copytree(folder, keep)
web_name = next(r["name"] for r in rows if r["destination"] == "web")
res_web = (applied.get("web") or {}).get("registered", {}).get("resource_id")
r = bpy.ops.em.asset_remove_versions(mode="DISK", names=web_name)
check("Versions on disk… removes the web version", r == {"FINISHED"})
check("its files are gone, the other stays",
      not any(x["name"] == web_name for x in UP.list_versions(folder))
      and any(x["destination"] == "aton-heriverse" for x in UP.list_versions(folder)))
check("its node left the graph", res_web and graph.find_node_by_id(res_web) is None)

with open(os.path.join(OUT, "smoke.json"), "w") as f:
    json.dump({"diagnosis": report, "applied": applied}, f, indent=1, default=str)
print("[SMOKE] ALL PASS" if not FAILURES else f"[SMOKE] FAILED: {FAILURES}")
sys.exit(1 if FAILURES else 0)
