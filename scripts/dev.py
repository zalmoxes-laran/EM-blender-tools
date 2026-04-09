# scripts/dev.py
"""
EM Tools Development Helper
Usage: python scripts/dev.py <command> [options]
"""

import sys
import subprocess
import argparse
from pathlib import Path
from version_manager import VersionManager

def setup_dev():
    """Setup development environment"""
    print("🔧 Setting up development environment...")
    
    # Detect OS
    import platform
    system = platform.system().lower()
    
    script_dir = Path(__file__).parent
    
    if system == 'windows':
        script = script_dir / "setup_dev_windows.bat"
        subprocess.run(str(script), shell=True)
    elif system == 'darwin':
        script = script_dir / "setup_dev_macos.sh"
        subprocess.run(["bash", str(script)])
    else:  # Linux
        script = script_dir / "setup_dev_linux.sh"
        subprocess.run(["bash", str(script)])

def increment_version(part='dev_build'):
    """Increment version and update files"""
    vm = VersionManager(Path(__file__).parent.parent)
    version = vm.increment_version(part)
    vm.update_manifest()
    vm.update_init_py()
    print(f"✅ Version incremented to: {version}")
    return version

def set_mode(mode):
    """Set development mode"""
    vm = VersionManager(Path(__file__).parent.parent)
    version = vm.set_mode(mode)
    vm.update_manifest()
    vm.update_init_py()
    print(f"✅ Mode set to {mode}, version: {version}")
    return version

def build_extension(mode='dev', increment_part=None):
    """Build extension package"""
    print(f"🏗️ Building extension in {mode} mode...")
    
    build_script = Path(__file__).parent / "build.py"
    cmd = [sys.executable, str(build_script), "--mode", mode]
    
    if increment_part:
        cmd.extend(["--increment", increment_part])
    
    subprocess.run(cmd)

def current_status():
    """Show current version and status"""
    vm = VersionManager(Path(__file__).parent.parent)
    config = vm.load_version_config()
    version = vm.get_version_string(config)
    
    print("📋 Current Status:")
    print(f"   Version: {version}")
    print(f"   Mode: {config['mode']}")
    print(f"   Dev Build: {config['dev_build']}")

def main():
    parser = argparse.ArgumentParser(
        description="EM Tools Development Helper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/dev.py setup                 # Setup dev environment
  python scripts/dev.py inc                   # Increment dev build
  python scripts/dev.py inc -p patch          # Increment patch version
  python scripts/dev.py mode -m rc            # Switch to RC mode
  python scripts/dev.py build                 # Build dev version
  python scripts/dev.py build -m stable -i patch  # Build stable with patch increment
  python scripts/dev.py status                # Show current version/mode
  
Quick Commands:
  python scripts/dev.py setup                 # First time setup
  python scripts/dev.py inc && python scripts/dev.py build  # Quick dev iteration
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Setup command
    setup_parser = subparsers.add_parser('setup', help='Setup development environment')
    
    # Increment command
    inc_parser = subparsers.add_parser('inc', help='Increment version')
    inc_parser.add_argument('-p', '--part', choices=['dev_build', 'patch', 'minor', 'major'],
                           default='dev_build', help='Version part to increment')
    
    # Mode command
    mode_parser = subparsers.add_parser('mode', help='Set development mode')
    mode_parser.add_argument('-m', '--mode', choices=['dev', 'rc', 'stable'],
                            required=True, help='Mode to set')
    
    # Build command
    build_parser = subparsers.add_parser('build', help='Build extension')
    build_parser.add_argument('-m', '--mode', choices=['dev', 'rc', 'stable'],
                             default='dev', help='Build mode')
    build_parser.add_argument('-i', '--increment', choices=['dev_build', 'patch', 'minor', 'major'],
                             help='Increment version before building')
    
    # Status command
    status_parser = subparsers.add_parser('status', help='Show current status')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    if args.command == 'setup':
        setup_dev()
    elif args.command == 'inc':
        increment_version(args.part)
    elif args.command == 'mode':
        set_mode(args.mode)
    elif args.command == 'build':
        build_extension(args.mode, args.increment)
    elif args.command == 'status':
        current_status()

if __name__ == "__main__":
    main()