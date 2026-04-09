# scripts/setup_development.py
import os
import subprocess
import platform
import sys
import shutil
from pathlib import Path

def clean_wheels_directory(force=False, python_version='3.11'):
    """Pulisce la directory wheels solo se necessario"""
    script_dir = os.path.dirname(__file__)
    cp_tag = f"cp{python_version.replace('.', '')}"
    wheels_dir = os.path.join(script_dir, '..', 'wheels', cp_tag)

    # Se force=True, rimuovi sempre
    if force:
        if os.path.exists(wheels_dir):
            print(f"FORCE MODE: Cleaning existing wheels directory ({cp_tag})...")
            shutil.rmtree(wheels_dir)

        # Clean Python caches quando in force mode
        print("\n🧹 FORCE MODE: Cleaning Python caches...")
        try:
            from clean_caches import clean_python_caches
            root_dir = os.path.abspath(os.path.join(script_dir, '..'))
            clean_python_caches(root_dir)
        except Exception as e:
            print(f"⚠️  Warning: Could not clean Python caches: {e}")
            print(f"   You can manually run: python scripts/clean_caches.py")

        os.makedirs(wheels_dir, exist_ok=True)
        return wheels_dir

    # Se force=False, crea solo se non esiste
    if not os.path.exists(wheels_dir):
        print(f"Creating wheels directory ({cp_tag})...")
        os.makedirs(wheels_dir, exist_ok=True)
    else:
        print(f"Using existing wheels directory ({cp_tag})...")

    return wheels_dir

def check_existing_wheels(wheels_dir):
    """Controlla se esistono già wheels valide"""
    if not os.path.exists(wheels_dir):
        return []
    
    wheels = list(Path(wheels_dir).glob("*.whl"))
    return wheels

def check_and_clean_duplicates(wheels_dir, python_version='3.11'):
    """Rimuove wheel duplicate mantenendo solo quelle per la versione Python target"""
    from collections import defaultdict

    cp_tag = f"cp{python_version.replace('.', '')}"

    files = os.listdir(wheels_dir)
    packages = defaultdict(list)

    # Raggruppa i file per pacchetto
    for file in files:
        if file.endswith('.whl'):
            package_name = file.split('-')[0]
            packages[package_name].append(file)

    # Rimuovi duplicati preferendo la versione target
    for package, versions in packages.items():
        if len(versions) > 1:
            print(f"\nFound multiple versions for {package}:")
            target_versions = [v for v in versions if cp_tag in v]

            if target_versions:
                keep = target_versions[0]
                print(f"  Keeping: {keep}")

                for version in versions:
                    if version != keep:
                        print(f"  Removing: {version}")
                        os.remove(os.path.join(wheels_dir, version))
            else:
                print(f"  No {cp_tag} version found, keeping: {versions[0]}")

