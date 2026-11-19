"""MICRO-PL26 (row X6 of the extensions plan, E.D. 18-19 Nov 2026): EM Tools,
a client of the same repositories EMStudio reads — ``community_packages/
repositories.py`` (no bpy), measured on a ``file://`` repository of /tmp
built from em-profiles' examples (invented, D-5) and a plugin for Blender
written here.

The machine folders are redirected (``S3DGRAPHY_*_DIR``, ``EM_VOCABULARIES_DIR``):
the real ``~/.s3dgraphy`` is never written. No network: every repository is a
folder.
"""
import importlib.util
import pathlib
import re
import shutil
import sys
import textwrap

import pytest

_REPO = pathlib.Path(__file__).resolve().parent.parent
EXAMPLES = _REPO.parent / "em-profiles" / "examples"

X = pytest.importorskip("s3dgraphy.extensions")
if not hasattr(X, "check_updates"):
    pytest.skip("s3dgraphy without the repositories (X2-X4)", allow_module_level=True)
if not (EXAMPLES / "esempio-statuaria").is_dir():
    pytest.skip("em-profiles' examples are not beside EM-blender-tools", allow_module_level=True)


def _load(name, rel, package=None):
    spec = importlib.util.spec_from_file_location(name, _REPO / rel,
                                                  submodule_search_locations=None)
    mod = importlib.util.module_from_spec(spec)
    if package:
        mod.__package__ = package
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# the package as a package, so ``from . import core`` holds without Blender
_pkg = type(sys)("pl26pkg")
_pkg.__path__ = [str(_REPO / "community_packages")]
sys.modules["pl26pkg"] = _pkg
C = _load("pl26pkg.core", "community_packages/core.py", "pl26pkg")
R = _load("pl26pkg.repositories", "community_packages/repositories.py", "pl26pkg")
I18N = _load("pl26pkg.i18n", "community_packages/i18n.py", "pl26pkg")


@pytest.fixture
def machine(tmp_path, monkeypatch):
    for env, sub in (("S3DGRAPHY_PROFILES_DIR", "profiles"), ("S3DGRAPHY_EXTENSIONS_DIR", "extensions"),
                     ("S3DGRAPHY_PLUGINS_DIR", "plugins"), ("S3DGRAPHY_PLUGINS_DATA_DIR", "plugins-data"),
                     ("EM_VOCABULARIES_DIR", "vocab")):
        monkeypatch.setenv(env, str(tmp_path / sub))
    monkeypatch.delenv("S3DGRAPHY_ONLINE_ACCESS", raising=False)
    from s3dgraphy.authorities import packages as pk
    pk._changed()
    C.forget_cache()
    R.forget_cache()
    R._env_before = R._SENTINEL
    yield tmp_path
    R.respect_blender(True)
    pk._changed()
    C.forget_cache()
    R.forget_cache()


MODULE = '''
def setup(ctx):
    ctx.command("count", lambda s: 0)


plugin = type("Plugin", (), {"setup": staticmethod(setup)})
'''


def blender_plugin(tmp_path, version="0.1.0", *, perms=None, requires=True, hosts='["blender", "emstudio"]'):
    """A plugin whose code runs in Blender, requiring esempio-statuaria's data."""
    folder = tmp_path / "src" / f"conta-{version}"
    shutil.rmtree(folder, ignore_errors=True)
    (folder / "conta_pl26").mkdir(parents=True)
    (folder / "conta_pl26" / "__init__.py").write_text(textwrap.dedent(MODULE), encoding="utf-8")
    (folder / "LICENSE").write_text("EUPL-1.2 (test)\n", encoding="utf-8")
    perms = perms or {"files": "Reads the file it is given"}
    perm_lines = "\n".join(f'  {k} = "{v}"' for k, v in perms.items())
    req = ('[requires]\nextensions = [{ id = "esempio-statuaria", version = "^0.1", part = "data" }]\n'
           if requires else "")
    (folder / "em-extension.toml").write_text(f'''schema_version = "1.0.0"
id = "conta"
version = "{version}"
name = "Count (TEST)"
tagline = "A plugin for Blender of the tests"
maintainer = "Tests"
license = ["SPDX:EUPL-1.2"]
em_api_min = "1.0"
type = "plugin"
{req}
[code]
entry = "conta_pl26:plugin"
hosts = {hosts}
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
''', encoding="utf-8")
    return folder


