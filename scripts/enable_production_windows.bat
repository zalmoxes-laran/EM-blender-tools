@echo off
echo ============================================
echo    EM Tools - Enable Production Mode
echo ============================================
echo.

:: Verifica che siamo nella cartella scripts
if not exist "switch_dev_mode.py" (
    echo ERROR: Please run this script from the scripts directory!
    echo Current directory: %CD%
    pause
    exit /b 1
)

:: Switch to production mode
echo Switching to production mode...
call switch_dev_mode.py prod

:: Vai alla cartella root
cd ..

:: Verifica che esistano le wheels per tutte le piattaforme
echo.
echo Checking wheels for all platforms...
if not exist "wheels" (
    echo ERROR: wheels directory not found!
    echo Please run setup_development.py first
    pause
    exit /b 1
)

echo Verifying wheels:
dir wheels\*.whl /b | findstr /c:"win_amd64" >nul
if errorlevel 1 echo WARNING: No Windows wheels found

dir wheels\*.whl /b | findstr /c:"macosx" >nul
if errorlevel 1 echo WARNING: No macOS wheels found

dir wheels\*.whl /b | findstr /c:"linux" >nul
if errorlevel 1 echo WARNING: No Linux wheels found

:: Mostra il manifest attuale
echo.
echo Current manifest (blender_manifest.toml):
echo ==========================================
type blender_manifest.toml
echo ==========================================

:: Update version in __init__.py if needed
echo.
echo Checking version in __init__.py...
findstr /c:"bl_info" __init__.py | findstr /c:"version"

echo.
echo ============================================
echo Production mode enabled!
echo ============================================
echo.
echo You can now:
echo 1. Create a git tag: git tag v1.5.0
echo 2. Push tag: git push origin v1.5.0
echo 3. GitHub Actions will create the release
echo.
echo Or create manual package:
echo 1. Zip the entire directory (excluding .git)
echo 2. Rename to .blext extension
echo 3. Upload to Blender Extensions Platform
echo.
pause