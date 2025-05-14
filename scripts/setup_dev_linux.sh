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
fi

# Install dependencies for local development
echo
echo "Installing dependencies for local development..."
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

# Crea settings.json da template o manualmente
if [ -f ".vscode/settings_template.json" ]; then
    cp .vscode/settings_template.json .vscode/settings.json
    
    # Aggiorna il path di Blender se trovato
    if [ $BLENDER_FOUND -eq 1 ]; then
        echo "Updating VSCode settings with Blender path..."
        sed -i "s|BLENDER_PATH_PLACEHOLDER|$BLENDER_PATH|g" .vscode/settings.json
    fi
else
    # Crea settings.json manualmente
    cat > .vscode/settings.json << EOF
{
    "blender.addon.sourceDirectory": ".",
    "blender.addon.reloadOnSave": true,$(if [ $BLENDER_FOUND -eq 1 ]; then echo "
    \"blender.executable\": \"$BLENDER_PATH\","; else echo "
    // \"blender.executable\": \"/usr/bin/blender\","; fi)
    "python.defaultInterpreterPath": "$PYTHON_CMD",
    "files.exclude": {
        "**/__pycache__": true,
        "**/*.pyc": true,
        "build/": true,
        "wheels/": true
    }
}
EOF
fi

# Status finale
echo
echo "============================================"
echo "Development setup complete!"
echo "============================================"
echo
$PYTHON_CMD scripts/version_manager.py current
echo
echo "Next steps:"
echo "1. Open project in VSCode"
echo "2. Install 'Blender Development' extension"
echo "3. Press Ctrl+Shift+P and run 'Blender: Start'"
echo
echo "Quick commands:"
echo "  Increment dev build:  $PYTHON_CMD scripts/dev.py inc"
echo "  Build dev version:    $PYTHON_CMD scripts/dev.py build"
echo "  Create release:       $PYTHON_CMD scripts/release.py"
echo
read -p "Press enter to continue..."