#!/usr/bin/env python3
"""Rebuild the BUNDLED s3dgraphy wheel from the sibling checkout, so it cannot lie.

## The defect this closes (measured, 17 Aug 2026)

EMtools ships s3dgraphy as a **wheel** — a copy — downloaded from PyPI by
`setup_development.py`. A published `1.6.0.dev14` and a local source that also
says `1.6.0.dev14` are **not the same code**: the bundled copy was days behind,
EMtools ran the old one, and the only symptom was an `ImportError` inside a click
(`geometry_summary` missing). `sync_manager.materialise.LibraryTooOld` catches
that symptom; this removes the cause.

Building the wheel **from the source in front of you** makes "the bundle is older
than the library" impossible rather than detectable: the wheel is produced from
`../s3Dgraphy` at the moment you ask, so its content IS that source.

## What it does

1. `pip wheel ../s3Dgraphy --no-deps` into a temporary directory (setuptools
   build backend, pure-python `py3-none-any` wheel — the same artefact PyPI would
   publish);
2. removes the previous `s3dgraphy-*.whl` from the target `wheels/cp3XX/` — a
   bundle with two versions of the same package is a bundle whose behaviour
   depends on which one pip sees first;
3. copies the new one in;
4. tells you whether `blender_manifest.toml` needs regenerating: it lists wheels
   **by file name**, so a rebuild at the SAME version needs nothing, and a
   version bump needs `./em.sh manifest 3.11|3.13`. (Said rather than done: the
   manifest is generated for one Python at a time and guessing which one you meant
   would rewrite the other.)
5. and verifies by CONTENT — `python -m s3dgraphy.tools.wheel_drift --check`,
   which compares the bytes of the code and not the version string. A rebuild that
   claims success without that check would be the same trust that failed here.

## Usage

    python scripts/rebundle_s3dgraphy.py                    # both cp311 and cp313
    python scripts/rebundle_s3dgraphy.py --python 3.13      # just that one
    python scripts/rebundle_s3dgraphy.py --source ~/src/s3Dgraphy
    python scripts/rebundle_s3dgraphy.py --check            # verify only, build nothing

s3dgraphy is pure Python (`py3-none-any`), so the same file serves both
interpreter directories — they exist because the *other* wheels in the bundle are
per-Python (numpy, lxml…), and keeping s3dgraphy in both keeps every directory
self-sufficient.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Optional

HERE = Path(__file__).resolve().parent
ADDON = HERE.parent
#: the sibling checkout, by the layout every other script here assumes
DEFAULT_SOURCE = ADDON.parent / "s3Dgraphy"
PYTHONS = ("3.11", "3.13")


def wheels_dir(python_version: str) -> Path:
    """`wheels/cp311` for 3.11 — the same tag `setup_development.py` uses."""
    return ADDON / "wheels" / f"cp{python_version.replace('.', '')}"


#: What is NOT the library: build artefacts, environments, history, caches. Copied
#: nothing of it, because the first three make the build slow and the FIRST one
#: makes it wrong (see `build_wheel`).
_NOT_THE_LIBRARY = shutil.ignore_patterns(
    "build", "dist", ".git", ".venv", "venv", "*.egg-info", "__pycache__",
    ".pytest_cache", ".mypy_cache", "node_modules", "outputs")


def build_wheel(source: Path, into: Path) -> Path:
    """One wheel from `source`, built by pip. Raises with pip's own words.

    Built from a **clean copy** of the checkout, and that is the whole point of
    this function rather than a one-line `pip wheel`:

    setuptools keeps a `build/lib/` beside the source and copies from it, so a
    file DELETED from `src/` is still in the wheel as long as an old build dir
    remembers it. Measured here, the first time this script ran: the fresh wheel
    still carried `s3dgraphy/nodes/link_node.py`, a module renamed away days
    earlier — which is the same class of lie the whole script exists to remove,
    arriving through the back door.

    A copy, rather than deleting the checkout's `build/`: this script must not
    have side effects on the library's tree. What it builds is what `src/` says.
    """
    print(f"▶ building a wheel from {source}", flush=True)
    staged = into / "src-copy"
    shutil.copytree(source, staged, ignore=_NOT_THE_LIBRARY)
    result = subprocess.run(
        [sys.executable, "-m", "pip", "wheel", str(staged), "--no-deps",
         "--no-build-isolation" if _has_setuptools() else "--isolated",
         "-w", str(into)],
        capture_output=True, text=True)
    if result.returncode != 0:
        # pip's message is the useful one; ours would only be a paraphrase
        raise RuntimeError(
            f"pip could not build a wheel from {source}:\n"
            f"{result.stdout[-2000:]}\n{result.stderr[-2000:]}")
    built = sorted(into.glob("s3dgraphy-*.whl"))
    if not built:
        raise RuntimeError(
            f"pip reported success but produced no s3dgraphy wheel in {into} — "
            f"is {source} the s3Dgraphy checkout?")
    return built[-1]


def _has_setuptools() -> bool:
    """Can we build without downloading the backend? (An offline laptop can.)"""
    try:
        import setuptools  # noqa: F401
        import wheel       # noqa: F401
    except ImportError:
        return False
    return True


def install_into(wheel: Path, target: Path) -> Path:
    """Put `wheel` in `target`, removing any older s3dgraphy beside it."""
    target.mkdir(parents=True, exist_ok=True)
    replaced: List[str] = []
    for old in sorted(target.glob("s3dgraphy-*.whl")):
        if old.name != wheel.name:
            replaced.append(old.name)
        old.unlink()
    destination = target / wheel.name
    shutil.copy2(wheel, destination)
    for name in replaced:
        print(f"  · removed {name} (a bundle must hold ONE s3dgraphy)")
    print(f"  ✓ {destination.relative_to(ADDON)}")
    return destination


def verify(source: Path, wheel: Optional[Path] = None) -> int:
    """The CONTENT check, from the library itself.

    Run as a subprocess with the source's `src/` on the path, so what verifies the
    bundle is the checkout it was built from — not whatever s3dgraphy happens to be
    installed in the interpreter running this script.
    """
    tool = source / "src" / "s3dgraphy" / "tools" / "wheel_drift.py"
    if not tool.is_file():
        print(f"  ! no wheel_drift in {source} — cannot verify by content "
              f"(update the s3Dgraphy checkout)")
        return 0
    argv = [sys.executable, "-m", "s3dgraphy.tools.wheel_drift", "--check"]
    if wheel:
        argv += ["--wheel", str(wheel)]
    env = {"PYTHONPATH": str(source / "src")}
    import os

    result = subprocess.run(argv, cwd=str(source), env={**os.environ, **env})
    return result.returncode


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--python", choices=PYTHONS, action="append",
                        help="which wheels directory (repeatable; default both)")
    parser.add_argument("--source", default=str(DEFAULT_SOURCE),
                        help="the s3Dgraphy checkout to build from")
    parser.add_argument("--check", action="store_true",
                        help="verify the bundled wheels by content and build nothing")
    args = parser.parse_args()

    source = Path(args.source).expanduser().resolve()
    if not (source / "pyproject.toml").is_file():
        print(f"✗ {source} does not look like the s3Dgraphy checkout "
              f"(no pyproject.toml). Pass --source.")
        return 2

    if args.check:
        return verify(source)

    targets = [wheels_dir(p) for p in (args.python or list(PYTHONS))]
    with tempfile.TemporaryDirectory() as tmp:
        built = build_wheel(source, Path(tmp))
        print(f"  built {built.name}")
        for target in targets:
            install_into(built, target)

    print("\nthe manifest lists wheels BY NAME: a rebuild at the same version "
          "needs nothing;\nafter a version bump run  ./em.sh manifest 3.11  "
          "(or 3.13) for the one you ship.")
    print("\n▶ verifying by CONTENT (not by version string)", flush=True)
    return verify(source)


if __name__ == "__main__":
    sys.exit(main())
