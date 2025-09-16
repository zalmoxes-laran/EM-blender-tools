#!/usr/bin/env python3
"""
EMtools → s3dgraphy Development Sync Script
Replaces s3dgraphy wheel with development version without touching requirements.

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
            
        self.wheels_dir = self.emtools_root / "wheels"
        self.s3dgraphy_root = None
        
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
        if not path.exists():
            return False
            
        # Check for characteristic s3dgraphy files
        indicators = [
            path / "pyproject.toml",
            path / "setup.py", 
            path / "src" / "s3dgraphy",
        ]
        
        return any(indicator.exists() for indicator in indicators)
    
    def get_current_s3dgraphy_wheels(self):
        """Get current s3dgraphy wheels in EMtools"""
        if not self.wheels_dir.exists():
            return []
        return list(self.wheels_dir.glob("s3dgraphy-*.whl"))
    
    def backup_current_wheels(self):
        """Backup current s3dgraphy wheels"""
        current_wheels = self.get_current_s3dgraphy_wheels()
        backup_dir = self.wheels_dir / ".backup"
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
        return False
    
    def find_latest_s3dgraphy_wheel(self):
        """Find the most recently built s3dgraphy wheel"""
        dist_dir = self.s3dgraphy_root / "dist"
        if not dist_dir.exists():
            return None
            
        wheels = list(dist_dir.glob("s3dgraphy-*.whl"))
        if not wheels:
            return None
            
        # Return the most recent wheel
        return max(wheels, key=lambda p: p.stat().st_mtime)
    
    def remove_current_s3dgraphy_wheels(self):
        """Remove current s3dgraphy wheels from EMtools (but keep backup)"""
        current_wheels = self.get_current_s3dgraphy_wheels()
        
        for wheel in current_wheels:
            print(f"🗑️  Removing: {wheel.name}")
            wheel.unlink()
    
    def install_dev_wheel(self, wheel_path):
        """Install development wheel to EMtools"""
        # Ensure wheels directory exists
        self.wheels_dir.mkdir(exist_ok=True)
        
        # Copy new wheel
        dest_path = self.wheels_dir / wheel_path.name
        shutil.copy2(wheel_path, dest_path)
        
        print(f"📦 Installed dev wheel: {dest_path.name}")
        print(f"🔗 Source: {wheel_path}")
        return dest_path
    
    def restore_pypi_version(self):
        """Restore PyPI version of s3dgraphy"""
        print("🔄 Restoring PyPI version of s3dgraphy...")
        
        # Remove current dev wheels
        self.remove_current_s3dgraphy_wheels()
        
        # Check if we have backups
        backup_dir = self.wheels_dir / ".backup"
        if backup_dir.exists():
            backup_wheels = list(backup_dir.glob("s3dgraphy-*.whl"))
            if backup_wheels:
                # Restore the most recent backup
                latest_backup = max(backup_wheels, key=lambda p: p.stat().st_mtime)
                restored_path = self.wheels_dir / latest_backup.name
                shutil.copy2(latest_backup, restored_path)
                print(f"♻️  Restored from backup: {latest_backup.name}")
                return True
        
        # No backup available, download from PyPI
        print("📥 No backup found, downloading from PyPI...")
        return self.download_from_pypi()
    
    def download_from_pypi(self):
        """Download s3dgraphy from PyPI"""
        # Read the required version from requirements
        requirements_file = self.emtools_root / "scripts" / "requirements_wheels.txt"
        s3dgraphy_req = "s3dgraphy>=0.1.0"  # default
        
        if requirements_file.exists():
            with open(requirements_file, 'r') as f:
                for line in f:
                    if line.strip().startswith('s3dgraphy'):
                        s3dgraphy_req = line.strip()
                        break
        
        print(f"📦 Downloading: {s3dgraphy_req}")
        
        cmd = [
            sys.executable, '-m', 'pip', 'download',
            s3dgraphy_req,
            '--only-binary=:all:',
            '--python-version=3.11',
            '--no-deps',
            '-d', str(self.wheels_dir)
        ]
        
        try:
            subprocess.run(cmd, check=True)
            print("✅ Downloaded from PyPI")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to download: {e}")
            return False
    
    def regenerate_manifest_if_needed(self):
        """Regenerate manifest only if the version changed significantly"""
        version_manager = self.emtools_root / "scripts" / "version_manager.py"
        
        if not version_manager.exists():
            print("⚠️  version_manager.py not found - skipping manifest check")
            return
            
        print("🔄 Updating blender_manifest.toml...")
        
        try:
            subprocess.run([
                sys.executable, 
                str(version_manager), 
                "update"
            ], cwd=self.emtools_root, check=True, capture_output=True)
            
            print("✅ Manifest updated")
            
        except subprocess.CalledProcessError as e:
            print(f"⚠️  Failed to update manifest: {e}")
    
    def show_status(self):
        """Show current s3dgraphy status in EMtools"""
        current_wheels = self.get_current_s3dgraphy_wheels()
        
        print("\n📊 Current s3dgraphy status in EMtools:")
        if current_wheels:
            for wheel in current_wheels:
                # Try to determine if it's dev or PyPI version
                if "dev" in wheel.name or "+dev" in wheel.name:
                    status = "🔧 DEVELOPMENT"
                else:
                    status = "📦 PyPI"
                print(f"   {status}: {wheel.name}")
        else:
            print("   ❌ No s3dgraphy wheels found!")
        
        # Check for backups
        backup_dir = self.wheels_dir / ".backup"
        if backup_dir.exists():
            backups = list(backup_dir.glob("s3dgraphy-*.whl"))
            if backups:
                print(f"💾 Backups available: {len(backups)}")
    
    def sync_dev_version(self, s3dgraphy_path=None, clean=False):
        """Sync development version of s3dgraphy"""
        print("🚀 Syncing s3dgraphy development version to EMtools...")
        
        # 1. Find s3dgraphy
        if s3dgraphy_path:
            self.s3dgraphy_root = Path(s3dgraphy_path)
        else:
            self.s3dgraphy_root = self.find_s3dgraphy_automatically()
        
        if not self.s3dgraphy_root:
            print("❌ Could not find s3dgraphy directory!")
            print("   Try: python sync_s3dgraphy_dev.py /path/to/s3dgraphy")
            return False
            
        if not self.is_valid_s3dgraphy_directory(self.s3dgraphy_root):
            print(f"❌ Invalid s3dgraphy directory: {self.s3dgraphy_root}")
            return False
        
        print(f"🎯 Source s3dgraphy: {self.s3dgraphy_root}")
        
        # 2. Backup current wheels
        self.backup_current_wheels()
        
        # 3. Build development wheel
        if not self.build_s3dgraphy_wheel(clean=clean):
            return False
        
        # 4. Find the wheel
        wheel_path = self.find_latest_s3dgraphy_wheel()
        if not wheel_path:
            print("❌ No wheel found after build!")
            return False
            
        print(f"📦 Built wheel: {wheel_path.name}")
        
        # 5. Replace in EMtools
        self.remove_current_s3dgraphy_wheels()
        self.install_dev_wheel(wheel_path)
        
        # 6. Update manifest
        self.regenerate_manifest_if_needed()
        
        print("✅ Development version sync completed!")
        print("🔄 Reload EM Tools extension in Blender to use updated s3dgraphy")
        
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
