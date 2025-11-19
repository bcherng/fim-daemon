# =============================
# install.ps1 - FIM Daemon Installer
# =============================

$targetDir = "C:\Program Files\FIM-Daemon"
$serviceName = "FIMDaemon"

Write-Host "Starting FIM Daemon installation..."
Write-Host "Installation directory: $targetDir"

# Check what files were actually installed
Write-Host "Files found in installation directory:"
if (Test-Path $targetDir) {
    Get-ChildItem $targetDir | ForEach-Object { Write-Host "  - $($_.Name)" }
} else {
    Write-Error "Installation directory does not exist: $targetDir"
    exit 1
}

$nssmExe = Join-Path $targetDir "nssm.exe"
$mainExe = Join-Path $targetDir "fim-daemon.exe"

Write-Host "Looking for NSSM at: $nssmExe"
Write-Host "Looking for main executable at: $mainExe"

# Validate files exist
if (-not (Test-Path $mainExe)) {
    Write-Error "Main executable not found: $mainExe"
    exit 1
}

if (-not (Test-Path $nssmExe)) {
    Write-Error "NSSM not found at: $nssmExe"
    exit 1
}

Write-Host "All required files found. Proceeding with service installation..."

# Remove existing service if present
$existingService = Get-Service -Name $serviceName -ErrorAction SilentlyContinue
if ($existingService) {
    Write-Host "Service '$serviceName' already exists. Stopping and removing..."
    Stop-Service $serviceName -Force
    & $nssmExe remove $serviceName confirm
    Start-Sleep -Seconds 2
}

# Install service using NSSM
Write-Host "Installing Windows service '$serviceName'..."
$installResult = & $nssmExe install $serviceName $mainExe

if ($LASTEXITCODE -ne 0) {
    Write-Error "NSSM failed to install service. Exit code: $LASTEXITCODE"
    Write-Host "NSSM output: $installResult"
    exit 1
}

# Configure service properties
& $nssmExe set $serviceName DisplayName "File Integrity Monitoring Daemon"
& $nssmExe set $serviceName Description "Monitors file integrity and reports changes to central server"
& $nssmExe set $serviceName Start SERVICE_AUTO_START
& $nssmExe set $serviceName AppStdout (Join-Path $targetDir "service.log")
& $nssmExe set $serviceName AppStderr (Join-Path $targetDir "service-error.log")

Write-Host "Service configured successfully."

# Start the service
Write-Host "Starting service '$serviceName'..."
Start-Service $serviceName

# Verify service status
Start-Sleep -Seconds 3
$serviceStatus = Get-Service -Name $serviceName
if ($serviceStatus.Status -eq 'Running') {
    Write-Host "Service started successfully!"
} else {
    Write-Warning "Service installed but not running. Current status: $($serviceStatus.Status)"
}

Write-Host "Installation complete!"
Write-Host "Service Name: $serviceName"
Write-Host "Installation Directory: $targetDir"
Write-Host "Log files: $targetDir\service.log"