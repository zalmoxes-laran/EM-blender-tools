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

:: Cerca Blender in modo intelligente
echo Searching for Blender installation...
set BLENDER_FOUND=0
set BLENDER_PATH=
set CURRENT_DIR=%CD%

:: Metodo 1: Siamo nella cartella extensions di Blender - deduce il path
echo Checking if we're in Blender's extensions directory...
echo Current path: %CURRENT_DIR%

:: Estrai la versione di Blender dal path se possibile
echo %CURRENT_DIR% | findstr /i "Blender.*extensions" >nul
if not errorlevel 1 (
    echo Found - we're in Blender's extensions directory!
    
    :: Trova la cartella Blender Foundation nel path
    for /f "tokens=1-10 delims=\" %%a in ("%CURRENT_DIR%") do (
        if /i "%%b"=="Users" if /i "%%d"=="AppData" (
            if /i "%%f"=="Blender Foundation" if /i "%%g"=="Blender" (
                set BLENDER_VERSION=%%h
                echo Detected Blender version: !BLENDER_VERSION!
                
                :: Costruisci possibili paths
                set "PROG_FILES_PATH=C:\Program Files\Blender Foundation\Blender !BLENDER_VERSION!\blender.exe"
                set "PROG_FILES_X86_PATH=C:\Program Files (x86)\Blender Foundation\Blender !BLENDER_VERSION!\blender.exe"
                set "LOCAL_PATH=%LOCALAPPDATA%\Programs\Blender Foundation\Blender !BLENDER_VERSION!\blender.exe"
                
                echo Checking: !PROG_FILES_PATH!
                if exist "!PROG_FILES_PATH!" (
                    set "BLENDER_PATH=!PROG_FILES_PATH!"
                    set BLENDER_FOUND=1
                    echo Found Blender: !BLENDER_PATH!
                    goto :found_blender
                )
                
                echo Checking: !PROG_FILES_X86_PATH!
                if exist "!PROG_FILES_X86_PATH!" (
                    set "BLENDER_PATH=!PROG_FILES_X86_PATH!"
                    set BLENDER_FOUND=1
                    echo Found Blender: !BLENDER_PATH!
                    goto :found_blender
                )
                
                echo Checking: !LOCAL_PATH!
                if exist "!LOCAL_PATH!" (
                    set "BLENDER_PATH=!LOCAL_PATH!"
                    set BLENDER_FOUND=1
                    echo Found Blender: !BLENDER_PATH!
                    goto :found_blender
                )
            )
        )
    )
)

:: Metodo 2: Ricerca nelle locazioni standard
if !BLENDER_FOUND!==0 (
    echo Searching in standard locations...
    for %%d in ("C:\Program Files\Blender Foundation" "C:\Program Files (x86)\Blender Foundation" "%LOCALAPPDATA%\Programs\Blender Foundation") do (
        if exist %%d (
            for /d %%v in ("%%d\Blender*") do (
                if exist "%%v\blender.exe" (
                    set "BLENDER_PATH=%%v\blender.exe"
                    set BLENDER_FOUND=1
                    echo Found Blender: !BLENDER_PATH!
                    goto :found_blender
                )
            )
        )
    )
)

:: Metodo 3: Controlla nel PATH
if !BLENDER_FOUND!==0 (
    echo Checking if Blender is in PATH...
    where blender >nul 2>&1
    if not errorlevel 1 (
        for /f "tokens=*" %%i in ('where blender') do (
            set "BLENDER_PATH=%%i"
            set BLENDER_FOUND=1
            echo Found Blender in PATH: !BLENDER_PATH!
            goto :found_blender
        )
    )
)

:found_blender
if !BLENDER_FOUND!==0 (
    echo.
    echo WARNING: Blender not found automatically
    echo Please ensure Blender 4.0+ is installed
    echo.
    echo Try installing Blender from:
    echo - https://www.blender.org/download/
    echo - Microsoft Store
    echo - Steam
    echo.
    echo You can manually set the path later in .vscode\settings.json
)

