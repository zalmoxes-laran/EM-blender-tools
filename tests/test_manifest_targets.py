"""A package says which Blender it is for, coherent with its wheels — and the
local manifest's wheels target is changed only by `./em.sh manifest X.Y`.

27 Oct 2026: build 1.6.0-dev.31 (`dev.py inc` → `update_manifest()` with no
Python) rewrote E.D.'s local manifest to cp311 wheels and EM Tools refused to
load in Blender 5.2 (Python 3.13); the released cp311 package declared only
`blender_version_min = "4.4.0"`, so 5.1/5.2 installed it and broke.

The table is `scripts/version_manager.BLENDER_TARGETS`; the CI's refusal is
`scripts/check_manifest.py`. The commands are run on a COPY of the repository
files in a temporary folder, never on the real manifest.
"""
import os
import pathlib
import re
import shutil
import subprocess
import sys
import zipfile

import pytest

_REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "scripts"))

import check_manifest as CM  # noqa: E402
import version_manager as VM  # noqa: E402

WHEELS = {
    "cp311": ["pandas-2.2.3-cp311-cp311-macosx_11_0_arm64.whl",
              "PyMuPDF-1.24.14-cp39-abi3-macosx_11_0_arm64.whl",
              "networkx-3.2.1-py3-none-any.whl",
              "six-1.17.0-py2.py3-none-any.whl"],
    "cp313": ["pandas-2.2.3-cp313-cp313-macosx_11_0_arm64.whl",
              "PyMuPDF-1.24.14-cp39-abi3-macosx_11_0_arm64.whl",
              "networkx-3.2.1-py3-none-any.whl",
              "six-1.17.0-py2.py3-none-any.whl"],
}


# ── the table ──────────────────────────────────────────────────────────────

def test_the_two_targets():
    t11, t13 = VM.target_for("3.11"), VM.target_for("3.13")
    assert (t11["cp_tag"], t11["blender_min"], t11["blender_max"]) == ("cp311", "4.4.0", "5.1.0")
    assert (t13["cp_tag"], t13["blender_min"], t13["blender_max"]) == ("cp313", "5.1.0", None)
    assert t11["package_tag"] != t13["package_tag"]
    with pytest.raises(ValueError):
        VM.target_for("3.12")


@pytest.mark.parametrize("py", sorted(VM.BLENDER_TARGETS))
def test_every_target_is_coherent_with_the_pythons_blender_ships(py):
    t = VM.target_for(py)
    assert CM.range_problems(t["blender_min"], t["blender_max"], py) == []


def test_the_blender_series_measured_here():
    # /Applications/Blender 501/510/520.app: python3.11, python3.13, python3.13
    assert VM.BLENDER_PYTHON[(5, 0)] == "3.11"
    assert VM.BLENDER_PYTHON[(5, 1)] == "3.13"
    assert VM.BLENDER_PYTHON[(5, 2)] == "3.13"


def test_package_names_and_release_notes_from_the_table():
    assert VM.package_name("1.6.0-dev.33", "macosx-arm64", "3.13") == \
        "em_tools-v1.6.0-dev.33-macosx-arm64-blender51plus.zip"
    assert VM.package_name("1.6.0-dev.33", "linux-x64", "3.11") == \
        "em_tools-v1.6.0-dev.33-linux-x64-blender44-50.zip"
    body = VM.release_notes("v1.6.0-dev.33")
    for py in VM.BLENDER_TARGETS:
        for plat, _ in VM.RELEASE_PLATFORMS:
            assert VM.package_name("1.6.0-dev.33", plat, py) in body
    assert "5.1.0" in body and "4.4.0" in body


# ── check_manifest: the wheels ─────────────────────────────────────────────

@pytest.mark.parametrize("path,cp,bad", [
    ("./wheels/pandas-2.2.3-cp313-cp313-macosx_11_0_arm64.whl", "cp313", False),
    ("./wheels/pandas-2.2.3-cp311-cp311-macosx_11_0_arm64.whl", "cp313", True),
    ("./wheels/pandas-2.2.3-cp313-cp313-macosx_11_0_arm64.whl", "cp311", True),
    ("./wheels/PyMuPDF-1.24.14-cp39-abi3-macosx_11_0_arm64.whl", "cp313", False),
    ("./wheels/foo-1.0-cp314-abi3-macosx_11_0_arm64.whl", "cp313", True),
    ("./wheels/six-1.17.0-py2.py3-none-any.whl", "cp311", False),
    ("./wheels/cp311/networkx-3.2.1-py3-none-any.whl", "cp313", True),   # its folder
    ("./wheels/cp313/networkx-3.2.1-py3-none-any.whl", "cp313", False),
    ("./wheels/foo-1.0-1-cp313-cp313-linux_x86_64.whl", "cp313", False),  # build tag
    ("./wheels/notawheel.tar.gz", "cp313", True),
])
def test_wheel_problem(path, cp, bad):
    assert (CM.wheel_problem(path, cp) is not None) is bad


