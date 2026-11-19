"""Headless smoke: EM Tools, a client of the repositories (MICRO-PL26, X6).

NOT a pytest test (needs bpy). The machine folders MUST be redirected, or the
real ~/.s3dgraphy is written; the s3dgraphy with the repositories (after
dev124) comes from PYTHONPATH::

    D=/tmp/pl26-smoke; S3DGRAPHY_PROFILES_DIR=$D/profiles S3DGRAPHY_EXTENSIONS_DIR=$D/ext \\
    S3DGRAPHY_PLUGINS_DIR=$D/plugins S3DGRAPHY_PLUGINS_DATA_DIR=$D/pdata EM_VOCABULARIES_DIR=$D/vocab \\
    PL26_SRC=<copy of em-profiles/examples> PL26_WORK=$D/work PYTHONPATH=…/s3Dgraphy/src \\
    "/Applications/Blender 520.app/Contents/MacOS/Blender" -b --python-use-system-env \\
        --python-exit-code 1 --python tests/blender_smoke_em_repositories.py

Builds a folder of the lab (esempio-statuaria, EMStudio's facemesh_fit, a
plugin for Blender that requires esempio-statuaria), adds it in EM Tools'
Preferences, draws what it offers, installs the plugin with the tick (its
requirement first), sees it loaded in Blender, updates all after a newer
version with one permission more, removes the repository (what was
installed stays), and reads the sentences in Italian.
"""
import importlib
import os
import shutil
import sys
import textwrap

import bpy

FAILURES = []


def check(label, condition, detail=""):
    print(f"[SMOKE] {'PASS' if condition else 'FAIL'}: {label} {detail}")
    if not condition:
        FAILURES.append(label)
    return condition


for env in ("S3DGRAPHY_PROFILES_DIR", "S3DGRAPHY_EXTENSIONS_DIR", "S3DGRAPHY_PLUGINS_DIR",
            "S3DGRAPHY_PLUGINS_DATA_DIR", "EM_VOCABULARIES_DIR", "PL26_WORK"):
    if not os.environ.get(env, "").startswith("/tmp"):
        print(f"[SMOKE] FAIL: {env} must point into /tmp (the real machine folders are not written)")
        sys.exit(1)
SRC, WORK = os.environ["PL26_SRC"], os.environ["PL26_WORK"]

pkg = next((n.rsplit(".", 1)[0] for n in list(sys.modules)
            if n.startswith("bl_ext.") and n.endswith(".graph_updaters")), None)
if not check("addon loaded", pkg is not None and hasattr(bpy.ops.empkg, "install_from_repo")):
    sys.exit(1)
R = importlib.import_module(pkg + ".community_packages.repositories")
core = importlib.import_module(pkg + ".community_packages.core")
ui = importlib.import_module(pkg + ".community_packages.ui")
i18n = importlib.import_module(pkg + ".community_packages.i18n")
if not check("the s3dgraphy in use has the repositories", R.available()):
    sys.exit(1)
from s3dgraphy import extensions as X  # noqa: E402


class Rec:
    def __init__(self, calls): self.calls = calls
    def _c(self, *a, **k): return Rec(self.calls)
    column = row = box = split = _c
    alert = enabled = False
    def label(self, **k): self.calls.append(k.get("text", ""))
    def prop(self, data, name, **k): self.calls.append(f"prop:{name}")
    def operator(self, idname, **k):
        self.calls.append(f"op:{idname}:{k.get('text', '')}")
        return type("OpProps", (), {})()
    def separator(self, **k): pass


def draw():
    calls = []
    R.forget_cache()
    ui.draw_preferences(Rec(calls), bpy.context)
    return calls


MODULE = '''
def setup(ctx):
    ctx.command("count", lambda s: 0)


plugin = type("Plugin", (), {"setup": staticmethod(setup)})
'''


def blender_plugin(version, perms):
    folder = os.path.join(WORK, "src", f"conta-{version}")
    shutil.rmtree(folder, ignore_errors=True)
    os.makedirs(os.path.join(folder, "conta_pl26"))
    with open(os.path.join(folder, "conta_pl26", "__init__.py"), "w") as f:
        f.write(textwrap.dedent(MODULE))
    with open(os.path.join(folder, "LICENSE"), "w") as f:
        f.write("EUPL-1.2 (test)\n")
    perm_lines = "\n".join(f'  {k} = "{v}"' for k, v in perms.items())
    with open(os.path.join(folder, "em-extension.toml"), "w") as f:
        f.write(f'''schema_version = "1.0.0"
id = "conta"
version = "{version}"
name = "Count (TEST)"
tagline = "A plugin for Blender of the smoke"
maintainer = "Tests"
license = ["SPDX:EUPL-1.2"]
em_api_min = "1.0"
type = "plugin"
[requires]
extensions = [{{ id = "esempio-statuaria", version = "^0.1", part = "data" }}]
[code]
entry = "conta_pl26:plugin"
hosts = ["blender", "emstudio"]
  [code.permissions]
{perm_lines}
  [code.descriptor]
  host = "app-side"
  transport = ["direct"]
  capabilities = ["read-graph"]
  provenance = "derivation"
  [[code.commands]]
  id = "count"
  label = "Count"
  writes = false
  in = ["menu.tools@1"]
''')
    return folder