:: Download wheels - FIXED: Pass force parameter correctly
echo.
echo Downloading wheels...
if "%1"=="force" (
    echo FORCE MODE enabled - will re-download all wheels
    python setup_development.py --force
) else (
    echo NORMAL MODE - will skip if wheels exist
    python setup_development.py
)

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
echo Note: This installs Python packages for VSCode IntelliSense
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
        :: Escape del path per PowerShell (converte \ in \\)
        set "ESCAPED_PATH=!BLENDER_PATH:\=\\!"
        echo Using path: !ESCAPED_PATH!
        powershell -Command "(Get-Content '.vscode\settings.json') -replace 'BLENDER_PATH_PLACEHOLDER', '!ESCAPED_PATH!' | Set-Content '.vscode\settings.json'"
        echo SUCCESS: VSCode configured with Blender path
    ) else (
        echo WARNING: Blender not found, leaving placeholder
        echo You'll need to manually set the path in .vscode\settings.json
        echo Format: "blender.executable": "C:\\\\Path\\\\To\\\\blender.exe"
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
            echo     "blender.executable": "C:\\\\Path\\\\To\\\\blender.exe",
        )
        echo     "python.defaultInterpreterPath": "python",
        echo     "files.exclude": {
        echo         "**/__pycache__": true,
        echo         "**/*.pyc": true,
        echo         "build/": true,
        echo         "wheels/": true,
        echo         "*.blext": true
        }
        echo }
    ) > .vscode\settings.json
)

::
:: Final verification
echo.
echo ============================================
echo Final Verification
echo ============================================
echo.

:: Check critical files - FIXED: Use !ALL_OK! for enabledelayedexpansion
set ALL_OK=1

:: Check manifest
if not exist "blender_manifest.toml" (
    echo [ERROR] blender_manifest.toml missing
    set ALL_OK=0
) else (
    echo [OK] blender_manifest.toml exists
)

:: Check wheels
if not exist "wheels" (
    echo [ERROR] wheels directory missing
    set ALL_OK=0
) else (
    echo [OK] wheels directory exists
)

:: Check VSCode settings
if not exist ".vscode\settings.json" (
    echo [ERROR] .vscode\settings.json missing
    set ALL_OK=0
) else (
    echo [OK] .vscode\settings.json exists
    
    :: Verifica se il path di Blender è stato impostato (SOLO WARNING, non errore)
    findstr /c:"BLENDER_PATH_PLACEHOLDER" .vscode\settings.json >nul
    if not errorlevel 1 (
        echo [WARNING] Blender path still contains placeholder
        if !BLENDER_FOUND!==1 (
            echo [INFO] But Blender was found at: !BLENDER_PATH!
            echo [INFO] There may have been an issue with the path substitution
        )
    ) else (
        if !BLENDER_FOUND!==1 (
            echo [OK] Blender path configured successfully
        )
    )
)

echo.
echo Current version:
python scripts/version_manager.py current

echo.
echo ============================================
echo Development setup complete!
echo ============================================
echo.

:: FIXED: Use !ALL_OK! instead of %ALL_OK% for enabledelayedexpansion
if !ALL_OK!==1 (
    echo ✅ SUCCESS: All files configured correctly
    echo.
    echo EM Tools is configured as a Blender EXTENSION (not addon)
    if !BLENDER_FOUND!==1 (
        echo ✅ Blender found and configured at: !BLENDER_PATH!
    ) else (
        echo ⚠️  Blender not found automatically - you'll need to set the path manually
    )
    echo.
    echo Next steps:
    echo 1. Open this project in VSCode
    echo 2. Make sure you have the latest "Blender Development" extension
    echo 3. Press Ctrl+Shift+P and run "Blender: Start"
    echo 4. The extension should load automatically
    echo.
    if !BLENDER_FOUND!==0 (
        echo To set Blender path manually:
        echo 1. Open .vscode\settings.json
        echo 2. Replace BLENDER_PATH_PLACEHOLDER with your Blender path
        echo 3. Use double backslashes: "C:\\\\Program Files\\\\Blender Foundation\\\\Blender 4.4\\\\blender.exe"
        echo.
    )
    echo If VSCode fails to load the extension:
    echo - Check that Blender Development extension supports Extensions format
    echo - Verify .vscode/settings.json has correct "loadAsExtension": true
    echo - Try building manually: python scripts/dev.py build
    echo.
) else (
    echo ❌ SETUP FAILED: Critical files missing
    echo Please check the errors above and run setup again
    echo.
)

echo Quick commands with em.bat:
echo   em inc                 :: Increment dev build (1.5.0-dev.66 to 1.5.0-dev.67)
echo   em build               :: Build extension for testing  
echo   em dev                 :: Quick: increment + build
echo   em devrel              :: Dev release: increment + build + git tag + push
echo.
echo   em inc patch           :: Increment patch (1.5.0 to 1.5.1)
echo   em inc minor           :: Increment minor (1.5.0 to 1.6.0)
echo   em rc                  :: Create release candidate
echo   em stable              :: Create stable release
echo.
echo   em status              :: Show version and git status
echo   em setup force         :: Re-download wheels and setup
echo.
echo   Type "em help" for complete list of commands
echo.
pause