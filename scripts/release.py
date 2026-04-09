# scripts/release.py
"""
EM Tools Release Helper
Handles building and publishing releases with git tagging
"""

import sys
import subprocess
import argparse
import json
from pathlib import Path
from version_manager import VersionManager
from build import build_extension

def check_git_status():
    """Check if git working directory is clean"""
    result = subprocess.run(['git', 'status', '--porcelain'], 
                          capture_output=True, text=True)
    if result.stdout.strip():
        print("⚠️  Warning: You have uncommitted changes:")
        print(result.stdout)
        response = input("Continue anyway? (y/N): ")
        if response.lower() != 'y':
            sys.exit(1)

def create_and_push_tag(version, mode):
    """Create git tag and optionally push"""
    tag = f"v{version}"
    
    print(f"🏷️  Creating git tag: {tag}")
    result = subprocess.run(['git', 'tag', tag], capture_output=True)
    
    if result.returncode != 0:
        print(f"❌ Failed to create tag {tag}")
        print(result.stderr.decode())
        return False
    
    # Ask to push
    if mode != 'dev':
        response = input(f"Push tag {tag} to remote? (Y/n): ")
        if response.lower() != 'n':
            print(f"🚀 Pushing tag to remote...")
            subprocess.run(['git', 'push', 'origin', tag])
            
            # Also push the release branch if stable
            if mode == 'stable':
                subprocess.run(['git', 'push', 'origin', 'main'])
    
    return True

def publish_release(mode='stable', increment_part='patch', skip_git=False):
    """Complete release workflow"""
    print(f"🚀 Starting {mode} release process...")
    
    # Check git status
    if not skip_git:
        check_git_status()
    
    # Get version info before build
    vm = VersionManager(Path(__file__).parent.parent)
    old_config = vm.load_version_config()
    old_version = vm.get_version_string(old_config)
    
    # Build extension (which increments version if specified)
    package_path, new_version = build_extension(mode)
    
    # Generate commit message
    if mode == 'rc':
        commit_msg = f"release: create RC {new_version} from {old_version}"
    elif mode == 'stable':
        commit_msg = f"release: stable {new_version}"
    else:
        commit_msg = f"build: {mode} version {new_version}"
    
    # Auto-commit changes
    if not skip_git:
        print(f"\n📝 Committing changes: {commit_msg}")
        subprocess.run(['git', 'add', '-A'])
        subprocess.run(['git', 'commit', '-m', commit_msg])
    
    # Create and push git tag
    if not skip_git:
        create_and_push_tag(new_version, mode)
    
    # Instructions for manual steps
    print(f"\n✅ Release {new_version} created successfully!")
    print(f"📦 Package: {package_path}")
    print(f"💬 Committed: {commit_msg}")
    
    if mode == 'stable':
        print("\n📝 Next steps for stable release:")
        print("1. ✅ Package created")
        print("2. ✅ Git tag created and pushed") 
        print("3. ✅ Changes committed")
        print("4. 🔄 GitHub Actions will create the release automatically")
        print("5. 📤 Manually upload to Blender Extensions Platform if needed")
    elif mode == 'rc':
        print(f"\n📝 Next steps for RC {new_version}:")
        print("1. Test the package thoroughly")
        print("2. If issues found, fix and create new RC")
        print("3. If all good, run: python scripts/release.py --mode stable")
    
    # Show release info
    config = vm.load_version_config()
    if 'changelog' in config and new_version in config['changelog']:
        print(f"\n📋 Changelog for {new_version}:")
        for item in config['changelog'][new_version]:
            print(f"  • {item}")

def quick_dev_release():
    """Quick development release without git operations"""
    print("🏃‍♂️ Quick development build...")
    package_path, version = build_extension('dev')
    print(f"✅ Dev build {version} ready: {package_path}")

def main():
    parser = argparse.ArgumentParser(
        description="EM Tools Release Helper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/release.py                   # Quick dev build
  python scripts/release.py --mode rc         # Create release candidate
  python scripts/release.py --mode stable     # Create stable release
  python scripts/release.py --skip-git        # Build without git operations
  python scripts/release.py --mode stable -i minor  # Stable with minor increment
  
Release Workflow:
  1. Development: python scripts/dev.py inc && python scripts/dev.py build
  2. Release Candidate: python scripts/release.py --mode rc
  3. Test RC thoroughly
  4. Stable Release: python scripts/release.py --mode stable
        """
    )
    
    parser.add_argument('-m', '--mode', choices=['dev', 'rc', 'stable'],
                       default='dev', help='Release mode')
    parser.add_argument('-i', '--increment', choices=['dev_build', 'patch', 'minor', 'major'],
                       default='patch', help='Version part to increment')
    parser.add_argument('--skip-git', action='store_true',
                       help='Skip git operations (tag creation/push)')
    parser.add_argument('--quick', action='store_true',
                       help='Quick dev build without prompts')
    
    args = parser.parse_args()
    
    if args.quick or args.mode == 'dev':
        quick_dev_release()
    else:
        publish_release(args.mode, args.increment, args.skip_git)

if __name__ == "__main__":
    main()