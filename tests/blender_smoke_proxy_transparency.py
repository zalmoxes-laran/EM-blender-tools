"""Headless smoke · P4 (MICRO pannelli puliti, 6 Oct 2026): the slider «Proxy
Transparency» changes the alpha of the proxies' materials in every display
mode — «select» (the old default, which did nothing), EM, Epochs — and a file
with «select» gets the mode its materials show. A COPY of Templu Mare, never
saved; its first graph loaded from a copy of its file.

    PYTHONPATH=~/Documents/GitHub/s3Dgraphy/src \\
    "/Applications/Blender 520.app/Contents/MacOS/Blender" -b --python-use-system-env \\
        <copy>.blend --python tests/blender_smoke_proxy_transparency.py -- <out.json>
"""
import json
import os
import shutil
import sys
import tempfile

import bpy

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = ARGS[0] if ARGS else "/tmp/proxy_transparency.json"
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append({"check": name, "ok": bool(ok), "detail": detail})
    print(f"[SMOKE] {'PASS' if ok else 'FAIL'} {name} {detail}")


def mod(suffix):
    names = [n for n in sys.modules if n.endswith("." + suffix) and n.startswith("bl_ext.")]
    return sys.modules[names[0]]


fn = mod("EM-blender-tools.functions")  # not 3D-survey-collection's functions
sc = bpy.context.scene
et = sc.em_tools

row0 = et.graphml_files[0]
src = bpy.path.abspath(row0.graphml_path)
if src.lower().endswith(".graphml"):
    dst = os.path.join(tempfile.mkdtemp(prefix="em-p4-"), os.path.basename(src))
    shutil.copy2(src, dst)
    row0.graphml_path = dst
et.active_file_index = 0
getattr(bpy.ops, "import").em_graphml(graphml_index=0)

proxies = fn.proxy_objects(bpy.context)
check("the copy has proxies", len(proxies) > 0, f"{len(proxies)} proxies")


def alphas():
    """The alpha of every material on a proxy: (Principled Alpha, diffuse α)."""
    out = []
    for ob in proxies:
        for slot in ob.material_slots:
            mat = slot.material
            if mat is None:
                continue
            p = next((n for n in (mat.node_tree.nodes if mat.node_tree else [])
                      if n.type == 'BSDF_PRINCIPLED'), None)
            out.append((round(p.inputs['Alpha'].default_value, 3) if p else None,
                        round(mat.diffuse_color[3], 3), mat.blend_method))
    return out


def slide(mode_label):
    et.proxy_display_alpha = 1.0
    before = alphas()
    et.proxy_display_alpha = 0.2
    after = alphas()
    ok = bool(after) and all(a[0] in (None, 0.2) and a[1] == 0.2 and a[2] == 'BLEND'
                             for a in after)
    check(f"slider 1 → 0.2 changes the alpha in mode {mode_label}", ok,
          f"{len(after)} materials · before {sorted(set(before))[:3]} · "
          f"after {sorted(set(after))[:3]} · mode now {et.proxy_display_mode}")


# 1 · the case measured on 5 Oct: the mode «select», materials of EM on the proxies
bpy.ops.emset.emmaterial()
et.proxy_display_mode = "select"
slide("select (old default)")
check("«select» is replaced by the mode the materials show", et.proxy_display_mode == "EM",
      et.proxy_display_mode)

# 2 · EM
bpy.ops.emset.emmaterial()
slide("EM")

# 3 · Epochs
try:
    bpy.ops.emset.epochmaterial()
    slide(et.proxy_display_mode)
except Exception as exc:  # noqa: BLE001
    check("Epochs applied", False, str(exc))

# 4 · inference on the materials
et.proxy_display_mode = "select"
check("the inference reads epochs off the materials",
      fn.infer_display_mode(bpy.context) in ("Epochs", "EM"),
      fn.infer_display_mode(bpy.context))

with open(OUT, "w") as fh:
    json.dump(RESULTS, fh, indent=1)
print("[SMOKE]", "ALL PASS" if all(r["ok"] for r in RESULTS) else "SOME FAIL")
sys.stdout.flush()
os._exit(0)
