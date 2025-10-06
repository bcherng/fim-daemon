# install.ps1
param (
    [string]$InstallDir = "C:\Program Files\FimDaemon"
)

Write-Host "Installing File Integrity Monitoring Daemon..." -ForegroundColor Cyan

# Ensure admin rights
if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Write-Host "Please run this script as Administrator!" -ForegroundColor Red
    exit 1
}

# Install Python if missing
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "Python not found, installing..."
    $pythonInstaller = "$env:TEMP\python_installer.exe"
    Invoke-WebRequest -Uri "https://www.python.org/ftp/python/3.12.5/python-3.12.5-amd64.exe" -OutFile $pythonInstaller
    Start-Process -FilePath $pythonInstaller -ArgumentList "/quiet InstallAllUsers=1 PrependPath=1" -Wait
    Write-Host "Python installed."
}

# Create install directory
if (-not (Test-Path $InstallDir)) {
    New-Item -Path $InstallDir -ItemType Directory | Out-Null
}

# Copy files
Write-Host "Copying daemon files to $InstallDir..."
Copy-Item -Path ".\fim_daemon.py" -Destination $InstallDir -Force
Copy-Item -Path ".\fim_service.py" -Destination $InstallDir -Force
Copy-Item -Path ".\requirements.txt" -Destination $InstallDir -Force

# Install dependencies
Write-Host "Installing Python dependencies..."
Start-Process -FilePath "python" -ArgumentList "-m pip install --upgrade pip" -Wait
Start-Process -FilePath "python" -ArgumentList "-m pip install -r `"$InstallDir\requirements.txt`"" -Wait

# Register service
Write-Host "Registering Windows service..."
Start-Process -FilePath "python" -ArgumentList "`"$InstallDir\fim_service.py`" install" -Wait
Start-Process -FilePath "python" -ArgumentList "`"$InstallDir\fim_service.py`" start" -Wait

# Set startup type to auto
sc.exe config FimDaemon start= auto | Out-Null

Write-Host "Installation complete!"
Write-Host "The service 'FimDaemon' will start automatically at boot."
Write-Host "You can manage it using 'services.msc' or:"
Write-Host "  python $InstallDir\fim_service.py stop"
Write-Host "  python $InstallDir\fim_service.py remove"
