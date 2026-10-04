"""Headless smoke · T-U1, ONE change of level on the COPY of Templu Mare.

    PYTHONPATH=~/Documents/GitHub/s3Dgraphy/src \\
    "/Applications/Blender 520.app/Contents/MacOS/Blender" -b --python-use-system-env \\
        <copy>.blend --python tests/blender_smoke_lod_one.py

The same operators (`em.asset_lod_step`, `em.asset_set_level`) as Asset
versions, called the way RM Manager's and Anastylosis's panels call them:
a tile `ME_EST_fr_LOD2` (its LOD0…LOD2 beside it in `RB/TempluMare_2021.blend`)
and an RMSF fragment `ME_TM038` (`ME_TM038_LOD3`, LOD0…LOD3 in
`TM038_semented.blend`) change level; the rows of both lists follow; the old
operators are gone. The .blend is NOT saved.
"""
import importlib
import sys

import bpy

FAILURES = []


def check(label, condition, detail=""):
    print(f"[SMOKE] {'PASS' if condition else 'FAIL'}: {label} {detail}")
    if not condition:
        FAILURES.append(label)


names = [n for n in sys.modules if n.endswith(".graph_origins") and n.startswith("bl_ext.")]
PKG = names[0].rsplit(".graph_origins", 1)[0]
av = importlib.import_module(PKG + ".sync_manager.asset_versions")
scene = bpy.context.scene

for old in ("switch_lod", "batch_switch_lod", "batch_lod_selected", "open_lod_menu"):
    check(f"rm.{old} is gone", not hasattr(bpy.types, "RM_OT_" + old))
    check(f"anastylosis.{old} is gone", not hasattr(bpy.types, "ANASTYLOSIS_OT_" + old))
check("anastylosis.open_linked_file stays", hasattr(bpy.types, "ANASTYLOSIS_OT_open_linked_file"))

# ── the tile, from RM Manager's row (scope OBJECT) ──────────────────────────
tile = bpy.data.objects["ME_EST_fr_LOD2"]
levels = av.all_levels(tile)
check("the tile has LOD0…LOD2 from its library", sorted(levels) == ["LOD0", "LOD1", "LOD2"], str(sorted(levels)))
rm_item = next(it for it in scene.rm_list if it.name == "ME_EST_fr_LOD2")
tris = {}
r = bpy.ops.em.asset_lod_step(direction=-1, scope="OBJECT", object_name="ME_EST_fr_LOD2")
check("◂ LOD from the RM row finished", r == {"FINISHED"}, str(r))
check("the tile shows LOD1", tile.data.name == "ME_EST_fr_LOD1", tile.data.name)
check("…and its name follows", tile.name == "ME_EST_fr_LOD1", tile.name)
check("the RM row follows it", rm_item.name == "ME_EST_fr_LOD1" and rm_item.active_lod == 1,
      f"{rm_item.name} {rm_item.active_lod}")
tris["LOD1"] = len(tile.data.polygons)
bpy.ops.em.asset_lod_step(direction=1, scope="OBJECT", object_name=tile.name)
tris["LOD2"] = len(tile.data.polygons)
check("LOD ▸ goes back to LOD2", tile.data.name == "ME_EST_fr_LOD2", tile.data.name)
check("LOD ▸ is the lighter one", tris["LOD2"] < tris["LOD1"], str(tris))

# ── the same tile from Asset versions (scope SELECTED, the default) ─────────
for o in bpy.context.view_layer.objects:
    o.select_set(False)
tile.select_set(True)
bpy.context.view_layer.objects.active = tile
r = bpy.ops.em.asset_set_level(level="LOD0")
check("Show level LOD0 from Asset versions finished", r == {"FINISHED"}, str(r))
check("the tile shows LOD0", tile.data.name == "ME_EST_fr_LOD0" and tile.name == "ME_EST_fr_LOD0",
      f"{tile.name} {tile.data.name}")
check("the RM row says 0", rm_item.active_lod == 0 and rm_item.name == tile.name)
bpy.ops.em.asset_set_level(level="LOD2", scope="OBJECT", object_name=tile.name)

# ── the whole RM list ───────────────────────────────────────────────────────
others = [bpy.data.objects[n] for n in ("ME_EST_bk_LOD2", "ME_INT_L_LOD2")]
r = bpy.ops.em.asset_lod_step(direction=-1, scope="RM_LIST")
check("◂ LOD on the whole RM list finished", r == {"FINISHED"}, str(r))
check("the other tiles moved too", all(o.data.name.endswith("_LOD1") for o in others),
      str([o.data.name for o in others]))
bpy.ops.em.asset_lod_step(direction=1, scope="RM_LIST")

# ── the RMSF fragment, from Anastylosis's row ───────────────────────────────
frag = bpy.data.objects["ME_TM038"]
an_item = next(it for it in scene.em_tools.anastylosis.list if it.name == "ME_TM038")
check("the fragment has LOD0…LOD3", sorted(av.all_levels(frag)) == ["LOD0", "LOD1", "LOD2", "LOD3"],
      str(sorted(av.all_levels(frag))))
r = bpy.ops.em.asset_set_level(level="LOD1", scope="OBJECT", object_name="ME_TM038")
check("LOD1 from the Anastylosis row finished", r == {"FINISHED"}, str(r))
check("the fragment shows LOD1, its name stays", frag.data.name == "ME_TM038_LOD1" and frag.name == "ME_TM038",
      f"{frag.name} {frag.data.name}")
check("the Anastylosis row says 1", an_item.active_lod == 1, str(an_item.active_lod))
r = bpy.ops.em.asset_lod_step(direction=1, scope="ANASTYLOSIS")
check("LOD ▸ on the whole Anastylosis list finished", r == {"FINISHED"}, str(r))
check("the fragment went to LOD2", frag.data.name == "ME_TM038_LOD2", frag.data.name)
# the fallback: LOD4 is not there, LOD3 is shown and said
r = bpy.ops.em.asset_set_level(level="LOD4", scope="OBJECT", object_name="ME_TM038")
check("LOD4, missing, shows the nearest heavier LOD3", frag.data.name == "ME_TM038_LOD3", frag.data.name)
check("…and the row says 3", an_item.active_lod == 3)
# a level nobody has is refused
try:
    r = bpy.ops.em.asset_set_level(level="master", scope="OBJECT", object_name="ME_TM038")
except RuntimeError as e:   # headless, an operator's ERROR report is raised
    r = str(e)
check("a level the fragment does not have is refused, saying which", "no level master for ME_TM038" in str(r), str(r))

# ── the panels' column, without touching bpy.data ───────────────────────────
check("the panel lists the tile's levels", av.levels_to_draw(tile) == ["LOD0", "LOD1", "LOD2"],
      str(av.levels_to_draw(tile)))
check("the list column counts them", av.level_summary(frag) == (4, 3), str(av.level_summary(frag)))

print("[SMOKE] RESULT:", "ALL PASS" if not FAILURES else f"FAILED {FAILURES}")
