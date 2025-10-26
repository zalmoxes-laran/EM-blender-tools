@echo off
REM Build Blender Extension Package
REM Script launcher per Windows

echo ================================================
echo   Building Blender Extension Package
echo ================================================
echo.

REM Controlla Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python non trovato
    echo         Installa Python 3.8+ da python.org
    echo.
    pause
    exit /b 1
)

REM Controlla dipendenze
echo Controllo dipendenze...

python -c "import tomli" >nul 2>&1
if errorlevel 1 (
    echo Installazione tomli...
    python -m pip install --user tomli --quiet
)

python -c "import requests" >nul 2>&1
if errorlevel 1 (
    echo Installazione requests...
    python -m pip install --user requests --quiet
)

echo.

REM Esegui lo script Python
python "%~dp0build_extension.py" %*

if errorlevel 1 (
    echo.
    echo [ERROR] Script terminato con errori
    echo.
    pause
    exit /b 1
) else (
    echo.
    echo ================================================
    echo   Script completato con successo
    echo ================================================
    echo.
    pause
    exit /b 0
)
