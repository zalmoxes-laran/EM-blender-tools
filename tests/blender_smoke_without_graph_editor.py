"""Headless smoke · T-U3: the add-on loads clean without graph_editor.

    "/Applications/Blender 520.app/Contents/MacOS/Blender" -b --python-use-system-env \\
        --python tests/blender_smoke_without_graph_editor.py 2>&1 | tee /tmp/u3.log
    grep -c "Traceback\\|Error registering" /tmp/u3.log    # → 0

The add-on is loaded by Blender at startup: the log of THAT load must carry no
«Error registering» and no traceback (the grep above), and nothing of the
graph editor is registered. (Disabling and enabling it again in the same
session logs «already registered» for five modules that do not unregister
their property groups — graph_info, dtc_authoring, resources_tab,
publication_deck_ui, shelf_tool —, measured on 4 Oct 2026 and not caused by
the graph editor: said in the report as open.)
"""
import sys

import bpy

FAILURES = []


def check(label, condition, detail=""):
    print(f"[SMOKE] {'PASS' if condition else 'FAIL'}: {label} {detail}")
    if not condition:
        FAILURES.append(label)


names = [n for n in sys.modules if n.endswith(".graph_origins") and n.startswith("bl_ext.")]
PKG = names[0].rsplit(".graph_origins", 1)[0]
check("EM Tools is enabled", PKG in bpy.context.preferences.addons)
check("no graph_editor module is loaded", not any(n.startswith(PKG + ".graph_editor") for n in sys.modules))
check("no EMGraph node tree type", not hasattr(bpy.types, "EMGraphNodeTreeType"))
check("no EMGraph Tools panel", not any(hasattr(bpy.types, c) for c in (
    "GRAPHEDIT_PT_main_panel", "GRAPHEDIT_PT_edge_filters", "GRAPHEDIT_PT_appearance",
    "GRAPHEDIT_PT_node_info", "VIEW3D_PT_graphedit_sync")))
check("no graphedit operator", not hasattr(bpy.ops, "graphedit") or not dir(bpy.ops.graphedit))
check("no graph_editor_settings on the scene", not hasattr(bpy.types.Scene, "graph_editor_settings"))
check("the EM panels are there", hasattr(bpy.types, "VIEW3D_PT_RM_Manager") and hasattr(bpy.types, "VIEW3D_PT_EM_Tools_Setup"))
print("[SMOKE] RESULT:", "ALL PASS" if not FAILURES else f"FAILED {FAILURES}")
sys.stdout.flush()
