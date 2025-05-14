@echo off
setlocal enabledelayedexpansion

echo ============================================
echo    EM Tools - Quick Commands (Windows)
echo ============================================
echo.

if "%1"=="" goto :show_help
if "%1"=="help" goto :show_help
if "%1"=="-h" goto :show_help
if "%1"=="--help" goto :show_help

cd /d "%~dp0"

if "%1"=="" goto :show_help
if "%1"=="help" goto :show_help
if "%1"=="-h" goto :show_help
if "%1"=="--help" goto :show_help

cd /d "%~dp0"

:: Setup command
if "%1"=="setup" (
    echo Setting up development environment...
    
    :: Verifica che esista la cartella scripts
    if not exist "scripts" (
        echo ERROR: scripts directory not found!
        echo Make sure you're running this from the EM-blender-tools root directory
        echo Current directory: %CD%
        pause
        exit /b 1
    )
    
    :: Verifica che lo script di setup esista
    if not exist "scripts\setup_dev_windows.bat" (
        echo ERROR: setup_dev_windows.bat not found!
        echo Expected location: %CD%\scripts\setup_dev_windows.bat
        pause
        exit /b 1
    )
    
    echo Changing to scripts directory...
    pushd scripts
    
    :: Esegui il setup
    echo Running setup script...
    call setup_dev_windows.bat
    
    :: Salva l'exit code
    set SETUP_EXIT_CODE=%ERRORLEVEL%
    
    :: Torna alla directory originale
    popd
    
    :: Controlla se il setup è riuscito
    if !SETUP_EXIT_CODE! NEQ 0 (
        echo Setup failed with exit code !SETUP_EXIT_CODE!
        pause
        exit /b !SETUP_EXIT_CODE!
    )
    
    echo Setup completed successfully!
    goto :end
)

:: Development commands
if "%1"=="inc" (
    if "%2"=="" (set PART=dev_build) else (set PART=%2)
    echo Incrementing %PART% version...
    python scripts\dev.py inc --part %PART%
    echo.
    echo Suggested commit message:
    for /f "tokens=*" %%a in ('python scripts\version_manager.py current') do set VERSION=%%a
    for %%b in (%VERSION%) do set VERSION=%%b
    if "%PART%"=="dev_build" (
        echo "build: increment to %VERSION%"
    ) else (
        echo "release: %PART% version bump to %VERSION%"
    )
    goto :end
)

if "%1"=="build" (
    :: Debug delle variabili
    echo DEBUG: Argument 1 = "%1"
    echo DEBUG: Argument 2 = "%2"
    
    if "%2"=="" (
        set MODE=dev
        echo DEBUG: No mode specified, using default: dev
    ) else (
        set MODE=%2
        echo DEBUG: Mode specified: %2
    )
    
    echo DEBUG: Final MODE = "!MODE!"
    echo.
    echo Building extension in !MODE! mode...
    echo This creates a .blext package for testing/distribution
    
    :: Mostra il comando che verrà eseguito
    echo COMMAND: python scripts\dev.py build --mode !MODE!
    echo.
    
    python scripts\dev.py build --mode !MODE!
    
    :: Controlla se il comando ha avuto successo
    if errorlevel 1 (
        echo ERROR: Build failed!
        goto :end
    )
    
    :: Resto del codice...
    echo.
    echo Build completed successfully!
    goto :end
)

if "%1"=="dev" (
    echo Quick development iteration...
    python scripts\dev.py inc
    python scripts\dev.py build
    echo.
    echo Suggested commit message:
    for /f "tokens=3" %%v in ('python scripts\version_manager.py current ^| findstr "Current version"') do set VERSION=%%v

    :found_version
    echo "build: increment dev to %VERSION%"
    goto :end
)

:: NEW: Dev Release Workflow
if "%1"=="devrel" (
    echo Creating development release for GitHub...
    python scripts\dev.py inc
    python scripts\dev.py build
    for /f "tokens=*" %%a in ('python scripts\version_manager.py current') do set VERSION=%%a
    for %%b in (%VERSION%) do set VERSION=%%b
    echo.
    echo Committing and tagging...
    git add -A
    git commit -m "build: dev release %VERSION%"
    git tag v%VERSION%
    git push origin main
    git push origin v%VERSION%
    echo ✅ Dev release %VERSION% pushed to GitHub!
    goto :end
)

