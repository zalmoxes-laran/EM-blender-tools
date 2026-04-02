# scripts/build.py
import os
import sys
import shutil
import subprocess
import zipfile
from pathlib import Path
from version_manager import VersionManager

def clean_build_directory(build_dir: Path):
    """Pulisce la directory di build completamente"""
    if build_dir.exists():
        print(f"Cleaning build directory: {build_dir}")
        shutil.rmtree(build_dir)
    build_dir.mkdir(parents=True)
    print(f"✅ Build directory cleaned and recreated")

def copy_source_files(source_dir: Path, build_dir: Path):
    """Copia i file sorgente nella directory di build"""
    exclude_patterns = {
        '.git', '.github', '__pycache__', '*.pyc', 'build', 'dist',
        'scripts', '.gitignore', '.vscode', '.DS_Store', '*.blext',
        'blender_manifest_template.toml', 'version.json', 'em.bat', 'em.sh',
        '*.backup', 'lib'  # Escludi 'lib' (vecchio approccio) ma NON 'wheels'!
    }
    
    exclude_extensions = {'.blext', '.backup'}  # Escludi per estensione
    
    print(f"Copying source files from {source_dir} to {build_dir}")
    copied_files = 0
    skipped_files = 0
    
    for item in source_dir.iterdir():
        # Skip excluded patterns
        if item.name in exclude_patterns:
            print(f"  Skipping (excluded): {item.name}")
            skipped_files += 1
            continue
            
        # Skip by extension
        if item.suffix in exclude_extensions:
            print(f"  Skipping (extension): {item.name}")
            skipped_files += 1
            continue
            
        if item.name.startswith('.'):
            print(f"  Skipping (hidden): {item.name}")
            skipped_files += 1
            continue
            
        dest = build_dir / item.name
        if item.is_dir():
            # Skip certain directories entirely  
            if item.name in {'build', '__pycache__', '.git', '.github', 'lib'}:
                print(f"  Skipping directory: {item.name}")
                skipped_files += 1
                continue
            print(f"  Copying directory: {item.name}")
            shutil.copytree(item, dest, ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '*.blext'))
        else:
            print(f"  Copying file: {item.name}")
            shutil.copy2(item, dest)
            copied_files += 1
    
    print(f"✅ Copied {copied_files} files and directories")
    print(f"⏭️  Skipped {skipped_files} excluded items")

def download_platform_wheels(platform: str, wheels_dir: Path, python_version: str = '3.11'):
    """Download wheels for specific platform"""
    # Platform mapping
    platform_map = {
        'windows': 'win_amd64',
        'macos-intel': 'macosx_10_13_x86_64',
        'macos-arm': 'macosx_11_0_arm64',
        'linux': 'manylinux2014_x86_64'
    }

    cp_tag = f"cp{python_version.replace('.', '')}"
    pip_platform = platform_map.get(platform, 'win_amd64')
    requirements_file = Path(__file__).parent / 'requirements_wheels.txt'

    print(f"Downloading wheels for {platform} ({pip_platform}) Python {python_version}...")

    with open(requirements_file, 'r') as f:
        packages = [line.strip() for line in f if line.strip() and not line.startswith('#')]

    for package in packages:
        cmd = [
            sys.executable, '-m', 'pip', 'download',
            package,
            '--only-binary=:all:',
            '--platform', pip_platform,
            '--python-version', python_version,
            '--implementation', 'cp',
            '--abi', cp_tag,
            '-d', str(wheels_dir)
        ]
        result = subprocess.run(cmd, capture_output=True)
        if result.returncode != 0:
            print(f"Warning: Failed to download {package} for {platform} (Python {python_version})")

