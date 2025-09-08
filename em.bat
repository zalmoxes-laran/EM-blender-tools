@echo off
chcp 65001 >nul
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

:: ============================================
:: DEV SYNC FUNCTIONS
:: ============================================

:: Function to check if development s3dgraphy is active
:check_dev_s3dgraphy
    if exist "scripts\sync_s3dgraphy_dev.py" (
        python scripts\sync_s3dgraphy_dev.py --status 2>nul | findstr "DEVELOPMENT" >nul
        if not errorlevel 1 (
            set "DEV_S3DGRAPHY_ACTIVE=true"
        ) else (
            set "DEV_S3DGRAPHY_ACTIVE=false"
        )
    ) else (
        set "DEV_S3DGRAPHY_ACTIVE=false"
    )
goto :eof

:: Function to warn about dev version before setup
:warn_dev_override
    if "%DEV_S3DGRAPHY_ACTIVE%"=="true" (
        echo.
        echo ⚠️  WARNING: Development version of s3dgraphy is currently active
        echo    Running 'setup' will replace it with the PyPI version
        echo.
        set /p "continue=Continue anyway? (y/N): "
        if /i not "!continue!"=="y" (
            echo.
            echo 🚫 Setup cancelled
            echo 💡 Use 'em s3d restore' if you want to switch to PyPI version
            exit /b 1
        )
        echo.
        echo 🔄 Proceeding with PyPI version replacement...
    )
goto :eof

:: Function to notify after setup that dev version was replaced
:notify_dev_replaced
    if "%DEV_S3DGRAPHY_ACTIVE%"=="true" (
        echo.
        echo ℹ️  Development version of s3dgraphy was replaced with PyPI version
        echo 💡 Use 'em s3d on' to reactivate development version if needed
    )
goto :eof

:: ============================================
:: MAIN COMMANDS
:: ============================================

:: Setup command
if "%1"=="setup" (
    :: Check if dev s3dgraphy is active before setup
    call :check_dev_s3dgraphy
    
    :: Warn user if dev version will be overridden
    if "%2"=="force" (
        call :warn_dev_override
    )
    
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
    
    :: Controllo opzione force
    if "%2"=="force" (
        echo FORCE MODE: Cleaning existing wheels...
        cd ..
        if exist "wheels" (
            rmdir /s /q "wheels"
            echo Wheels directory removed
        )
        cd scripts
    )
    
    :: FIXED: Passa il parametro force allo script di setup
    echo Running setup script...
    if "%2"=="force" (
        call setup_dev_windows.bat force
    ) else (
        call setup_dev_windows.bat
    )
    
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
    
    :: Notify if dev version was replaced
    call :notify_dev_replaced
    
    goto :end
)

:: s3dgraphy development sync command
if "%1"=="s3d" (
    echo.
    if exist "sync_dev.bat" (
        call sync_dev.bat %2 %3 %4
    ) else (
        echo ❌ s3dgraphy development sync not available
        echo Please ensure sync_dev.bat is in the EM-blender-tools root directory
        echo Run setup first if this is a fresh installation
    )
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
    
    :: FIX: Elimina tag vuoto se esiste
    git tag -d v 2>nul
    git push origin :refs/tags/v 2>nul
    
    :: FIX: Il comando version_manager.py current restituisce "Current version: X.X.X (mode: dev)"
    :: Quindi prendiamo il token 3 (dopo "Current version:")
    for /f "tokens=3" %%v in ('python scripts\version_manager.py current') do set VERSION=%%v
    
    echo.
    echo Debug: Versione estratta dal command = [%VERSION%]
    
    :: Verifica che la versione sia valida (contiene almeno un punto)
    echo %VERSION% | findstr /C:"." >nul
    if errorlevel 1 (
        echo ERROR: Invalid version format: %VERSION%
        echo Trying alternative method - reading from manifest...
        
        :: Fallback: leggi dal manifest
        for /f "tokens=3" %%v in ('findstr "^version" blender_manifest.toml') do (
            set VERSION=%%v
            set VERSION=!VERSION:"=!
        )
        echo Debug: Version from manifest = [!VERSION!]
    )
    
    :: Final check
    if "%VERSION%"=="" (
        echo ERROR: Could not extract version!
        pause
        goto :end
    )
    
    echo Final: Creating release v%VERSION%
    echo Committing and tagging...
    git add -A
    git commit -m "build: dev release %VERSION%"
    git tag v%VERSION%
    git push origin HEAD
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
echo   setup force        Setup and force re-download wheels (clean install)
echo.
echo === s3dgraphy DEVELOPMENT ===
echo   s3d                Activate s3dgraphy development version
echo   s3d on             Same as above
echo   s3d off            Restore PyPI version
echo   s3d status         Check current s3dgraphy version
echo   s3d clean          Clean build + activate development version
echo   s3d restore        Restore PyPI version
echo   s3d help           Show detailed s3dgraphy sync help
echo.
echo === EM TOOLS DEVELOPMENT ===
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
echo   em setup force     # Clean setup (re-downloads wheels)
echo   em s3d             # Activate s3dgraphy development version
echo   em s3d off         # Back to s3dgraphy PyPI version
echo   em dev             # Quick EMtools dev iteration  
echo   em devrel          # EMtools dev release to GitHub
echo   em inc patch       # Increment patch: 1.5.0 → 1.5.1
echo   em build stable    # Build stable package (no version change)
echo   em rc              # 1.5.0-dev.X → 1.5.1-rc.1
echo   em rc+             # 1.5.1-rc.1 → 1.5.1-rc.2  
echo   em stable          # 1.5.1-rc.X → 1.5.1
echo   em commit "fix: bug in loader"
echo   em push
echo.
echo === s3dgraphy DEVELOPMENT WORKFLOW ===
echo   em s3d             # Activate s3dgraphy dev version
echo   [modify s3dgraphy in other VSCode session]
echo   em s3d             # Re-sync after changes
echo   [test in Blender]
echo   em s3d off         # Back to stable when done
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