def build(src, lab):
    res = X.build(src, output_dir=lab)
    check(f"built {os.path.basename(src)}", res["ok"], str(res.get("errors"))[:200])


# ── the lab's folder ────────────────────────────────────────────────────────
LAB = os.path.join(WORK, "nas", "estensioni")
shutil.rmtree(WORK, ignore_errors=True)
os.makedirs(LAB)
build(os.path.join(SRC, "esempio-statuaria"), LAB)
build(os.path.join(SRC, "facemesh_fit"), LAB)
build(blender_plugin("0.1.0", {"files": "Reads the file it is given"}), LAB)
check("index written", X.server_generate(LAB)["ok"])

# ── empty, then the folder added ────────────────────────────────────────────
calls = draw()
check("the Repositories box", "Repositories" in calls and any(c.startswith("op:empkg.repo_add") for c in calls))
blender_online = getattr(bpy.app, "online_access", None)
if blender_online is False:
    check("Blender's switch off is said", any("Online access is off in Blender" in c for c in calls))
else:
    check("our switch drawn", any(c.startswith("op:empkg.online_access") for c in calls))
r = bpy.ops.empkg.repo_add('EXEC_DEFAULT', folder=LAB, repo_name="lab")
check("folder added and read", r == {"FINISHED"} and [x["name"] for x in X.repositories()] == ["lab"], str(r))
calls = draw()
check("its state", any(c.startswith("read ") and "3 entries" in c for c in calls), str(calls)[:400])
check("offered: the package and the plugin for Blender",
      any(c.startswith("esempio-statuaria 0.1.0 · community package · lab") or
          ("0.1.0 · community package · lab" in c) for c in calls)
      and any(c.startswith("Count (TEST) 0.1.0 · plugin for Blender · lab") for c in calls))
check("EMStudio's plugin counted, not listed", "1 plugin(s) for EMStudio only, not listed here" in calls)

# ── the plugin installed with the tick, its requirement first ───────────────
r = bpy.ops.empkg.install_from_repo('EXEC_DEFAULT', repo="lab", package_id="conta", version="0.1.0",
                                    with_code=True)
check("installed from the repository", r == {"FINISHED"}, str(r))
row = X.get("conta") or {}
check("code under plugins/lab", (row.get("code") or {}).get("path", "").startswith("plugins/lab/conta/"))
check("requirement installed first", (X.get("esempio-statuaria") or {}).get("source") == "lab")
try:
    from s3dgraphy import em
    p = em.plugins.get("conta")
    check("loaded in Blender", p is not None and p.state == "loaded", str(getattr(p, "state", None)))
except ImportError:
    check("em in the s3dgraphy in use", False)
calls = draw()
check("the row says where from and what Blender made of it",
      "from lab" in calls and "code: loaded in Blender, not verified" in calls)
check("installed, no button", "installed 0.1.0" in calls)

# ── «Update all» after a version with one permission more ───────────────────
build(blender_plugin("0.2.0", {"files": "Reads the file it is given", "network": "Reads a model online"}), LAB)
X.server_generate(LAB)
r = bpy.ops.empkg.repo_sync('EXEC_DEFAULT', name="lab")
check("read again", r == {"FINISHED"}, str(r))
calls = draw()
check("Update all (1)", any(c == "op:empkg.update_all:Update all (1)" for c in calls), str(calls)[-400:])
r = bpy.ops.empkg.update_all('EXEC_DEFAULT', trust_too=False)
check("without the tick it waits", X.get("conta")["code"]["version"] == "0.1.0")
r = bpy.ops.empkg.update_all('EXEC_DEFAULT', trust_too=True)
check("with the tick it is updated", X.get("conta")["code"]["version"] == "0.2.0", str(r))

# ── the switches of a repository ────────────────────────────────────────────
r = bpy.ops.empkg.repo_set('EXEC_DEFAULT', name="lab", key="check_on_startup", value=True)
check("check at start-up on", X.get_repository("lab")["check_on_startup"])
r = bpy.ops.empkg.repo_token('EXEC_DEFAULT', name="lab", token="s3cret")
check("token set, never shown", X.get_repository("lab")["has_token"] and
      not any("s3cret" in c for c in draw()))
bpy.ops.empkg.repo_token('EXEC_DEFAULT', name="lab", token="")
check("token cleared", not X.get_repository("lab")["has_token"])

# ── Italian ─────────────────────────────────────────────────────────────────
prefs = bpy.context.preferences.view
prefs.language = 'it_IT'
prefs.use_translate_interface = True
check("Italian: Aggiungi repository…", i18n.tr("Add repository…") == "Aggiungi repository…",
      i18n.tr("Add repository…"))
calls = draw()
check("Italian: the box", "Offerti dai repository" in calls and "da lab" in calls, str(calls)[:300])
prefs.language = 'en_US'

# ── the repository removed: what came from it stays ─────────────────────────
r = bpy.ops.empkg.repo_remove('EXEC_DEFAULT', name="lab")
check("removed", r == {"FINISHED"} and X.repositories() == [])
check("what was installed stays", X.get("conta") is not None and X.get("esempio-statuaria") is not None)

try:
    em.plugins.reset()
except Exception:  # noqa: BLE001
    pass
print(f"[SMOKE] {'OK' if not FAILURES else 'FAILED: ' + ', '.join(FAILURES)}")
sys.exit(1 if FAILURES else 0)