def download_wheels(force=False, python_version='3.11'):
    # Check for --force argument
    if "--force" in sys.argv:
        force = True
        print("🔄 FORCE MODE: Will re-download all wheels")

    cp_tag = f"cp{python_version.replace('.', '')}"
    print(f"🐍 Target Python version: {python_version} ({cp_tag})")

    script_dir = os.path.dirname(__file__)
    requirements_file = os.path.join(script_dir, 'requirements_wheels.txt')

    print(f"📄 Requirements file: {requirements_file}")

    # Verifica che il file requirements esista
    if not os.path.exists(requirements_file):
        print(f"❌ ERROR: Requirements file not found: {requirements_file}")
        return False

    # Setup wheels directory
    wheels_dir = clean_wheels_directory(force, python_version)
    print(f"📁 Wheels directory: {wheels_dir}")

    # Se non è force e ci sono già wheels, verifica se sono sufficienti
    if not force:
        existing_wheels = check_existing_wheels(wheels_dir)
        if existing_wheels:
            print(f"⚠️  Found {len(existing_wheels)} existing wheels")
            # Leggi il numero di pacchetti richiesti (EXCLUDING numpy)
            with open(requirements_file, 'r') as f:
                packages = [line.strip() for line in f if line.strip() and not line.startswith('#') and not line.lower().startswith('numpy')]

            # Se abbiamo enough wheels (almeno lo stesso numero di pacchetti), skippa
            if len(existing_wheels) >= len(packages):
                print("✅ Sufficient wheels already exist. Use '--force' to re-download")
                print("   Or use 'em.sh setup force' to force re-download")
                return True

    # Leggi i pacchetti dal file requirements (EXCLUDING numpy)
    with open(requirements_file, 'r') as f:
        all_packages = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        # FILTER OUT numpy - it's included with Blender 4.0+
        packages = [pkg for pkg in all_packages if not pkg.lower().startswith('numpy')]

    print(f"📦 Packages to download: {len(packages)} (numpy excluded - using Blender's built-in version)")
    for pkg in packages:
        print(f"   - {pkg}")

    # Skip numpy download completely - Blender 4.0+ includes it
    print("\n⏭️  Skipping numpy download - using Blender's built-in numpy")

    # Download packages ONE BY ONE without dependencies
    success_count = 0
    for package in packages:
        print(f"\n⬇️  Downloading {package} for {cp_tag}...")

        # Download ONLY the specific package, without dependencies
        cmd = [
            sys.executable, '-m', 'pip', 'download',
            package,
            '--only-binary=:all:',
            f'--python-version={python_version}',
            '--no-deps',  # DON'T download dependencies
            '-d', wheels_dir
        ]

        print(f"Command: {' '.join(cmd)}")
        result = subprocess.run(cmd)

        if result.returncode == 0:
            print(f"✅ Successfully downloaded {package}")
            success_count += 1
        else:
            print(f"❌ Failed to download {package}, trying without version constraint...")
            package_name = package.split('==')[0].split('>=')[0]
            cmd_fallback = [
                sys.executable, '-m', 'pip', 'download',
                package_name,
                '--only-binary=:all:',
                f'--python-version={python_version}',
                '--no-deps',
                '-d', wheels_dir
            ]
            print(f"Fallback command: {' '.join(cmd_fallback)}")
            result_fallback = subprocess.run(cmd_fallback)
            if result_fallback.returncode == 0:
                print(f"✅ Downloaded {package_name} (fallback)")
                success_count += 1
            else:
                print(f"❌ Failed to download {package_name} completely")

    print(f"\n📊 Download Summary:")
    print(f"   Target Python: {python_version} ({cp_tag})")
    print(f"   Total packages: {len(packages)} (numpy excluded)")
    print(f"   Successfully downloaded: {success_count}")

    # Verifica finale
    downloaded_wheels = list(Path(wheels_dir).glob("*.whl"))
    print(f"   Wheels in directory: {len(downloaded_wheels)}")

    if downloaded_wheels:
        print(f"\n📋 Downloaded wheels:")
        for wheel in downloaded_wheels:
            print(f"   - {wheel.name}")
        check_and_clean_duplicates(wheels_dir, python_version)
        return True
    else:
        print(f"\n❌ No wheels were downloaded! Check your internet connection and pip configuration.")
        return False

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description="Download wheels for EM Tools")
    parser.add_argument('--force', action='store_true', help='Force re-download all wheels')
    parser.add_argument('--python-version', default='3.11',
                        help='Target Python version (default: 3.11). Use 3.13 for Blender 5.1+')
    args, _ = parser.parse_known_args()

    # Also support legacy --force via sys.argv
    force_mode = args.force or "--force" in sys.argv

    print("🚀 Starting EM Tools wheels download...")
    print(f"🐍 Target Python: {args.python_version}")
    print("📝 Note: numpy is excluded - using Blender's built-in version")

    if force_mode:
        print("🔄 FORCE MODE ENABLED")

    success = download_wheels(force_mode, args.python_version)
    if success:
        print("\n✅ Setup completed successfully!")
        print("🔍 numpy will be loaded from Blender's built-in libraries")
    else:
        print("\n❌ Setup failed! Please check the errors above.")
        sys.exit(1)