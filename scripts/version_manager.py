# scripts/version_manager.py
import re
import json
from pathlib import Path
from typing import Dict, Tuple, Optional

# ─────────────────────────────────────────────────────────────────────────────
# THE ONE PLACE where a package's Python decides its wheels, the Blender
# versions it is for, and its name. Read by the CI (.github/workflows/release.yml
# through `version_manager.py target|render|release-notes`), by `./em.sh
# manifest X.Y`, by scripts/build.py and by scripts/check_manifest.py.
#
# 27 Oct 2026: the cp311 package declared only `blender_version_min = "4.4.0"`,
# so Blender 5.1/5.2 (Python 3.13) offered to install it and it broke on its
# wheels. Blender's `blender_version_max` is EXCLUSIVE.
# ─────────────────────────────────────────────────────────────────────────────

#: the Python each Blender series ships (measured on the 5.0.1 / 5.1.0 / 5.2.0
#: builds on E.D.'s machine; 4.2–4.5 from the Blender release notes: 3.11)
BLENDER_PYTHON = {
    (4, 2): "3.11", (4, 3): "3.11", (4, 4): "3.11", (4, 5): "3.11",
    (5, 0): "3.11",
    (5, 1): "3.13", (5, 2): "3.13",
}

#: python version → what its package is
BLENDER_TARGETS = {
    "3.11": {
        "cp_tag": "cp311",
        "blender_min": "4.4.0",
        "blender_max": "5.1.0",          # exclusive: 4.4 … 5.0.x
        "package_tag": "blender44-50",
        "label": "Blender 4.4 – 5.0.x",
    },
    "3.13": {
        "cp_tag": "cp313",
        "blender_min": "5.1.0",
        "blender_max": None,             # open: 5.1 and later
        "package_tag": "blender51plus",
        "label": "Blender 5.1 and later",
    },
}

#: the platforms of a release, as the CI names them (matrix.platform)
RELEASE_PLATFORMS = (
    ("windows-x64", "Windows (x64)"),
    ("macosx-arm64", "macOS (Apple Silicon)"),
    ("macosx-x64", "macOS (Intel)"),
    ("linux-x64", "Linux (x64)"),
)


def target_for(python_version: str) -> Dict:
    """The package of a Python version (``"3.11"`` / ``"3.13"``), or ValueError."""
    key = str(python_version or "").strip()
    if key not in BLENDER_TARGETS:
        raise ValueError(f"no Blender target for Python {key!r}: "
                         f"known {', '.join(sorted(BLENDER_TARGETS))}")
    return dict(BLENDER_TARGETS[key], python_version=key)


def python_of_cp(cp_tag: str) -> Optional[str]:
    """``cp313`` → ``"3.13"`` (None when it is not a CPython tag)."""
    m = re.fullmatch(r"cp(\d)(\d+)", str(cp_tag or ""))
    return f"{m.group(1)}.{m.group(2)}" if m else None


def version_tuple(text: str) -> Tuple[int, ...]:
    return tuple(int(x) for x in re.findall(r"\d+", str(text))[:3])


def package_name(version: str, platform: str, python_version: str,
                 ext: str = "zip") -> str:
    """``em_tools-v<version>-<platform>-<package_tag>.<ext>`` — the CI's name."""
    tag = target_for(python_version)["package_tag"]
    return f"em_tools-v{version}-{platform}-{tag}.{ext}"


def release_notes(tag: str, release_type: str = "pre-release") -> str:
    """The body of a GitHub release: which file for which Blender."""
    version = tag[1:] if tag.startswith("v") else tag
    lines = [f"## EM Tools {tag}", "",
             f"This is a **{release_type}** of EM Tools.", ""]
    for py in sorted(BLENDER_TARGETS):
        t = target_for(py)
        rng = f"`blender_version_min = {t['blender_min']}`"
        if t["blender_max"]:
            rng += f", `blender_version_max = {t['blender_max']}` (excluded)"
        lines += [f"### Downloads for {t['label']} (Python {py}, {rng})"]
        lines += [f"- **{label}**: `{package_name(version, plat, py)}`"
                  for plat, label in RELEASE_PLATFORMS]
        lines += [""]
    lines += ["### Installation",
              "1. Choose the `.zip` file matching your **platform** and **Blender version**"]
    lines += [f"   - {target_for(py)['label']} → `{target_for(py)['package_tag']}` files"
              for py in sorted(BLENDER_TARGETS)]
    lines += ["2. In Blender: **Extensions** → **Install from Disk**",
              "3. Select the downloaded zip file (do not unzip)",
              "4. Enable the extension", "",
              "### What's Included",
              "Each package contains wheels compiled for one platform and one Python "
              "version, and declares the Blender versions that ship that Python: "
              "Blender refuses a package outside its range instead of installing "
              "wheels it cannot load."]
    return "\n".join(lines) + "\n"


