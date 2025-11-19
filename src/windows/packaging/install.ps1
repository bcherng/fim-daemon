# =============================
# install.ps1 - FIM Daemon Installer
# =============================

# Determine directory of EXE/script
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$targetDir = "C:\Program Files\FIM-Daemon"
$serviceName = "FIMDaemon"

# Create target directory
if (-not (Test-Path $targetDir)) {
    New-Item -ItemType Directory -Path $targetDir | Out-Null
    Write-Host "Created directory: $targetDir"
}

# Use NSSM to create the Windows service
$nssmExe = Join-Path $targetDir "bin\nssm.exe"
$mainExe = Join-Path $targetDir "fim-daemon.exe"

if (-not (Test-Path $mainExe)) {
    Write-Error "Main executable not found: $mainExe"
    Write-Host "Available files in target directory:"
    Get-ChildItem $targetDir | ForEach-Object { Write-Host "  - $($_.Name)" }
    exit 1
}

if (-not (Test-Path $nssmExe)) {
    Write-Error "NSSM not found at: $nssmExe"
    exit 1
}

# Check if service already exists
if (Get-Service -Name $serviceName -ErrorAction SilentlyContinue) {
    Write-Host "Service '$serviceName' already exists. Stopping and reconfiguring..."
    Stop-Service $serviceName -Force
    & $nssmExe remove $serviceName confirm
    Start-Sleep -Seconds 2
}

# Install service using NSSM
Write-Host "Installing Windows service '$serviceName'..."
$serviceResult = & $nssmExe install $serviceName $mainExe

if ($LASTEXITCODE -eq 0) {
    # Configure service properties
    & $nssmExe set $serviceName DisplayName "File Integrity Monitoring Daemon"
    & $nssmExe set $serviceName Description "Monitors file integrity and reports changes to central server"
    & $nssmExe set $serviceName Start SERVICE_AUTO_START
    & $nssmExe set $serviceName AppStdout (Join-Path $targetDir "service.log")
    & $nssmExe set $serviceName AppStderr (Join-Path $targetDir "service-error.log")
    
    Write-Host "Service configured successfully"
    
    # Start the service
    Write-Host "Starting service '$serviceName'..."
    Start-Service $serviceName
    
    # Check if service started successfully
    Start-Sleep -Seconds 3
    $serviceStatus = Get-Service -Name $serviceName
    if ($serviceStatus.Status -eq 'Running') {
        Write-Host "Service started successfully!"
    } else {
        Write-Warning "Service installed but not running. Current status: $($serviceStatus.Status)"
    }
} else {
    Write-Error "Failed to install service. NSSM exit code: $LASTEXITCODE"
    Write-Host "NSSM output: $serviceResult"
    exit 1
}

Write-Host "Installation complete!"
Write-Host "Service Name: $serviceName"
Write-Host "Installation Directory: $targetDir"
Write-Host "Log files: $targetDir\service.log"
