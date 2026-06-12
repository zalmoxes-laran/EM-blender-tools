"""Headless smoke test for the em.proxy_demote operator.

NOT a pytest test (needs bpy) — run it inside Blender with the EM-tools
extension enabled:

    /Applications/Blender\\ 510.app/Contents/MacOS/Blender --background \\
        --python tests/blender_smoke_proxy_demote.py

Builds a minimal in-memory scenario (no files are read or written) and
exercises the three resolution paths: selection-driven, explicit
node_name (Stratigraphy Manager row button), and batch multi-selection.
Exits non-zero on failure.
"""
import sys
import bpy

FAILURES = []


def check(label, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print(f"[SMOKE] {status}: {label} {detail}")
    if not condition:
        FAILURES.append(label)


def make_mesh(name):
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def add_unit(name, icon="LINKED"):
    strat = bpy.context.scene.em_tools.stratigraphy
    u = strat.units.add()
    u.name = name
    u.icon = icon
    return u


def select_only(*objs):
    for o in bpy.context.scene.objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    if objs:
        bpy.context.view_layer.objects.active = objs[0]


# --- 0. addon / operator presence -------------------------------------------
check("scene.em_tools exists", hasattr(bpy.context.scene, "em_tools"))
has_op = hasattr(bpy.ops.em, "proxy_demote")
check("em.proxy_demote registered", has_op)
if not has_op or not hasattr(bpy.context.scene, "em_tools"):
    print("[SMOKE] aborting: addon not loaded")
    sys.exit(1)

rna = bpy.ops.em.proxy_demote.get_rna_type()
check("F3 label", rna.name == "Demote Proxy from Stratigraphic Node", f"got '{rna.name}'")
check("tooltip mentions Demote proxy", rna.description.startswith("Demote proxy"))

scene = bpy.context.scene
strat = scene.em_tools.stratigraphy

# --- 1. selection-driven demote (single) -------------------------------------
obj_a = make_mesh("US_TESTA")
add_unit("US_TESTA")
strat.units_index = 0
select_only(obj_a)

result = bpy.ops.em.proxy_demote()
check("selection demote returns FINISHED", result == {"FINISHED"})
check("object renamed with suffix", obj_a.name == "US_TESTA_demoted", f"got '{obj_a.name}'")
check(
    "unlinked material applied",
    len(obj_a.data.materials) == 1 and obj_a.data.materials[0].name == "mat_NotInTheMatrix",
    f"got {[m.name if m else None for m in obj_a.data.materials]}",
)
check("list icon flipped to UNLINKED", strat.units[0].icon == "UNLINKED")
check("mesh data intact", obj_a.data is not None and obj_a.type == "MESH")

# --- 2. explicit node_name (Stratigraphy Manager row button) -----------------
obj_b = make_mesh("US_TESTB")
add_unit("US_TESTB")
select_only()  # nothing selected: must resolve from the node name

result = bpy.ops.em.proxy_demote(node_name="US_TESTB")
check("node_name demote returns FINISHED", result == {"FINISHED"})
check("node_name demote renamed object", obj_b.name == "US_TESTB_demoted", f"got '{obj_b.name}'")

# --- 3. batch demote of a multi-selection ------------------------------------
obj_c = make_mesh("US_TESTC")
obj_d = make_mesh("US_TESTD")
add_unit("US_TESTC")
add_unit("US_TESTD")
select_only(obj_c, obj_d)

result = bpy.ops.em.proxy_demote()
check("batch demote returns FINISHED", result == {"FINISHED"})
check(
    "both proxies demoted",
    obj_c.name == "US_TESTC_demoted" and obj_d.name == "US_TESTD_demoted",
    f"got '{obj_c.name}', '{obj_d.name}'",
)

# --- 4. nothing bound: graceful CANCELLED ------------------------------------
free_obj = make_mesh("temporary_item")
select_only(free_obj)
strat.units_index = 0  # row whose proxy is already demoted

result = bpy.ops.em.proxy_demote()
check("unbound selection cancels gracefully", result == {"CANCELLED"})
check("free object untouched", free_obj.name == "temporary_item")

# --- 5. name collision: Blender dedups ---------------------------------------
obj_e = make_mesh("US_TESTE")
make_mesh("US_TESTE_demoted")  # occupy the target name
add_unit("US_TESTE")
select_only(obj_e)

result = bpy.ops.em.proxy_demote()
check(
    "collision handled by Blender dedup",
    result == {"FINISHED"} and obj_e.name.startswith("US_TESTE_demoted."),
    f"got '{obj_e.name}'",
)

print(f"[SMOKE] {len(FAILURES)} failure(s)")
sys.exit(1 if FAILURES else 0)
