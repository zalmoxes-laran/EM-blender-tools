"""Headless smoke · MICRO-PREPARA-DIAGNOSI — the two dialogs DRAWN (in -b an
operator runs in EXEC and its dialog is never drawn): «Prepare for a use:
diagnosis…» for mobile webXR on Templu Mare's 87 objects (its grid by group,
the groups opened, their rows' parameters — MICRO-PREPARA-RITOCCHI), and «Remove versions…» in
its DISK mode on a versions/ folder. A recording layout stands in for the
region (the same as blender_smoke_graph_delete)::

    PD_MODELS=/tmp/pd/models.txt PD_VERSIONS=/tmp/pd/out/made \\
    PYTHONPATH=~/Documents/GitHub/s3Dgraphy/src BLENDER_USER_RESOURCES=<profile> \\
    "/Applications/Blender 520.app/Contents/MacOS/Blender" -b --python-use-system-env \\
        /tmp/pd/TM/SB/GreatTemple_2026_v2.blend \\
        --python tests/blender_smoke_prepare_diagnosis_draw.py
"""
import os
import sys
import types

import bpy

FAILURES = []


def check(label, condition, detail=""):
    print(f"[SMOKE] {'PASS' if condition else 'FAIL'}: {label} {detail}")
    if not condition:
        FAILURES.append(label)


class Rec:
    def __init__(self, calls):
        self.calls = calls

    def _c(self, *a, **k):
        return Rec(self.calls)

    column = row = box = _c

    def label(self, **k):
        self.calls.append(k.get("text", ""))

    def prop(self, data, name, **k):
        self.calls.append(f"prop:{name}")

    def separator(self, **k):
        pass

    def prop_enum(self, data, name, value, **k):
        self.calls.append(f"enum:{value}")

    def operator(self, idname, **k):
        self.calls.append(f"op:{idname}")
        return types.SimpleNamespace()


pkg = next(n.rsplit(".sync_manager.prepare_diagnosis", 1)[0] for n in sys.modules
           if n.endswith(".sync_manager.prepare_diagnosis"))
PD = sys.modules[pkg + ".sync_manager.prepare_diagnosis"]
AV = sys.modules[pkg + ".sync_manager.asset_versions"]
UP = PD.use_profiles()
names = [ln.strip() for ln in open(os.environ.get("PD_MODELS", "/tmp/pd/models.txt")) if ln.strip()]
objs = [bpy.data.objects[n] for n in names if n in bpy.data.objects]
for o in bpy.context.view_layer.objects:
    o.select_set(False)
for o in objs:
    o.select_set(True)
bpy.context.view_layer.objects.active = objs[0]

d = PD.diagnose_here(bpy.context, objs, "mobile_webxr")
rows = []
for r in d["improvements"]:
    pr = r.get("params") or {}
    rows.append(types.SimpleNamespace(
        row_id=r["id"], kind=r["kind"], group=r.get("group", ""), problem=r["problem"], action=r["action"],
        rationale=r.get("rationale", ""), effect=PD.effect_line(r["effect"]), why=r.get("why", ""),
        available=bool(r.get("available", True)), checked=bool(r.get("checked")),
        separate=bool(r.get("separate")), has_triangles="triangles_to" in pr, has_side="side" in pr,
        has_format="format" in pr, triangles_to=int(pr.get("triangles_to") or 0),
        side=int(pr.get("side") or 0), fmt=pr.get("format") or "jpeg"))
groups = [types.SimpleNamespace(gid=g["id"], label=g["label"], rationale=g["rationale"],
                                available=g["available"], checked=g["checked"], expanded=True)
          for g in d["groups"]]
OP = next(c for c in PD._CLASSES if getattr(c, "bl_idname", "") == "em.prepare_diagnose")
calls = []
fake = types.SimpleNamespace(layout=Rec(calls), profile="mobile_webxr", scope="SELECTED", rows=rows,
                             groups=groups, model="TempluMare_SB", level="", replace=False, folder="",
                             params_json="")
for m in ("_folder", "_checked", "_params", "_estimate"):
    setattr(fake, m, (lambda name: (lambda *a: getattr(OP, name)(fake, *a)))(m))
OP.draw(fake, bpy.context)
text = " | ".join(c for c in calls if c)
print("[SMOKE] diagnosis dialog:", text[:2400])
check("the dialog: what the profile is for, totals, budgets, copies, peaks",
      "phones and stand-alone headsets" in text and "87 objects" in text and "copies of" in text
      and "Over the budget per object" in text and "triangles: 3,028,338 of 500,000" in text)
check("the dialog: the groups with their tick and rationale",
      calls.count("prop:checked") >= len(groups) + len([r for r in rows if r.group != "tileset" and r.kind != "packaging"])
      and "Copies of one mesh → instances" in text and "make_lod_set / rebake_atlas" in text)
check("the dialog: opened, the rows' parameters (triangles, side, format)",
      "prop:triangles_to" in calls and "prop:side" in calls and "prop:fmt" in calls)
check("the dialog: the unavailable say why", "gltfpack" in text)
check("the dialog: before → after and the target in versions/ (level auto: lod0, decimation unticked)",
      "Download" in text and "versions/TempluMare_SB@lod0-mobile.glb" in text)

# «Remove versions…» › Files in versions/
folder = os.environ.get("PD_VERSIONS", "/tmp/pd/out/made")
listed = UP.list_versions(folder)
files = [types.SimpleNamespace(name=r["name"], entry=r["entry"], profile=r["profile"],
                               destination=r["destination"], triangles=int(r["triangles"] or 0),
                               size_mb=round(r["bytes"] / 1048576, 2), files=len(r["files"]),
                               date="2026-10-30 07:30", stamped=bool(r["stamp"]),
                               nodes="x\tTempluMare_SB lod1 for Web", remove=i == 0)
         for i, r in enumerate(listed)]
RM = next(c for c in AV._CLASSES if getattr(c, "bl_idname", "") == "em.asset_remove_versions")
calls = []
fake = types.SimpleNamespace(layout=Rec(calls), mode="DISK", files=files)
fake._draw_disk = lambda col: RM._draw_disk(fake, col)
RM.draw(fake, bpy.context)
text = " | ".join(c for c in calls if c)
print("[SMOKE] versions dialog:", text[:1200])
check("the versions on disk: name, profile, triangles, size, stamp",
      all(f.name in text for f in files) and "MB" in text and "yes" in text, f"{len(files)} rows")
check("the ticked one says its files and its node, and that it cannot be undone",
      "file(s)" in text and "graph: TempluMare_SB lod1 for Web" in text and "cannot be undone" in text)
print("[SMOKE] ALL PASS" if not FAILURES else f"[SMOKE] FAILED: {FAILURES}")
sys.exit(1 if FAILURES else 0)
