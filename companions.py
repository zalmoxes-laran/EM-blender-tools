"""The add-ons that lean on EM Tools and live apart from it.

E3 (decisions of E.D., 4 Oct 2026): Tapestry left EM Tools and became **EM
Tapestry**, an add-on of its own that reads epochs and proxies from here.
EM Tools does not need it and does not import it: it only says whether it is
there (EM ▸ About), so that a person who used to find Tapestry in EM Room
knows where it went.
"""

import bpy

TAPESTRY_ID = "em_tapestry"


def tapestry_state():
    """→ `(installed, sentence)`. Installed means enabled in this Blender:
    its settings are on the scene (`scene.em_tapestry`)."""
    if hasattr(bpy.types.Scene, "em_tapestry"):
        version = ""
        for name in bpy.context.preferences.addons.keys():
            if name == TAPESTRY_ID or name.endswith("." + TAPESTRY_ID):
                version = _version_of(name)
                break
        return True, f"EM Tapestry {version}".strip()
    return False, "EM Tapestry not installed (a separate add-on)"


def _version_of(module_name):
    import sys
    mod = sys.modules.get(module_name)
    if mod is None:
        return ""
    try:
        import addon_utils
        info = addon_utils.module_bl_info(mod)
        v = info.get("version")
        return ".".join(str(x) for x in v) if v else ""
    except Exception:  # noqa: BLE001
        return ""
