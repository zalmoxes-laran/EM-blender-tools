"""Headless smoke · T-E3, Tapestry as an add-on of its own (EM Tapestry).

    PYTHONPATH=~/Documents/GitHub/s3Dgraphy/src \\
    "/Applications/Blender 520.app/Contents/MacOS/Blender" -b --python-use-system-env \\
        --python tests/blender_smoke_tapestry_apart.py -- ~/Documents/GitHub/EM-Tapestry-blender

(1) EM Tools without EM Tapestry: no Tapestry panel, no `tapestry` in its
settings, EM ▸ About says it is not installed; (2) EM Tapestry enabled (its
folder and its wheels on the path, as an installed extension has them): its
panel, `scene.em_tapestry`, the link to EM Tools, its gestures on a camera
and a proxy, «Test connection» with no server saying so; About says it is
there; (3) EM Tapestry disabled: EM Tools untouched; (4) EM Tapestry without
EM Tools: the gestures that need it are off, the network ones work, nothing
raises.
"""
import glob
import os
import sys

import bpy

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
REPO = os.path.expanduser(ARGS[0] if ARGS else "~/Documents/GitHub/EM-Tapestry-blender")
FAILURES = []


def check(label, condition, detail=""):
    print(f"[SMOKE] {'PASS' if condition else 'FAIL'}: {label} {detail}")
    if not condition:
        FAILURES.append(label)


em_pkg = [n for n in sys.modules if n.endswith(".graph_origins") and n.startswith("bl_ext.")][0].rsplit(".", 1)[0]
companions = sys.modules.get(em_pkg + ".companions") or __import__(em_pkg + ".companions", fromlist=["x"])

# ── (1) EM Tools alone ─────────────────────────────────────────────────────
check("EM Tools is enabled", hasattr(bpy.context.scene, "em_tools"), em_pkg)
check("no Tapestry panel in EM Tools", not hasattr(bpy.types, "TAPESTRY_PT_main_panel"))
check("no tapestry in EM Tools' settings", "tapestry" not in bpy.context.scene.em_tools.bl_rna.properties.keys())
check("no tapestry_integration module", not any(n.endswith(".tapestry_integration") for n in sys.modules))
on, said = companions.tapestry_state()
check("About says EM Tapestry is not installed", not on, said)

# ── (2) EM Tapestry enabled ────────────────────────────────────────────────
for whl in sorted(glob.glob(os.path.join(REPO, "em_tapestry", "wheels", "*.whl"))):
    sys.path.insert(0, whl)
sys.path.insert(0, REPO)
import em_tapestry  # noqa: E402
em_tapestry.register()
check("its panel is registered", hasattr(bpy.types, "TAPESTRY_PT_main_panel"))
check("its settings are scene.em_tapestry", hasattr(bpy.context.scene, "em_tapestry"))
from em_tapestry import em_link  # noqa: E402
check("it finds EM Tools", em_link.em_tools_package() == em_pkg and em_link.available(),
      str(em_link.em_tools_package()))
on, said = companions.tapestry_state()
check("About says EM Tapestry is there", on, said)

cam_data = bpy.data.cameras.new("TapCam")
cam = bpy.data.objects.new("TapCam", cam_data)
bpy.context.scene.collection.objects.link(cam)
cam.location = (0, -10, 0)
cam.rotation_euler = (1.5708, 0, 0)
bpy.context.scene.camera = cam
mesh = bpy.data.meshes.new("US1")
proxy = bpy.data.objects.new("US1", mesh)
bpy.context.scene.collection.objects.link(proxy)
tap = bpy.context.scene.em_tapestry
tap.render_camera = cam
r = bpy.ops.tapestry.generate_job_name()
check("Generate job name", r == {"FINISHED"} and bool(tap.job_name), tap.job_name)
try:
    r = bpy.ops.tapestry.analyze_camera_view()
    check("Analyze camera view runs with EM Tools", r in ({"FINISHED"}, {"CANCELLED"}), f"{r} {tap.visible_proxies_count}")
except RuntimeError as e:
    check("Analyze camera view runs with EM Tools", "Error" not in str(e).split(":")[0], str(e)[:200])
tap.server_address = "127.0.0.1"
tap.server_port = 9
try:
    bpy.ops.tapestry.test_connection()
    raised = ""
except RuntimeError as e:
    raised = str(e)[:200]
# in -b an ERROR report comes back as RuntimeError: that IS the sentence
check("Test connection with no server says so", "Cannot connect" in raised and not tap.connection_status, raised)
import requests  # noqa: E402
print("[SMOKE] INFO: requests", requests.__version__, "from", os.path.dirname(requests.__file__))

# ── (3) EM Tapestry disabled ───────────────────────────────────────────────
em_tapestry.unregister()
check("its panel is gone", not hasattr(bpy.types, "TAPESTRY_PT_main_panel"))
check("its settings are gone", not hasattr(bpy.types.Scene, "em_tapestry"))
check("EM Tools untouched", hasattr(bpy.context.scene, "em_tools") and len(bpy.context.scene.em_tools.bl_rna.properties) > 10)

# ── (4) EM Tapestry without EM Tools ───────────────────────────────────────
import addon_utils  # noqa: E402
addon_utils.disable(em_pkg, default_set=False)
check("EM Tools disabled", not hasattr(bpy.context.scene, "em_tools"))
em_tapestry.register()
check("EM Tapestry registers without EM Tools", hasattr(bpy.types, "TAPESTRY_PT_main_panel"))
check("it knows EM Tools is missing", not em_link.available())
check("Analyze camera view is off", not bpy.ops.tapestry.analyze_camera_view.poll())
check("Render for Tapestry is off", not bpy.ops.tapestry.render_for_tapestry.poll())
tap = bpy.context.scene.em_tapestry
tap.render_camera = cam
r = bpy.ops.tapestry.generate_job_name()
check("Generate job name works without EM Tools", r == {"FINISHED"}, tap.job_name)
tap.server_address, tap.server_port = "127.0.0.1", 9
try:
    bpy.ops.tapestry.test_connection()
    raised = ""
except RuntimeError as e:
    raised = str(e)[:200]
check("Test connection works without EM Tools", "Cannot connect" in raised, raised)
em_tapestry.unregister()
addon_utils.enable(em_pkg, default_set=False)
check("EM Tools enabled again", hasattr(bpy.context.scene, "em_tools"))
print("[SMOKE] RESULT:", "ALL PASS" if not FAILURES else f"FAILED {FAILURES}")
sys.stdout.flush()
