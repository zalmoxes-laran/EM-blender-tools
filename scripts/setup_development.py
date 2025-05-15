# scripts/setup_development.py
import os
import subprocess
import platform
import sys
import shutil
from pathlib import Path

def clean_wheels_directory(force=False):
    """Pulisce la directory wheels solo se necessario"""
    script_dir = os.path.dirname(__file__)
    wheels_dir = os.path.join(script_dir, '..', 'wheels')
    
    # Se force=True, rimuovi sempre
    if force:
        if os.path.exists(wheels_dir):
            print("FORCE MODE: Cleaning existing wheels directory...")
            shutil.rmtree(wheels_dir)
        os.makedirs(wheels_dir, exist_ok=True)
        return wheels_dir
    
    # Se force=False, crea solo se non esiste
    if not os.path.exists(wheels_dir):
        print("Creating wheels directory...")
        os.makedirs(wheels_dir)
    else:
        print("Using existing wheels directory...")
    
    return wheels_dir

def check_existing_wheels(wheels_dir):
    """Controlla se esistono già wheels valide"""
    if not os.path.exists(wheels_dir):
        return []
    
    wheels = list(Path(wheels_dir).glob("*.whl"))
    return wheels

def check_and_clean_duplicates(wheels_dir):
    """Rimuove wheel duplicate mantenendo solo quelle per Python 3.11"""
    from collections import defaultdict
    
    files = os.listdir(wheels_dir)
    packages = defaultdict(list)
    
    # Raggruppa i file per pacchetto
    for file in files:
        if file.endswith('.whl'):
            package_name = file.split('-')[0]
            packages[package_name].append(file)
    
    # Rimuovi duplicati preferendo cp311
    for package, versions in packages.items():
        if len(versions) > 1:
            print(f"\nFound multiple versions for {package}:")
            cp311_versions = [v for v in versions if 'cp311' in v]
            
            if cp311_versions:
                # Mantieni solo la versione cp311 più specifica (es. preferisci versioni exact)
                keep = cp311_versions[0]
                print(f"  Keeping: {keep}")
                
                for version in versions:
                    if version != keep:
                        print(f"  Removing: {version}")
                        os.remove(os.path.join(wheels_dir, version))
            else:
                print(f"  No cp311 version found, keeping: {versions[0]}")

def download_wheels(force=False):
    # Check for --force argument
    if "--force" in sys.argv:
        force = True
        print("🔄 FORCE MODE: Will re-download all wheels")
    
    script_dir = os.path.dirname(__file__)
    requirements_file = os.path.join(script_dir, 'requirements_wheels.txt')
    
    print(f"📄 Requirements file: {requirements_file}")
    
    # Verifica che il file requirements esista
    if not os.path.exists(requirements_file):
        print(f"❌ ERROR: Requirements file not found: {requirements_file}")
        return False
    
    # Setup wheels directory
    wheels_dir = clean_wheels_directory(force)
    print(f"📁 Wheels directory: {wheels_dir}")
    
    # Se non è force e ci sono già wheels, verifica se sono sufficienti
    if not force:
        existing_wheels = check_existing_wheels(wheels_dir)
        if existing_wheels:
            print(f"⚠️  Found {len(existing_wheels)} existing wheels")
            # Leggi il numero di pacchetti richiesti
            with open(requirements_file, 'r') as f:
                packages = [line.strip() for line in f if line.strip() and not line.startswith('#')]
            
            # Se abbiamo enough wheels (almeno lo stesso numero di pacchetti), skippa
            if len(existing_wheels) >= len(packages):
                print("✅ Sufficient wheels already exist. Use '--force' to re-download")
                print("   Or use 'em.bat setup force' to force re-download")
                return True
    
    # Leggi i pacchetti dal file requirements
    with open(requirements_file, 'r') as f:
        packages = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    
    print(f"📦 Packages to download: {len(packages)}")
    for pkg in packages:
        print(f"   - {pkg}")
    
    # Download numpy per primo per garantire la versione corretta
    print("\n⬇️  Downloading numpy first to ensure correct version...")
    numpy_cmd = [
        sys.executable, '-m', 'pip', 'download',
        'numpy==1.26.4',
        '--only-binary=:all:',
        '--python-version=3.11',
        '--no-deps',  # Non scaricare dipendenze per evitare conflitti
        '-d', wheels_dir
    ]
    
    print(f"Command: {' '.join(numpy_cmd)}")
    result = subprocess.run(numpy_cmd)
    if result.returncode == 0:
        print("✅ Successfully downloaded numpy 1.26.4")
        # Rimuovi numpy dalla lista
        packages = [p for p in packages if not p.lower().startswith('numpy')]
    else:
        print("⚠️  Failed to download numpy, will try with other packages")
    
    # Download il resto dei pacchetti UNO ALLA VOLTA senza dipendenze
    success_count = 0
    for package in packages:
        print(f"\n⬇️  Downloading {package}...")
        
        # Download SOLO il pacchetto specifico, senza dipendenze
        cmd = [
            sys.executable, '-m', 'pip', 'download',
            package,
            '--only-binary=:all:',
            '--python-version=3.11',
            '--no-deps',  # NON scaricare dipendenze
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
                '--python-version=3.11',
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
    print(f"   Total packages: {len(packages) + 1}")  # +1 for numpy
    print(f"   Successfully downloaded: {success_count + 1}")  # +1 for numpy
    
    # Verifica finale
    downloaded_wheels = list(Path(wheels_dir).glob("*.whl"))
    print(f"   Wheels in directory: {len(downloaded_wheels)}")
    
    if downloaded_wheels:
        print(f"\n📋 Downloaded wheels:")
        for wheel in downloaded_wheels:
            print(f"   - {wheel.name}")
        check_and_clean_duplicates(wheels_dir)
        return True
    else:
        print(f"\n❌ No wheels were downloaded! Check your internet connection and pip configuration.")
        return False

if __name__ == '__main__':
    print("🚀 Starting EM Tools wheels download...")
    
    # Check for force mode
    force_mode = "--force" in sys.argv
    if force_mode:
        print("🔄 FORCE MODE ENABLED")
    
    success = download_wheels(force_mode)
    if success:
        print("\n✅ Setup completed successfully!")
    else:
        print("\n❌ Setup failed! Please check the errors above.")
        sys.exit(1)