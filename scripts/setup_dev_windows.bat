@echo off
setlocal enabledelayedexpansion

echo ============================================
echo    EM Tools - Windows Development Setup
echo ============================================
echo.

:: Verifica che siamo nella cartella scripts
if not exist "requirements_wheels.txt" (
    echo ERROR: Please run this script from the scripts directory!
    echo Expected file: requirements_wheels.txt
    echo Current directory: %CD%
    pause
    exit /b 1
)

:: Trova Blender automaticamente
echo Searching for Blender installation...
set BLENDER_PYTHON=

for /d %%i in ("C:\Program Files\Blender Foundation\Blender*") do (
    for /d %%j in ("%%i\*") do (
        if exist "%%j\python\bin\python.exe" (
            set BLENDER_PYTHON=%%j\python\bin\python.exe
            echo Found Blender: !BLENDER_PYTHON!
            goto foundblender
        )
    )
)

:foundblender
if not defined BLENDER_PYTHON (
    echo ERROR: Could not find Blender installation!
    echo Please check your Blender installation.
    pause
    exit /b 1
)

:: Scarica le wheels
echo.
echo Downloading wheels...
call setup_development.py
if errorlevel 1 (
    echo ERROR: Failed to download wheels
    pause
    exit /b 1
)

:: Leggi packages dal file requirements_wheels.txt
echo.
echo Reading packages from requirements_wheels.txt...
for /f "tokens=* delims=" %%a in (requirements_wheels.txt) do (
    set line=%%a
    :: Salta righe vuote e commenti
    if not "!line!"=="" (
        if not "!line:~0,1!"=="#" (
            echo Installing !line!...
            "%BLENDER_PYTHON%" -m pip install "!line!" --user --upgrade
            if errorlevel 1 (
                echo WARNING: Failed to install !line!
            )
        )
    )
)

:: Switch to dev mode
echo.
echo Switching to development mode...
call switch_dev_mode.py dev

:: Setup VSCode
echo.
echo Setting up VSCode configuration...
cd ..
if not exist ".vscode" mkdir .vscode

:: Crea settings.json se non esiste
if not exist ".vscode\settings.json" (
    set BLENDER_EXE=!BLENDER_PYTHON:\python\bin\python.exe=\blender.exe!
    (
        echo {
        echo     "blender.addon.sourceDirectory": ".",
        echo     "blender.addon.reloadOnSave": true,
        echo     "blender.executable": "!BLENDER_EXE:\\=\\\\!"
        echo }
    ) > .vscode\settings.json
    echo VSCode settings created
)

echo.
echo ============================================
echo Development setup complete!
echo ============================================
echo.
echo Next steps:
echo 1. Open project in VSCode
echo 2. Press Ctrl+Shift+P
echo 3. Run "Blender: Start"
pause