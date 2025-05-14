# scripts/build.py
import os
import sys
import shutil
import subprocess
import zipfile
from pathlib import Path
from version_manager import VersionManager

def clean_build_directory(build_dir: Path):
    """Pulisce la directory di build"""
    if build_dir.exists():
        shutil.rmtree(build_dir)
    build_dir.mkdir(parents=True)

def copy_source_files(source_dir: Path, build_dir: Path):
    """Copia i file sorgente nella directory di build"""
    exclude_patterns = {
        '.git', '.github', '__pycache__', '*.pyc', 'build', 'dist',
        'scripts', '.gitignore', '.vscode', '.DS_Store', '*.blext',
        'blender_manifest_template.toml', 'version.json'
    }
    
    for item in source_dir.iterdir():
        if item.name in exclude_patterns:
            continue
            
        if item.name.startswith('.'):
            continue
            
        dest = build_dir / item.name
        if item.is_dir():
            shutil.copytree(item, dest, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        else:
            shutil.copy2(item, dest)

def download_platform_wheels(platform: str, wheels_dir: Path):
    """Download wheels for specific platform"""
    # Platform mapping
    platform_map = {
        'windows': 'win_amd64',
        'macos-intel': 'macosx_10_13_x86_64',
        'macos-arm': 'macosx_11_0_arm64',
        'linux': 'manylinux2014_x86_64'
    }
    
    pip_platform = platform_map.get(platform, 'win_amd64')
    requirements_file = Path(__file__).parent / 'requirements_wheels.txt'
    
    print(f"Downloading wheels for {platform} ({pip_platform})...")
    
    with open(requirements_file, 'r') as f:
        packages = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    
    for package in packages:
        cmd = [
            sys.executable, '-m', 'pip', 'download',
            package,
            '--only-binary=:all:',
            '--platform', pip_platform,
            '--python-version', '3.11',
            '--implementation', 'cp',
            '--abi', 'cp311',
            '-d', str(wheels_dir)
        ]
        result = subprocess.run(cmd, capture_output=True)
        if result.returncode != 0:
            print(f"Warning: Failed to download {package} for {platform}")

def build_extension(mode: str = 'dev', platform: str = None):
    """Costruisce l'extension in modalità specificata"""
    root_dir = Path(__file__).parent.parent
    build_dir = root_dir / "build"
    
    # Gestione versione
    vm = VersionManager(root_dir)
    
    # Set mode se specificato
    if mode != 'dev':
        vm.set_mode(mode)
    
    # Aggiorna i file con la versione corrente
    version = vm.update_manifest()
    
    print(f"Building EM Tools v{version} in {mode} mode...")
    
    # Pulisci e prepara build directory
    clean_build_directory(build_dir)
    
    # Copia file sorgente
    copy_source_files(root_dir, build_dir)
    
    # Se modalità produzione, scarica wheels
    if mode != 'dev':
        wheels_dir = root_dir / "wheels"
        wheels_dir.mkdir(exist_ok=True)
        
        if platform:
            # Download per piattaforma specifica
            download_platform_wheels(platform, wheels_dir)
        else:
            # Download generico (usa setup_development.py)
            print("Downloading wheels for development...")
            wheels_script = root_dir / "scripts" / "setup_development.py"
            subprocess.run([sys.executable, str(wheels_script)], cwd=root_dir)
        
        # Copia wheels nella build
        wheels_build = build_dir / "wheels"
        if wheels_dir.exists():
            shutil.copytree(wheels_dir, wheels_build)
    
    # Crea il package blext con nome appropriato
    if platform and mode != 'dev':
        package_name = f"em_tools-v{version}-{platform}.blext"
    else:
        package_name = f"em_tools-v{version}.blext"
    
    package_path = root_dir / package_name
    
    print(f"Creating package: {package_name}")
    
    with zipfile.ZipFile(package_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for file_path in build_dir.rglob('*'):
            if file_path.is_file():
                arc_name = file_path.relative_to(build_dir)
                zf.write(file_path, arc_name)
    
    print(f"✅ Extension built successfully: {package_path}")
    print(f"📦 Size: {package_path.stat().st_size / (1024*1024):.1f} MB")
    
    return package_path, version

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Build EM Tools extension")
    parser.add_argument('--mode', choices=['dev', 'rc', 'stable'], default='dev',
                       help="Build mode")
    parser.add_argument('--increment', choices=['dev_build', 'patch', 'minor', 'major'],
                       help="Increment version before building")
    parser.add_argument('--platform', choices=['windows', 'macos-intel', 'macos-arm', 'linux'],
                       help="Build for specific platform (production only)")
    
    args = parser.parse_args()
    
    # Incrementa versione se richiesto
    if args.increment:
        vm = VersionManager(Path(__file__).parent.parent)
        version = vm.increment_version(args.increment)
        print(f"Version incremented to: {version}")
    
    # Build extension
    package_path, version = build_extension(args.mode, args.platform)
    
    # Auto-tag per stable releases
    if args.mode == 'stable' and not args.platform:
        tag = f"v{version}"
        print(f"Creating git tag: {tag}")
        subprocess.run(['git', 'tag', tag])
        print("Remember to push the tag: git push origin --tags")

if __name__ == "__main__":
    main()