def built(src, repo):
    res = X.build(src, output_dir=repo)
    assert res["ok"], res["errors"]
    return pathlib.Path(res["path"])


@pytest.fixture
def lab(machine):
    """A folder of the lab: the separate package, EMStudio's plugin, a plugin for Blender."""
    d = machine / "nas" / "estensioni"
    d.mkdir(parents=True)
    built(EXAMPLES / "esempio-statuaria", d)
    built(EXAMPLES / "facemesh_fit", d)
    built(blender_plugin(machine), d)
    assert X.server_generate(d)["ok"]
    return d


def add_lab(lab, **kw):
    got = R.add_and_read(str(lab), name="lab", **kw)
    assert got["sync"]["repositories"][0]["ok"], got
    return got


# ── the sentences ───────────────────────────────────────────────────────────

def test_the_new_sentences_have_their_italian_and_placeholders():
    for msgid, by in I18N.MESSAGES.items():
        assert by.get("it_IT"), msgid
        assert sorted(re.findall(r"\{(\w+)\}", by["it_IT"])) == sorted(re.findall(r"\{(\w+)\}", msgid)), msgid
    for s in I18N.AUTO:
        assert s in I18N.MESSAGES, s
    it = I18N.catalogue("it_IT")
    assert I18N.translate("Installed: Count (TEST) 0.1.0 from lab (data and code)", it) == \
        "Installato: Count (TEST) 0.1.0 da lab (dati e codice)"
    assert I18N.translate("Update all (2)", it) == "Aggiorna tutto (2)"


def test_every_sentence_the_repository_code_says_is_in_the_catalogue():
    import ast
    missing = []
    for rel in ("repositories.py", "repo_ui.py", "repo_operators.py"):
        src = (_REPO / "community_packages" / rel).read_text(encoding="utf-8")
        for m in re.finditer(r'tr\(\s*((?:"[^"]*"\s*)+)', src):
            s = "".join(ast.literal_eval(x) for x in re.findall(r'"[^"]*"', m.group(1)))
            if s not in I18N.MESSAGES:
                missing.append(s)
        for m in re.finditer(r'\n\s+"(\w[\w :()]+)": "([^"]+)",', src):   # the KIND labels
            if rel == "repo_ui.py" and m.group(2) not in I18N.MESSAGES:
                missing.append(m.group(2))
    assert missing == []


# ── the library as the bundled wheel has it ─────────────────────────────────

def test_an_older_s3dgraphy_has_no_repositories(monkeypatch):
    monkeypatch.setattr(C, "library", lambda: (None, type(sys)("old_extensions")))
    assert R.library() is None and not R.available()
    assert R.offers()["offers"] == [] and R.updates() == [] and R.repositories() == []
    assert R.startup_check()["updates"] == []


# ── Blender's «Allow Online Access» ─────────────────────────────────────────

def test_blenders_switch_off_keeps_ours_off_in_this_process_only(machine):
    X.set_online_access(True)
    assert R.respect_blender(None) is True              # a Blender without the switch: nothing changes
    assert R.respect_blender(False) is False
    assert R.blocked_by_blender() and R.online_state()["blender_off"]
    # the machine's switch is not touched (EMStudio still reads the internet)
    assert X.online_access_setting()["setting"] is True
    assert R.respect_blender(True) is True and not R.blocked_by_blender()
    import os
    assert "S3DGRAPHY_ONLINE_ACCESS" not in os.environ


def test_with_blenders_switch_off_an_https_repository_is_not_read_and_a_folder_is(lab):
    R.respect_blender(False)
    X.set_online_access(True)
    X.add_repository("https://repo.example.org/em/index.json", name="web")
    got = add_lab(lab)
    assert [r["name"] for r in got["sync"]["repositories"]] == ["lab"]
    res = X.sync("web")
    [r] = res["repositories"]
    assert not r["ok"] and r["problems"][0]["code"] == "repo_offline"
    lines = R.sync_lines(res, "it", lambda s: I18N.translate(s, I18N.catalogue("it_IT")))
    assert "accesso in rete" in lines[0]


# ── what Blender is offered ─────────────────────────────────────────────────

