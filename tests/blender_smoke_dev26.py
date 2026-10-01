"""Headless smoke: dev26 and dtcstamp 0.1.2 in a real Blender (MICRO-EMTOOLS-DEV26).

NOT a pytest test (needs bpy) — run it inside Blender with the EM-tools
extension installed from the built package, in a CLEAN user folder:

    export BLENDER_USER_RESOURCES=$(mktemp -d)
    /Applications/Blender\\ 520.app/Contents/MacOS/Blender --background \\
        --command extension install-file -r user_default -e <em_tools-….blext>
    /Applications/Blender\\ 520.app/Contents/MacOS/Blender --background \\
        --python tests/blender_smoke_dev26.py

* the datamodel fingerprint at startup says ``aligned``;
* dtcstamp is the installed 0.1.2 wheel (no ``_vendor``), and the digests work;
* ``s3dgraphy.stamp`` imports (it needs dtcstamp's ``stamp_description``).

Exits non-zero on failure.
"""
import importlib
import sys

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
if not check("addon loaded", pkg is not None and hasattr(bpy.context.scene, "em_tools"),
             f"({pkg}, Blender {bpy.app.version_string}, Python {sys.version.split()[0]})"):
    sys.exit(1)

import s3dgraphy  # noqa: E402
import dtcstamp  # noqa: E402

banner = importlib.import_module(pkg + ".em_setup.version_banner")
result = banner.check_datamodel()
check("datamodel aligned", result["state"] == "aligned",
      f"({result['state']}, s3dgraphy {result['found_version']} vs pin "
      f"{result['expected_version']}; {result['differences'][:2]})")
check("s3dgraphy is dev26", s3dgraphy.__version__ == "1.6.0.dev26", s3dgraphy.__version__)
check("dtcstamp is 0.1.2", dtcstamp.__version__ == "0.1.2",
      f"{dtcstamp.__version__} at {dtcstamp.__file__}")

digest = importlib.import_module(pkg + ".resource_digest")
check("resource_digest uses the installed dtcstamp", digest.dtcstamp() is dtcstamp,
      digest.dtcstamp_origin())
check("no _vendor in the package", importlib.util.find_spec(pkg + "._vendor") is None)
members = digest.members_digest([{"role": "entry_point", "path": "a.gltf",
                                  "checksum": "sha256:" + "0" * 64}])
check("members_digest", members.startswith("sha256:"), members[:23] + "…")

try:
    import s3dgraphy.stamp  # noqa: F401
    check("s3dgraphy.stamp imports", True)
except Exception as exc:  # noqa: BLE001
    check("s3dgraphy.stamp imports", False, repr(exc))

print(f"[SMOKE] {'OK' if not FAILURES else 'FAILED: ' + ', '.join(FAILURES)}")
sys.exit(1 if FAILURES else 0)
