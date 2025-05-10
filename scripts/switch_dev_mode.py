# scripts/switch_dev_mode.py
import os
import shutil
import sys

def switch_to_dev():
    """Configura per lo sviluppo con VSCode"""
    if os.path.exists('blender_manifest.toml'):
        shutil.copy('blender_manifest.toml', 'blender_manifest_prod.toml')
    
    # Crea un manifest semplificato per VSCode
    dev_manifest = """schema_version = "1.0.0"

id = "em_tools"
name = "EM Tools"
version = "1.5.0"
tagline = "Blender tools for Extended Matrix"
maintainer = "E. Demetrescu <emanuel.demetrescu@cnr.it>"
type = "add-on"
license = ["GPL-3.0"]

blender_version_min = "4.0.0"

platforms = ["windows-amd64", "macos-arm64", "macos-x64", "linux-x64"]
tags = ["3D View", "Import-Export", "Tools"]
"""
    
    with open('blender_manifest.toml', 'w') as f:
        f.write(dev_manifest)
    
    print("Switched to development mode")

def switch_to_prod():
    """Ripristina configurazione per produzione"""
    if os.path.exists('blender_manifest_prod.toml'):
        shutil.copy('blender_manifest_prod.toml', 'blender_manifest.toml')
        print("Switched to production mode")
    else:
        print("Production manifest not found!")

if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'dev'
    if mode == 'dev':
        switch_to_dev()
    elif mode == 'prod':
        switch_to_prod()
    else:
        print("Usage: python switch_dev_mode.py [dev|prod]")