def build_extension(mode: str = 'dev', platform: str = None, python_version: str = '3.11'):
    """Costruisce l'extension in modalità specificata"""
    root_dir = Path(__file__).parent.parent
    build_dir = root_dir / "build"

    # Rimuovi vecchi file .blext per evitare raddoppiamenti
    print("Cleaning old .blext files...")
    for old_blext in root_dir.glob("*.blext"):
        print(f"  Removing: {old_blext.name}")
        old_blext.unlink()

    # Gestione versione - PRIMA genera il manifest!
    vm = VersionManager(root_dir)

    # Set mode se specificato
    if mode != 'dev':
        vm.set_mode(mode)

    # Aggiorna i file con la versione corrente (con python_version per selezionare le wheels giuste)
    version = vm.update_manifest(python_version)  # Questo genera blender_manifest.toml valido!
    
    print(f"Building EM Tools v{version} in {mode} mode...")
    
    # Verifica che il manifest sia stato generato correttamente
    manifest_file = root_dir / "blender_manifest.toml"
    if not manifest_file.exists():
        raise FileNotFoundError("blender_manifest.toml not found! Version manager failed.")
    
    # Verifica che il manifest contenga i campi richiesti
    with open(manifest_file, 'r') as f:
        manifest_content = f.read()
        if '{VERSION}' in manifest_content or 'id' not in manifest_content:
            raise ValueError("blender_manifest.toml contains unresolved placeholders!")
    
    print(f"✅ Manifest generated successfully for version {version}")
    
    # Pulisci e prepara build directory COMPLETAMENTE
    clean_build_directory(build_dir)
    
    # Copia file sorgente (ESCLUSI i vecchi wheels/build)
    copy_source_files(root_dir, build_dir)
    
    # VERIFICA WHEELS PRIMA DELLA COPIA
    wheels_dir = root_dir / "wheels"
    print(f"\n🔍 Checking wheels directory: {wheels_dir}")
    print(f"   Exists: {wheels_dir.exists()}")
    
    if wheels_dir.exists():
        wheel_files = list(wheels_dir.glob("*.whl"))
        print(f"   Wheel files found: {len(wheel_files)}")
        for wheel in wheel_files[:3]:  # Show first 3
            print(f"     - {wheel.name}")
        if len(wheel_files) > 3:
            print(f"     ... and {len(wheel_files) - 3} more")
        
        # Verifica se le wheels sono già nella build directory
        wheels_build = build_dir / "wheels"
        if wheels_build.exists():
            copied_wheels = list(wheels_build.glob("*.whl"))
            print(f"   ✅ Wheels already copied to build: {len(copied_wheels)}")
        else:
            print(f"   ❌ No wheels in build directory!")
    else:
        print("   ❌ Wheels directory not found!")
        print("   Run 'em setup' to download wheels")
    
    # Se modalità produzione e non ci sono wheels, scaricale
    if mode != 'dev' and not wheels_dir.exists():
        print(f"Production mode but no wheels found - downloading for Python {python_version}...")
        wheels_script = root_dir / "scripts" / "setup_development.py"
        subprocess.run([sys.executable, str(wheels_script), f'--python-version={python_version}'], cwd=root_dir)

    # Mapping Python version → Blender compatibility tag (user-friendly)
    BLENDER_TAG_MAP = {
        '3.11': 'blender50',
        '3.13': 'blender51',
    }
    blender_tag = BLENDER_TAG_MAP.get(python_version, f'py{python_version.replace(".", "")}')

    # Crea il package blext con nome appropriato
    if platform and mode != 'dev':
        package_name = f"em_tools-v{version}-{platform}-{blender_tag}.blext"
    else:
        package_name = f"em_tools-v{version}.blext"
    
    releases_dir = root_dir.parent / "EM_Tools_Releases"
    releases_dir.mkdir(exist_ok=True)
    package_path = releases_dir / package_name
    
    print(f"Creating package: {package_name}")
    
    with zipfile.ZipFile(package_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for file_path in build_dir.rglob('*'):
            if file_path.is_file():
                arc_name = file_path.relative_to(build_dir)
                zf.write(file_path, arc_name)
    
    print(f"✅ Extension built successfully: {package_path}")
    
    # Calcola e mostra la dimensione
    size_mb = package_path.stat().st_size / (1024*1024)
    print(f"📦 Size: {size_mb:.1f} MB")
    
    # Debug info sui contenuti del package
    with zipfile.ZipFile(package_path, 'r') as zf:
        files_count = len(zf.namelist())
        wheels_in_zip = [f for f in zf.namelist() if f.startswith('wheels/')]
        manifest_in_zip = [f for f in zf.namelist() if f == 'blender_manifest.toml']
        
        print(f"📊 Package contents:")
        print(f"   Total files: {files_count}")
        print(f"   Wheels included: {len(wheels_in_zip)}")
        print(f"   Manifest found: {'✅' if manifest_in_zip else '❌'}")
        
        if wheels_in_zip:
            print(f"   Wheels list:")
            for wheel in wheels_in_zip[:5]:  # Show first 5
                print(f"     - {wheel}")
            if len(wheels_in_zip) > 5:
                print(f"     ... and {len(wheels_in_zip) - 5} more")
        
        # Verify manifest content in zip
        if manifest_in_zip:
            manifest_content = zf.read('blender_manifest.toml').decode('utf-8')
            if 'wheels = [' in manifest_content:
                print(f"   Manifest wheels section: ✅ Found")
            else:
                print(f"   Manifest wheels section: ❌ Missing")
    
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
    parser.add_argument('--python-version', default='3.11',
                       help="Target Python version (default: 3.11). Use 3.13 for Blender 5.1+")

    args = parser.parse_args()

    # Incrementa versione se richiesto
    if args.increment:
        vm = VersionManager(Path(__file__).parent.parent)
        version = vm.increment_version(args.increment)
        print(f"Version incremented to: {version}")

    # Build extension
    package_path, version = build_extension(args.mode, args.platform, args.python_version)

    # Auto-tag per stable releases
    if args.mode == 'stable' and not args.platform:
        tag = f"v{version}"
        print(f"Creating git tag: {tag}")
        subprocess.run(['git', 'tag', tag])
        print("Remember to push the tag: git push origin --tags")

if __name__ == "__main__":
    main()