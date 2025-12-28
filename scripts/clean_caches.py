# scripts/clean_caches.py
"""
Clean Python and Blender caches for EM-blender-tools
Called by setup_development.py when using force mode
"""

import os
import sys
import shutil
from pathlib import Path


def clean_python_caches(root_dir):
    """Remove all __pycache__ directories and .pyc files"""
    print("\n🧹 Cleaning Python caches...")

    removed_dirs = 0
    removed_files = 0

    # Find and remove __pycache__ directories
    for pycache_dir in Path(root_dir).rglob('__pycache__'):
        try:
            shutil.rmtree(pycache_dir)
            removed_dirs += 1
            print(f"   Removed: {pycache_dir.relative_to(root_dir)}")
        except Exception as e:
            print(f"   Warning: Could not remove {pycache_dir}: {e}")

    # Find and remove .pyc files
    for pyc_file in Path(root_dir).rglob('*.pyc'):
        try:
            pyc_file.unlink()
            removed_files += 1
        except Exception as e:
            print(f"   Warning: Could not remove {pyc_file}: {e}")

    print(f"   ✓ Removed {removed_dirs} __pycache__ directories")
    print(f"   ✓ Removed {removed_files} .pyc files")

    return removed_dirs + removed_files > 0


def clean_blender_extension_cache():
    """
    Clean Blender site-packages cache

    Removes:
    - Python site-packages cache (.local/lib/python3.11/site-packages)

    NOTE: Does NOT remove the extension installation itself.
    This only cleans cached Python packages to force fresh installation of wheels.
    """
    print("\n🧹 Checking Blender site-packages cache...")

    blender_sitepackages_paths = []

    # Windows
    if os.name == 'nt':
        appdata = os.environ.get('APPDATA')
        if appdata:
            # Blender 4.0+ extensions location
            base_path = Path(appdata) / "Blender Foundation" / "Blender"
            if base_path.exists():
                # Find all Blender versions
                for version_dir in base_path.glob("*"):
                    if version_dir.is_dir():
                        # Python site-packages cache
                        sitepackages_path = version_dir / "extensions" / ".local" / "lib" / "python3.11" / "site-packages"
                        if sitepackages_path.exists():
                            blender_sitepackages_paths.append(sitepackages_path)

    # Linux
    elif os.name == 'posix' and not sys.platform.startswith('darwin'):
        home = os.environ.get('HOME')
        if home:
            base_path = Path(home) / ".config" / "blender"
            if base_path.exists():
                for version_dir in base_path.glob("*"):
                    if version_dir.is_dir():
                        # Python site-packages cache
                        sitepackages_path = version_dir / "extensions" / ".local" / "lib" / "python3.11" / "site-packages"
                        if sitepackages_path.exists():
                            blender_sitepackages_paths.append(sitepackages_path)

    # macOS
    elif sys.platform.startswith('darwin'):
        home = os.environ.get('HOME')
        if home:
            base_path = Path(home) / "Library" / "Application Support" / "Blender"
            if base_path.exists():
                for version_dir in base_path.glob("*"):
                    if version_dir.is_dir():
                        # Python site-packages cache
                        sitepackages_path = version_dir / "extensions" / ".local" / "lib" / "python3.11" / "site-packages"
                        if sitepackages_path.exists():
                            blender_sitepackages_paths.append(sitepackages_path)

    if not blender_sitepackages_paths:
        print("   ℹ️  No Blender site-packages cache found")
        return False

    # Show what will be removed
    print(f"   Found {len(blender_sitepackages_paths)} Blender site-packages cache location(s):")
    for path in blender_sitepackages_paths:
        print(f"   - {path}")

    print("\n   ⚠️  WARNING: Removing Blender site-packages caches")
    print("   This will force Blender to reinstall wheels from the extension on next activation")
    print("   The extension itself will NOT be removed")

    response = input("\n   Remove site-packages caches? (y/N): ")

    if response.lower() == 'y':
        removed = 0

        # Remove site-packages caches
        for path in blender_sitepackages_paths:
            try:
                shutil.rmtree(path)
                print(f"   ✓ Removed: {path}")
                removed += 1
            except Exception as e:
                print(f"   ✗ Failed to remove {path}: {e}")

        print(f"\n   ✓ Removed {removed}/{len(blender_sitepackages_paths)} site-packages caches")
        print("   Restart Blender or disable/enable the extension to reinstall wheels")
        return True
    else:
        print("   Skipped site-packages cache removal")
        return False


def clean_pip_cache():
    """Clean pip cache for downloaded packages"""
    print("\n🧹 Cleaning pip cache...")

    try:
        import subprocess
        result = subprocess.run(
            ['pip', 'cache', 'purge'],
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            print("   ✓ Pip cache cleared")
            return True
        else:
            print(f"   ⚠️  Pip cache purge failed: {result.stderr}")
            return False
    except Exception as e:
        print(f"   ⚠️  Could not clear pip cache: {e}")
        return False


def clean_all(root_dir, include_blender=False, include_pip=False):
    """
    Clean all caches

    Args:
        root_dir: Root directory of EM-blender-tools
        include_blender: If True, also clean Blender extension installations
        include_pip: If True, also clean pip cache
    """
    print("\n" + "=" * 60)
    print("   EM Tools - Cache Cleaning")
    print("=" * 60)

    results = {}

    # Always clean Python caches
    results['python'] = clean_python_caches(root_dir)

    # Optional: Clean Blender extension cache
    if include_blender:
        results['blender'] = clean_blender_extension_cache()

    # Optional: Clean pip cache
    if include_pip:
        results['pip'] = clean_pip_cache()

    print("\n" + "=" * 60)
    print("   Cache Cleaning Complete")
    print("=" * 60)

    return results


if __name__ == '__main__':
    import sys
    import argparse

    parser = argparse.ArgumentParser(description="Clean EM Tools caches")
    parser.add_argument('--blender', action='store_true',
                       help='Also clean Blender extension installations')
    parser.add_argument('--pip', action='store_true',
                       help='Also clean pip cache')
    parser.add_argument('--all', action='store_true',
                       help='Clean everything (Python + Blender + pip)')

    args = parser.parse_args()

    # Get root directory (parent of scripts/)
    root_dir = Path(__file__).parent.parent

    include_blender = args.blender or args.all
    include_pip = args.pip or args.all

    clean_all(root_dir, include_blender=include_blender, include_pip=include_pip)
