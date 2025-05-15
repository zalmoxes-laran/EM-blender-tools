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

:: Download wheels
echo.
echo Downloading wheels...
python setup_development.py
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
    dir wheels\*.whl /b | find /c ".whl" > temp_count.txt
    set /p WHEEL_COUNT=<temp_count.txt
    del temp_count.txt
    echo Found !WHEEL_COUNT! wheel files
)
cd scripts

:: Genera il manifest DOPO aver scaricato le wheels
echo.
echo Generating blender_manifest.toml...
cd ..
python scripts/version_manager.py update
if not exist "blender_manifest.toml" (
    echo ERROR: Failed to generate blender_manifest.toml!
    pause
    exit /b 1
) else (
    echo SUCCESS: blender_manifest.toml generated
)
cd scripts

:: Installa dipendenze per sviluppo locale con VSCode
echo.
echo Installing dependencies for local development...
echo Note: This installs Python packages globally for VSCode IntelliSense
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
    echo Using settings template...
    copy ".vscode\settings_template.json" ".vscode\settings.json" >nul
    
    :: Aggiorna il path di Blender se trovato
    if !BLENDER_FOUND!==1 (
        echo Updating VSCode settings with Blender path...
        :: Usa PowerShell per sostituire il placeholder con il path corretto
        powershell -Command "(Get-Content '.vscode\settings.json') -replace 'BLENDER_PATH_PLACEHOLDER', '!BLENDER_PATH:\=\\!' | Set-Content '.vscode\settings.json'"
    ) else (
        echo WARNING: Blender not found, you'll need to set the path manually
        echo Edit .vscode/settings.json and update "blender.executable"
    )
    echo SUCCESS: .vscode/settings.json created from template
) else (
    echo WARNING: settings_template.json not found, creating basic settings...
    :: Crea settings.json manualmente con supporto Extensions
    (
        echo {
        echo     "blender.addon.sourceDirectory": ".",
        echo     "blender.addon.reloadOnSave": true,
        echo     "blender.addon.loadAsExtension": true,
        echo     "blender.addon.extensionDirectoryType": "user",
        echo     "blender.addon.extensionType": "add-on",
        if !BLENDER_FOUND!==1 (
            echo     "blender.executable": "!BLENDER_PATH:\\=\\\\!",
        ) else (
            echo     "// blender.executable": "C:\\Path\\To\\Blender\\blender.exe",
        )
        echo     "python.defaultInterpreterPath": "python",
        echo     "files.exclude": {
        echo         "**/__pycache__": true,
        echo         "**/*.pyc": true,
        echo         "build/": true,
        echo         "wheels/": true,
        echo         "*.blext": true
        echo     }
        echo }
    ) > .vscode\settings.json
)

:: Final verification
echo.
echo ============================================
echo Final Verification
echo ============================================
echo.

:: Check critical files
set ALL_OK=1
if not exist "blender_manifest.toml" (
    echo [ERROR] blender_manifest.toml missing
    set ALL_OK=0
) else (
    echo [OK] blender_manifest.toml exists
)

if not exist "wheels" (
    echo [ERROR] wheels directory missing
    set ALL_OK=0
) else (
    echo [OK] wheels directory exists
)

if not exist ".vscode\settings.json" (
    echo [ERROR] .vscode\settings.json missing
    set ALL_OK=0
) else (
    echo [OK] .vscode\settings.json exists
)

echo.
echo Current version:
python scripts/version_manager.py current

echo.
echo ============================================
echo Development setup complete!
echo ============================================
echo.

if !ALL_OK!==1 (
    echo ✅ SUCCESS: All files configured correctly
    echo.
    echo EM Tools is configured as a Blender EXTENSION (not addon)
    echo.
    echo Next steps:
    echo 1. Open this project in VSCode
    echo 2. Make sure you have the latest "Blender Development" extension
    echo 3. Press Ctrl+Shift+P and run "Blender: Start"
    echo 4. The extension should load automatically
    echo.
    echo If VSCode fails to load the extension:
    echo - Check that Blender Development extension supports Extensions format
    echo - Verify .vscode/settings.json has correct "loadAsExtension": true
    echo - Try building manually: python scripts/dev.py build
    echo.
) else (
    echo ❌ ERRORS DETECTED: Please check the errors above
    echo.
)

echo Quick commands:
echo   Increment dev build:  python scripts/dev.py inc
echo   Build dev version:    python scripts/dev.py build  
echo   Create release:       python scripts/release.py
echo.
pause