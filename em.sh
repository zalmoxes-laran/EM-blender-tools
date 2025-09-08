#!/bin/bash

echo "============================================"
echo "    EM Tools - Quick Commands (Unix)"
echo "============================================"
echo

# Detect script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Detect Python command
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
else
    PYTHON_CMD="python"
fi

# ============================================
# DEV SYNC FUNCTIONS
# ============================================

# Function to check if development s3dgraphy is active
check_dev_s3dgraphy() {
    if [ -f "scripts/sync_s3dgraphy_dev.py" ]; then
        if $PYTHON_CMD scripts/sync_s3dgraphy_dev.py --status 2>/dev/null | grep -q "DEVELOPMENT"; then
            DEV_S3DGRAPHY_ACTIVE="true"
        else
            DEV_S3DGRAPHY_ACTIVE="false"
        fi
    else
        DEV_S3DGRAPHY_ACTIVE="false"
    fi
}

# Function to warn about dev version before setup
warn_dev_override() {
    if [ "$DEV_S3DGRAPHY_ACTIVE" = "true" ]; then
        echo
        echo "⚠️  WARNING: Development version of s3dgraphy is currently active"
        echo "   Running 'setup' will replace it with the PyPI version"
        echo
        read -p "Continue anyway? (y/N): " continue
        if [ "$continue" != "y" ] && [ "$continue" != "Y" ]; then
            echo
            echo "🚫 Setup cancelled"
            echo "💡 Use './em.sh s3d restore' if you want to switch to PyPI version"
            exit 1
        fi
        echo
        echo "🔄 Proceeding with PyPI version replacement..."
    fi
}

# Function to notify after setup that dev version was replaced
notify_dev_replaced() {
    if [ "$DEV_S3DGRAPHY_ACTIVE" = "true" ]; then
        echo
        echo "ℹ️  Development version of s3dgraphy was replaced with PyPI version"
        echo "💡 Use './em.sh s3d on' to reactivate development version if needed"
    fi
}

# s3dgraphy development sync command
s3d_command() {
    echo
    if [ -f "sync_dev.sh" ]; then
        ./sync_dev.sh "$@"
    else
        echo "❌ s3dgraphy development sync not available"
        echo "Please ensure sync_dev.sh is in the EM-blender-tools root directory"
        echo "Run setup first if this is a fresh installation"
    fi
}

# ============================================
# UTILITY FUNCTIONS
# ============================================

# Help function
show_help() {
    echo "Usage: ./em.sh [command] [options]"
    echo
    echo "=== SETUP ==="
    echo "  setup              Setup development environment"
    echo
    echo "=== s3dgraphy DEVELOPMENT ==="
    echo "  s3d                Activate s3dgraphy development version"
    echo "  s3d on             Same as above"
    echo "  s3d off            Restore PyPI version"
    echo "  s3d status         Check current s3dgraphy version"
    echo "  s3d clean          Clean build + activate development version"
    echo "  s3d restore        Restore PyPI version"
    echo "  s3d help           Show detailed s3dgraphy sync help"
    echo
    echo "=== EM TOOLS DEVELOPMENT ==="
    echo "  inc [part]         Increment version part:"
    echo "                       dev_build : 1.5.0-dev.43 → 1.5.0-dev.44"
    echo "                       patch     : 1.5.0 → 1.5.1"
    echo "                       minor     : 1.5.0 → 1.6.0"
    echo "                       major     : 1.5.0 → 2.0.0"
    echo "                       rc_build  : 1.5.0-rc.1 → 1.5.0-rc.2"
    echo "  build [mode]       Build extension only (no version change)"
    echo "                       dev, rc, stable"
    echo "  dev                Quick dev: increment dev_build + build"
    echo "  devrel             DEV RELEASE: inc + build + commit + tag + push"
    echo
    echo "=== RELEASE WORKFLOW ==="
    echo "  rc                 Create Release Candidate (inc patch + build RC)"
    echo "  rc+                Create Additional RC (rc.1 → rc.2 → rc.3...)"
    echo "  stable             Create Stable Release (from current RC)"
    echo
    echo "=== UTILITIES ==="
    echo "  status             Show version, mode, and git status"
    echo "  commit [msg]       Commit with auto-generated message"
    echo "  push               Push changes and tags to remote"
    echo
    echo "=== EXAMPLES ==="
    echo "  ./em.sh setup      # First time setup"
    echo "  ./em.sh s3d        # Activate s3dgraphy development version"
    echo "  ./em.sh s3d off    # Back to s3dgraphy PyPI version"
    echo "  ./em.sh dev        # Quick EMtools dev iteration"
    echo "  ./em.sh devrel     # EMtools dev release to GitHub"
    echo "  ./em.sh inc patch  # Increment patch: 1.5.0 → 1.5.1"
    echo "  ./em.sh build stable # Build stable package (no version change)"
    echo "  ./em.sh rc         # 1.5.0-dev.X → 1.5.1-rc.1"
    echo "  ./em.sh rc+        # 1.5.1-rc.1 → 1.5.1-rc.2"
    echo "  ./em.sh stable     # 1.5.1-rc.X → 1.5.1"
    echo "  ./em.sh commit \"fix: bug in loader\""
    echo "  ./em.sh push"
    echo
    echo "=== s3dgraphy DEVELOPMENT WORKFLOW ==="
    echo "  ./em.sh s3d        # Activate s3dgraphy dev version"
    echo "  [modify s3dgraphy in other VSCode session]"
    echo "  ./em.sh s3d        # Re-sync after changes"
    echo "  [test in Blender]"
    echo "  ./em.sh s3d off    # Back to stable when done"
    echo
}

