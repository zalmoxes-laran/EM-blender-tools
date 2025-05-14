# scripts/generate_manifest.py
import os
import sys

def get_wheels_for_platform(platform):
    """Ottiene le wheels per una specifica piattaforma"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    wheels_dir = os.path.join(os.path.dirname(script_dir), 'wheels')
    
    if not os.path.exists(wheels_dir):
        return []
    
    platform_map = {
        'windows': 'win_amd64',
        'macos-arm': 'macosx_11_0_arm64',
        'macos-intel': 'macosx_10_10_x86_64',
        'linux': 'manylinux'
    }
    
    platform_tag = platform_map.get(platform, platform)
    wheels = []
    
    for file in os.listdir(wheels_dir):
        if file.endswith('.whl'):
            # Include wheels specifiche per la piattaforma o universali
            if platform_tag in file or 'none-any' in file:
                wheels.append(f"./wheels/{file}")
    
    return sorted(wheels)

def switch_to_prod(platform='windows'):
    """Configura per produzione con wheels specifiche per piattaforma"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(script_dir)
    manifest_path = os.path.join(root_dir, 'blender_manifest.toml')
    
    # Ottieni le wheels per la piattaforma
    wheels = get_wheels_for_platform(platform)
    
    # Crea la sezione wheels
    wheels_section = '[\n'
    for wheel in wheels:
        wheels_section += f'    "{wheel}",\n'
    wheels_section = wheels_section.rstrip(',\n') + '\n]'
    
    # Manifest completo per produzione
    prod_manifest = f"""schema_version = "1.0.0"

id = "em_tools"
name = "EM Tools"
version = "1.5.0"
tagline = "Blender tools for Extended Matrix"
maintainer = "E. Demetrescu <emanuel.demetrescu@cnr.it>"
type = "add-on"
license = ["GPL-3.0"]

blender_version_min = "4.0.0"

platforms = ["windows-x64", "macos-arm64", "macos-x64", "linux-x64"]
tags = ["3D View", "Import-Export", "Tools"]

[permissions]
wheels = {wheels_section}
"""
    
    with open(manifest_path, 'w') as f:
        f.write(prod_manifest)
    
    print(f"Switched to production mode with {len(wheels)} wheels for {platform}")
    print("Wheels included:")
    for wheel in wheels:
        print(f"  {wheel}")

def switch_to_dev():
    """Configura per lo sviluppo con VSCode"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(script_dir)
    manifest_path = os.path.join(root_dir, 'blender_manifest.toml')
    
    # Manifest semplificato per sviluppo
    dev_manifest = """schema_version = "1.0.0"

id = "em_tools"
name = "EM Tools (Dev)"
version = "1.5.0"
tagline = "Blender tools for Extended Matrix - Development"
maintainer = "E. Demetrescu <emanuel.demetrescu@cnr.it>"
type = "add-on"
license = ["GPL-3.0"]

blender_version_min = "4.0.0"

platforms = ["windows-x64", "macos-arm64", "macos-x64", "linux-x64"]
tags = ["3D View", "Import-Export", "Tools"]
"""
    
    with open(manifest_path, 'w') as f:
        f.write(dev_manifest)
    
    print("Switched to development mode (no wheels for VSCode)")

if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'dev'
    
    if mode == 'dev':
        switch_to_dev()
    elif mode == 'prod':
        platform = sys.argv[2] if len(sys.argv) > 2 else 'windows'
        switch_to_prod(platform)
    else:
        print("Usage: python generate_manifest.py [dev|prod] [platform]")
        print("Platforms: windows, macos-arm, macos-intel, linux")