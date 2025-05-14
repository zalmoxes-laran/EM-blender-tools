@echo off
echo ============================================
echo    Rimuovi File Tracciati da Git
echo ============================================
echo.

:: 1. Rimuovi blender_manifest.toml dal tracking
echo [1/2] Rimuovendo blender_manifest.toml dal tracking...
git rm --cached blender_manifest.toml 2>nul
if errorlevel 1 (
    echo   blender_manifest.toml non era tracciato
) else (
    echo   ✅ blender_manifest.toml rimosso dal tracking
)

:: 2. Rimuovi .vscode/settings.json dal tracking
echo [2/2] Rimuovendo .vscode/settings.json dal tracking...
git rm --cached .vscode\settings.json 2>nul
if errorlevel 1 (
    echo   settings.json non era tracciato
) else (
    echo   ✅ settings.json rimosso dal tracking
)

echo.
echo Verifico lo status...
git status --porcelain

echo.
echo ============================================
echo I file sono ora "untracked" ma esistono ancora
echo GitHub Desktop non dovrebbe più mostrarli
echo ============================================

echo.
echo Vuoi committare questi cambiamenti? (s/n)
set /p choice=
if /i "%choice%"=="s" (
    git commit -m "fix: remove tracked files that should be ignored"
    echo ✅ Cambiamenti committati!
) else (
    echo I file sono stati rimossi dal tracking ma non hai committato.
    echo Puoi farlo più tardi con: git commit -m "fix: remove tracked files"
)

pause