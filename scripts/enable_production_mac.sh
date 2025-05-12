#!/bin/bash

echo "============================================"
echo "    EM Tools - Enable Production Mode"
echo "============================================"
echo

# Verifica che siamo nella cartella scripts
if [ ! -f "switch_dev_mode.py" ]; then
    echo "ERROR: Please run this script from the scripts directory!"
    echo "Current directory: $(pwd)"
    read -p "Press enter to exit..."
    exit 1
fi

# Switch to production mode
echo "Switching to production mode..."
python switch_dev_mode.py prod

# Vai alla cartella root
cd ..

# Verifica che esistano le wheels per tutte le piattaforme
echo
echo "Checking wheels for all platforms..."
if [ ! -d "wheels" ]; then
    echo "ERROR: wheels directory not found!"
    echo "Please run setup_development.py first"
    read -p "Press enter to exit..."
    exit 1
fi

echo "Verifying wheels:"
if ! ls wheels/*.whl | grep -q "macosx"; then
    echo "WARNING: No macOS wheels found"
fi

if ! ls wheels/*.whl | grep -q "win_amd64"; then
    echo "WARNING: No Windows wheels found"
fi

if ! ls wheels/*.whl | grep -q "linux"; then
    echo "WARNING: No Linux wheels found"
fi

# Mostra il manifest attuale
echo
echo "Current manifest (blender_manifest.toml):"
echo "=========================================="
cat blender_manifest.toml
echo "=========================================="

# Update version in __init__.py if needed
echo
echo "Checking version in __init__.py..."
grep -n "bl_info" __init__.py | grep "version"

echo
echo "============================================"
echo "Production mode enabled!"
echo "============================================"
echo
echo "You can now:"
echo "1. Create a git tag: git tag v1.5.0"
echo "2. Push tag: git push origin v1.5.0"
echo "3. GitHub Actions will create the release"
echo
echo "Or create manual package:"
echo "1. Zip the entire directory (excluding .git)"
echo "2. Rename to .blext extension" 
echo "3. Upload to Blender Extensions Platform"
echo
read -p "Press enter to continue..."