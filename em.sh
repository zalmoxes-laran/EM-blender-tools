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
    if [ -f "scripts/sync_s3dgraphy_dev.py" ]; then
        case "$1" in
            status)
                $PYTHON_CMD scripts/sync_s3dgraphy_dev.py --status
                ;;
            restore|off)
                $PYTHON_CMD scripts/sync_s3dgraphy_dev.py --restore
                ;;
            clean)
                $PYTHON_CMD scripts/sync_s3dgraphy_dev.py --clean
                ;;
            help)
                echo "🔧 s3dgraphy Development Sync Helper"
                echo "===================================="
                echo
                echo "COMMANDS:"
                echo "  ./em.sh s3d           Auto-detect s3dgraphy location"
                echo "  ./em.sh s3d on        Same as above"
                echo "  ./em.sh s3d off       Restore PyPI version"
                echo "  ./em.sh s3d status    Show current s3dgraphy version"
                echo "  ./em.sh s3d clean     Clean build + activate development"
                echo "  ./em.sh s3d restore   Restore PyPI version"
                echo
                echo "NOTE: After any change, restart Blender"
                ;;
            ""|on)
                $PYTHON_CMD scripts/sync_s3dgraphy_dev.py
                ;;
            *)
                $PYTHON_CMD scripts/sync_s3dgraphy_dev.py "$1"
                ;;
        esac
    else
        echo "❌ s3dgraphy development sync not available"
        echo "Please ensure scripts/sync_s3dgraphy_dev.py exists"
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
    echo "  setup force        Setup and force re-download wheels"
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
    echo "  dev                Quick dev: increment dev_build + build LOCAL .zip"
    echo
    echo "=== GITHUB RELEASES (builds .zip on GitHub Actions) ==="
    echo "  devrel             DEV RELEASE: inc + tag + push → GitHub builds"
    echo "  ghrelease          STABLE RELEASE: inc + tag + push → GitHub builds"
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
    echo "  ./em.sh dev        # Quick: inc dev + build LOCAL .zip for testing"
    echo "  ./em.sh devrel     # Push dev tag → GitHub builds .zip x4 platforms"
    echo "  ./em.sh ghrelease  # Push stable tag → GitHub builds .zip x4 platforms"
    echo "  ./em.sh inc patch  # Increment patch: 1.5.0 → 1.5.1"
    echo "  ./em.sh build stable # Build stable .zip locally (for testing)"
    echo "  ./em.sh rc         # 1.5.0-dev.X → 1.5.1-rc.1"
    echo "  ./em.sh rc+        # 1.5.1-rc.1 → 1.5.1-rc.2"
    echo "  ./em.sh stable     # 1.5.1-rc.X → 1.5.1"
    echo "  ./em.sh commit \"fix: bug in loader\""
    echo "  ./em.sh push"
    echo
    echo "=== WORKFLOW SUMMARY ==="
    echo
    echo "LOCAL DEVELOPMENT (quick testing):"
    echo "  ./em.sh dev        Creates LOCAL .zip for Blender testing"
    echo "                     ↓ increment dev version"
    echo "                     ↓ build .zip locally"
    echo "                     → Test in Blender"
    echo
    echo "GITHUB RELEASES (for distribution):"
    echo "  ./em.sh devrel     Push tag → GitHub Actions builds .zip x4 platforms"
    echo "  ./em.sh ghrelease  Push stable tag → GitHub Actions builds .zip x4"
    echo "                     ↓ tag pushed to GitHub"
    echo "                     ↓ GitHub Actions compiles (10-15 min)"
    echo "                     → Release with 4 platform-specific .zip files"
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
    $PYTHON_CMD scripts/version_manager.py current | awk '{print $3}'
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
        echo "============================================"
        echo "  Creating GitHub Dev Release"
        echo "============================================"
        echo
        echo "⚠️  This will push a TAG to GitHub"
        echo "🔄 GitHub Actions will build .zip files automatically"
        echo "⏱️  Build takes ~10-15 minutes"
        echo
        read -p "Continue? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "❌ Cancelled"
            exit 0
        fi
        
        echo
        echo "📝 Incrementing dev version..."
        $PYTHON_CMD scripts/dev.py inc
        
        VERSION=$(get_version)
        
        if [ -z "$VERSION" ]; then
            echo "❌ ERROR: Could not extract version!"
            exit 1
        fi
        
        echo
        echo "============================================"
        echo "📦 Creating release: v$VERSION"
        echo "============================================"
        echo
        
        echo "💾 Committing changes..."
        git add -A
        git commit -m "build: dev release $VERSION"
        
        echo "🏷️  Creating tag v$VERSION..."
        git tag "v$VERSION"
        
        echo "📤 Pushing to GitHub..."
        git push origin $(git branch --show-current)
        git push origin "v$VERSION"
        
        echo
        echo "============================================"
        echo "✅ Dev release v$VERSION created!"
        echo "============================================"
        echo
        echo "🔄 GitHub Actions is building .zip files for all platforms..."
        echo
        echo "📦 Monitor build progress:"
        echo "   https://github.com/zalmoxes-laran/EM-blender-tools/actions"
        echo
        echo "📥 Downloads will be available at:"
        echo "   https://github.com/zalmoxes-laran/EM-blender-tools/releases/tag/v$VERSION"
        echo
        echo "⏱️  Expected completion: ~10-15 minutes"
        echo
        echo "💡 Files will be:"
        echo "   - em_tools-v$VERSION-windows-x64.zip"
        echo "   - em_tools-v$VERSION-macosx-arm64.zip"
        echo "   - em_tools-v$VERSION-macosx-x64.zip"
        echo "   - em_tools-v$VERSION-linux-x64.zip"
        echo
        ;;
    
    ghrelease)
        echo "============================================"
        echo "  Creating GitHub Stable Release"
        echo "============================================"
        echo
        
        echo "📊 Current version:"
        $PYTHON_CMD scripts/version_manager.py current
        echo
        
        read -p "Increment type (patch/minor/major) [patch]: " INCREMENT
        INCREMENT=${INCREMENT:-patch}
        
        echo
        echo "📝 Incrementing $INCREMENT version and setting to STABLE..."
        
        $PYTHON_CMD scripts/version_manager.py inc $INCREMENT
        $PYTHON_CMD scripts/version_manager.py set-mode --mode stable
        
        VERSION=$(get_version)
        
        echo
        echo "============================================"
        echo "📦 Will create STABLE release: v$VERSION"
        echo "============================================"
        echo
        echo "⚠️  This will:"
        echo "   1. Commit version changes"
        echo "   2. Create tag v$VERSION"
        echo "   3. Push to GitHub"
        echo "   4. Trigger GitHub Actions build"
        echo
        read -p "Proceed with stable release? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo
            echo "❌ Release cancelled"
            exit 0
        fi
        
        echo
        echo "💾 Committing changes..."
        git add -A
        git commit -m "release: v$VERSION"
        
        echo "🏷️  Creating tag v$VERSION..."
        git tag "v$VERSION"
        
        echo "📤 Pushing to GitHub..."
        git push origin $(git branch --show-current)
        git push origin "v$VERSION"
        
        echo
        echo "============================================"
        echo "✅ Stable release v$VERSION initiated!"
        echo "============================================"
        echo
        echo "🔄 GitHub Actions is building..."
        echo
        echo "📦 Monitor: https://github.com/zalmoxes-laran/EM-blender-tools/actions"
        echo "📥 Release: https://github.com/zalmoxes-laran/EM-blender-tools/releases/tag/v$VERSION"
        echo "⏱️  Takes ~10-15 minutes"
        echo
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