# ── check_manifest: the range ──────────────────────────────────────────────

def test_the_range_of_dev31_is_refused():
    # the released cp311 package: a min and no max
    probs = CM.range_problems("4.4.0", None, "3.11")
    assert any("5.1 (Python 3.13)" in p for p in probs)
    assert any("blender_version_max" in p for p in probs)


@pytest.mark.parametrize("lo,hi,py", [
    ("5.1.0", "4.4.0", "3.11"),     # unordered
    ("4.4.0", "5.2.0", "3.11"),     # 5.1 inside a 3.11 package
    ("4.4.0", "5.1.1", "3.11"),     # 5.1.0 inside
    ("4.4.0", None, "3.13"),        # 4.4–5.0 inside a 3.13 package
    ("5.0.0", None, "3.13"),
    (None, None, "3.13"),
])
def test_incoherent_ranges(lo, hi, py):
    assert CM.range_problems(lo, hi, py)


def _manifest(lo, hi, wheels):
    lines = ['schema_version = "1.0.0"', 'id = "em_tools"', 'version = "1.6.0-dev.33"']
    if lo:
        lines.append(f'blender_version_min = "{lo}"')
    if hi:
        lines.append(f'blender_version_max = "{hi}"')
    lines.append("wheels = [" + ", ".join(f'"./wheels/{w}"' for w in wheels) + "]")
    return "\n".join(lines) + "\n"


def test_check_manifest_text():
    good13 = _manifest("5.1.0", None, WHEELS["cp313"])
    assert CM.check_manifest_text(good13, "3.13") == []
    good11 = _manifest("4.4.0", "5.1.0", WHEELS["cp311"])
    assert CM.check_manifest_text(good11, "3.11") == []
    # cp311 wheels under a 3.13 range: the 27 Oct manifest the other way round
    mixed = _manifest("5.1.0", None, WHEELS["cp311"])
    assert any("cp311" in p for p in CM.check_manifest_text(mixed, "3.13"))
    assert CM.check_manifest_text("not = [toml", "3.13")
    assert any("no wheels" in p for p in CM.check_manifest_text(_manifest("5.1.0", None, []), "3.13"))


def test_check_path_dir_and_zip(tmp_path):
    pkg = tmp_path / "pkg"
    (pkg / "wheels").mkdir(parents=True)
    for w in WHEELS["cp313"]:
        (pkg / "wheels" / w).write_bytes(b"x")
    (pkg / "blender_manifest.toml").write_text(_manifest("5.1.0", None, WHEELS["cp313"]))
    assert CM.check_path(pkg, "3.13") == []
    assert CM.main([str(pkg), "--python-version", "3.13"]) == 0
    assert CM.main([str(pkg), "--python-version", "3.11"]) == 1
    (pkg / "wheels" / WHEELS["cp313"][0]).unlink()
    assert any("not in the package" in p for p in CM.check_path(pkg, "3.13"))
    (pkg / "wheels" / WHEELS["cp313"][0]).write_bytes(b"x")
    z = tmp_path / "p.zip"
    with zipfile.ZipFile(z, "w") as zf:
        for f in pkg.rglob("*"):
            if f.is_file():
                zf.write(f, f.relative_to(pkg).as_posix())
    assert CM.check_path(z, "3.13") == []


# ── the local manifest, on a copy of the repository ────────────────────────

