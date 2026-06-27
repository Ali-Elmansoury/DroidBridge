@echo off
REM Build DroidBridge Windows distribution
REM Run from the project root on a Windows machine with Python + PyInstaller installed
REM
REM Prerequisites:
REM   pip install pyinstaller PyQt6
REM   (Python 3.10+ from python.org, added to PATH)
REM
REM Output: dist\droidbridge-windows\   (~400 MB)
REM         releases\droidbridge-windows-x64.zip

setlocal
if "%VERSION%"=="" set VERSION=1.0.0

echo === DroidBridge Windows Packaging (v%VERSION%) ===

REM Step 1: PyInstaller build
echo [1/2] Building with PyInstaller...
pyinstaller droidbridge-gui.spec --distpath dist --workpath build\pyinstaller --noconfirm
if errorlevel 1 goto :error

REM Step 2: Create zip archive
echo [2/2] Creating zip archive...
if not exist releases mkdir releases
powershell -Command "Compress-Archive -Force -Path 'dist\droidbridge-windows' -DestinationPath 'releases\droidbridge-windows-x64.zip'"
if errorlevel 1 goto :error

echo.
echo === Done ===
echo   Archive: releases\droidbridge-windows-x64.zip
echo.
echo To install:
echo   1. Extract releases\droidbridge-windows-x64.zip to C:\Program Files\DroidBridge\
echo   2. Add C:\Program Files\DroidBridge\ to PATH (optional, for CLI)
echo   3. Run droidbridge-gui.exe for the GUI
goto :eof

:error
echo BUILD FAILED
exit /b 1
