@echo off
echo ============================================
echo    Soluzione Definitiva per Gitignore
echo ============================================
echo.

:: Metodo 1: Git assume-unchanged
echo [Metodo 1] Diciamo a Git di ignorare le modifiche future...
git update-index --assume-unchanged blender_manifest.toml
echo ✅ Git ora ignorerà le modifiche a blender_manifest.toml

:: Verifica
echo.
echo === Verifica 1 ===
git status

:: Se il file appare ancora, proviamo il metodo 2
echo.
echo [Metodo 2] Aggiungiamo una riga specifica al gitignore...

:: Controlla se la riga esiste già
findstr /C:"# Generated manifest - ignore" .gitignore >nul
if errorlevel 1 (
    echo.>> .gitignore
    echo # Generated manifest - ignore>> .gitignore
    echo /blender_manifest.toml>> .gitignore
    echo ✅ Riga specifica aggiunta al gitignore
) else (
    echo ℹ️ Riga già presente nel gitignore
)

:: Metodo 3: Force refresh completo
echo.
echo [Metodo 3] Refresh completo della cache Git...
git rm -r --cached .
git add .

echo.
echo === Verifica finale ===
git status

echo.
echo Se blender_manifest.toml appare ancora:
echo 1. È possibile che sia in un commit precedente
echo 2. Prova a fare: git reset --hard HEAD
echo 3. O contattami per una soluzione più specifica
echo.

pause