@echo off
setlocal enabledelayedexpansion

:: sync_dev.bat - s3dgraphy Development Sync Helper
:: ================================================

set "SCRIPT_PATH=%~dp0scripts\sync_s3dgraphy_dev.py"

if not exist "%SCRIPT_PATH%" (
    echo ❌ Sync script not found: %SCRIPT_PATH%
    echo Please run this from the EM-blender-tools root directory
    pause
    exit /b 1
)

:: Help function
if "%1"=="help" goto :show_help
if "%1"=="/?" goto :show_help
if "%1"=="-h" goto :show_help
if "%1"=="--help" goto :show_help

:: Status function
if "%1"=="status" goto :show_status

:: Restore function  
if "%1"=="restore" goto :restore_pypi
if "%1"=="off" goto :restore_pypi
if "%1"=="disable" goto :restore_pypi

:: Activate function
if "%1"=="on" goto :activate_dev
if "%1"=="activate" goto :activate_dev
if "%1"=="dev" goto :activate_dev

:: Clean activate
if "%1"=="clean" goto :activate_clean

:: Default behavior based on arguments
if "%1"=="" goto :activate_auto
if exist "%1" goto :activate_with_path

echo.
echo ⚠️  Unknown command: %1
echo.
goto :show_help

:show_help
echo.
echo 🔧 s3dgraphy Development Sync Helper
echo ====================================
echo.
echo USAGE:
echo   sync_dev [command] [path]
echo.
echo COMMANDS:
echo   help                    Show this help
echo   status                  Show current s3dgraphy version status
echo.
echo ACTIVATE DEVELOPMENT VERSION:
echo   sync_dev               Auto-detect s3dgraphy location
echo   sync_dev on            Same as above
echo   sync_dev dev           Same as above  
echo   sync_dev activate      Same as above
echo   sync_dev clean         Auto-detect + clean build
echo   sync_dev C:\path\to\s3dgraphy    Use specific path
echo.
echo RESTORE PYPI VERSION:
echo   sync_dev restore       Restore PyPI version
echo   sync_dev off           Same as above
echo   sync_dev disable       Same as above
echo.
echo EXAMPLES:
echo   sync_dev                          # Try auto-detect
echo   sync_dev ..\s3dgraphy            # Use relative path
echo   sync_dev C:\dev\s3dgraphy        # Use absolute path
echo   sync_dev clean                    # Clean build
echo   sync_dev restore                  # Back to PyPI version
echo   sync_dev status                   # Check what's active
echo.
echo NOTE: After any change, restart Blender to load the new version
echo.
goto :end

:show_status
echo.
echo 📊 Checking s3dgraphy status...
python "%SCRIPT_PATH%" --status
goto :end

:restore_pypi
echo.
echo ♻️  Restoring PyPI version of s3dgraphy...
python "%SCRIPT_PATH%" --restore
if errorlevel 1 (
    echo.
    echo ❌ Failed to restore PyPI version
    pause
    exit /b 1
)
echo.
echo ✅ PyPI version restored
echo 🔄 Restart Blender to use the PyPI version
goto :end

:activate_clean
echo.
echo 🧹 Activating development version with clean build...
python "%SCRIPT_PATH%" --clean
goto :check_activate_result

:activate_dev
echo.
echo 🔧 Activating development version...
python "%SCRIPT_PATH%"
goto :check_activate_result

:activate_auto
echo.
echo 🔍 Auto-detecting s3dgraphy location...
python "%SCRIPT_PATH%"
if errorlevel 1 (
    echo.
    echo ⚠️  Auto-detection failed. Let's try to find it manually.
    goto :prompt_for_path
)
goto :check_activate_result

:activate_with_path
echo.
echo 🎯 Using specified path: %1
python "%SCRIPT_PATH%" "%1"
goto :check_activate_result

:prompt_for_path
echo.
echo 📁 Common s3dgraphy locations to check:
echo    1. ..\s3dgraphy
echo    2. %USERPROFILE%\Documents\GitHub\s3dgraphy  
echo    3. Custom path
echo.
set /p "choice=Enter choice (1-3) or full path: "

if "%choice%"=="1" (
    set "s3d_path=..\s3dgraphy"
) else if "%choice%"=="2" (
    set "s3d_path=%USERPROFILE%\Documents\GitHub\s3dgraphy"
) else if "%choice%"=="3" (
    set /p "s3d_path=Enter full path to s3dgraphy: "
) else (
    set "s3d_path=%choice%"
)

if not exist "!s3d_path!" (
    echo.
    echo ❌ Path not found: !s3d_path!
    echo Please check the path and try again
    pause
    exit /b 1
)

echo.
echo 🎯 Using path: !s3d_path!
python "%SCRIPT_PATH%" "!s3d_path!"
goto :check_activate_result

:check_activate_result
if errorlevel 1 (
    echo.
    echo ❌ Activation failed
    echo Check the error messages above
    pause
    exit /b 1
)
echo.
echo ✅ Development version activated
echo 🔄 Restart Blender to use your development s3dgraphy
goto :end

:end
