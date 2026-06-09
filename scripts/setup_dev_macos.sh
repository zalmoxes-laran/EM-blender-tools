#!/bin/bash

# Arguments: $1 = "force" or "", $2 = python version (default: 3.11)
FORCE_ARG="$1"
PYTHON_VER="${2:-3.11}"

echo "============================================"
echo "    EM Tools - macOS Development Setup"
echo "    Python target: $PYTHON_VER"
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
    echo "Please install Python 3.11+ (recommended via Homebrew: brew install python)"
    read -p "Press enter to exit..."
    exit 1
fi

# Usa python3 per compatibilità macOS
PYTHON_CMD="python3"

# Version management
#
# NOTE: setup intentionally does NOT call `set-mode --mode dev` here
# anymore. The previous behaviour silently flipped `version.json` to
# `mode: dev` every time `em.sh setup` ran, which polluted stable
# release branches (e.g. `EM-tools_v1.5.0` at the v1.5.2 tag) the
# moment the maintainer ran a local dev setup to test a patch. The
# rule now is the standard one: `setup` installs dependencies; mode
# is controlled explicitly via `em.sh stable` / `em.sh dev` (or a
# direct `python3 scripts/version_manager.py set-mode --mode <...>`).
# Branches that should run setup in dev mode already declare it in
# their tracked `version.json`, so the manifest regeneration step
# below picks up the right mode without any forced flip.

# Cerca Blender
echo "Searching for Blender..."
BLENDER_FOUND=0
BLENDER_PATH=""

# Controlla locazioni comuni
for blender_path in \
    "/Applications/Blender.app/Contents/MacOS/Blender" \
    "/Applications/Blender */Contents/MacOS/Blender" \
    "$HOME/Applications/Blender.app/Contents/MacOS/Blender"
do
    if [ -f "$blender_path" ]; then
        BLENDER_PATH="$blender_path"
        BLENDER_FOUND=1
        echo "Found Blender: $BLENDER_PATH"
        break
    fi
done

if [ $BLENDER_FOUND -eq 0 ]; then
    echo "WARNING: Blender not found in standard locations"
    echo "Please ensure Blender 4.0+ is installed in /Applications/"
fi

# Download wheels
echo
echo "Downloading wheels for Python $PYTHON_VER..."
SETUP_ARGS="--python-version=$PYTHON_VER"
if [ "$FORCE_ARG" = "force" ]; then
    SETUP_ARGS="$SETUP_ARGS --force"
fi
$PYTHON_CMD setup_development.py $SETUP_ARGS
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
CP_TAG="cp${PYTHON_VER//.}"
cd ..
if [ -d "wheels/$CP_TAG" ]; then
    echo "SUCCESS: wheels/$CP_TAG directory found"
    WHEEL_COUNT=$(ls wheels/$CP_TAG/*.whl 2>/dev/null | wc -l)
    echo "Found $WHEEL_COUNT wheel files"
elif [ -d "wheels" ]; then
    echo "SUCCESS: wheels directory found (legacy flat structure)"
    WHEEL_COUNT=$(ls wheels/*.whl 2>/dev/null | wc -l)
    echo "Found $WHEEL_COUNT wheel files"
else
    echo "WARNING: wheels directory not created!"
    echo "This means the download failed silently"
fi
cd scripts

# Genera il manifest DOPO aver scaricato le wheels
echo
echo "Generating blender_manifest.toml (Python $PYTHON_VER wheels)..."
cd ..
# Generate the manifest under the CURRENT mode declared in
# version.json — do NOT force `--mode dev` here (see the rationale
# at the top of this file). If the maintainer is on a stable
# release branch running setup to test a patch, the manifest stays
# stable; if they are on the main dev branch, version.json already
# carries `mode: dev` and the manifest reflects it.
$PYTHON_CMD scripts/version_manager.py update --python-version $PYTHON_VER
if [ ! -f "blender_manifest.toml" ]; then
    echo "ERROR: Failed to generate blender_manifest.toml!"
    read -p "Press enter to exit..."
    exit 1
else
    # Aggiunto controllo del contenuto, non solo dell'esistenza del file
    VERSION=$($PYTHON_CMD scripts/version_manager.py current | awk '{print $3}')
    if grep -q "version = \"$VERSION\"" blender_manifest.toml; then
        echo "SUCCESS: blender_manifest.toml generated with correct version: $VERSION"
    else
        echo "WARNING: Version mismatch in manifest, fixing..."
        $PYTHON_CMD -c "
import re
with open('blender_manifest.toml', 'r') as f:
    content = f.read()
with open('version.json', 'r') as f:
    import json
    config = json.load(f)
version = f\"{config.get('major', 1)}.{config.get('minor', 5)}.{config.get('patch', 0)}\"
if config.get('mode') == 'dev':
    version += f\"-dev.{config.get('dev_build', 0)}\"
elif config.get('mode') == 'rc':
    version += f\"-rc.{config.get('rc_build', 1)}\"
content = re.sub(r'version = \"[^\"]*\"', f'version = \"{version}\"', content)
with open('blender_manifest.toml', 'w') as f:
    f.write(content)
print(f'Fixed version to {version}')
"
    fi
fi
cd scripts

# Local dev dependencies are handled by ./em.sh first_setup (isolated .venv).
# Don't pip-install into the system Python — modern Python rejects it
# (PEP 668 "externally-managed-environment").
echo
echo "Checking dev venv for VSCode IntelliSense..."
if [ -d "../.venv" ]; then
    echo "✅ .venv/ detected at repo root — VSCode IntelliSense is configured"
    echo "   (To refresh dev deps: ./em.sh first_setup from repo root)"
else
    echo "ℹ️  No .venv/ found at repo root."
    echo "   Run './em.sh first_setup' once from the repo root to set up"
    echo "   VSCode IntelliSense in an isolated venv."
    echo "   (Skipping system-wide pip install — modern Python rejects it"
    echo "    with 'externally-managed-environment' / PEP 668.)"
fi

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
        sed -i '' "s|BLENDER_PATH_PLACEHOLDER|$ESCAPED_PATH|g" .vscode/settings.json
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
    // \"blender.executable\": \"/Applications/Blender.app/Contents/MacOS/Blender\","; fi)
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
    echo "3. Press Cmd+Shift+P and run \"Blender: Start\""
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