_VERSION_LINE = re.compile(r'^version\s*=\s*"([^"]*)"', re.MULTILINE)
_CP_DIR = re.compile(r'wheels/(cp\d+)/')


class VersionManager:
    def __init__(self, root_dir: Path):
        self.root_dir = Path(root_dir)
        self.version_file = self.root_dir / "version.json"
        self.manifest_template = self.root_dir / "blender_manifest_template.toml"
        self.manifest_file = self.root_dir / "blender_manifest.toml"
        self.init_file = self.root_dir / "__init__.py"
    
    def load_version_config(self) -> Dict:
        """Carica la configurazione della versione da version.json"""
        if self.version_file.exists():
            with open(self.version_file, 'r') as f:
                return json.load(f)
        return {
            "major": 1,
            "minor": 5,
            "patch": 0,
            "dev_build": 43,
            "mode": "dev"  # dev, rc, stable
        }
    
    def save_version_config(self, config: Dict):
        """Salva la configurazione della versione"""
        with open(self.version_file, 'w') as f:
            json.dump(config, f, indent=2)
    
    def get_version_string(self, config: Dict) -> str:
        """Genera stringa di versione basata sul mode"""
        base = f"{config.get('major', 1)}.{config.get('minor', 5)}.{config.get('patch', 0)}"
        
        if config.get('mode') == 'dev':
            return f"{base}-dev.{config.get('dev_build', 0)}"
        elif config.get('mode') == 'rc':
            return f"{base}-rc.{config.get('rc_build', 1)}"
        else:  # stable
            return base
    
    def increment_version(self, part: str = 'dev_build') -> str:
        """Incrementa la versione specificata"""
        config = self.load_version_config()
        
        if part == 'dev_build':
            config['dev_build'] = config.get('dev_build', 0) + 1
        elif part == 'rc_build':
            config['rc_build'] = config.get('rc_build', 0) + 1
        elif part == 'patch':
            config['patch'] = config.get('patch', 0) + 1
            config['dev_build'] = 0
            # Reset RC quando incrementiamo patch
            config['rc_build'] = 1
        elif part == 'minor':
            config['minor'] = config.get('minor', 5) + 1
            config['patch'] = 0
            config['dev_build'] = 0
            config['rc_build'] = 1
        elif part == 'major':
            config['major'] = config.get('major', 1) + 1
            config['minor'] = 0
            config['patch'] = 0
            config['dev_build'] = 0
            config['rc_build'] = 1
        
        self.save_version_config(config)
        return self.get_version_string(config)
    
    def set_mode(self, mode: str):
        """Cambia la modalità (dev, rc, stable)"""
        config = self.load_version_config()
        config['mode'] = mode
        self.save_version_config(config)
        self.update_manifest_version()     # the version line; the wheels target stays
        return self.get_version_string(config)
        
    def generate_wheels_section(self, mode: str, python_version: str = None,
                                wheels_prefix: Optional[str] = None) -> str:
        """The ``wheels = [...]`` of ONE Python version: ``wheels/cp{ver}/``,
        or the old flat ``wheels/`` when there is no versioned folder.

        ``python_version`` is required: until 27 Oct 2026 a call without it took
        the FIRST ``wheels/cp*`` folder (cp311), and `./em.sh inc` turned a
        cp313 manifest into a cp311 one. ``wheels_prefix`` is the folder the
        manifest names (the CI's package flattens them into ``wheels/``).
        """
        if not python_version:
            raise ValueError("generate_wheels_section needs the target Python "
                             "(./em.sh manifest 3.11|3.13)")
        wheels_dir = self.root_dir / "wheels"
        cp_tag = target_for(python_version)["cp_tag"]
        versioned_dir = wheels_dir / cp_tag
        if versioned_dir.is_dir() and any(versioned_dir.glob("*.whl")):
            scan_dir, relative_prefix = versioned_dir, f"wheels/{cp_tag}"
        elif wheels_dir.is_dir() and any(wheels_dir.glob("*.whl")):
            scan_dir, relative_prefix = wheels_dir, "wheels"   # old flat layout
        else:
            return ""
        if wheels_prefix is not None:
            relative_prefix = wheels_prefix.rstrip("/")
        wheels = sorted(scan_dir.glob("*.whl"), key=lambda w: w.name.lower())
        wheels_list = [f'    "./{relative_prefix}/{w.name}",' for w in wheels]
        wheels_list[-1] = wheels_list[-1].rstrip(',')
        return "wheels = [\n" + "\n".join(wheels_list) + "\n]"

    def generate_dependencies_section(self, mode: str) -> str:
        """Genera la sezione dipendenze"""
        wheels_dir = self.root_dir / "wheels"
        if wheels_dir.exists() and any(wheels_dir.glob("*.whl")):
            return ""  # Se hai wheels, non serve la sezione dependencies
        else:
            return '''# External dependencies required:
    # pip install pandas networkx Pillow openpyxl matplotlib
    # Note: Run setup script to download wheels for packaging'''

    def manifest_python_version(self) -> Optional[str]:
        """The Python the LOCAL manifest targets, read from its wheels
        (``./wheels/cp313/…`` → ``"3.13"``); None without a manifest or with
        no versioned wheels in it."""
        if not self.manifest_file.exists():
            return None
        tags = set(_CP_DIR.findall(self.manifest_file.read_text(encoding="utf-8")))
        if len(tags) != 1:
            return None
        return python_of_cp(tags.pop())

    def repair_manifest_version(self):
        """Assicura che il manifest contenga la versione corretta"""
        try:
            return self.update_manifest_version(quiet=True) is not None
        except Exception as e:
            print(f"⚠️ Error repairing manifest: {e}")
            return False

    def update_manifest_version(self, quiet: bool = False) -> Optional[str]:
        """Rewrite ONLY the ``version = "…"`` line of the local manifest.

        Its wheels, its Blender range, everything else stay byte for byte: the
        target is E.D.'s choice (``./em.sh manifest X.Y``), not a side effect
        of ``inc`` / ``build`` / ``devrel``. → the version, or None when there
        is no manifest (then nothing is written)."""
        config = self.load_version_config()
        version = self.get_version_string(config)
        if not self.manifest_file.exists():
            print(f"ℹ️  no {self.manifest_file.name} here: version.json says {version}; "
                  f"make the manifest with ./em.sh manifest 3.11|3.13")
            return None
        content = self.manifest_file.read_text(encoding="utf-8")
        if not _VERSION_LINE.search(content):
            raise ValueError(f"{self.manifest_file} has no version line")
        new = _VERSION_LINE.sub(f'version = "{version}"', content, count=1)
        if new != content:
            with open(self.manifest_file, "w", encoding="utf-8", newline="") as f:
                f.write(new)
        if not quiet:
            target = self.manifest_python_version()
            print(f"✅ Manifest version: {version} (wheels target kept: "
                  f"{('Python ' + target) if target else 'unchanged'})")
        return version

    def render_manifest(self, python_version: str, version: Optional[str] = None,
                        wheels_prefix: Optional[str] = None) -> str:
        """The text of a manifest for ``python_version``: its wheels and its
        Blender range from ``BLENDER_TARGETS``. ``version`` overrides the one of
        version.json (the CI passes the tag's)."""
        target = target_for(python_version)
        if version is None:
            version = self.get_version_string(self.load_version_config())
        if not self.manifest_template.exists():
            raise FileNotFoundError(f"Template manifest not found: {self.manifest_template}")
        template = self.manifest_template.read_text(encoding="utf-8")
        for key in ("{VERSION}", "{BLENDER_RANGE}", "{WHEELS_SECTION}"):
            if key not in template:
                raise ValueError(f"Template manifest missing {key} placeholder")
        rng = f'blender_version_min = "{target["blender_min"]}"'
        if target["blender_max"]:
            rng += (f'\n# exclusive: Blender {target["blender_max"]} ships another Python'
                    f'\nblender_version_max = "{target["blender_max"]}"')
        config = self.load_version_config()
        return template.format(
            VERSION=version, BLENDER_RANGE=rng,
            WHEELS_SECTION=self.generate_wheels_section(
                config.get('mode', 'dev'), python_version, wheels_prefix))

    def update_manifest(self, python_version: str = None):
        """With ``python_version``: (re)generate the manifest for that Python —
        the explicit switch, ``./em.sh manifest X.Y``. Without it: only the
        version line (``update_manifest_version``), the wheels target kept."""
        if not python_version:
            return self.update_manifest_version() or \
                self.get_version_string(self.load_version_config())
        config = self.load_version_config()
        version = self.get_version_string(config)
        manifest_content = self.render_manifest(python_version, version)
        with open(self.manifest_file, 'w', encoding="utf-8") as f:
            f.write(manifest_content)
        target = target_for(python_version)
        print(f"✅ Manifest generated: {self.manifest_file}")
        print(f"   Version: {version}")
        print(f"   Mode: {config.get('mode', 'dev')}")
        print(f"   Python target: {python_version} ({target['cp_tag']}, {target['label']})")
        return version

    def update_init_py(self):
        """NOTA: Aggiornamento __init__.py rimosso perché bl_info non esiste più!"""
        # Non facciamo nulla perché Blender Extensions usano solo il manifest
        # Il versionamento è gestito interamente da blender_manifest.toml
        config = self.load_version_config()
        version = self.get_version_string(config)
        print(f"Note: __init__.py update skipped (Extensions use manifest only)")
        return version

