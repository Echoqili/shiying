@echo off
cd /d "%~dp0"
if exist "dist\Shiying\Shiying.exe" (
    start "" "dist\Shiying\Shiying.exe"
    exit /b
)
if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" "main.py"
    exit /b
)
echo Please install dependencies first. See README.md.
pause
