"""Headless smoke: the three kind drop-downs of the DTC panel are full (VLONG-DEV28/E1).

The defect (dev27 report, part D, «Aperti»): with ``from __future__ import
annotations`` in ``dtc_authoring/properties.py`` the ``items=lambda …`` of the
three EnumProperty were created inside the annotation strings Blender
evaluates, and called at draw time without this module's globals:
``NameError: name '_kind_items' is not defined``, the drop-downs empty.
Measured in Blender 5.2.0 with a module of eight lines: the lambda raises, a
function referenced by name lists its items. The fix is three named functions.

NOT a pytest test (needs bpy) — run it inside Blender with the extension
installed from the built package, in a CLEAN user folder (see
``blender_smoke_dev26.py`` for the two commands).

How a drop-down is COUNTED headless: there is no window to open it in, so the
items are read the way Blender reads them — assigning a value that is not
there makes Blender list the valid ones in the ``TypeError`` — and the draw
function of the panel is run on a stub layout that records what it is asked to
draw. Exits non-zero on failure.
"""
import io
import re
import sys
from contextlib import redirect_stderr

import bpy

FAILURES = []


def check(label, condition, detail=""):
    print(f"[SMOKE] {'PASS' if condition else 'FAIL'}: {label} {detail}")
    if not condition:
        FAILURES.append(label)
    return condition


def addon_module():
    for name in list(sys.modules):
        if name.endswith(".graph_updaters") and name.startswith("bl_ext."):
            return name.rsplit(".", 1)[0]
    return None


pkg = addon_module()
if not check("addon loaded", pkg is not None and hasattr(bpy.context.scene, "em_dtc"),
             f"({pkg}, Blender {bpy.app.version_string})"):
    sys.exit(1)

props_mod = sys.modules[pkg + ".dtc_authoring.properties"]
p = bpy.context.scene.em_dtc


def items_blender_sees(name):
    """The identifiers of a dynamic enum, from Blender's own refusal."""
    try:
        setattr(p, name, "__no_such_kind__")
    except TypeError as exc:
        inside = re.search(r"not found in \((.*)\)", str(exc))
        return re.findall(r"'([^']*)'", inside.group(1)) if inside else []
    return []


err = io.StringIO()
with redirect_stderr(err):
    seen = {name: items_blender_sees(name)
            for name in ("process_kind", "input_kind", "output_kind")}
check("no NameError while Blender evaluates the items", "NameError" not in err.getvalue(),
      err.getvalue().strip()[:200])

from s3dgraphy.utils.utils import get_dtc_kinds  # noqa: E402
vocab = get_dtc_kinds()
for name, axis in (("process_kind", "process"), ("input_kind", "input"), ("output_kind", "output")):
    want = list(vocab.get(axis) or ())
    check(f"{name}: full", len(seen[name]) == len(want) and len(want) > 0,
          f"({len(seen[name])} items, the vocabulary has {len(want)}: {seen[name][:4]}…)")

# the three named functions of the fix, as the installed addon has them
for fn in ("_process_kind_items", "_input_kind_items", "_output_kind_items"):
    got = getattr(props_mod, fn, None)
    check(f"{fn} is a named function", callable(got) and got.__name__ == fn)
    if callable(got):
        rows = got(p, bpy.context)
        check(f"{fn} lists labels", len(rows) > 1 and all(len(r) == 3 for r in rows),
              f"(first: {rows[0]})")


class StubLayout:
    """Records what a draw asks for. Enough of UILayout for draw_dtc_section."""

    def __init__(self, calls):
        self.calls = calls
        self.alert = False
        self.enabled = True

    def _child(self, *a, **k):
        return StubLayout(self.calls)

    box = row = column = split = _child

    def prop(self, data, name, **k):
        self.calls.append(("prop", name))

    def label(self, **k):
        self.calls.append(("label", k.get("text", "")))

    def operator(self, idname, **k):
        self.calls.append(("operator", idname))

        class _Op:
            pass
        return _Op()

    def separator(self, *a, **k):
        pass


ui = sys.modules[pkg + ".dtc_authoring.ui"]
p.show = True
calls = []
with redirect_stderr(err):
    ui.draw_dtc_section(StubLayout(calls), bpy.context)
check("the panel draws", ("prop", "show") in calls, f"({len(calls)} calls)")
check("no NameError while the panel draws", "NameError" not in err.getvalue())

print(f"[SMOKE] {'OK' if not FAILURES else 'FAILED: ' + ', '.join(FAILURES)}")
sys.exit(1 if FAILURES else 0)