:: Release commands - CON AUTO-INCREMENT
if "%1"=="release" (
    if "%2"=="" goto :release_help
    if "%2"=="--help" goto :release_help
    echo Creating release...
    python scripts\release.py %2 %3 %4
    goto :end
)

if "%1"=="rc" (
    echo Creating release candidate...
    echo This will increment patch version and set mode to RC
    pause
    python scripts\release.py --mode rc --increment patch
    goto :end
)

if "%1"=="rc+" (
    echo Creating additional release candidate...
    echo This will increment RC build number (e.g., rc.1 → rc.2)
    pause
    python scripts\release.py --mode rc --increment rc_build
    goto :end
)

if "%1"=="stable" (
    echo Creating stable release...
    echo This will create stable release from current RC version
    pause
    python scripts\release.py --mode stable
    goto :end
)

:: Utility commands
if "%1"=="status" (
    python scripts\version_manager.py current
    echo.
    echo Git status:
    git status --porcelain
    goto :end
)

if "%1"=="commit" (
    echo Committing current changes...
    for /f "tokens=*" %%a in ('python scripts\version_manager.py current') do set VERSION=%%a
    for %%b in (%VERSION%) do set VERSION=%%b
    if "%2"=="" (
        echo No custom message provided, using auto-generated
        git add -A
        git commit -m "build: increment to %VERSION%"
    ) else (
        git add -A
        git commit -m "%2 (%VERSION%)"
    )
    goto :end
)

if "%1"=="push" (
    echo Pushing current changes and tags...
    git push origin main
    for /f "tokens=*" %%a in ('python scripts\version_manager.py current') do set VERSION=%%a
    for %%b in (%VERSION%) do set VERSION=%%b
    git push origin v%VERSION% 2>nul
    goto :end
)

echo Unknown command: %1
echo.

:show_help
echo Usage: em.bat [command] [options]
echo.
echo === SETUP ===
echo   setup              Setup development environment
echo.
echo === DEVELOPMENT ===
echo   inc [part]         Increment version part:
echo                        dev_build : 1.5.0-dev.43 → 1.5.0-dev.44
echo                        patch     : 1.5.0 → 1.5.1  
echo                        minor     : 1.5.0 → 1.6.0
echo                        major     : 1.5.0 → 2.0.0
echo                        rc_build  : 1.5.0-rc.1 → 1.5.0-rc.2
echo   build [mode]       Build extension package for testing/distribution
echo                        dev, rc, stable
echo                        Creates .blext file for manual installation
echo   dev                Quick dev: increment dev_build + build
echo   devrel             DEV RELEASE: inc + build + commit + tag + push
echo.
echo === RELEASE WORKFLOW ===
echo   rc                 Create Release Candidate (inc patch + build RC)
echo   rc+                Create Additional RC (rc.1 → rc.2 → rc.3...)
echo   stable             Create Stable Release (from current RC)
echo.
echo === UTILITIES ===
echo   status             Show version, mode, and git status
echo   commit [msg]       Commit with auto-generated message
echo   push               Push changes and tags to remote
echo.
echo === EXAMPLES ===
echo   em setup           # First time setup
echo   em dev             # Quick dev iteration  
echo   em devrel          # Dev release to GitHub
echo   em inc patch       # Increment patch: 1.5.0 → 1.5.1
echo   em build stable    # Build stable package (no version change)
echo   em rc              # 1.5.0-dev.X → 1.5.1-rc.1
echo   em rc+             # 1.5.1-rc.1 → 1.5.1-rc.2  
echo   em stable          # 1.5.1-rc.X → 1.5.1
echo   em commit "fix: bug in loader"
echo   em push
echo.
goto :end

:release_help
echo.
echo Release command usage:
echo   em release --mode rc --increment patch
echo   em release --mode stable
echo   em release --help
echo.
goto :end

:end
echo.
pause