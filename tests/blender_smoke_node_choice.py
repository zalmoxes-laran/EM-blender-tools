"""Headless smoke · N1/N2 in EM Tools: «Choose the node» finds the dev node
without an address; «Turn on a node on this computer» starts the personal node
(this computer only), the finder then sees it as personal; «Turn off».

    PYTHONPATH=~/Documents/GitHub/s3Dgraphy/src \\
    "/Applications/Blender 520.app/Contents/MacOS/Blender" -b --python-use-system-env \\
        --python tests/blender_smoke_node_choice.py -- <project root>
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
nc = importlib.import_module(PKG + ".sync_manager.node_choice")
root = sys.argv[sys.argv.index("--") + 1]
check("the launcher next door is found", bool(nc.launcher()), str(nc.launcher()))
got = nc.find()
print("[SMOKE] local:", [(n["url"], n.get("profile")) for n in got["local"]], "lan via", got["lan_how"])
check("the dev node is found without an address",
      any(n["url"] == "http://localhost:8000" for n in got["local"]))
on = nc.personal("start", root)
check("turned on, this computer only", on.get("ok") and on.get("lan") is False, str(on)[:200])
got = nc.find()
check("…and the finder sees a personal node", got["suggestion_key"] == "personal", got["suggestion"])
off = nc.personal("stop")
check("turned off", off.get("ok"))
print(f"[SMOKE] {'ALL PASS' if not FAILURES else 'FAILURES: ' + ', '.join(FAILURES)}")
sys.exit(1 if FAILURES else 0)