# CLI interface
if __name__ == "__main__":
    import sys
    import argparse

    parser = argparse.ArgumentParser(description="Manage EM Tools versions")
    parser.add_argument('action', choices=['increment', 'set-mode', 'update', 'current',
                                           'target', 'render', 'release-notes'])
    parser.add_argument('--part', choices=['dev_build', 'patch', 'minor', 'major'],
                       default='dev_build', help="Part to increment")
    parser.add_argument('--mode', choices=['dev', 'rc', 'stable'],
                       help="Mode to set")
    parser.add_argument('--python-version', default=None,
                       help="Target Python version for wheels (e.g., 3.11, 3.13). "
                            "Only given, it changes the manifest's wheels target")
    parser.add_argument('--version', default=None,
                        help="render: the version to write (default: version.json's)")
    parser.add_argument('--wheels-prefix', default=None,
                        help="render: the folder the manifest names for its wheels")
    parser.add_argument('--output', default=None, help="render: where to write it")
    parser.add_argument('--tag', default=None, help="release-notes: the tag (v1.6.0-dev.33)")
    parser.add_argument('--release-type', default='pre-release',
                        help="release-notes: pre-release / stable")
    parser.add_argument('--files-only', action='store_true',
                        help="release-notes: only the package names")

    args = parser.parse_args()
    vm = VersionManager(Path(__file__).parent.parent)

    if args.action == 'increment':
        version = vm.increment_version(args.part)
        vm.update_manifest(args.python_version)
        vm.update_init_py()
        print(f"Version incremented to: {version}")

    elif args.action == 'set-mode':
        if not args.mode:
            print("Mode required for set-mode action")
            sys.exit(1)
        version = vm.set_mode(args.mode)
        if args.python_version:
            vm.update_manifest(args.python_version)
        vm.update_init_py()
        print(f"Mode set to {args.mode}, version: {version}")

    elif args.action == 'update':
        version = vm.update_manifest(args.python_version)
        vm.update_init_py()
        print(f"Files updated to version: {version}")

    elif args.action == 'current':
        config = vm.load_version_config()
        version = vm.get_version_string(config)
        print(f"Current version: {version} (mode: {config.get('mode', 'dev')})")

    elif args.action == 'target':
        # key=value lines, for $GITHUB_OUTPUT
        t = target_for(args.python_version)
        for key in ("cp_tag", "package_tag", "blender_min", "blender_max", "label"):
            print(f"{key}={t[key] or ''}")
        print(f"blender_tag={t['package_tag']}")

    elif args.action == 'render':
        if not args.python_version:
            print("render needs --python-version")
            sys.exit(1)
        text = vm.render_manifest(args.python_version, args.version, args.wheels_prefix)
        if args.output:
            Path(args.output).write_text(text, encoding="utf-8")
            print(f"✅ {args.output}: Python {args.python_version}, "
                  f"{target_for(args.python_version)['label']}")
        else:
            sys.stdout.write(text)

    elif args.action == 'release-notes':
        tag = args.tag or ("v" + vm.get_version_string(vm.load_version_config()))
        if args.files_only:
            version = tag[1:] if tag.startswith("v") else tag
            for py in sorted(BLENDER_TARGETS):
                print(f"   For {target_for(py)['label']}:")
                for plat, _label in RELEASE_PLATFORMS:
                    print(f"   - {package_name(version, plat, py)}")
        else:
            sys.stdout.write(release_notes(tag, args.release_type))