# Get current version for commit messages
get_version() {
    $PYTHON_CMD scripts/version_manager.py current | cut -d' ' -f3
}

# Generate commit message
suggest_commit_message() {
    local part=${1:-dev_build}
    local version=$(get_version)
    
    if [ "$part" = "dev_build" ]; then
        echo "build: increment to $version"
    else
        echo "release: $part version bump to $version"
    fi
}

# ============================================
# MAIN COMMAND PROCESSING
# ============================================

# Check for help
if [ $# -eq 0 ] || [ "$1" = "help" ] || [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
    show_help
    exit 0
fi

# Parse commands
case "$1" in
    setup)
        # Check if dev s3dgraphy is active before setup
        check_dev_s3dgraphy
        
        # Warn user if dev version will be overridden
        if [ "$2" = "force" ]; then
            warn_dev_override
        fi
        
        echo "Setting up development environment..."
        # Change to scripts directory before running setup
        cd scripts
        case "$(uname -s)" in
            Darwin)
                bash setup_dev_macos.sh "$2"
                ;;
            Linux)
                bash setup_dev_linux.sh "$2"
                ;;
            *)
                echo "Unsupported OS: $(uname -s)"
                exit 1
                ;;
        esac
        # Return to original directory
        cd "$SCRIPT_DIR"
        
        # Notify if dev version was replaced
        notify_dev_replaced
        ;;
    
    s3d)
        shift  # Remove 's3d' from arguments
        s3d_command "$@"
        ;;
    
    inc)
        PART=${2:-dev_build}
        echo "Incrementing $PART version..."
        $PYTHON_CMD scripts/dev.py inc --part $PART
        echo
        echo "Suggested commit message:"
        echo "\"$(suggest_commit_message $PART)\""
        ;;
    
    build)
        MODE=${2:-dev}
        echo "Building extension in $MODE mode..."
        $PYTHON_CMD scripts/dev.py build --mode $MODE
        ;;
    
    dev)
        echo "Quick development iteration..."
        $PYTHON_CMD scripts/dev.py inc
        $PYTHON_CMD scripts/dev.py build
        echo
        echo "Suggested commit message:"
        echo "\"$(suggest_commit_message dev_build)\""
        ;;
    
    devrel)
        echo "Creating development release for GitHub..."
        $PYTHON_CMD scripts/dev.py inc
        $PYTHON_CMD scripts/dev.py build
        VERSION=$(get_version)
        echo
        echo "Committing and tagging..."
        git add -A
        git commit -m "build: dev release $VERSION"
        git tag "v$VERSION"
        git push origin $(git branch --show-current)
        git push origin "v$VERSION"
        echo "✅ Dev release $VERSION pushed to GitHub!"
        ;;
    
    rc)
        echo "Creating release candidate..."
        echo "This will increment patch version and set mode to RC"
        read -p "Continue? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            $PYTHON_CMD scripts/release.py --mode rc --increment patch
        fi
        ;;
    
    "rc+")
        echo "Creating additional release candidate..."
        echo "This will increment RC build number (e.g., rc.1 → rc.2)"
        read -p "Continue? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            $PYTHON_CMD scripts/release.py --mode rc --increment rc_build
        fi
        ;;
    
    stable)
        echo "Creating stable release..."
        echo "This will create stable release from current RC version"
        read -p "Continue? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            $PYTHON_CMD scripts/release.py --mode stable
        fi
        ;;
    
    status)
        $PYTHON_CMD scripts/version_manager.py current
        echo
        echo "Git status:"
        git status --porcelain
        ;;
    
    commit)
        echo "Committing current changes..."
        VERSION=$(get_version)
        if [ -z "$2" ]; then
            echo "No custom message provided, using auto-generated"
            git add -A
            git commit -m "build: increment to $VERSION"
        else
            git add -A
            git commit -m "$2 ($VERSION)"
        fi
        ;;
    
    push)
        echo "Pushing current changes and tags..."
        git push origin $(git branch --show-current)
        VERSION=$(get_version)
        git push origin "v$VERSION" 2>/dev/null || true
        ;;
    
    *)
        echo "Unknown command: $1"
        echo
        show_help
        exit 1
        ;;
esac