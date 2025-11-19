# =============================
# install.ps1 - FIM Daemon Installer
# =============================

$targetDir = "C:\Program Files\FIM-Daemon"
$serviceName = "FIMDaemon"

Write-Host "Starting FIM Daemon installation..."
Write-Host "Installation directory: $targetDir"

# Check installed files
Write-Host "Files in installation directory:"
Get-ChildItem $targetDir | ForEach-Object { Write-Host "  - $($_.Name)" }

$nssmExe = Join-Path $targetDir "nssm.exe"
$mainExe = Join-Path $targetDir "fim-daemon.exe"

Write-Host "NSSM path: $nssmExe - Exists: $(Test-Path $nssmExe)"
Write-Host "Main executable: $mainExe - Exists: $(Test-Path $mainExe)"

# FORCE REMOVE existing service (multiple methods)
Write-Host "Removing any existing service..."
try {
    # Method 1: Stop service if running
    $service = Get-Service -Name $serviceName -ErrorAction SilentlyContinue
    if ($service) {
        Write-Host "Stopping existing service..."
        Stop-Service $serviceName -Force -ErrorAction SilentlyContinue
    }
    
    # Method 2: Remove via NSSM
    if (Test-Path $nssmExe) {
        Write-Host "Removing service via NSSM..."
        & $nssmExe remove $serviceName confirm
        Start-Sleep -Seconds 2
    }
    
    # Method 3: Remove via sc.exe
    Write-Host "Removing service via sc.exe..."
    & sc.exe delete $serviceName 2>&1 | Out-Null
    Start-Sleep -Seconds 2
    
    # Method 4: Remove via PowerShell
    Remove-Service -Name $serviceName -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
} catch {
    Write-Host "Service removal encountered issues (may not exist): $_"
}

# Wait to ensure service is fully removed
Start-Sleep -Seconds 3

# Verify service is gone
$remainingService = Get-Service -Name $serviceName -ErrorAction SilentlyContinue
if ($remainingService) {
    Write-Error "Service still exists after removal attempts. Please reboot and try again."
    exit 1
}

Write-Host "Service successfully removed. Installing fresh..."

# Install service using NSSM with the COMPILED executable
Write-Host "Installing service '$serviceName' with compiled executable..."
$installResult = & $nssmExe install $serviceName $mainExe

if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to install service. NSSM exit code: $LASTEXITCODE"
    Write-Host "NSSM output: $installResult"
    exit 1
}

# VERIFY the service points to the correct executable
Write-Host "Verifying service configuration..."
$verifyResult = & $nssmExe get $serviceName Application
Write-Host "Service Application path: $verifyResult"

# Configure service properties
& $nssmExe set $serviceName DisplayName "File Integrity Monitoring Daemon"
& $nssmExe set $serviceName Description "Monitors file integrity and reports changes to central server"
& $nssmExe set $serviceName Start SERVICE_AUTO_START
& $nssmExe set $serviceName AppStdout (Join-Path $targetDir "service.log")
& $nssmExe set $serviceName AppStderr (Join-Path $targetDir "service-error.log")

Write-Host "Service configured successfully."

# Start the service
Write-Host "Starting service..."
try {
    Start-Service $serviceName
    Write-Host "Service start command sent."
    
    # Wait and check status
    Start-Sleep -Seconds 5
    $serviceStatus = Get-Service -Name $serviceName
    Write-Host "Service status: $($serviceStatus.Status)"
    
    if ($serviceStatus.Status -eq 'Running') {
        Write-Host "✅ Service started successfully!"
    } else {
        Write-Warning "Service installed but not running. Status: $($serviceStatus.Status)"
        Write-Host "Check service-error.log for details"
    }
} catch {
    Write-Error "Failed to start service: $_"
    Write-Host "Check Windows Event Viewer for detailed error information"
}

Write-Host "Installation complete!"