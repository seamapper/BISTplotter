@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo Building BIST Plotter with PyInstaller...
echo.

python -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
    echo Python is not on PATH or PyInstaller is not installed.
    echo Install PyInstaller in this environment:  pip install pyinstaller
    pause
    exit /b 1
)

python -m PyInstaller --clean --noconfirm BIST_Plotter.spec
if errorlevel 1 (
    echo.
    echo Build failed.
    pause
    exit /b 1
)

echo.
echo Build finished. Look under the "dist" folder for the executable.
echo.
pause
exit /b 0
