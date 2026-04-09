#!/bin/bash
# Build Blender Extension Package
# Script launcher per Unix/Linux/macOS

echo "🚀 Building Blender Extension Package..."
echo ""

# Controlla Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 non trovato"
    echo "   Installa Python 3.8+ e riprova"
    exit 1
fi

# Controlla dipendenze
echo "🔍 Controllo dipendenze..."
python3 -c "import tomli" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "📦 Installazione tomli..."
    python3 -m pip install tomli --quiet
fi

python3 -c "import requests" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "📦 Installazione requests..."
    python3 -m pip install requests --quiet
fi

echo ""

# Esegui lo script Python
python3 "$(dirname "$0")/build_extension.py" "$@"

exit_code=$?

if [ $exit_code -eq 0 ]; then
    echo ""
    echo "✅ Script completato con successo"
else
    echo ""
    echo "❌ Script terminato con errori (codice: $exit_code)"
fi

exit $exit_code
