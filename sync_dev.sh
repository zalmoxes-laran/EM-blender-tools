#!/bin/bash

# sync_dev.sh - s3dgraphy Development Sync Helper
# ===============================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT_PATH="$SCRIPT_DIR/scripts/sync_s3dgraphy_dev.py"

if [ ! -f "$SCRIPT_PATH" ]; then
    echo "❌ Sync script not found: $SCRIPT_PATH"
    echo "Please run this from the EM-blender-tools root directory"
    exit 1
fi

# Help function
show_help() {
    echo
    echo "🔧 s3dgraphy Development Sync Helper"
    echo "===================================="
    echo
    echo "USAGE:"
    echo "  ./sync_dev.sh [command] [path]"
    echo
    echo "COMMANDS:"
    echo "  help                    Show this help"
    echo "  status                  Show current s3dgraphy version status"
    echo
    echo "ACTIVATE DEVELOPMENT VERSION:"
    echo "  ./sync_dev.sh               Auto-detect s3dgraphy location"
    echo "  ./sync_dev.sh on            Same as above"
    echo "  ./sync_dev.sh dev           Same as above"
    echo "  ./sync_dev.sh activate      Same as above"
    echo "  ./sync_dev.sh clean         Auto-detect + clean build"
    echo "  ./sync_dev.sh /path/to/s3dgraphy    Use specific path"
    echo
    echo "RESTORE PYPI VERSION:"
    echo "  ./sync_dev.sh restore       Restore PyPI version"
    echo "  ./sync_dev.sh off           Same as above"
    echo "  ./sync_dev.sh disable       Same as above"
    echo
    echo "EXAMPLES:"
    echo "  ./sync_dev.sh                          # Try auto-detect"
    echo "  ./sync_dev.sh ../s3dgraphy            # Use relative path"
    echo "  ./sync_dev.sh ~/dev/s3dgraphy         # Use absolute path"
    echo "  ./sync_dev.sh clean                    # Clean build"
    echo "  ./sync_dev.sh restore                  # Back to PyPI version"
    echo "  ./sync_dev.sh status                   # Check what's active"
    echo
    echo "NOTE: After any change, restart Blender to load the new version"
    echo
}

# Status function
show_status() {
    echo
    echo "📊 Checking s3dgraphy status..."
    python3 "$SCRIPT_PATH" --status
}

# Restore PyPI version
restore_pypi() {
    echo
    echo "♻️  Restoring PyPI version of s3dgraphy..."
    python3 "$SCRIPT_PATH" --restore
    if [ $? -ne 0 ]; then
        echo
        echo "❌ Failed to restore PyPI version"
        exit 1
    fi
    echo
    echo "✅ PyPI version restored"
    echo "🔄 Restart Blender to use the PyPI version"
}

# Activate development version
activate_dev() {
    local clean_flag=""
    local path_arg=""
    
    if [ "$1" = "clean" ]; then
        clean_flag="--clean"
        echo
        echo "🧹 Activating development version with clean build..."
    else
        echo
        echo "🔧 Activating development version..."
        if [ -n "$1" ]; then
            path_arg="$1"
            echo "🎯 Using specified path: $1"
        else
            echo "🔍 Auto-detecting s3dgraphy location..."
        fi
    fi
    
    if [ -n "$path_arg" ]; then
        python3 "$SCRIPT_PATH" $clean_flag "$path_arg"
    else
        python3 "$SCRIPT_PATH" $clean_flag
    fi
    
    if [ $? -ne 0 ]; then
        if [ -z "$path_arg" ]; then
            echo
            echo "⚠️  Auto-detection failed. Let's try to find it manually."
            prompt_for_path
        else
            echo
            echo "❌ Activation failed"
            echo "Check the error messages above"
            exit 1
        fi
    else
        echo
        echo "✅ Development version activated"
        echo "🔄 Restart Blender to use your development s3dgraphy"
    fi
}

# Prompt for manual path input
prompt_for_path() {
    echo
    echo "📁 Common s3dgraphy locations to check:"
    echo "   1. ../s3dgraphy"
    echo "   2. $HOME/Documents/GitHub/s3dgraphy"
    echo "   3. Custom path"
    echo
    read -p "Enter choice (1-3) or full path: " choice
    
    case "$choice" in
        1)
            s3d_path="../s3dgraphy"
            ;;
        2)
            s3d_path="$HOME/Documents/GitHub/s3dgraphy"
            ;;
        3)
            read -p "Enter full path to s3dgraphy: " s3d_path
            ;;
        *)
            s3d_path="$choice"
            ;;
    esac
    
    if [ ! -d "$s3d_path" ]; then
        echo
        echo "❌ Path not found: $s3d_path"
        echo "Please check the path and try again"
        exit 1
    fi
    
    echo
    echo "🎯 Using path: $s3d_path"
    python3 "$SCRIPT_PATH" "$s3d_path"
    
    if [ $? -ne 0 ]; then
        echo
        echo "❌ Activation failed"
        echo "Check the error messages above"
        exit 1
    fi
    
    echo
    echo "✅ Development version activated"
    echo "🔄 Restart Blender to use your development s3dgraphy"
}

# Main script logic
case "$1" in
    help|-h|--help)
        show_help
        ;;
    status)
        show_status
        ;;
    restore|off|disable)
        restore_pypi
        ;;
    on|activate|dev)
        activate_dev
        ;;
    clean)
        activate_dev clean
        ;;
    "")
        activate_dev
        ;;
    *)
        if [ -d "$1" ]; then
            activate_dev "$1"
        else
            echo
            echo "⚠️  Unknown command or invalid path: $1"
            echo
            show_help
            exit 1
        fi
        ;;
esac
