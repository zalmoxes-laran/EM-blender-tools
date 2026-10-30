"""Headless smoke · MICRO-BLEND-OFFICINA-1 (E.D., 30 Oct 2026) on a COPY of
Templu Mare, Blender 5.2, EM Tools as the working copy::

    BO_PROJECT=/tmp/officina/T PYTHONPATH=~/Documents/GitHub/s3Dgraphy/src \\
    BLENDER_USER_RESOURCES=<profile> \\
    "/Applications/Blender 520.app/Contents/MacOS/Blender" -b --python-use-system-env \\
        /tmp/officina/T/SB/GreatTemple_2026_v2.blend \\
        --python tests/blender_smoke_blend_officina.py

``BO_PROJECT``: the copy (``SB/GreatTemple_2026_v2.blend`` with its em_cache,
``RB/TempluMare_2021.blend``, ``EM/TempluMare_v6_optimized.em.json``). The
.blend as a folder (208 objects, the RB library, the Walls master in
em_cache); «Check against the graph»; «Export as master» of an architrave
(glTF + external textures in SB/Reconstruction II AC/master/, stamped, the
graph's master pointing at it); the mesh changed → ↑; «Register as a
version…» → aligned again; the object deleted → ✗, «Restore from the master»
→ back. The .blend and the em.json are never saved."""
import json
import os
import sys

import bpy

PROJECT = os.environ.get("BO_PROJECT", "/tmp/officina/T")
OUT = os.environ.get("BO_OUT", "/tmp/officina/smoke-out")
OBJ = "Architrave_1_BAKE_SM_Architrave_1_BAKE"
FAILURES = []
os.makedirs(OUT, exist_ok=True)


def check(label, condition, detail=""):
    print(f"[SMOKE] {'PASS' if condition else 'FAIL'}: {label} {detail}")
    if not condition:
        FAILURES.append(label)
    return condition


def pkg():
    for name in sys.modules:
        if name.endswith(".sync_manager.blend_officina"):
            return sys.modules[name.rsplit(".sync_manager.blend_officina", 1)[0]]
    raise RuntimeError("EM Tools (with blend_officina) is not loaded")


em = pkg()
BO = sys.modules[em.__name__ + ".sync_manager.blend_officina"]
from s3dgraphy.resources import blend_folder as BF  # noqa: E402

emjson = os.path.join(PROJECT, "EM", "TempluMare_v6_optimized.em.json")
before_bytes = open(emjson, "rb").read()
blend_mtime = os.path.getmtime(bpy.data.filepath)

# ── the .blend as a folder
inv = BO.inventory()
json.dump(inv, open(os.path.join(OUT, "inventory.json"), "w"), indent=1, default=str)
c = inv["counts"]
check("inventory: every object", c["objects"] == len(bpy.data.objects), c["objects"])
check("inventory: two libraries, none missing", c["libraries"] == 2 and c["libraries_missing"] == 0, c)
check("inventory: packed textures counted", c["textures"]["packed"] >= 50, c["textures"])
by = {o["name"]: o for o in inv["objects"]}
check("the RB meshes come from ../RB/TempluMare_2021.blend",
      by["ME_PODIO_LOD1"]["source_rel"] == "../RB/TempluMare_2021.blend", by["ME_PODIO_LOD1"]["source_rel"])
check("the Walls mesh comes from em_cache",
      by["Walls_BAKE_SM_Walls_BAKE"]["source_rel"].startswith("em_cache/local/"),
      by["Walls_BAKE_SM_Walls_BAKE"]["source_rel"])
check("graph properties only (old add-ons' ignored)",
      not any(k in by[OBJ]["props"] for k in ("graswald", "cycles", "CAPObj")), sorted(by[OBJ]["props"]))
check("the proxies are proxies", by["GT16.SU001"]["kind"] == "proxy", by["GT16.SU001"]["kind"])
tr = BF.tree(inv)
check("the tree: collections then libraries",
      any(n["kind"] == "library" and n["name"] == "TempluMare_2021.blend" for n in tr), [n["name"] for n in tr][:8])
