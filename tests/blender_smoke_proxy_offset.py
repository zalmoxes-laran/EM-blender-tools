"""Headless smoke · T-U2 on the COPY of Templu Mare (never saved).

    PYTHONPATH=~/Documents/GitHub/s3Dgraphy/src \\
    "/Applications/Blender 520.app/Contents/MacOS/Blender" -b --python-use-system-env \\
        <copy>.blend --python tests/blender_smoke_proxy_offset.py

The old inflation is gone; the copy's 61 Solidify «_inflate» modifiers are
removed by the panel's button; «Offset proxy» on one proxy moves its vertices
1 cm along the normals (measured on the evaluated mesh), the mesh itself is
untouched; the distance moves every offset proxy; «All proxies» reaches the
stratigraphy list; «Back on the surface» removes it.
"""
import sys

import bpy

FAILURES = []


def check(label, condition, detail=""):
    print(f"[SMOKE] {'PASS' if condition else 'FAIL'}: {label} {detail}")
    if not condition:
        FAILURES.append(label)


for old in ("proxy_add_inflate", "proxy_activate_inflate", "proxy_deactivate_inflate",
            "proxy_remove_inflate", "proxy_inflate_all"):
    check(f"em.{old} is gone", old.upper() not in {c.__name__.upper() for c in bpy.types.Operator.__subclasses__()}
          and not any(getattr(c, "bl_idname", "") == f"em.{old}" for c in bpy.types.Operator.__subclasses__()))
check("the panel of the inflation is gone", not hasattr(bpy.types, "VIEW3D_PT_ProxyInflatePanel"))
check("«Offset proxy» is there", hasattr(bpy.types, "VIEW3D_PT_proxy_offset"))
scene = bpy.context.scene
check("the distance defaults to 1 cm", abs(scene.em_tools.proxy_offset_distance - 0.01) < 1e-9,
      str(scene.em_tools.proxy_offset_distance))

r = bpy.ops.em.proxy_old_inflate_remove()
left = sum(1 for o in bpy.data.objects for m in o.modifiers if m.name.endswith("_inflate"))
check("the old inflation is removed from the copy", r == {"FINISHED"} and left == 0, f"left {left}")

obj = bpy.data.objects["GT16.USV140"]
before = [v.co.copy() for v in obj.data.vertices]
for o in bpy.context.view_layer.objects:
    o.select_set(False)
obj.select_set(True)
bpy.context.view_layer.objects.active = obj
r = bpy.ops.em.proxy_offset(scope="ACTIVE")
check("Offset proxy finished", r == {"FINISHED"}, str(r))
mod = obj.modifiers.get("EM offset")
check("one Displace «EM offset» along the normals", mod is not None and mod.type == 'DISPLACE'
      and mod.direction == 'NORMAL', str(mod))


def moved(o):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = o.evaluated_get(dg).to_mesh()
    mw = o.matrix_world
    d = [((mw @ a.co) - (mw @ b)).length for a, b in zip(ev.vertices, before)]
    o.evaluated_get(dg).to_mesh_clear()
    return sorted(d)[len(d) // 2]


m = moved(obj)
check("the evaluated vertices moved 1 cm", abs(m - 0.01) < 0.002, f"median {m:.4f} m")
check("the mesh itself is untouched", all((v.co - b).length < 1e-9 for v, b in zip(obj.data.vertices, before)))
scene.em_tools.proxy_offset_distance = 0.005
m = moved(obj)
check("changing the distance moves the offset proxy", abs(m - 0.005) < 0.001, f"median {m:.4f} m")
r = bpy.ops.em.proxy_offset(scope="ALL")
n = sum(1 for o in bpy.data.objects if o.modifiers.get("EM offset"))
check("with no graph, All proxies takes the «Proxy» collection", r == {"FINISHED"} and n > 30, f"{n} offset")
bpy.ops.em.proxy_offset_remove(scope="ALL")
# G1 · loading the GraphML writes an em.json BESIDE it: the GraphML of the
# copy's slot 0 is in E.D.'s examples, so it is copied to a temporary folder
# first and the slot points at the copy (the .blend is not saved)
import os as _os, shutil as _shutil, tempfile as _tempfile  # noqa: E401,E402
_row0 = bpy.context.scene.em_tools.graphml_files[0]
_src0 = bpy.path.abspath(_row0.graphml_path)
if _src0.lower().endswith(".graphml"):
    _dst0 = _os.path.join(_tempfile.mkdtemp(prefix="em-smoke-"), _os.path.basename(_src0))
    _shutil.copy2(_src0, _dst0)
    _row0.graphml_path = _dst0
scene.em_tools.active_file_index = 0
getattr(bpy.ops, "import").em_graphml(graphml_index=0)
units = len(scene.em_tools.stratigraphy.units)
r = bpy.ops.em.proxy_offset(scope="ALL")
n = sum(1 for o in bpy.data.objects if o.modifiers.get("EM offset"))
check("with the graph, All proxies reaches the stratigraphy list", r == {"FINISHED"} and n > 30,
      f"{n} offset, {units} units")
r = bpy.ops.em.proxy_offset_remove(scope="ALL")
n = sum(1 for o in bpy.data.objects if o.modifiers.get("EM offset"))
check("Back on the surface for all", r == {"FINISHED"} and n == 0, f"{n} left")

print("[SMOKE] RESULT:", "ALL PASS" if not FAILURES else f"FAILED {FAILURES}")
sys.stdout.flush()
