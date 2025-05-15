#!/bin/bash

echo "============================================"
echo "    EM Tools - Linux Development Setup"
echo "============================================"
echo

# Verifica che siamo nella cartella scripts
if [ ! -f "requirements_wheels.txt" ]; then
    echo "ERROR: Please run this script from the scripts directory!"
    echo "Current directory: $(pwd)"
    read -p "Press enter to exit..."
    exit 1
fi

# Verifica Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 not found!"
    echo "Please install Python 3.11+ via your package manager:"
    echo "  Ubuntu/Debian: sudo apt install python3 python3-pip"
    echo "  Fedora/RHEL:   sudo dnf install python3 python3-pip"
    echo "  Arch:          sudo pacman -S python python-pip"
    read -p "Press enter to exit..."
    exit 1
fi

PYTHON_CMD="python3"

# Setup version management
echo "Setting up version management..."
cd ..
$PYTHON_CMD scripts/version_manager.py set-mode --mode dev
cd scripts

# Cerca Blender
echo "Searching for Blender..."
BLENDER_FOUND=0
BLENDER_PATH=""

# Controlla locazioni comuni Linux
for blender_path in \
    "/usr/bin/blender" \
    "/usr/local/bin/blender" \
    "$HOME/.local/bin/blender" \
    "/opt/blender/blender" \
    "/snap/bin/blender" \
    "$HOME/blender*/blender"
do
    if [ -f "$blender_path" ] || [ -L "$blender_path" ]; then
        BLENDER_PATH="$blender_path"
        BLENDER_FOUND=1
        echo "Found Blender: $BLENDER_PATH"
        break
    fi
done

# Controlla anche il comando blender nel PATH
if [ $BLENDER_FOUND -eq 0 ] && command -v blender &> /dev/null; then
    BLENDER_PATH=$(which blender)
    BLENDER_FOUND=1
    echo "Found Blender in PATH: $BLENDER_PATH"
fi

if [ $BLENDER_FOUND -eq 0 ]; then
    echo "WARNING: Blender not found"
    echo "Please install Blender 4.0+ via:"
    echo "  - Official website: https://www.blender.org/download/"
    echo "  - Snap: sudo snap install blender --classic"
    echo "  - Flatpak: flatpak install flathub org.blender.Blender"
fi

# Download wheels
echo
echo "Downloading wheels..."
$PYTHON_CMD setup_development.py
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to download wheels"
    read -p "Press enter to exit..."
    exit 1
else
    echo "SUCCESS: Wheels download completed"
fi

# Verifica wheels
echo
echo "Verifying wheels directory..."
cd ..
if [ ! -d "wheels" ]; then
    echo "WARNING: wheels directory not created!"
    echo "This means the download failed silently"