check("chase: an RB mesh to its .blend", BF.chase(inv, "ME_PODIO_LOD1")["file"].endswith("RB/TempluMare_2021.blend"))

# ── the graph
scene = bpy.context.scene
emt = scene.em_tools
emt.graphml_files.clear()
row = emt.graphml_files.add()
row.name = "TempluMare_v6"
row.graphml_path = emjson
emt.active_file_index = 0
getattr(bpy.ops, "import").em_emjson(file_index=0)
graph, doc, em_folder = BO.active_graph_doc(bpy.context)
check("the graph of the copy is loaded", graph is not None and em_folder.endswith("/EM"), em_folder)

res = BO.check_here(bpy.context)
json.dump(res, open(os.path.join(OUT, "check1.json"), "w"), indent=1, default=str)
print("[SMOKE] check:", res["sentence"])
st = res["objects"]
check("check: an architrave is aligned, its master inside the .blend", st.get(OBJ) == "aligned", st.get(OBJ))
r_obj = next(r for r in res["rows"] if r["key"] == "object:" + OBJ)
check("… and «Export as master» is proposed", r_obj["action"] == "export_master", r_obj)
check("check: only-here objects exist", res["counts"]["only_here"] > 0, res["counts"])

# the ROOM as source, never resolved here: the last state known, said
rr = BO.check_here(bpy.context, source="room")
check("source room, not resolved: offline, said", rr["offline"] and rr["as_of"] == "never resolved", rr["as_of"])

# ── «Export as master»
obj = bpy.data.objects[OBJ]
out = BO.export_master(bpy.context, graph, obj, emjson)
print("[SMOKE] master:", out)
check("the master is in SB/<Container>/master/", "/SB/Reconstruction II AC/master/" in out["path"], out["path"])
check("glTF with external textures", out["path"].endswith(".gltf") and
      any(f.endswith((".jpg", ".png", ".jpeg")) for f in os.listdir(os.path.dirname(out["path"]))),
      os.listdir(os.path.dirname(out["path"])))
check("stamped", os.path.isfile(out["path"] + ".stamp.json") or out["state"] in ("stamped", "revised"), out["state"])
node = graph.find_node_by_id(out["master_id"])
check("the graph's master points at the file, relative", node is not None and
      node.data.get("url") == out["rel"] and out["rel"].startswith("../SB/"), node.data.get("url") if node else None)
check("the datablock it came from is kept", str(node.data.get("from_datablock") or "").startswith("blend://"))

res = BO.check_here(bpy.context)
r_obj = next(r for r in res["rows"] if r["key"] == "object:" + OBJ)
check("after the export: aligned, nothing proposed", r_obj["state"] == "aligned" and not r_obj["action"], r_obj)

# ── changed in Blender → ↑
obj.data.vertices[0].co.z += 0.5
res = BO.check_here(bpy.context)
check("a vertex moved: ↑ changed here", res["objects"].get(OBJ) == "changed_here", res["objects"].get(OBJ))

# ── «Register as a version…»
v = BO.register_version(bpy.context, graph, obj, emjson)
print("[SMOKE] version:", v)
vn = graph.find_node_by_id(v["version_id"])
check("the version is in the graph", vn is not None)
check("its url relative to the em.json", vn is not None and str(vn.data.get("url") or "").startswith("../SB/"),
      vn.data.get("url") if vn else None)
check("born from the master", any(e.edge_type == "dtc_derived_from" and e.edge_source == v["version_id"]
                                  for e in graph.edges))
res = BO.check_here(bpy.context)
check("after registering: aligned", res["objects"].get(OBJ) == "aligned", res["objects"].get(OBJ))

# ── deleted → ✗, «Restore from the master» → back
master_id = out["master_id"]
for o in list(bpy.data.objects):
    if o.name == OBJ:
        bpy.data.objects.remove(o, do_unlink=True)
