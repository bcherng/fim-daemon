REM -------------------------------------------------------------------
REM Windows Build Script
REM build/build_local.bat

@echo off
REM FIM Client - Windows Build Script

echo ===================================
echo FIM Client - Windows Build Script
echo ===================================
echo.

REM Check Python
python --version
if errorlevel 1 (
    echo Error: Python not found!
    exit /b 1
)

REM Install dependencies
echo.
echo Installing dependencies...
pip install -r requirements.txt
pip install pyinstaller

REM Clean previous builds
echo.
echo Cleaning previous builds...
if exist dist rmdir /s /q dist
if exist "build\windows\Output" rmdir /s /q "build\windows\Output"

REM Build with PyInstaller
echo.
echo Building executable with PyInstaller...
cd build\windows
pyinstaller --clean --noconfirm fim_client.spec
cd ..\..

REM Check Inno Setup
echo.
echo Checking for Inno Setup...
set INNO_SETUP="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if not exist %INNO_SETUP% (
    echo Error: Inno Setup not found!
    echo Please install Inno Setup from: https://jrsoftware.org/isdl.php
    exit /b 1
)

REM Build installer
echo.
echo Building installer with Inno Setup...
%INNO_SETUP% "build\windows\installer.iss"

echo.
echo ===================================
echo Build completed successfully!
echo ===================================
echo.
echo Installer: build\windows\Output\FIMClient-Setup.exe
echo.

pause