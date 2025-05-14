# scripts/switch_dev_mode.py
import os
import shutil
import sys

def switch_to_dev():
    """Configura per lo sviluppo con VSCode"""
    # Vai alla cartella root del progetto (parent della cartella scripts)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(script_dir)
    
    manifest_path = os.path.join(root_dir, 'blender_manifest.toml')
    manifest_prod_path = os.path.join(root_dir, 'blender_manifest_prod.toml')
    
    if os.path.exists(manifest_path):
        shutil.copy(manifest_path, manifest_prod_path)
    
    # Crea un manifest semplificato per VSCode
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
    
    print("Switched to development mode")

def switch_to_prod():
    """Ripristina configurazione per produzione"""
    # Vai alla cartella root del progetto (parent della cartella scripts)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(script_dir)
    
    manifest_path = os.path.join(root_dir, 'blender_manifest.toml')
    manifest_prod_path = os.path.join(root_dir, 'blender_manifest_prod.toml')
    
    if os.path.exists(manifest_prod_path):
        shutil.copy(manifest_prod_path, manifest_path)
        print("Switched to production mode")
    else:
        # Crea il manifest di produzione se non esiste
        prod_manifest = """schema_version = "1.0.0"

id = "em_tools"
name = "EM Tools"
version = "1.5.0"
tagline = "Blender tools for Extended Matrix"
maintainer = "E. Demetrescu <emanuel.demetrescu@cnr.it>"
type = "add-on"
license = ["GPL-3.0"]

blender_version_min = "4.0.0"

[permissions]
wheels = [
    "./wheels/*.whl"
]

platforms = ["windows-x64", "macos-arm64", "macos-x64", "linux-x64"]
tags = ["3D View", "Import-Export", "Tools"]
"""
        with open(manifest_path, 'w') as f:
            f.write(prod_manifest)
        print("Created and switched to production mode")

if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'dev'
    if mode == 'dev':
        switch_to_dev()
    elif mode == 'prod':
        switch_to_prod()
    else:
        print("Usage: python switch_dev_mode.py [dev|prod]")