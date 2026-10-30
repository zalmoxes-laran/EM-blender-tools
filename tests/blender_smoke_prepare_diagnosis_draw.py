"""Headless smoke · MICRO-PREPARA-DIAGNOSI — the two dialogs DRAWN (in -b an
operator runs in EXEC and its dialog is never drawn): «Prepare for a use:
diagnosis…» for the web on Templu Mare's 87 objects, and «Remove versions…» in
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

d = PD.diagnose_here(bpy.context, objs, "web")
rows = [types.SimpleNamespace(row_id=r["id"], kind=r["kind"], problem=r["problem"], action=r["action"],
                              effect=PD.effect_line(r["effect"]), why=r.get("why", ""),
                              available=bool(r.get("available", True)), checked=bool(r.get("checked")))
        for r in d["improvements"]]
OP = next(c for c in PD._CLASSES if getattr(c, "bl_idname", "") == "em.prepare_diagnose")
calls = []
fake = types.SimpleNamespace(layout=Rec(calls), profile="web", scope="SELECTED", rows=rows,
                             model="TempluMare_SB", level="lod1", replace=False, folder="")
fake._folder = lambda: OP._folder(fake)
OP.draw(fake, bpy.context)
text = " | ".join(c for c in calls if c)
print("[SMOKE] diagnosis dialog:", text[:1500])
check("the dialog: totals, budgets, copies, peaks", "87 objects" in text and "copies of" in text
      and "Over the budget per object" in text and "triangles: 3,028,338 of 1,500,000" in text)
check("the dialog: one tick per row, the unavailable say why",
      calls.count("prop:checked") == len(rows) and "gltfpack" in text)
check("the dialog: before → after and the target in versions/",
      "Download 81.3 MB →" in text and "versions/TempluMare_SB@lod1-web.glb" in text)

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
