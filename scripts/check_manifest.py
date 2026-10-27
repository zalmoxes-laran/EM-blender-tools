# scripts/check_manifest.py
"""Refuse a package whose manifest lies about its Python or its Blender.

    python scripts/check_manifest.py <manifest.toml | package dir | .zip> --python-version 3.13

Fails (exit 1, one line per problem) when

* a wheel the manifest lists is built for another CPython than the target
  (``cp311`` in a 3.13 package; an ``abi3`` wheel newer than the target), or
  sits in a ``wheels/cpXY/`` folder of another Python;
* a listed wheel is not in the package (directory or zip given);
* ``blender_version_min`` / ``blender_version_max`` are missing, unordered, not
  the ones ``version_manager.BLENDER_TARGETS`` gives that Python, or admit a
  Blender series that ships another Python (``version_manager.BLENDER_PYTHON``).

27 Oct 2026: a cp311 package declared only ``blender_version_min = "4.4.0"`` and
Blender 5.2 (Python 3.13) installed it; the CI runs this before zipping.
"""
import argparse
import re
import sys
import zipfile
from pathlib import Path
from typing import Iterable, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from version_manager import (BLENDER_PYTHON, python_of_cp, target_for,  # noqa: E402
                             version_tuple)

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover — Python < 3.11
    import tomli as tomllib  # type: ignore


def _cp_number(tag: str) -> Optional[int]:
    m = re.fullmatch(r"cp(\d+)", tag)
    return int(m.group(1)) if m else None


def wheel_problem(path: str, cp_tag: str) -> Optional[str]:
    """Why the wheel at ``path`` (as the manifest lists it) cannot load in the
    CPython ``cp_tag``; None when it can."""
    name = path.rsplit("/", 1)[-1]
    folder = re.search(r"wheels/(cp\d+)/", path)
    if folder and folder.group(1) != cp_tag:
        return f"{path}: in the folder of {folder.group(1)}, the target is {cp_tag}"
    if not name.endswith(".whl"):
        return f"{path}: not a wheel"
    parts = name[:-4].split("-")
    if len(parts) not in (5, 6):
        return f"{path}: not a wheel file name (name-version-python-abi-platform)"
    py_tags, abi_tags = parts[-3].split("."), parts[-2].split(".")
    want = _cp_number(cp_tag)
    ok = False
    for py in py_tags:
        for abi in abi_tags:
            if abi == "none" and re.fullmatch(r"py\d*", py):
                ok = True                      # pure Python
            elif abi == "abi3" and _cp_number(py) is not None:
                ok = ok or _cp_number(py) <= want   # stable ABI: that CPython or later
            elif _cp_number(py) is not None:
                ok = ok or _cp_number(py) == want
    if not ok:
        return f"{path}: built for {parts[-3]}/{parts[-2]}, the target is {cp_tag}"
    return None


def range_problems(blender_min: Optional[str], blender_max: Optional[str],
                   python_version: str) -> List[str]:
    """What is wrong with ``[min, max)`` for a package of ``python_version``."""
    out: List[str] = []
    target = target_for(python_version)
    if not blender_min:
        return ["blender_version_min missing"]
    lo = version_tuple(blender_min)
    hi = version_tuple(blender_max) if blender_max else None
    if hi is not None and hi <= lo:
        out.append(f"blender_version_max {blender_max} is not after "
                   f"blender_version_min {blender_min}")
    if blender_min != target["blender_min"]:
        out.append(f"blender_version_min {blender_min}: Python {python_version} "
                   f"packages say {target['blender_min']}")
    if (blender_max or None) != target["blender_max"]:
        out.append(f"blender_version_max {blender_max or '(none)'}: Python "
                   f"{python_version} packages say {target['blender_max'] or '(none)'}")
    for series, py in sorted(BLENDER_PYTHON.items()):
        inside = series >= lo[:2] and (hi is None or series < hi[:2] or
                                       (series == hi[:2] and hi[2:] > (0,)))
        if inside and py != python_version:
            out.append(f"Blender {series[0]}.{series[1]} (Python {py}) is inside "
                       f"[{blender_min}, {blender_max or '…'}) of a Python "
                       f"{python_version} package")
    return out


def check_manifest_text(text: str, python_version: str,
                        present: Optional[Iterable[str]] = None) -> List[str]:
    """Every problem of a manifest for ``python_version``. ``present``: the
    files of the package (relative, ``/``), to check the wheels are in it."""
    try:
        data = tomllib.loads(text)
    except Exception as exc:  # noqa: BLE001
        return [f"the manifest does not parse: {exc}"]
    target = target_for(python_version)
    problems = range_problems(data.get("blender_version_min"),
                              data.get("blender_version_max"), python_version)
    wheels = data.get("wheels") or []
    if not wheels:
        problems.append("no wheels listed")
    have = set(present) if present is not None else None
    for w in wheels:
        bad = wheel_problem(w, target["cp_tag"])
        if bad:
            problems.append(bad)
        rel = w[2:] if w.startswith("./") else w
        if have is not None and rel not in have:
            problems.append(f"{w}: listed, not in the package")
    return problems


def check_path(path: Path, python_version: str) -> List[str]:
    path = Path(path)
    if path.is_dir():
        manifest = path / "blender_manifest.toml"
        if not manifest.is_file():
            return [f"{manifest}: missing"]
        present = [p.relative_to(path).as_posix() for p in path.rglob("*") if p.is_file()]
        return check_manifest_text(manifest.read_text(encoding="utf-8"),
                                   python_version, present)
    if path.suffix.lower() in (".zip", ".blext"):
        with zipfile.ZipFile(path) as zf:
            names = zf.namelist()
            if "blender_manifest.toml" not in names:
                return [f"{path}: no blender_manifest.toml at its root"]
            text = zf.read("blender_manifest.toml").decode("utf-8")
        return check_manifest_text(text, python_version, names)
    return check_manifest_text(path.read_text(encoding="utf-8"), python_version)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("path", help="blender_manifest.toml, a package folder, or a .zip")
    ap.add_argument("--python-version", required=True, help="3.11 / 3.13")
    args = ap.parse_args(argv)
    problems = check_path(Path(args.path), args.python_version)
    t = target_for(args.python_version)
    if problems:
        print(f"❌ {args.path} is not a coherent Python {args.python_version} package:")
        for p in problems:
            print(f"   - {p}")
        return 1
    print(f"✅ {args.path}: Python {args.python_version} ({t['cp_tag']}), {t['label']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
