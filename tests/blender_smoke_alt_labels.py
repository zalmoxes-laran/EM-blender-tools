"""Headless smoke · A1 in EM Tools: the alternative labels of a unit.

    PYTHONPATH=~/Documents/GitHub/s3Dgraphy/src \\
    "/Applications/Blender 520.app/Contents/MacOS/Blender" -b --python-use-system-env \\
        --python tests/blender_smoke_alt_labels.py

s3Dgraphy's golden (`tests/fixtures/alternative_labels.em.json`, a COPY) is
opened: 1.US10 keeps its label in the list, its line «Also known as» holds the
three labels with their numbering, and the list's search finds it by «1004».
"""
import os
import shutil
import sys
import tempfile

import bpy

FAILURES = []


def check(label, condition, detail=""):
    print(f"[SMOKE] {'PASS' if condition else 'FAIL'}: {label} {detail}")
    if not condition:
        FAILURES.append(label)


src = os.path.expanduser("~/Documents/GitHub/s3Dgraphy/tests/fixtures/alternative_labels.em.json")
path = os.path.join(tempfile.mkdtemp(prefix="em-alt-"), "alternative_labels.em.json")
shutil.copyfile(src, path)
r = getattr(bpy.ops, "import").em_emjson(filepath=path)
check("the golden opens", r == {"FINISHED"}, str(r))
units = bpy.context.scene.em_tools.stratigraphy.units
by = {u.name: u for u in units}
check("1.US10 keeps its own label", "1.US10" in by, str(sorted(by)))
line = by["1.US10"].alt_labels if "1.US10" in by else ""
print("[SMOKE] also known as:", line)
check("its three labels with their numbering", line == "US 1004 (scavo 2013) · A.12 (tesi Demetrescu) · Muro del podio", line)
check("1.US11 has none", by.get("1.US11") is not None and by["1.US11"].alt_labels == "")
from importlib import import_module  # noqa: E402
_pkg = [n for n in sys.modules if n.endswith(".graph_origins") and n.startswith("bl_ext.")][0].rsplit(".", 1)[0]
UL = import_module(_pkg + ".stratigraphy_manager.ui").EM_STRAT_UL_List


class _Probe:
    filter_name = "1004"
    use_filter_invert = False
    bitflag_filter_item = 1 << 30


flags, _order = UL.filter_items(_Probe(), bpy.context, bpy.context.scene.em_tools.stratigraphy, "units")
found = [u.name for u, f in zip(units, flags) if f]
check("the list's search finds 1.US10 by «1004»", found == ["1.US10"], str(found))
print("[SMOKE] RESULT:", "ALL PASS" if not FAILURES else f"FAILED {FAILURES}")
