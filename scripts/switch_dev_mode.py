# scripts/switch_dev_mode.py
import os
import sys

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

[permissions]
wheels = "./wheels/"
"""
    
    with open(manifest_path, 'w') as f:
        f.write(dev_manifest)
    
    print("Switched to development mode")

def switch_to_prod():
    """Configura per produzione"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(script_dir)
    manifest_path = os.path.join(root_dir, 'blender_manifest.toml')
    
    # Manifest completo per produzione
    prod_manifest = """schema_version = "1.0.0"

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
wheels = "./wheels/"
"""
    
    with open(manifest_path, 'w') as f:
        f.write(prod_manifest)
    
    print("Switched to production mode")

if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'dev'
    if mode == 'dev':
        switch_to_dev()
    elif mode == 'prod':
        switch_to_prod()
    else:
        print("Usage: python switch_dev_mode.py [dev|prod]")