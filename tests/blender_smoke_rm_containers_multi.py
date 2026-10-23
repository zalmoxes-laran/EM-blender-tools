"""Headless smoke · RM containers mandatory, a mesh in several containers, the
containers' default epochs (E.D., 23 Oct 2026), on the COPY of Templu Mare
(never saved; the GraphML row is copied to a temp folder before importing, so
no em.json lands beside the original).

    PYTHONPATH=~/Documents/GitHub/s3Dgraphy/src \\
    "/Applications/Blender 520.app/Contents/MacOS/Blender" -b --python-use-system-env \\
        ~/Documents/GitHub/_datasets/templu-mare-prove/GreatTemple_2026_v3_multigraph_test_CLAUDE.blend \\
        --python ~/Documents/GitHub/EM-blender-tools/tests/blender_smoke_rm_containers_multi.py

(1) no container → «+ to the active epoch» refused; (2) «New container…» with
an epoch, a mesh added → it has the epoch in the scene and in the graph;
(3) the same mesh in a second container with another epoch → in both
containers, both epochs, member of both groups after the before-save
projection; (4) «Apply to its meshes» adds without removing; (5) the RM panel
and the new-container dialog draw without errors.
"""
import importlib
import os
import shutil
import sys
import tempfile
import types

import bpy

FAILURES = []


def check(label, condition, detail=""):
    print(f"[SMOKE] {'PASS' if condition else 'FAIL'}: {label} {detail}")
    if not condition:
        FAILURES.append(label)


names = [n for n in sys.modules if n.endswith(".graph_origins") and n.startswith("bl_ext.")]
PKG = names[0].rsplit(".graph_origins", 1)[0]
cont = importlib.import_module(PKG + ".rm_manager.containers")
gn = importlib.import_module(PKG + ".rm_manager.group_nodes")
rm_ui = importlib.import_module(PKG + ".rm_manager.ui")
cops = importlib.import_module(PKG + ".rm_manager.container_operators")
scene = bpy.context.scene
em = scene.em_tools
row0 = em.graphml_files[0]
src0 = bpy.path.abspath(row0.graphml_path)
if src0.lower().endswith(".graphml"):
    dst0 = os.path.join(tempfile.mkdtemp(prefix="em-cont-"), os.path.basename(src0))
    shutil.copy2(src0, dst0)
    row0.graphml_path = dst0
em.active_file_index = 0
getattr(bpy.ops, "import").em_graphml(graphml_index=0)
from s3dgraphy import get_graph  # noqa: E402
graph = get_graph(em.graphml_files[0].name)
gid = em.graphml_files[0].name

scene.rm_containers.clear()
epochs = em.epochs
E0, E1 = epochs.list[0].name, epochs.list[1].name
print("[SMOKE] epochs:", E0, E1)

bpy.ops.mesh.primitive_cube_add(location=(200, 0, 0))
M = bpy.context.active_object
M.name = "SMOKE_MULTI_A"
bpy.ops.mesh.primitive_cube_add(location=(210, 0, 0))
N = bpy.context.active_object
N.name = "SMOKE_MULTI_B"


def select(*objs):
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]


def on(objs, op, **kw):
    """Run an operator with ``objs`` as the selection (the active first): in
    background mode the selection set with select_set does not always reach
    an operator's context."""
    with bpy.context.temp_override(selected_objects=list(objs), active_object=objs[0],
                                   object=objs[0]):
        try:
            return op(**kw)
        except RuntimeError:
            import traceback
            klass = getattr(cops, op.idname(), None)
            ac = cont.active_container(bpy.context.scene)
            try:
                said = klass.poll(bpy.context) if klass else "?"
            except Exception as exc:  # noqa: BLE001
                said = repr(exc)
            print("[SMOKE] poll says:", said, "active container:", ac and ac.label,
                  [o.name for o in bpy.context.selected_objects],
                  [cont.is_rm_candidate(o) for o in bpy.context.selected_objects])
            traceback.print_exc()
            raise


def epochs_of(obj):
    return [e.epoch for e in obj.EM_ep_belong_ob if e.epoch != "no_epoch"]


def graph_epochs(obj):
    rid = cont.resolve_rm_node_id(graph, obj, scene=scene) or obj.get("em_rm_node_id")
    names_by_id = {n.node_id: n.name for n in graph.nodes if n.node_type == "EpochNode"}
    return sorted(names_by_id[e.edge_target] for e in graph.edges
                  if e.edge_source == rid and e.edge_type in ("has_first_epoch", "survive_in_epoch")
                  and e.edge_target in names_by_id), rid


