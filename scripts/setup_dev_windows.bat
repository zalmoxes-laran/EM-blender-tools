@echo off
setlocal enabledelayedexpansion

echo ============================================
echo    EM Tools - Windows Development Setup
echo ============================================
echo.

:: Verifica che siamo nella cartella scripts
if not exist "requirements_wheels.txt" (
    echo ERROR: Please run this script from the scripts directory!
    echo Current directory: %CD%
    pause
    exit /b 1
)

:: Verifica Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found in PATH!
    echo Please install Python 3.11+ and add it to PATH
    pause
    exit /b 1
)

:: Setup version management
echo Setting up version management...
cd ..
python scripts/version_manager.py set-mode --mode dev
cd scripts

:: Cerca Blender automaticamente
echo Searching for Blender installation...
set BLENDER_FOUND=0
set BLENDER_PATH=

:: Cerca in diverse locazioni comuni
for %%d in (
    "C:\Program Files\Blender Foundation\Blender*\*\blender.exe"
    "C:\Program Files (x86)\Blender Foundation\Blender*\*\blender.exe"
    "%LOCALAPPDATA%\Blender Foundation\Blender*\*\blender.exe"
    "C:\Blender\blender.exe"
) do (
    for %%f in ("%%d") do (
        if exist "%%f" (
            set BLENDER_PATH=%%f
            set BLENDER_FOUND=1
            echo Found Blender: !BLENDER_PATH!
            goto :found_blender
        )
    )
)

:found_blender
if !BLENDER_FOUND!==0 (
    echo WARNING: Blender not found automatically
    echo Please ensure Blender 4.0+ is installed
)

:: Scarica wheels
echo.
echo Downloading wheels...
python setup_development.py

:: Verifica il risultato
if errorlevel 1 (
    echo ERROR: Failed to download wheels
    echo Check the error messages above
    pause
    exit /b 1
) else (
    echo SUCCESS: Wheels download completed
)

:: Verifica che le wheels siano state create
echo.
echo Verifying wheels directory...
cd ..
if not exist "wheels" (
    echo WARNING: wheels directory not created!
    echo This means the download failed silently
) else (
    echo SUCCESS: wheels directory found
    dir wheels\*.whl
    echo.
)
cd scripts

:: Installa dipendenze per sviluppo locale con VSCode
echo.
echo Installing dependencies for local development...

:: Leggi packages dal file requirements_wheels.txt e installa
echo Installing packages from requirements_wheels.txt...
for /f "tokens=* delims=" %%a in (requirements_wheels.txt) do (
    set line=%%a
    :: Salta righe vuote e commenti
    if not "!line!"=="" (
        if not "!line:~0,1!"=="#" (
            echo Installing !line! for local development...
            python -m pip install "!line!" --user --upgrade
            if errorlevel 1 (
                echo WARNING: Failed to install !line!
            )
        )
    )
)

:: Setup VSCode
echo.
echo Setting up VSCode configuration...
cd ..

if not exist ".vscode" mkdir .vscode

:: Crea settings.json da template
if exist ".vscode/settings_template.json" (
    copy ".vscode\settings_template.json" ".vscode\settings.json" >nul
    
    :: Aggiorna il path di Blender se trovato
    if !BLENDER_FOUND!==1 (
        echo Updating VSCode settings with Blender path...
        powershell -Command "(Get-Content '.vscode\settings.json') -replace '\"BLENDER_PATH_PLACEHOLDER\"', '\"!BLENDER_PATH:\\=\\\\!\"' | Set-Content '.vscode\settings.json'"
    )
) else (
    :: Crea settings.json manualmente
    (
        echo {
        echo     "blender.addon.sourceDirectory": ".",
        echo     "blender.addon.reloadOnSave": true,
        if !BLENDER_FOUND!==1 (
            echo     "blender.executable": "!BLENDER_PATH:\\=\\\\!",
        ) else (
            echo     "// blender.executable": "PATH_TO_BLENDER/blender.exe",
        )
        echo     "python.defaultInterpreterPath": "python",
        echo     "files.exclude": {
        echo         "**/__pycache__": true,
        echo         "**/*.pyc": true,
        echo         "build/": true,
        echo         "wheels/": true
        echo     }
        echo }
    ) > .vscode\settings.json
)

:: Mostra status finale
echo.
echo ============================================
echo Development setup complete!
echo ============================================
echo.
python scripts/version_manager.py current
echo.
echo Next steps:
echo 1. Open project in VSCode
echo 2. Install 'Blender Development' extension
echo 3. Press Ctrl+Shift+P and run 'Blender: Start'
echo.
echo Quick commands:
echo   Increment dev build:  python scripts/dev.py inc
echo   Build dev version:    python scripts/dev.py build
echo   Create release:       python scripts/release.py
echo.
pause