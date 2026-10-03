"""Headless smoke · T-M1, the second half: an existing .blend keeps loading.

NOT a pytest test. Open a .blend and read its graph tree:

    "/Applications/Blender 520.app/Contents/MacOS/Blender" -b <file.blend> \\
        --python tests/blender_smoke_multigraph_reopen.py -- <branches> [legacy]

* `<branches>` — how many branches the tree must have;
* `legacy` — the rows were written by an older EMtools (no origin recorded):
  their origin must come from their `graphml_path`, unchanged.

Read-only: nothing is saved.
"""
import os
import sys

import bpy

FAILURES = []


def check(label, condition, detail=""):
    print(f"[SMOKE] {'PASS' if condition else 'FAIL'}: {label} {detail}")
    if not condition:
        FAILURES.append(label)


args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
want = int(args[0]) if args else 1
legacy = "legacy" in args

names = [n for n in sys.modules if n.endswith(".graph_origins") and n.startswith("bl_ext.")]
if not names:
    print("[SMOKE] aborting: graph_origins not loaded")
    sys.exit(1)
origins = sys.modules[names[0]]

em = bpy.context.scene.em_tools
rows = list(em.graphml_files)
tree = origins.tree(rows, abspath=bpy.path.abspath)
for origin, ix in tree:
    print(f"[SMOKE] branch {origin.kind} {origin.label!r} → "
          f"{[rows[i].graph_code or rows[i].name for i in ix]}")
check(f"{want} branch(es)", len(tree) == want, str(len(tree)))
if legacy:
    check("no origin recorded on the rows (an older .blend)",
          all(not r.origin_kind and not r.origin_path for r in rows))
    check("each origin is the row's own file",
          all(origins.origin_of(r, abspath=bpy.path.abspath).path
              == os.path.normpath(bpy.path.abspath(r.graphml_path)) for r in rows))
else:
    check("origins recorded on the rows",
          all(r.origin_kind == "FILE" and r.origin_path for r in rows))
    check("the aligned graph remembers what was applied",
          any(r.geo_applied and r.geo_note for r in rows))


# The panels cannot draw in -b (no window); a layout that RECORDS what it is
# asked to draw runs the same code and shows the tree as a person would read it.
class _Op:
    pass


class _Layout:
    lines = []

    def __init__(self, depth=0):
        self.depth = depth
        self.enabled = self.alert = True
        self.scale_y = 1.0

    def _sub(self, *a, **k):
        return _Layout(self.depth + 1)
    row = column = box = split = _sub

    def separator(self, *a, **k):
        pass

    def label(self, text="", icon="NONE", **k):
        if text:
            _Layout.lines.append("  " * self.depth + f"[{icon}] {text}")

    def operator(self, idname, text="", icon="NONE", **k):
        _Layout.lines.append("  " * self.depth + f"<{idname}> {text}")
        return _Op()

    def prop(self, *a, **k):
        pass
    prop_search = prop


pkg = origins.__name__.rsplit(".graph_origins", 1)[0]
import importlib                                                      # noqa: E402
tree_ui = importlib.import_module(pkg + ".em_setup.graph_tree")
georef_panel = importlib.import_module(pkg + ".georef_manager.panel")
try:
    tree_ui.draw_graph_tree(_Layout(), bpy.context, em)
    georef_panel._draw_graphs_box(_Layout(), bpy.context)
    drawn = True
except Exception as exc:  # noqa: BLE001
    drawn = False
    print(f"[SMOKE] draw failed: {exc!r}")
for line in _Layout.lines:
    print(f"[SMOKE] | {line}")
check("the tree and the georef box draw", drawn)

print(f"[SMOKE] {'OK' if not FAILURES else 'FAILED: ' + ', '.join(FAILURES)}")
sys.exit(1 if FAILURES else 0)
