@echo off
echo ============================================
echo    EM Tools - Git Cleanup Script
echo ============================================
echo.

:: Verifica di essere nella root del progetto
if not exist "scripts\build.py" (
    echo ERROR: Please run this script from the EM Tools root directory!
    echo Current directory: %CD%
    pause
    exit /b 1
)

echo Cleaning Git tracking for unwanted files...
echo.

:: 1. Rimuovi build/ dal tracking (se esiste)
echo [1/6] Removing build/ from tracking...
git rm -r --cached build\ 2>nul
if errorlevel 1 (
    echo   build/ was not tracked
) else (
    echo   ✅ build/ removed from tracking
)

:: 2. Rimuovi blender_manifest.toml dal tracking
echo [2/6] Removing blender_manifest.toml from tracking...
git rm --cached blender_manifest.toml 2>nul
if errorlevel 1 (
    echo   blender_manifest.toml was not tracked
) else (
    echo   ✅ blender_manifest.toml removed from tracking
)

:: 3. Rimuovi settings.json dal tracking
echo [3/6] Removing .vscode/settings.json from tracking...
git rm --cached .vscode\settings.json 2>nul
if errorlevel 1 (
    echo   settings.json was not tracked
) else (
    echo   ✅ settings.json removed from tracking
)

:: 4. Rimuovi eventuali .blext dal tracking
echo [4/6] Removing *.blext files from tracking...
git rm --cached *.blext 2>nul
if errorlevel 1 (
    echo   No .blext files were tracked
) else (
    echo   ✅ .blext files removed from tracking
)

:: 5. Rimuovi wheels/ dal tracking
echo [5/6] Removing wheels/ from tracking...
git rm -r --cached wheels\ 2>nul
if errorlevel 1 (
    echo   wheels/ was not tracked
) else (
    echo   ✅ wheels/ removed from tracking
)

:: 6. Aggiungi .gitignore e committa
echo [6/6] Staging .gitignore and committing...
git add .gitignore
git status --porcelain

echo.
echo Ready to commit changes. The commit will include:
echo - Updated .gitignore
echo - Removal of tracked files that should be ignored
echo.
set /p CONFIRM="Proceed with commit? (y/N): "
if /i "%CONFIRM%"=="y" (
    git commit -m "fix: remove unwanted files from tracking and update gitignore"
    echo.
    echo ✅ Changes committed successfully!
    echo.
    set /p PUSH="Push to remote? (y/N): "
    if /i "%PUSH%"=="y" (
        git push origin main
        echo ✅ Changes pushed to remote!
    )
) else (
    echo Changes staged but not committed.
    echo You can review with: git status
    echo And commit manually with: git commit -m "fix: remove unwanted files from tracking"
)

echo.
echo ============================================
echo Git cleanup complete!
echo ============================================
pause