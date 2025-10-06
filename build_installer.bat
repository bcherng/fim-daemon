@echo off
pip install ps2exe
ps2exe install.ps1 installer.exe -noconsole
echo.
echo Installer built successfully: installer.exe
pause
