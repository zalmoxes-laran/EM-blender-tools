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

# Help function
show_help() {
    echo "Usage: ./em.sh [command] [options]"
    echo
    echo "=== SETUP ==="
    echo "  setup              Setup development environment"
    echo
    echo "=== DEVELOPMENT ==="
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
    echo "  ./em.sh dev        # Quick dev iteration"
    echo "  ./em.sh devrel     # Dev release to GitHub"
    echo "  ./em.sh inc patch  # Increment patch: 1.5.0 → 1.5.1"
    echo "  ./em.sh build stable # Build stable package (no version change)"
    echo "  ./em.sh rc         # 1.5.0-dev.X → 1.5.1-rc.1"
    echo "  ./em.sh rc+        # 1.5.1-rc.1 → 1.5.1-rc.2"
    echo "  ./em.sh stable     # 1.5.1-rc.X → 1.5.1"
    echo "  ./em.sh commit \"fix: bug in loader\""
    echo "  ./em.sh push"
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

# Check for help
if [ $# -eq 0 ] || [ "$1" = "help" ] || [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
    show_help
    exit 0
fi

# Parse commands
case "$1" in
    setup)
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
        git push origin main
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
        git push origin main
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