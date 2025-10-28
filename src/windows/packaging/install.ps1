# =============================
# install.ps1 - FIM Daemon Installer
# =============================

# Determine directory of EXE/script
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$targetDir = "C:\Program Files\FIM-Daemon"

# Create target directory
if (-not (Test-Path $targetDir)) {
    New-Item -ItemType Directory -Path $targetDir | Out-Null
    Write-Host "Created directory: $targetDir"
}

# Copy bundled Python files
$filesToCopy = @("fim_daemon.py","fim_service.py","requirements.txt")
foreach ($file in $filesToCopy) {
    $src = Join-Path $scriptDir $file
    $dst = Join-Path $targetDir $file
    if (Test-Path $src) {
        Copy-Item $src $dst -Force
        Write-Host "Copied $file to $targetDir"
    } else {
        Write-Warning "File missing: $file"
    }
}

# Check if Python 3.12 is installed
$pythonPath = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $pythonPath) {
    Write-Error "Python 3.12+ not found. Please install Python first."
    exit 1
}

# Install Python dependencies
Write-Host "Installing Python dependencies..."
pip install --upgrade pip
pip install -r (Join-Path $targetDir "requirements.txt")

# Create a Windows service for the daemon
$serviceName = "FIMDaemon"
$exePath = "python"
$args = "`"$targetDir\fim_service.py`""

# Check if service already exists
if (Get-Service -Name $serviceName -ErrorAction SilentlyContinue) {
    Write-Host "Service '$serviceName' already exists. Restarting..."
    Restart-Service $serviceName
} else {
    New-Service -Name $serviceName -BinaryPathName "$exePath $args" `
        -DisplayName "File Integrity Monitoring Daemon" -Description "Monitors file integrity and reports to server" `
        -StartupType Automatic
    Start-Service $serviceName
    Write-Host "Service '$serviceName' installed and started."
}

Write-Host "Installation complete!"
