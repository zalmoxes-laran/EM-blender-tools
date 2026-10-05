"""Headless smoke · T-U4, «Import from tables» on COPIES (never the originals).

    cp ~/pyarchinit/pyarchinit_DB_folder/pyarchinit_db.sqlite /tmp/tu4/
    PYTHONPATH=~/Documents/GitHub/s3Dgraphy/src \\
    "/Applications/Blender 520.app/Contents/MacOS/Blender" -b --python-use-system-env \\
        --python tests/blender_smoke_import_from_table.py -- /tmp/tu4

(1) the pyArchInit database, filtered on one site, with «also the US
geometries» → a graph in the list, saved as em.json beside the copy, its US
in the stratigraphy list and their geometries in the scene; (2) the
example stratigraphy xlsx of s3Dgraphy through `excel_to_graphml_mapping` (the
xlsx wizard's) → another graph; (3) no trace of the 3D GIS mode.
"""
import json
import os
import shutil
import sys

import bpy

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
WORK = ARGS[0] if ARGS else "/tmp/tu4"
FAILURES = []


def check(label, condition, detail=""):
    print(f"[SMOKE] {'PASS' if condition else 'FAIL'}: {label} {detail}")
    if not condition:
        FAILURES.append(label)


em = bpy.context.scene.em_tools
check("the 3D GIS switch is gone", not hasattr(em, "mode_em_advanced") and not hasattr(bpy.ops.emtools, "switch_mode")
      or "switch_mode" not in dir(bpy.ops.emtools))
check("the old 3D GIS operator is gone", "import_3dgis_database" not in dir(bpy.ops.em))
for f in os.listdir(WORK):
    if f.endswith(".em.json"):
        os.remove(os.path.join(WORK, f))

# ── (1) pyArchInit, one site, with the geometries ──────────────────────────
db = os.path.join(WORK, "pyarchinit_db.sqlite")
em.table_import_type = "pyarchinit"
em.pyarchinit_connection_mode = "sqlite"
em.pyarchinit_db_path = db
em.pyarchinit_mapping = "pyarchinit_us_mapping"
cols = [em.get(f"pyarchinit_filter_{i}_column") for i in range(1, 6)]
print("[SMOKE] filters:", cols)
try:
    em.pyarchinit_filter_1 = "Scavo archeologico"
except Exception as e:  # noqa: BLE001
    print("[SMOKE] filter_1 not settable:", e)
em.pyarchinit_import_geometries = True
georef = bpy.context.scene.em_georef
# Enzo's reader wants EPSG and shift set first (as the panel says): set as a
# person would in Georeferencing — the SRID of the table, its centroid
import importlib  # noqa: E402
_pkg = [n for n in sys.modules if n.endswith(".graph_origins") and n.startswith("bl_ext.")][0].rsplit(".", 1)[0]
_rd = importlib.import_module(_pkg + ".import_operators.pyarchinit_db_reader")
_wkb = importlib.import_module(_pkg + ".import_operators.wkb_parser")
_gg = importlib.import_module(_pkg + ".import_operators.geom_georef")
_conn = _rd.open_readonly(db)
_col, _srid = _rd.detect_geometry_column(_conn)
_polys = []
for _row in _rd.fetch_polygons(_conn, _col, filters={"sito": "Scavo archeologico"}):
    _row["parsed_rings"] = _wkb.parse_wkb(_row["wkb"])
    _polys.append(_row)
_cx, _cy = _gg.compute_centroid(_polys)
georef.epsg = str(_srid)
georef.shift_x, georef.shift_y = _cx, _cy
print("[SMOKE] georef set:", georef.epsg, round(georef.shift_x, 2), round(georef.shift_y, 2), len(_polys), "polygons")
before_objs = set(bpy.data.objects.keys())
r = bpy.ops.em.import_from_table()
check("New graph from the table (pyArchInit) finished", r == {"FINISHED"}, str(r))
row = em.graphml_files[em.active_file_index] if len(em.graphml_files) else None
check("a row in the graphs list", row is not None, row and f"{row.name} {row.graph_code} {row.graphml_path}")
if row is not None:
    path = row.graphml_path
    check("saved as em.json beside the copy", path.endswith(".em.json") and os.path.dirname(path) == WORK
          and os.path.isfile(path), path)
    check("the row knows its file", getattr(row, "origin_kind", "FILE") == "FILE")
    with open(path) as fh:
        doc = json.load(fh)
    graphs = doc.get("graphs") or {}
    check("the em.json holds that graph", row.name in graphs, str(list(graphs)))
    units = len(em.stratigraphy.units)
    check("its US are in the stratigraphy list", units > 10, f"{units} units")
    check("the graph code says the site", "Scavo_archeologico" in row.graph_code, row.graph_code)
new_objs = set(bpy.data.objects.keys()) - before_objs
check("their geometries are in the scene", len(new_objs) > 10, f"{len(new_objs)} new objects, e.g. {sorted(new_objs)[:4]}")
# N1 (5 Oct 2026): the US keep the label of the mapping («1.US10») and the
# geometries find them through the adapter (pyarchinit_us_adapter), Enzo's
# reader unchanged. Measured: every polygon of the site on its US.
orphans = sorted(n for n in new_objs if n.startswith("orphan_"))
linked = [n for n in new_objs if not n.startswith("orphan_")]
print(f"[SMOKE] INFO: geometries linked to their US: {len(linked)} objects, "
      f"{len(orphans)} orphan polygons {orphans[:6]}")
_polys_on_us = len(_polys) - len(orphans)
check("every polygon of the site finds its US (N1)", len(orphans) == 0 and len(linked) > 0,
      f"{_polys_on_us} of {len(_polys)} polygons, {len(linked)} objects")
_names = sorted(linked)[:3]
check("the US keep the label of the mapping", all(".US" in n or ".USM" in n for n in linked), str(_names))

# ── (2) an xlsx through a mapping ───────────────────────────────────────────
src = os.path.expanduser("~/Documents/GitHub/s3Dgraphy/example_stratigraphy.xlsx")
xlsx = os.path.join(WORK, "example_stratigraphy.xlsx")
shutil.copyfile(src, xlsx)
em.table_import_type = "emdb_xlsx"
em.emdb_xlsx_file = xlsx
em.emdb_mapping = "excel_to_graphml_mapping"
n_rows = len(em.graphml_files)
r = bpy.ops.em.import_from_table()
check("New graph from the table (xlsx + mapping) finished", r == {"FINISHED"}, str(r))
check("a second graph in the list", len(em.graphml_files) == n_rows + 1, f"{n_rows} → {len(em.graphml_files)}")
row2 = em.graphml_files[em.active_file_index]
check("saved as example_stratigraphy.em.json", row2.graphml_path == os.path.join(WORK, "example_stratigraphy.em.json"),
      row2.graphml_path)
again = bpy.ops.em.import_from_table()
check("importing it again never overwrites: _2", em.graphml_files[em.active_file_index].graphml_path.endswith(
    "example_stratigraphy_2.em.json") if again == {"FINISHED"} else False,
      em.graphml_files[em.active_file_index].graphml_path)

# ── (3) no 3dgis_graph ──────────────────────────────────────────────────────
from s3dgraphy.multigraph.multigraph import multi_graph_manager  # noqa: E402
check("no graph called 3dgis_graph", "3dgis_graph" not in multi_graph_manager.graphs, str(list(multi_graph_manager.graphs)))
print("[SMOKE] RESULT:", "ALL PASS" if not FAILURES else f"FAILED {FAILURES}")
sys.stdout.flush()
