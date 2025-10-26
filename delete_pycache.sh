#!/bin/bash
# Recursively deletes all __pycache__ folders in the current directory

echo "🔍 Searching for __pycache__ folders..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null

echo "✅ All __pycache__ folders have been deleted."