@pytest.fixture
def repo(tmp_path):
    """A copy of what the version commands read and write; the real
    blender_manifest.toml is never opened."""
    root = tmp_path / "EM-blender-tools"
    (root / "scripts").mkdir(parents=True)
    for name in ("version_manager.py", "dev.py", "build.py", "check_manifest.py"):
        shutil.copy2(_REPO / "scripts" / name, root / "scripts" / name)
    for name in ("blender_manifest_template.toml", "version.json", "em.sh"):
        shutil.copy2(_REPO / name, root / name)
    (root / "__init__.py").write_text("# the add-on\n")
    for cp, names in WHEELS.items():
        (root / "wheels" / cp).mkdir(parents=True)
        for w in names:
            (root / "wheels" / cp / w).write_bytes(b"wheel")
    return root


def _run(root, *argv):
    out = subprocess.run([sys.executable, *argv], cwd=root, capture_output=True,
                         text=True, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
    assert out.returncode == 0, out.stdout + out.stderr
    return out.stdout


def _split(text):
    """(the version line, everything else)."""
    m = re.search(r'^version = "([^"]*)"$', text, re.MULTILINE)
    return m.group(1), text[:m.start()] + text[m.end():]


@pytest.mark.parametrize("py", ["3.13", "3.11"])
def test_inc_keeps_the_wheels_target(repo, py):
    _run(repo, "scripts/version_manager.py", "update", "--python-version", py)
    manifest = repo / "blender_manifest.toml"
    before = manifest.read_text()
    v0, rest0 = _split(before)
    assert f"wheels/{VM.target_for(py)['cp_tag']}/" in rest0
    _run(repo, "scripts/dev.py", "inc")
    v1, rest1 = _split(manifest.read_text())
    assert v1 != v0 and rest1 == rest0          # only the version line moved
    # the CLI increment and set-mode, without a Python: the same
    _run(repo, "scripts/version_manager.py", "increment")
    _run(repo, "scripts/version_manager.py", "set-mode", "--mode", "dev")
    _run(repo, "scripts/version_manager.py", "update")
    v2, rest2 = _split(manifest.read_text())
    assert v2 != v1 and rest2 == rest0
    assert VM.VersionManager(repo).manifest_python_version() == py


def test_em_sh_inc_keeps_the_wheels_target(repo):
    _run(repo, "scripts/version_manager.py", "update", "--python-version", "3.13")
    manifest = repo / "blender_manifest.toml"
    v0, rest0 = _split(manifest.read_text())
    out = subprocess.run(["bash", "em.sh", "inc"], cwd=repo, capture_output=True, text=True,
                         env=dict(os.environ, EM_PYTHON=sys.executable))
    assert out.returncode == 0, out.stdout + out.stderr
    v1, rest1 = _split(manifest.read_text())
    assert v1 != v0 and rest1 == rest0


def test_only_the_explicit_switch_changes_the_target(repo):
    _run(repo, "scripts/version_manager.py", "update", "--python-version", "3.13")
    text13 = (repo / "blender_manifest.toml").read_text()
    assert 'blender_version_min = "5.1.0"' in text13
    assert "blender_version_max" not in text13
    assert CM.check_path(repo / "blender_manifest.toml", "3.13") == []
    _run(repo, "scripts/version_manager.py", "update", "--python-version", "3.11")
    text11 = (repo / "blender_manifest.toml").read_text()
    assert "wheels/cp311/" in text11 and "wheels/cp313/" not in text11
    assert 'blender_version_max = "5.1.0"' in text11
    assert CM.check_path(repo / "blender_manifest.toml", "3.11") == []


def test_inc_without_a_manifest_makes_none(repo):
    _run(repo, "scripts/dev.py", "inc")
    assert not (repo / "blender_manifest.toml").exists()


def test_the_wheels_section_needs_its_python(repo):
    with pytest.raises(ValueError):
        VM.VersionManager(repo).generate_wheels_section("dev", None)


@pytest.mark.parametrize("py", ["3.13", "3.11"])
def test_build_keeps_the_local_target_and_packages_it(repo, py):
    _run(repo, "scripts/version_manager.py", "update", "--python-version", py)
    manifest = repo / "blender_manifest.toml"
    before = manifest.read_text()
    _run(repo, "scripts/dev.py", "build")
    assert manifest.read_text() == before      # same version, same target
    blext = list((repo.parent / "EM_Tools_Releases").glob("*.blext"))
    assert len(blext) == 1
    assert CM.check_path(blext[0], py) == []
    other = "cp311" if py == "3.13" else "cp313"
    with zipfile.ZipFile(blext[0]) as zf:
        assert not any(n.startswith(f"wheels/{other}/") for n in zf.namelist())