res = BO.check_here(bpy.context)
miss = [r for r in res["rows"] if r["kind"] == "resource" and r.get("master") == master_id]
check("deleted: ✗ missing, restore proposed", miss and miss[0]["state"] == "missing"
      and miss[0]["action"] == "restore_from_master", miss[:1])
done = BO.apply_rows(bpy.context, graph, [dict(miss[0], action="restore_from_master", object=OBJ)], emjson)
check("restored from the master", not done["failed"] and OBJ in bpy.data.objects, done)
check("the restored mesh has faces", len(bpy.data.objects[OBJ].data.polygons) > 0)

# ── presence: a background Blender writes none; the rule
check("a background Blender writes no presence", BF.read_session(bpy.data.filepath) is None)
rule = BF.session_state(bpy.data.filepath)
check("the rule: nobody has it open → background", rule["route"] == "background", rule)

# ── the panels: «Asset versions» keeps a status row and «Prepare in EMStudio»;
# the optimisation window's buttons left it, its operators stay registered
class _Lay:
    def __init__(self, out):
        object.__setattr__(self, "_out", out)
    def __setattr__(self, k, v):
        pass
    def __getattr__(self, k):
        return lambda *a, **kw: _Lay(self._out)
    def row(self, *a, **kw): return _Lay(self._out)
    def column(self, *a, **kw): return _Lay(self._out)
    def box(self, *a, **kw): return _Lay(self._out)
    def label(self, text="", **kw): self._out.append(("label", text))
    def operator(self, idname, text=None, **kw):
        self._out.append(("op", idname, text or ""))
        class _Op:
            def __setattr__(s, k, v): pass
        return _Op()


def drawn(cls):
    out = []
    fake = type("F", (object,), {k: v for k, v in vars(cls).items() if callable(v)})()
    fake.layout = _Lay(out)
    try:
        cls.draw(fake, bpy.context)
    except Exception as exc:  # noqa: BLE001
        out.append(("EXC", f"{type(exc).__name__}: {exc}"))
    return out


for o in bpy.context.view_layer.objects:
    o.select_set(False)
bpy.data.objects[OBJ].select_set(True)
bpy.context.view_layer.objects.active = bpy.data.objects[OBJ]
av_panel = drawn(bpy.types.VIEW3D_PT_em_asset_versions)
ops = [r[1] for r in av_panel if r[0] == "op"]
check("Asset versions draws", not any(r[0] == "EXC" for r in av_panel), [r for r in av_panel if r[0] == "EXC"])
check("…«Prepare in EMStudio» and the status row", "em.prepare_in_emstudio" in ops and
      any(r[0] == "label" and "master" in r[1] for r in av_panel), [r for r in av_panel if r[0] == "label"][:3])
check("…the gestures of who models", {"em.blend_register_version", "em.blend_restore_master",
                                      "em.blend_export_master"} <= set(ops), ops)
check("…no more the optimisation window's buttons",
      "em.prepare_diagnose" not in ops and "em.asset_prepare_for_use" not in ops, ops)
check("…whose operators stay registered (headless)",
      hasattr(bpy.ops.em, "prepare_diagnose") and hasattr(bpy.ops.em, "asset_prepare_for_use"))
gi = drawn(bpy.types.VIEW3D_PT_EM_GraphInfo)
check("The graph: «Check against the graph»", any(r[0] == "op" and r[1] == "em.blend_check_graph" for r in gi),
      [r for r in gi if r[0] != "label"][:6])

check("the .blend was not saved", os.path.getmtime(bpy.data.filepath) == blend_mtime)
check("the em.json was not written", open(emjson, "rb").read() == before_bytes)
print(f"[SMOKE] {'ALL PASS' if not FAILURES else 'FAILED: ' + ', '.join(FAILURES)}")
sys.exit(1 if FAILURES else 0)