def test_blender_is_offered_the_packages_and_its_plugins(lab):
    add_lab(lab)
    data = R.offers()
    kinds = {o.id: o.kind for o in data["offers"]}
    assert kinds == {"esempio-statuaria": "data", "conta": "code"}
    assert data["elsewhere"] == 1                 # facemesh_fit: for EMStudio only, counted
    assert R.for_blender({"data": {}, "code": {"hosts": ["emstudio"]}}) == "data_only"
    assert R.for_blender({"data": {}, "code": {"hosts": ["blender"]}}) == "mixed"
    # the same repositories EMStudio sees: one file for the machine
    assert [r["name"] for r in X.repositories()] == ["lab"] and R.repositories()[0]["local"]


def test_a_package_from_the_repository_installs_its_data(lab):
    add_lab(lab)
    pv = R.preview("lab", "esempio-statuaria")
    lines = [t for t, _i, _l in C.preview_lines(pv, "en") + R.plan_lines(pv, "en")]
    assert any(t.startswith("The archive is the one the index of lab names (sha256:") for t in lines)
    ans = R.install("lab", "esempio-statuaria", None, pv, with_code=False)
    assert ans["action"] == "data" and ans["installed"]["data"]["status"] == "installed"
    [row] = C.package_rows()
    assert row.id == "esempio-statuaria" and row.source == "lab" and row.data == "installed"
    [o] = [o for o in R.offers_cached()["offers"] if o.id == "esempio-statuaria"]
    assert o.installed == "0.1.0" and not o.update and o.same_source


def test_a_plugin_for_blender_needs_the_tick_and_its_requirement_comes_first(lab):
    add_lab(lab)
    pv = R.preview("lab", "conta")
    assert C.code_for_blender(pv)
    lines = [t for t, _i, _l in C.preview_lines(pv, "en") + R.plan_lines(pv, "en")]
    assert "Code 0.1.0: NOT VERIFIED, from lab" in lines
    assert "Installed first, because it requires them:" in lines
    assert any(t.startswith("esempio-statuaria 0.1.0 · from lab") or "· from lab" in t for t in lines)
    # nothing is «missing»: the plan installs it first
    assert not (pv.get("requires") or {}).get("missing")
    with pytest.raises(ValueError, match="plugin_needs_trust"):
        R.install("lab", "conta", None, pv, with_code=False)
    assert X.get("conta") is None
    ans = R.install("lab", "conta", None, pv, with_code=True)
    assert ans["action"] == "all"
    assert [r["id"] for r in ans["requires"]] == ["esempio-statuaria"]
    code = X.get("conta")["code"]
    assert code["status"] == "installed" and code["path"].startswith("plugins/lab/conta/")
    assert "conta" in C.active_code_ids()
    it = lambda s: I18N.translate(s, I18N.catalogue("it_IT"))
    assert R.install_lines(ans, "it", it)[0] == "Installato prima: esempio-statuaria 0.1.0 da lab"


def test_the_tick_answers_for_the_requirements_code_only_when_it_runs_in_blender():
    def pv(hosts):
        return {"plan": {"steps": [{"requested": False, "sections": ["code", "data"], "hosts": hosts},
                                   {"requested": True, "sections": ["code"], "hosts": ["blender"]}]}}
    assert R.trust_requires(pv(["blender"]), True)
    assert not R.trust_requires(pv(["emstudio"]), True)
    assert not R.trust_requires(pv(["blender"]), False)
    lines = [t for t, _i, _l in R.plan_lines(dict(pv(["emstudio"]), plan=dict(
        pv(["emstudio"])["plan"], steps=[{"requested": False, "sections": ["code"], "hosts": ["emstudio"],
                                          "id": "x", "version": "1.0.0", "repo": "lab"}])), "en")]
    assert "x 1.0.0 · from lab · with code for emstudio: left for EMStudio" in lines


def test_a_reviewed_plugin_installs_without_the_tick_and_says_who_read_it(lab):
    z = next(lab.glob("conta-0.1.0*.zip"))
    X.add_review(lab, z, by="E.D.", on="2026-11-19", as_="editor")
    assert X.server_generate(lab)["ok"]
    add_lab(lab)
    X.update_repository("lab", trust_reviews=True)
    [o] = [o for o in R.offers()["offers"] if o.id == "conta"]
    assert o.verified
    pv = R.preview("lab", "conta")
    code = pv["code"]
    assert code["verified"] and not code["trust_needed"]
    lines = [t for t, _i, _l in C.preview_lines(pv, "en")]
    assert any(t.startswith("Code 0.1.0: verified — code reviewed by E.D.") for t in lines)
    assert not any("NOT VERIFIED" in t or "Same permissions" in t for t in lines)
    R.install("lab", "conta", None, pv, with_code=True)
    code = X.get("conta")["code"]
    assert code["verified"] and code.get("trusted_by") == "review"
    [row] = [r for r in C.package_rows() if r.id == "conta"]
    assert row.verified


