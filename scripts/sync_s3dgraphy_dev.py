#!/usr/bin/env python3
"""
EMtools → s3dgraphy Development Sync Script
Replaces s3dgraphy wheel with development version without touching requirements.

NUOVO: Rimuove s3dgraphy dal site-packages di Blender prima di aggiornare!

Usage:
    python sync_s3dgraphy_dev.py                     # Auto-detect s3dgraphy
    python sync_s3dgraphy_dev.py /path/to/s3dgraphy  # Manual path
    python sync_s3dgraphy_dev.py --clean             # Clean build
    python sync_s3dgraphy_dev.py --restore           # Restore PyPI version
"""

import os
import sys
import shutil
import subprocess
import argparse
from pathlib import Path

class S3dGraphyDevSyncer:
    def __init__(self):
        # EMtools root is where this script is located
        if Path(__file__).parent.name == 'scripts':
            self.emtools_root = Path(__file__).parent.parent
        else:
            # If run from root directory
            self.emtools_root = Path(__file__).parent
            
        self.wheels_base_dir = self.emtools_root / "wheels"
        self.s3dgraphy_root = None

        # Rileva tutte le directory wheels (nuova struttura cp* + fallback flat)
        self.wheels_dirs = self._detect_wheels_dirs()

        # Per retrocompatibilità: self.wheels_dir punta alla prima disponibile
        self.wheels_dir = self.wheels_dirs[0] if self.wheels_dirs else self.wheels_base_dir

        # NUOVO: Rileva il site-packages di Blender
        self.blender_site_packages = self.detect_blender_site_packages()

    def _detect_wheels_dirs(self):
        """Rileva tutte le directory wheels disponibili (cp311, cp313, o flat)"""
        dirs = []

        # Nuova struttura: wheels/cp311/, wheels/cp313/, etc.
        if self.wheels_base_dir.exists():
            for subdir in sorted(self.wheels_base_dir.glob("cp*")):
                if subdir.is_dir() and any(subdir.glob("*.whl")):
                    dirs.append(subdir)

        # Fallback: struttura flat wheels/
        if not dirs and self.wheels_base_dir.exists() and any(self.wheels_base_dir.glob("*.whl")):
            dirs.append(self.wheels_base_dir)

        return dirs
        
    def detect_blender_site_packages(self):
        """
        Rileva TUTTI i percorsi dei site-packages di Blender installati.
        Ritorna una lista di Path, non un singolo path.
        """
        found_paths = []
        
        # Python versions to scan
        python_versions = ["python3.11", "python3.13"]

        # Cerca nelle posizioni comuni
        common_paths = [
            Path.home() / "AppData" / "Roaming" / "Blender Foundation" / "Blender",  # Windows
            Path.home() / ".config" / "blender",  # Linux
            Path.home() / "Library" / "Application Support" / "Blender",  # macOS
        ]

        for base in common_paths:
            if not base.exists():
                continue

            # Cerca TUTTE le versioni di Blender (4.3, 4.4, 4.5, 5.0, 5.1, etc.)
            for version_dir in sorted(base.glob("*.*")):
                for pyver in python_versions:
                    site_packages = version_dir / "extensions" / ".local" / "lib" / pyver / "site-packages"
                    if site_packages.exists():
                        found_paths.append(site_packages)
        
        if found_paths:
            print(f"✅ Trovati {len(found_paths)} site-packages di Blender:")
            for path in found_paths:
                # Estrae la versione dal path
                version = path.parts[-6] if len(path.parts) >= 6 else "unknown"
                print(f"   - Blender {version}: {path}")
        else:
            print("⚠️  Nessun site-packages di Blender trovato")
            print("    Il modulo potrebbe non aggiornarsi correttamente")
        
        return found_paths if found_paths else []
    
    def clean_blender_site_packages(self):
        """
        NUOVO: Rimuove s3dgraphy da TUTTI i site-packages di Blender trovati.
        Non fa assunzioni sulla versione - pulisce qualsiasi cosa trovi.
        """
        if not self.blender_site_packages:
            print("⚠️  Nessun site-packages di Blender rilevato, skip pulizia")
            return False
        
        print(f"\n🧹 Pulizia s3dgraphy da TUTTI i site-packages di Blender...")
        
        total_removed = 0
        
        # Itera su TUTTE le versioni di Blender trovate
        for site_packages_path in self.blender_site_packages:
            version = site_packages_path.parts[-6] if len(site_packages_path.parts) >= 6 else "unknown"
            print(f"\n   📂 Blender {version}:")
            print(f"      {site_packages_path}")
            
            removed_here = False
            
            # Rimuove la cartella s3dgraphy
            s3dgraphy_dir = site_packages_path / "s3dgraphy"
            if s3dgraphy_dir.exists():
                print(f"      🗑️  Rimozione cartella: s3dgraphy/")
                shutil.rmtree(s3dgraphy_dir)
                removed_here = True
                total_removed += 1
            else:
                print(f"      ℹ️  Cartella s3dgraphy/ non presente")
            
            # Rimuove TUTTE le cartelle .dist-info di s3dgraphy (qualsiasi versione)
            dist_info_pattern = list(site_packages_path.glob("s3dgraphy-*.dist-info"))
            if dist_info_pattern:
                for dist_info in dist_info_pattern:
                    print(f"      🗑️  Rimozione: {dist_info.name}")
                    shutil.rmtree(dist_info)
                    removed_here = True
                    total_removed += 1
            else:
                print(f"      ℹ️  Nessun .dist-info di s3dgraphy trovato")
            
            if removed_here:
                print(f"      ✅ Pulito!")
            else:
                print(f"      ℹ️  Niente da pulire")
        
        print(f"\n   📊 Totale elementi rimossi: {total_removed}")
        
        if total_removed > 0:
            print("   ✅ Pulizia completata su tutte le versioni!")
        else:
            print("   ℹ️  Nessuna installazione di s3dgraphy trovata")
        
        return True
        
    def find_s3dgraphy_automatically(self):
        """Try to find s3dgraphy repository automatically"""
        possible_locations = [
            # Same parent directory
            self.emtools_root.parent / "s3dgraphy",
            
            # Common GitHub locations
            Path.home() / "Documents" / "GitHub" / "s3dgraphy",
            self.emtools_root.parent / "GitHub" / "s3dgraphy",
            Path.home() / "Projects" / "s3dgraphy",
            Path.home() / "dev" / "s3dgraphy",
        ]
        
        for location in possible_locations:
            if self.is_valid_s3dgraphy_directory(location):
                print(f"🔍 Found s3dgraphy at: {location}")
                return location
                
        return None
    
    def is_valid_s3dgraphy_directory(self, path):
        """Check if a directory looks like s3dgraphy"""
        if not path or not path.exists():
            return False
            
        # Check for characteristic s3dgraphy files
        indicators = [
            path / "pyproject.toml",
            path / "setup.py", 
            path / "src" / "s3dgraphy",
        ]
        
        return any(indicator.exists() for indicator in indicators)
    
    def get_current_s3dgraphy_wheels(self):
        """Get current s3dgraphy wheels in EMtools (across all wheels dirs)"""
        wheels = []
        for wdir in self.wheels_dirs:
            wheels.extend(wdir.glob("s3dgraphy-*.whl"))
        return list(wheels)
    
    def backup_current_wheels(self):
        """Backup current s3dgraphy wheels"""
        current_wheels = self.get_current_s3dgraphy_wheels()
        if not current_wheels:
            return

        backup_dir = self.wheels_base_dir / ".backup"
        backup_dir.mkdir(exist_ok=True)

        for wheel in current_wheels:
            backup_path = backup_dir / wheel.name
            if not backup_path.exists():  # Don't overwrite existing backups
                shutil.copy2(wheel, backup_path)
                print(f"💾 Backed up: {wheel.name}")
    
    def clean_build_artifacts(self):
        """Clean previous build artifacts in s3dgraphy"""
        build_dirs = ["build", "dist", "*.egg-info"]
        
        for pattern in build_dirs:
            for path in self.s3dgraphy_root.glob(pattern):
                if path.is_dir():
                    print(f"🧹 Cleaning: {path}")
                    shutil.rmtree(path)
                elif path.is_file():
                    print(f"🧹 Removing: {path}")
                    path.unlink()
    
    def build_s3dgraphy_wheel(self, clean=False):
        """Build s3dgraphy wheel"""
        print("🔨 Building s3dgraphy development wheel...")
        
        if clean:
            self.clean_build_artifacts()
        
        # Try different build methods
        build_commands = [
            [sys.executable, "-m", "build", "--wheel"],  # Modern approach
            [sys.executable, "setup.py", "bdist_wheel"],  # Fallback
        ]
        
        for cmd in build_commands:
            try:
                result = subprocess.run(
                    cmd, 
                    cwd=self.s3dgraphy_root,
                    capture_output=True,
                    text=True,
                    check=True
                )
                print("✅ Wheel built successfully")
                return True
                
            except subprocess.CalledProcessError as e:
                print(f"⚠️  Command failed: {' '.join(cmd)}")
                continue
            except FileNotFoundError:
                print(f"⚠️  Command not found: {' '.join(cmd)}")
                continue
        
        print("❌ All build commands failed!")
        print("   Make sure 'build' package is installed: pip install build")
        return False
    
    def find_latest_s3dgraphy_wheel(self):
        """Find the latest built wheel in s3dgraphy/dist"""
        dist_dir = self.s3dgraphy_root / "dist"
        if not dist_dir.exists():
            return None
            
        wheels = list(dist_dir.glob("s3dgraphy-*.whl"))
        if not wheels:
            return None
            
        # Return the most recently created wheel
        return max(wheels, key=lambda p: p.stat().st_mtime)
    
    def remove_current_s3dgraphy_wheels(self):
        """Remove current s3dgraphy wheels from EMtools (all wheels dirs)"""
        current_wheels = self.get_current_s3dgraphy_wheels()
        for wheel in current_wheels:
            print(f"🗑️  Removing old wheel: {wheel.name} (from {wheel.parent.name})")
            wheel.unlink()

    def install_dev_wheel(self, wheel_path):
        """Copy development wheel to ALL EMtools wheels directories.

        s3dgraphy is pure-Python (py3-none-any), so the same wheel
        works in both cp311 and cp313 directories.
        """
        if not self.wheels_dirs:
            # Fallback: install in base dir
            dest = self.wheels_base_dir / wheel_path.name
            self.wheels_base_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(wheel_path, dest)
            print(f"📥 Installed: {dest.name}")
            return

        for wdir in self.wheels_dirs:
            dest = wdir / wheel_path.name
            shutil.copy2(wheel_path, dest)
            print(f"📥 Installed: {dest.name} → {wdir.name}/")
    
    def show_status(self):
        """Show current s3dgraphy status"""
        print("\n📊 s3dgraphy Status")
        print("=" * 50)
        
        # Check wheels directory
        current_wheels = self.get_current_s3dgraphy_wheels()
        if current_wheels:
            print(f"📦 Wheels in EMtools:")
            for wheel in current_wheels:
                print(f"   - {wheel.name}")
        else:
            print("📦 No s3dgraphy wheels in EMtools")
        
        # Check site-packages in ALL Blender versions
        if self.blender_site_packages:
            print(f"\n📂 Blender installations trovate: {len(self.blender_site_packages)}")
            
            for site_packages_path in self.blender_site_packages:
                version = site_packages_path.parts[-6] if len(site_packages_path.parts) >= 6 else "unknown"
                print(f"\n   🔹 Blender {version}:")
                
                s3d_dir = site_packages_path / "s3dgraphy"
                dist_infos = list(site_packages_path.glob("s3dgraphy-*.dist-info"))
                
                if s3d_dir.exists():
                    print(f"      ✅ s3dgraphy/ presente")
                else:
                    print(f"      ❌ s3dgraphy/ assente")
                    
                if dist_infos:
                    print(f"      📋 dist-info:")
                    for dist_info in dist_infos:
                        print(f"         - {dist_info.name}")
                else:
                    print(f"      📋 Nessun dist-info")
        else:
            print(f"\n📂 Nessun site-packages di Blender trovato")
        
        # Check for development version marker
        backup_dir = self.wheels_base_dir / ".backup"
        if backup_dir.exists() and any(backup_dir.glob("*.whl")):
            print(f"\n🔧 Backup wheels disponibili in .backup/")
            print(f"   Probabile versione DEVELOPMENT attiva")
        else:
            print(f"\n📦 Probabile versione PyPI attiva")
        
        print("=" * 50)
    
    def restore_pypi_version(self):
        """Restore PyPI version of s3dgraphy"""
        print("♻️  Restoring PyPI version...")

        # Remove development wheels
        self.remove_current_s3dgraphy_wheels()

        # NUOVO: Pulisci anche dal site-packages di Blender!
        self.clean_blender_site_packages()

        # Re-download PyPI version
        requirements_file = self.emtools_root / "scripts" / "requirements_wheels.txt"
        if not requirements_file.exists():
            print("❌ requirements_wheels.txt not found!")
            return False

        # Find s3dgraphy line in requirements
        with open(requirements_file, 'r') as f:
            for line in f:
                if line.strip().startswith('s3dgraphy'):
                    package = line.strip()
                    break
            else:
                print("❌ s3dgraphy not found in requirements!")
                return False

        # s3dgraphy is pure-Python (py3-none-any), so we only need to download once
        # and copy to all wheels directories
        print(f"📥 Downloading PyPI version: {package}")

        if self.wheels_dirs:
            # Download into the first directory, then copy to others
            first_dir = self.wheels_dirs[0]
            cmd = [
                sys.executable, '-m', 'pip', 'download',
                package,
                '--only-binary=:all:',
                '--no-deps',
                '-d', str(first_dir)
            ]

            result = subprocess.run(cmd)
            if result.returncode != 0:
                print("❌ Failed to download PyPI version")
                return False

            # Find the just-downloaded wheel
            new_wheels = list(first_dir.glob("s3dgraphy-*.whl"))
            if new_wheels and len(self.wheels_dirs) > 1:
                latest_wheel = max(new_wheels, key=lambda p: p.stat().st_mtime)
                for wdir in self.wheels_dirs[1:]:
                    dest = wdir / latest_wheel.name
                    shutil.copy2(latest_wheel, dest)
                    print(f"📥 Copied to: {wdir.name}/{latest_wheel.name}")
        else:
            # Fallback: flat structure
            cmd = [
                sys.executable, '-m', 'pip', 'download',
                package,
                '--only-binary=:all:',
                '--no-deps',
                '-d', str(self.wheels_base_dir)
            ]

            result = subprocess.run(cmd)
            if result.returncode != 0:
                print("❌ Failed to download PyPI version")
                return False

        print("✅ PyPI version restored")
        return True
    
    def _detect_current_python_version(self):
        """Detect which Python version the current manifest targets based on wheels dirs"""
        # If only one wheels dir, use that
        if len(self.wheels_dirs) == 1:
            name = self.wheels_dirs[0].name
            if name.startswith("cp"):
                ver = name[2:]
                return f"{ver[0]}.{ver[1:]}"
        # Try to read from existing manifest
        manifest_path = self.emtools_root / "blender_manifest.toml"
        if manifest_path.exists():
            content = manifest_path.read_text()
            if "wheels/cp313/" in content:
                return "3.13"
            if "wheels/cp311/" in content:
                return "3.11"
        return None

    def regenerate_manifest_if_needed(self):
        """Regenerate blender_manifest.toml if it exists"""
        manifest_path = self.emtools_root / "blender_manifest.toml"
        if manifest_path.exists():
            print("🔄 Regenerating manifest...")
            version_manager = self.emtools_root / "scripts" / "version_manager.py"
            if version_manager.exists():
                cmd = [sys.executable, str(version_manager), "update"]
                py_ver = self._detect_current_python_version()
                if py_ver:
                    cmd.extend(["--python-version", py_ver])
                subprocess.run(cmd, cwd=self.emtools_root)
    
    def sync_dev_version(self, s3dgraphy_path=None, clean=False):
        """Main sync function"""
        print("\n" + "=" * 50)
        print("🔧 s3dgraphy Development Version Sync")
        print("=" * 50)
        
        # 0. NUOVO: Prima di tutto, pulisci il site-packages di Blender!
        print("\n🎯 Step 0: Pulizia Blender site-packages")
        self.clean_blender_site_packages()
        
        # 1. Find s3dgraphy
        print("\n🎯 Step 1: Locating s3dgraphy")
        if s3dgraphy_path:
            self.s3dgraphy_root = Path(s3dgraphy_path).resolve()
        else:
            self.s3dgraphy_root = self.find_s3dgraphy_automatically()
        
        if not self.s3dgraphy_root:
            print("❌ s3dgraphy not found automatically!")
            print("   Please specify path manually:")
            print("   python sync_s3dgraphy_dev.py /path/to/s3dgraphy")
            return False
            
        if not self.is_valid_s3dgraphy_directory(self.s3dgraphy_root):
            print(f"❌ Invalid s3dgraphy directory: {self.s3dgraphy_root}")
            return False
        
        print(f"🎯 Source s3dgraphy: {self.s3dgraphy_root}")
        
        # 2. Backup current wheels
        print("\n🎯 Step 2: Backup current wheels")
        self.backup_current_wheels()
        
        # 3. Build development wheel
        print("\n🎯 Step 3: Build s3dgraphy wheel")
        if not self.build_s3dgraphy_wheel(clean=clean):
            return False
        
        # 4. Find the wheel
        print("\n🎯 Step 4: Locate built wheel")
        wheel_path = self.find_latest_s3dgraphy_wheel()
        if not wheel_path:
            print("❌ No wheel found after build!")
            return False
            
        print(f"📦 Built wheel: {wheel_path.name}")
        
        # 5. Replace in EMtools
        print("\n🎯 Step 5: Install in EMtools")
        self.remove_current_s3dgraphy_wheels()
        self.install_dev_wheel(wheel_path)
        
        # 6. Update manifest
        print("\n🎯 Step 6: Update manifest")
        self.regenerate_manifest_if_needed()
        
        print("\n" + "=" * 50)
        print("✅ Development version sync completed!")
        print("=" * 50)
        print("\n🔄 IMPORTANTE: Riavvia Blender per caricare la nuova versione")
        print("   Il modulo in site-packages è stato pulito e verrà")
        print("   reinstallato automaticamente dal wheel al prossimo avvio")
        
        return True

def main():
    parser = argparse.ArgumentParser(description="Sync s3dgraphy development version to EMtools")
    parser.add_argument(
        "s3dgraphy_path", 
        nargs="?", 
        help="Path to s3dgraphy directory (auto-detected if not provided)"
    )
    parser.add_argument(
        "--clean", 
        action="store_true", 
        help="Clean build artifacts before building"
    )
    parser.add_argument(
        "--restore", 
        action="store_true", 
        help="Restore PyPI version (remove development version)"
    )
    parser.add_argument(
        "--status", 
        action="store_true", 
        help="Show current s3dgraphy status"
    )
    
    args = parser.parse_args()
    
    syncer = S3dGraphyDevSyncer()
    
    if args.status:
        syncer.show_status()
        return
    
    if args.restore:
        success = syncer.restore_pypi_version()
        if success:
            syncer.regenerate_manifest_if_needed()
            print("✅ PyPI version restored!")
            print("🔄 Restart Blender to load the PyPI version")
    else:
        success = syncer.sync_dev_version(args.s3dgraphy_path, args.clean)
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()