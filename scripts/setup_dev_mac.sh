#!/bin/bash

echo "============================================"
echo "    EM Tools - macOS Development Setup"
echo "============================================"
echo

# Verifica che siamo nella cartella scripts
if [ ! -f "requirements_wheels.txt" ]; then
    echo "ERROR: Please run this script from the scripts directory!"
    echo "Expected file: requirements_wheels.txt"
    echo "Current directory: $(pwd)"
    read -p "Press enter to exit..."
    exit 1
fi

# Scarica le wheels
echo "Downloading wheels..."
python setup_development.py
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to download wheels"
    read -p "Press enter to exit..."
    exit 1
fi

# Switch to dev mode
echo
echo "Switching to development mode..."
python switch_dev_mode.py dev

# Setup VSCode
echo
echo "Setting up VSCode configuration..."
cd ..

if [ ! -d ".vscode" ]; then
    mkdir .vscode
fi

# Crea settings.json se non esiste
if [ ! -f ".vscode/settings.json" ]; then
    cat > .vscode/settings.json << EOF
{
    "blender.addon.sourceDirectory": ".",
    "blender.addon.reloadOnSave": true,
    "blender.executable": "/Applications/Blender.app/Contents/MacOS/Blender"
}
EOF
    echo "VSCode settings created"
fi

echo
echo "============================================"
echo "Development setup complete!"
echo "============================================"
echo
echo "Next steps:"
echo "1. Open project in VSCode"
echo "2. Press Cmd+Shift+P"
echo "3. Run 'Blender: Start'"
echo
read -p "Press enter to continue..."