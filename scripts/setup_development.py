# scripts/setup_development.py
import os
import subprocess
import platform
import sys
import shutil

def clean_wheels_directory():
    """Pulisce la directory wheels prima di scaricare"""
    script_dir = os.path.dirname(__file__)
    wheels_dir = os.path.join(script_dir, '..', 'wheels')
    
    if os.path.exists(wheels_dir):
        print("Cleaning existing wheels directory...")
        shutil.rmtree(wheels_dir)
    
    os.makedirs(wheels_dir, exist_ok=True)
    return wheels_dir

def get_platform_tags():
    """Restituisce una lista di tag di piattaforma da provare"""
    system = platform.system().lower()
    machine = platform.machine().lower()
    
    if system == 'windows':
        return ['win_amd64']
    elif system == 'darwin':
        if machine == 'arm64':
            return ['macosx_11_0_arm64', 'macosx_10_9_universal2']
        else:
            # Usa solo versioni compatibili con Python 3.11
            return ['macosx_10_9_x86_64', 'macosx_10_10_x86_64']
    else:
        return ['manylinux2014_x86_64', 'manylinux_2_17_x86_64']

def download_wheels():
    wheels_dir = clean_wheels_directory()
    script_dir = os.path.dirname(__file__)
    requirements_file = os.path.join(script_dir, 'requirements_wheels.txt')
    
    # Leggi i pacchetti dal file requirements
    with open(requirements_file, 'r') as f:
        packages = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    
    # Download numpy per primo per garantire la versione corretta
    print("Downloading numpy first to ensure correct version...")
    numpy_cmd = [
        sys.executable, '-m', 'pip', 'download',
        'numpy==1.26.4',
        '--only-binary=:all:',
        '--python-version=3.11',
        '-d', wheels_dir
    ]
    
    result = subprocess.run(numpy_cmd)
    if result.returncode == 0:
        print("Successfully downloaded numpy 1.26.4")
        # Rimuovi numpy dalla lista
        packages = [p for p in packages if not p.lower().startswith('numpy')]
    
    # Download il resto dei pacchetti
    for package in packages:
        print(f"\nDownloading {package}...")
        
        # Usa un approccio semplificato - lascia che pip scelga la piattaforma corretta
        cmd = [
            sys.executable, '-m', 'pip', 'download',
            package,
            '--only-binary=:all:',
            '--python-version=3.11',
            '-d', wheels_dir
        ]
        
        result = subprocess.run(cmd)
        
        if result.returncode != 0:
            print(f"Failed to download {package}, trying without version constraint...")
            package_name = package.split('==')[0].split('>=')[0]
            cmd_fallback = [
                sys.executable, '-m', 'pip', 'download',
                package_name,
                '--only-binary=:all:',
                '--python-version=3.11',
                '-d', wheels_dir
            ]
            subprocess.run(cmd_fallback)
    
    print("\nDownload complete. Checking for duplicates...")
    check_and_clean_duplicates(wheels_dir)

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
                # Mantieni solo la versione cp311
                keep = cp311_versions[0]
                print(f"  Keeping: {keep}")
                
                for version in versions:
                    if version != keep:
                        print(f"  Removing: {version}")
                        os.remove(os.path.join(wheels_dir, version))
            else:
                print(f"  No cp311 version found, keeping: {versions[0]}")

if __name__ == '__main__':
    download_wheels()