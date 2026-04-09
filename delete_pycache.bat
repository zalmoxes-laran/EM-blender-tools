@echo off
echo 🔍 Searching for __pycache__ folders...

REM Delete all __pycache__ folders recursively
for /d /r %%i in (__pycache__) do (
    echo Eliminazione: %%i
    rd /s /q "%%i"
)

echo ✅ All __pycache__ folders have been deleted.
pause
