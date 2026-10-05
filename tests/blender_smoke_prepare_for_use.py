"""Headless smoke · T-U1, «Prepare for a use…» on ME_PODIO of the COPY of
Templu Mare (never saved), and the Publication Deck offering it to Heriverse. The version's
glb and the asset's library go into the copy's `em_cache/` (a cache, beside
the copy): delete `em_cache/local/versions/ME_PODIO@lod*-web.glb` afterwards.

    PYTHONPATH=~/Documents/GitHub/s3Dgraphy/src \\
    "/Applications/Blender 520.app/Contents/MacOS/Blender" -b --python-use-system-env \\
        ~/Documents/GitHub/_datasets/templu-mare-prove/GreatTemple_2026_v3_multigraph_test_CLAUDE.blend \\
        --python ~/Documents/GitHub/EM-blender-tools/tests/blender_smoke_prepare_for_use.py -- /tmp/tu1

(1) ME_PODIO active, «Prepare for a use…» for the web: decimated to 0.5, the
textures capped at 1024 px, Draco; (2) a version `tier = distribution` with
`use = [web]`, its `lod_level` computed by the chain, the numbers measured,
the `lod_generation` step in the DTC with its technique and parameters;
(3) the Deck lists it ready for Heriverse, and the rule of the versions picks
it for ME_PODIO (H4: no engine package any more).
"""
import importlib
import json
import os
import shutil
import sys
import tempfile

import bpy

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
WORK = ARGS[0] if ARGS else "/tmp/tu1"
FAILURES = []


def check(label, condition, detail=""):
    print(f"[SMOKE] {'PASS' if condition else 'FAIL'}: {label} {detail}")
    if not condition:
        FAILURES.append(label)


shutil.rmtree(WORK, ignore_errors=True)
os.makedirs(WORK)
names = [n for n in sys.modules if n.endswith(".graph_origins") and n.startswith("bl_ext.")]
PKG = names[0].rsplit(".graph_origins", 1)[0]
av = importlib.import_module(PKG + ".sync_manager.asset_versions")
heri = importlib.import_module(PKG + ".publication_deck_ui.heriverse")
scene = bpy.context.scene
row0 = scene.em_tools.graphml_files[0]
src0 = bpy.path.abspath(row0.graphml_path)
if src0.lower().endswith(".graphml"):
    dst0 = os.path.join(tempfile.mkdtemp(prefix="em-u1-"), os.path.basename(src0))
    shutil.copy2(src0, dst0)
    row0.graphml_path = dst0
scene.em_tools.active_file_index = 0
getattr(bpy.ops, "import").em_graphml(graphml_index=0)
from s3dgraphy import api, get_graph  # noqa: E402
graph = get_graph(scene.em_tools.graphml_files[0].name)

obj = bpy.data.objects["ME_PODIO"]
for o in bpy.context.view_layer.objects:
    o.select_set(False)
obj.select_set(True)
bpy.context.view_layer.objects.active = obj

# ── (1) Prepare for a use ──────────────────────────────────────────────────
r = bpy.ops.em.asset_prepare_for_use(use={"web"}, ratio=0.5, max_texture=1024, draco=True)
check("Prepare for a use… (web)", r == {"FINISHED"}, str(r))
out = av.PREPARED
print("[SMOKE] prepared:", {k: out.get(k) for k in ("version_id", "level", "lod_level", "use")})
vid = out.get("version_id")
node = graph.find_node_by_id(vid) if vid else None
data = (node.data or {}) if node is not None else {}

# ── (2) the version, its level, its numbers, its step ──────────────────────
check("a distribution version", data.get("tier") == "distribution", str(data.get("tier")))
check("…for the web", out.get("use") == ["web"], str(out.get("use")))
check("…its lod_level computed by the chain", bool(out.get("lod_level"))
      and str(out["lod_level"]).startswith("lod"), str(out.get("lod_level")))
measures = out.get("measures") or {}
check("…the numbers measured", measures.get("tris_per_m2") is not None, str(measures))
proc = graph.find_node_by_id(out.get("process_id") or "")
pdata = (proc.data or {}) if proc is not None else {}
params = pdata.get("parameters") or {}
print("[SMOKE] step:", {k: pdata.get(k) for k in ("dtc_kind", "technique")}, params)
check("the lod_generation step in the DTC", pdata.get("dtc_kind") == "lod_generation",
      str(pdata.get("dtc_kind")))
check("…with its technique and parameters", pdata.get("technique") == "decimation"
      or params.get("technique") == "decimation", str(pdata.get("technique")))
step = (out.get("step") or {}).get("parameters") or {}
check("…Draco and the textures said", step.get("draco") is True
      and step.get("max_texture_px") == 1024, str(step))
check("the glb was written", os.path.isfile(out.get("glb") or ""), str(out.get("glb")))

# ── (3) the Deck offers it to Heriverse ────────────────────────────────────
scene.em_publication_deck.destinazione = "heriverse"
r = bpy.ops.em.deck_refresh()
deck_mod = importlib.import_module(PKG + ".publication_deck_ui.operators")
esito, _nota = deck_mod._calcola(bpy.context)
row = next((x for x in esito["righe"] if x["id"] == vid), None)
print("[SMOKE] deck row:", row and row.get("pronto_per"))
check("the Deck lists the version", row is not None)
check("…ready for Heriverse", row is not None and (row["pronto_per"].get("heriverse") or {}).get("ok"),
      str(row and row["pronto_per"]))
# H4 (E.D., 5 Oct 2026): no package made by an engine any more — the Deck
# says what the rule of the versions picks (`em.deck_heriverse`), and the
# package on disk is measured by `blender_smoke_heriverse_disk.py`
PH = importlib.import_module(PKG + ".publication_heriverse")
# the copy does not publish ME_PODIO (its RM list row): it is published here,
# in memory, as the Deck's check of what Heriverse finds reads that flag
for r in scene.rm_list:
    if r.name == "ME_PODIO":
        r.is_publishable = True
print("[SMOKE] publishable graphs:", [g for g, _ in heri.publishable_graphs(bpy.context)],
      "· ME_PODIO in the RM list publishable:",
      [r.is_publishable for r in scene.rm_list if r.name == "ME_PODIO"])
plan = heri.make_plan(bpy.context)
print("[SMOKE] plan:", PH.summary(plan))
podio = next((p for p in plan["ready"] if p["object"] == "ME_PODIO"), None)
check("Heriverse will take ME_PODIO's web version", podio is not None
      and podio["use"] == "web" and podio["version_id"] == vid, str(podio))
made = [PH.row_line(p) for p in plan["ready"][:5]]
with open(os.path.join(WORK, "u1.json"), "w") as fh:
    json.dump({"version": vid, "level": out.get("level"), "lod_level": out.get("lod_level"),
               "measures": measures, "step": step, "package": made[:20]}, fh, indent=1, default=str)
print("[SMOKE] RESULT:", "ALL PASS" if not FAILURES else f"FAILED {FAILURES}")
sys.stdout.flush()
sys.exit(0 if not FAILURES else 1)