else
    echo "SUCCESS: wheels directory found"
    WHEEL_COUNT=$(ls wheels/*.whl 2>/dev/null | wc -l)
    echo "Found $WHEEL_COUNT wheel files"
fi
cd scripts

# Genera il manifest DOPO aver scaricato le wheels
echo
echo "Generating blender_manifest.toml..."
cd ..
$PYTHON_CMD scripts/version_manager.py update
if [ ! -f "blender_manifest.toml" ]; then
    echo "ERROR: Failed to generate blender_manifest.toml!"
    read -p "Press enter to exit..."
    exit 1
else
    echo "SUCCESS: blender_manifest.toml generated"
fi
cd scripts

# Install dependencies for local development
echo
echo "Installing dependencies for local development..."
echo "Note: This installs Python packages for VSCode IntelliSense"
echo "Installing packages from requirements_wheels.txt..."
while IFS= read -r line || [ -n "$line" ]; do
    # Skip empty lines and comments
    [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
    
    echo "Installing $line for local development..."
    $PYTHON_CMD -m pip install "$line" --user --upgrade
    if [ $? -ne 0 ]; then
        echo "WARNING: Failed to install $line"
    fi
done < requirements_wheels.txt

# Setup VSCode
echo
echo "Setting up VSCode configuration..."
cd ..

mkdir -p .vscode

# Crea settings.json da template
if [ -f ".vscode/settings_template.json" ]; then
    echo "Using settings template..."
    cp .vscode/settings_template.json .vscode/settings.json
    
    # Aggiorna il path di Blender se trovato
    if [ $BLENDER_FOUND -eq 1 ]; then
        echo "Updating VSCode settings with Blender path..."
        # Escape the path for sed
        ESCAPED_PATH=$(echo "$BLENDER_PATH" | sed 's/[[\.*^$()+?{|]/\\&/g')
        sed -i "s|BLENDER_PATH_PLACEHOLDER|$ESCAPED_PATH|g" .vscode/settings.json
    else
        echo "WARNING: Blender not found, you'll need to set the path manually"
        echo "Edit .vscode/settings.json and update \"blender.executable\""
    fi
    echo "SUCCESS: .vscode/settings.json created from template"
else
    echo "WARNING: settings_template.json not found, creating basic settings..."
    # Crea settings.json manualmente
    cat > .vscode/settings.json << EOF
{
    "blender.addon.sourceDirectory": ".",
    "blender.addon.reloadOnSave": true,
    "blender.addon.loadAsExtension": true,
    "blender.addon.extensionDirectoryType": "user",
    "blender.addon.extensionType": "add-on",$(if [ $BLENDER_FOUND -eq 1 ]; then echo "
    \"blender.executable\": \"$BLENDER_PATH\","; else echo "
    // \"blender.executable\": \"/usr/bin/blender\","; fi)
    "python.defaultInterpreterPath": "$PYTHON_CMD",
    "files.exclude": {
        "**/__pycache__": true,
        "**/*.pyc": true,
        "build/": true,
        "wheels/": true,
        "*.blext": true
    }
}
EOF
fi

# Final verification
echo
echo "============================================"
echo "Final Verification"
echo "============================================"
echo

# Check critical files
ALL_OK=1
if [ ! -f "blender_manifest.toml" ]; then
    echo "[ERROR] blender_manifest.toml missing"
    ALL_OK=0
else
    echo "[OK] blender_manifest.toml exists"
fi

if [ ! -d "wheels" ]; then
    echo "[ERROR] wheels directory missing"
    ALL_OK=0
else
    echo "[OK] wheels directory exists"
fi

if [ ! -f ".vscode/settings.json" ]; then
    echo "[ERROR] .vscode/settings.json missing"
    ALL_OK=0
else
    echo "[OK] .vscode/settings.json exists"
fi

echo
echo "Current version:"
$PYTHON_CMD scripts/version_manager.py current

echo
echo "============================================"
echo "Development setup complete!"
echo "============================================"
echo

if [ $ALL_OK -eq 1 ]; then
    echo "✅ SUCCESS: All files configured correctly"
    echo
    echo "EM Tools is configured as a Blender EXTENSION (not addon)"
    echo
    echo "Next steps:"
    echo "1. Open this project in VSCode"
    echo "2. Make sure you have the latest \"Blender Development\" extension"
    echo "3. Press Ctrl+Shift+P and run \"Blender: Start\""
    echo "4. The extension should load automatically"
    echo
    echo "If VSCode fails to load the extension:"
    echo "- Check that Blender Development extension supports Extensions format"
    echo "- Verify .vscode/settings.json has correct \"loadAsExtension\": true"
    echo "- Try building manually: $PYTHON_CMD scripts/dev.py build"
    echo
else
    echo "❌ ERRORS DETECTED: Please check the errors above"
    echo
fi

echo "Quick commands with em.sh:"
echo "  ./em.sh inc                # Increment dev build (1.5.0-dev.66 → 1.5.0-dev.67)"
echo "  ./em.sh build              # Build extension for testing"
echo "  ./em.sh dev                # Quick: increment + build"
echo "  ./em.sh devrel             # Dev release: increment + build + git tag + push"
echo
echo "  ./em.sh inc patch          # Increment patch (1.5.0 → 1.5.1)"
echo "  ./em.sh inc minor          # Increment minor (1.5.0 → 1.6.0)"  
echo "  ./em.sh rc                 # Create release candidate"
echo "  ./em.sh stable             # Create stable release"
echo
echo "  ./em.sh status             # Show version and git status"
echo "  ./em.sh setup              # Re-run setup (use for updates)"
echo
echo "  Type \"./em.sh help\" for complete list of commands"
echo
read -p "Press enter to continue..."