# ── «Update all» from Blender ───────────────────────────────────────────────

def test_update_all_trusts_with_the_tick_only_the_codes_that_run_in_blender(lab, machine):
    add_lab(lab)
    R.install("lab", "conta", None, R.preview("lab", "conta"), with_code=True)
    # facemesh_fit installed for EMStudio, as its window would
    X.install_from("lab", "facemesh_fit", parts="all", trust=True)
    # newer versions with one permission more: both would ask the trust again
    built(blender_plugin(machine, "0.2.0", perms={"files": "Reads the file it is given",
                                                  "network": "Reads a model from the internet"}), lab)
    fm = machine / "src" / "facemesh_fit"
    shutil.copytree(EXAMPLES / "facemesh_fit", fm)
    toml = fm / "em-extension.toml"
    text = re.sub(r'^version = "[^"]+"', 'version = "9.9.0"', toml.read_text(encoding="utf-8"), count=1, flags=re.M)
    text = re.sub(r"(\[code\.permissions\]\n)", r'\1network = "Reads a model from the internet"\n', text, count=1)
    toml.write_text(text, encoding="utf-8")
    built(fm, lab)
    assert X.server_generate(lab)["ok"]
    X.sync("lab")
    ups = {u.id: u for u in R.updates()}
    assert set(ups) == {"conta", "facemesh_fit"}
    assert ups["conta"].trust_needed and ups["conta"].for_blender
    assert ups["facemesh_fit"].trust_needed and not ups["facemesh_fit"].for_blender
    # without the tick: nothing that asks is installed
    res = R.update_all(trust_blender=False)
    assert {n["id"] for n in res["needs_trust"]} == {"conta", "facemesh_fit"} and not res["updated"]
    # with the tick: Blender's goes in, EMStudio's waits for EMStudio
    res = R.update_all(trust_blender=True)
    assert [u["id"] for u in res["updated"]] == ["conta"]
    [n] = res["needs_trust"]
    assert n["id"] == "facemesh_fit" and n["emstudio"]
    assert X.get("conta")["code"]["version"] == "0.2.0"
    it = lambda s: I18N.translate(s, I18N.catalogue("it_IT"))
    lines = R.update_lines(res, "it", it)
    assert lines[0] == "Aggiornato: conta 0.1.0 → 0.2.0 (lab)"
    assert lines[1] == "Non aggiornato, chiede di nuovo la fiducia: facemesh_fit 9.9.0 — aggiornalo in EMStudio"


# ── at start-up ─────────────────────────────────────────────────────────────

def test_the_start_up_check_reads_only_the_repositories_that_ask_and_installs_nothing(lab, machine):
    add_lab(lab)
    R.install("lab", "conta", None, R.preview("lab", "conta"), with_code=True)
    built(blender_plugin(machine, "0.1.1"), lab)             # the same permissions: no new question
    assert X.server_generate(lab)["ok"]
    # «Check at start-up» off: the index is not read again, nothing is said
    assert R.startup_check()["updates"] == []
    X.update_repository("lab", check_on_startup=True)
    state = R.startup_check()
    assert [(u["id"], u["installed"], u["version"]) for u in state["updates"]] == [("conta", "0.1.0", "0.1.1")]
    assert R.startup_line(state) == "Updates available: conta 0.1.0 → 0.1.1"
    assert X.get("conta")["code"]["version"] == "0.1.0"      # said, never installed
    [u] = R.updates()
    assert not u.trust_needed and u.for_blender
    [o] = [o for o in R.offers()["offers"] if o.id == "conta"]
    assert o.update and o.installed == "0.1.0" and o.version == "0.1.1"


def test_a_bad_address_adds_nothing(machine):
    with pytest.raises(X.RepoError) as e:
        R.add_and_read("ftp://x/index.json")
    assert e.value.report.codes() == ["repo_url_bad"]
    assert X.repositories() == []