# ── (1) no container: «+» refused ──────────────────────────────────────────
select(M)
epochs.list_index = 0
try:
    r = on([M], bpy.ops.rm.promote_to_rm, mode="SELECTED")
    check("promote refused without a container", False, str(r))
except RuntimeError as exc:
    check("promote refused without a container", "containers" in str(exc), str(exc)[:120])
check("…the mesh got no epoch", epochs_of(M) == [], str(epochs_of(M)))

# ── (2) a container with its epoch, a mesh joins ──────────────────────────
r = bpy.ops.rmcontainer.create_empty(label="Survey smoke")
check("New container…", r == {"FINISHED"} and scene.rm_containers[-1].label == "Survey smoke",
      str([c.label for c in scene.rm_containers]))
r = bpy.ops.rmcontainer.epoch_add_active()
check("…its epoch", [e.name for e in scene.rm_containers[0].epochs] == [E0])
select(M)
r = on([M], bpy.ops.rmcontainer.add_selected_meshes)
check("mesh added to the container", r == {"FINISHED"}
      and [e.name for e in scene.rm_containers[0].mesh_names] == [M.name])
check("…it has the container's epoch in the scene", epochs_of(M) == [E0], str(epochs_of(M)))
ge, rid = graph_epochs(M)
check("…and in the graph", ge == [E0], f"{rid} {ge}")

# ── (3) the same mesh in a second container ───────────────────────────────
r = bpy.ops.rmcontainer.create_empty(label="Reconstruction smoke")
epochs.list_index = 1
bpy.ops.rmcontainer.epoch_add_active()
select(M)
r = on([M], bpy.ops.rmcontainer.add_selected_to_active)
check("Add selected to this container", r == {"FINISHED"}, str(r))
check("…the mesh is in both containers", cont.containers_of_mesh(scene, M.name) == [0, 1],
      str(cont.containers_of_mesh(scene, M.name)))
check("…with both epochs (first kept first)", epochs_of(M) == [E0, E1], str(epochs_of(M)))
ge, rid = graph_epochs(M)
check("…both in the graph", ge == sorted([E0, E1]), str(ge))
cont.project_containers_before_save(bpy.context, [gid])
groups = gn.groups_of_member(graph, rid)
check("member of both groups after the before-save projection", len(groups) == 2, str(groups))

# ── (4) apply adds, never removes ─────────────────────────────────────────
scene.rm_containers_index = 0
select(N)
on([N], bpy.ops.rmcontainer.add_selected_meshes)
check("a second mesh joins with the container's epoch", epochs_of(N) == [E0], str(epochs_of(N)))
epochs.list_index = 1
bpy.ops.rmcontainer.epoch_add_active()
r = bpy.ops.rmcontainer.epochs_apply()
check("Apply to its meshes", r == {"FINISHED"}, str(r))
check("…N gets the new epoch", epochs_of(N) == [E0, E1], str(epochs_of(N)))
check("…M keeps what it had", epochs_of(M) == [E0, E1], str(epochs_of(M)))
bpy.ops.rmcontainer.epoch_remove(index=1)
check("removing an epoch from the container leaves the meshes' epochs",
      epochs_of(N) == [E0, E1] and [e.name for e in scene.rm_containers[0].epochs] == [E0])

# ── (5) the panel and the dialog draw ─────────────────────────────────────
class L:
    def __init__(self):
        self.enabled = True
        self.alert = False
        self.scale_y = 1.0

    def __getattr__(self, name):
        def f(*a, **k):
            if name == "operator":
                return types.SimpleNamespace()
            return L()
        return f


for label, fn in (("RM panel with containers", lambda: rm_ui.VIEW3D_PT_RM_Manager.draw(
                      types.SimpleNamespace(layout=L()), bpy.context)),
                  ("new-container dialog", lambda: cops.RMCONTAINER_OT_create_empty.draw(
                      types.SimpleNamespace(layout=L(), label=""), bpy.context))):
    try:
        fn()
        check(f"{label} draws", True)
    except Exception as exc:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        check(f"{label} draws", False, repr(exc))
scene.rm_containers.clear()
try:
    rm_ui.VIEW3D_PT_RM_Manager.draw(types.SimpleNamespace(layout=L()), bpy.context)
    check("RM panel with no container draws", True)
except Exception as exc:  # noqa: BLE001
    import traceback
    traceback.print_exc()
    check("RM panel with no container draws", False, repr(exc))

print("[SMOKE] RESULT:", "ALL PASS" if not FAILURES else f"FAILED {FAILURES}")
sys.stdout.flush()
sys.exit(0 if not FAILURES else 1)
