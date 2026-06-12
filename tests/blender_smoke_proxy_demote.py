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

# Clean slate: ignore anything persisted in the user's startup scene
strat.units.clear()
scene.em_tools.graphml_files.clear()

# --- 1. graph requirement + selection-driven demote ---------------------------
obj_a = make_mesh("US_TESTA")
add_unit("US_TESTA")
strat.units_index = 0
select_only(obj_a)

# A loaded graph is a requirement: without it the operator must be disabled
check("poll False without a loaded graph", not bpy.ops.em.proxy_demote.poll())

# Register a minimal graph in the s3dgraphy registry (no graph_code, so
# name resolution stays prefix-less) and point the scene at it
from s3dgraphy.graph import Graph
from s3dgraphy.multigraph.multigraph import multi_graph_manager
smoke_graph = Graph(graph_id="smoke_graph")
multi_graph_manager.graphs["smoke_graph"] = smoke_graph
gfile = scene.em_tools.graphml_files.add()
gfile.name = "smoke_graph"
scene.em_tools.active_file_index = 0
check("poll True once a graph is loaded", bpy.ops.em.proxy_demote.poll())

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
check(
    "demoted object selected and active",
    obj_a.select_get() and bpy.context.view_layer.objects.active == obj_a,
)

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

# --- 6. prefixed graph + hidden proxy (real-project scenario) ----------------
# With an active graph code, proxies are named "<CODE>.<node>" and may be
# hidden in the viewport: demote must still resolve them, and must end with
# the object visible, selected and active so the user sees the result.
# Switch the loaded graph to a prefixed one, as after a real import
gfile.graph_code = "GT16"
smoke_graph.attributes["graph_code"] = "GT16"

obj_f = make_mesh("GT16.SU010")
obj_f.hide_set(True)  # buried/hidden proxy, like in real projects
unit_f = add_unit("SU010")
unit_f_index = len(strat.units) - 1
select_only()  # nothing selected: row-button path

result = bpy.ops.em.proxy_demote(node_name="SU010")
check("prefixed demote returns FINISHED", result == {"FINISHED"})
check("prefixed rename", obj_f.name == "GT16.SU010_demoted", f"got '{obj_f.name}'")
check("demoted proxy unhidden", obj_f.visible_get())
check(
    "demoted proxy selected and active",
    obj_f.select_get() and bpy.context.view_layer.objects.active == obj_f,
)
check("prefixed unit icon UNLINKED", strat.units[unit_f_index].icon == "UNLINKED")
check(
    "prefixed magenta applied",
    len(obj_f.data.materials) == 1 and obj_f.data.materials[0].name == "mat_NotInTheMatrix",
)

print(f"[SMOKE] {len(FAILURES)} failure(s)")
sys.exit(1 if FAILURES else 0)
