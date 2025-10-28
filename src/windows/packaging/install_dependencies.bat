@echo off
echo Installing Python dependencies for FIM Daemon...
python -m pip install watchdog
if %ERRORLEVEL% EQU 0 (
    echo Dependencies installed successfully.
) else (
    echo Failed to install dependencies.
    pause
)